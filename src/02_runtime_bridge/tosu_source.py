# tosu_source.py — Connects to tosu via WebSocket (instant) or HTTP (fallback),
# emits MAP_CHANGED and MUSIC_TIME.
#
# WebSocket gives ~0ms latency for map change detection compared to HTTP
# polling (0-500ms).  HTTP polling is kept as an automatic fallback when
# websocket-client is not installed.

import json
import logging
import os
import threading
import time

from events import (
    TOSU_STATUS, MAP_CHANGED, MUSIC_TIME, OVERLAY_STATE,
)
from contracts import MapInfo, STATE_WAITING_TOSU, STATE_IDLE

logger = logging.getLogger(__name__)

TOSU_WS_URL = "ws://127.0.0.1:24050/ws"
TOSU_JSON_URL = "http://127.0.0.1:24050/json"
POLL_INTERVAL = 0.5   # seconds — only used for HTTP fallback

_MUSIC_TIME_MIN_INTERVAL = 0.15  # min seconds between MUSIC_TIME emissions (WS)
_v2_lazer_rate = {"speed": None, "label": None}

try:
    import websocket as _websocket_mod
    _HAS_WEBSOCKET = True
except ImportError:
    _HAS_WEBSOCKET = False


def run(event_bus, stop_event, poll_interval=POLL_INTERVAL):
    """Main tosu data loop.  Runs in a daemon thread.

    Uses WebSocket when available (instant), falls back to HTTP polling.

    Emits
    -----
    TOSU_STATUS : {"connected": bool}
    MAP_CHANGED : MapInfo  (when md5, mod speed, or mod label changes)
    MUSIC_TIME  : {"ms": int, "wall": float, "playing": bool, "speed": float}
    """
    if _HAS_WEBSOCKET:
        logger.info("tosu_source: using WebSocket transport")
        threading.Thread(target=_run_v2_ws, args=(stop_event,), daemon=True).start()
        _run_ws(event_bus, stop_event)
    else:
        logger.info("tosu_source: websocket-client not installed, using HTTP polling")
        _run_http(event_bus, stop_event, poll_interval)


def _parse_lazer_mods(mods_array: list) -> tuple[float, str]:
    """Extracts (mod_speed, mod_label) from the lazer mods array.

    Searches for NC, DT, or HT in the array and reads speed_change settings.
    Returns (1.0, "") if no rate mods are found.

    Clamps:
      DT/NC: speed clamped to [1.01, 2.0]
      HT:    speed clamped to [0.5, 0.99]
    """
    _RATE_MODS = {"NC", "DT", "HT"}
    for mod_obj in mods_array:
        if not isinstance(mod_obj, dict):
            continue
        acronym = str(mod_obj.get("acronym", "")).upper()
        if acronym not in _RATE_MODS:
            continue
        settings = mod_obj.get("settings") or {}
        raw_speed = settings.get("speed_change")
        if raw_speed is not None:
            try:
                speed = float(raw_speed)
            except (TypeError, ValueError):
                speed = 1.5 if acronym != "HT" else 0.75
            # Clamp to maintain monotonic progression
            if acronym == "HT":
                speed = max(0.5, min(0.99, speed))
            else:
                speed = max(1.01, min(2.0, speed))
            return speed, acronym
        else:
            # Rate mod is active but missing speed_change; use standard defaults
            if acronym == "NC":
                return 1.5, "NC"
            elif acronym == "DT":
                return 1.5, "DT"
            else:
                return 0.75, "HT"
    return 1.0, ""


# ── Shared data extraction ─────────────────────────────────────────────────────

def _extract_and_emit(data, event_bus, state):
    """Process a tosu JSON payload and emit events.

    *state* is a mutable dict that tracks last_md5, last_mod_speed, etc.
    """
    menu = data.get("menu", {})
    bm = menu.get("bm", {})
    settings = data.get("settings", {})

    md5 = bm.get("md5", "")
    songs_dir = settings.get("folders", {}).get("songs", "")
    folder = bm.get("path", {}).get("folder", "")
    osu_file = bm.get("path", {}).get("file", "")
    bg_file = bm.get("path", {}).get("bg", "")
    full_path = os.path.join(songs_dir, folder, osu_file) if songs_dir else ""
    bg_path = os.path.join(songs_dir, folder, bg_file) if (songs_dir and folder and bg_file) else ""

    # Metadata
    meta = bm.get("metadata", {})
    artist = meta.get("artist", "")
    title = meta.get("title", "")
    # 'version' is the diff name in osu! file format; tosu may expose it as
    # 'version' or 'difficulty' depending on the endpoint / WS vs HTTP.
    version = meta.get("version", "") or meta.get("difficulty", "")
    mapper = meta.get("mapper", "")
    sr_official = bm.get("stats", {}).get("fullSR", 0.0)

    # Mods
    mods_num = menu.get("mods", {}).get("num", 0)
    is_lazer = str(data.get("client", "")).lower() == "lazer"

    if is_lazer and _v2_lazer_rate["speed"] is not None:
        # Use rate captured by lazer WS listener
        mod_speed = _v2_lazer_rate["speed"]
        mod_label = _v2_lazer_rate["label"]
    else:
        # Fallback a tosu v1 (gosumemory bitmask)
        if mods_num & 512:       # Nightcore
            mod_speed, mod_label = 1.5, "NC"
        elif mods_num & 64:      # Double Time
            mod_speed, mod_label = 1.5, "DT"
        elif mods_num & 256:     # Half Time
            mod_speed, mod_label = 0.75, "HT"
        else:
            mod_speed, mod_label = 1.0, ""

    # Keycount
    kc = bm.get("stats", {}).get("CS", 4)

    # Game state + time
    game_state = menu.get("state", 0)
    time_info = bm.get("time", {})
    current_ms = time_info.get("current", 0)
    raw_total_ms = time_info.get("mp3", 0)
    # Adjust total time for speed mods: DT (1.5x) makes the effective
    # duration shorter, HT (0.75x) makes it longer.  Tosu reports the
    # raw mp3 length regardless of mod, so the timer display needs this
    # adjustment to show correct remaining time.
    total_ms = int(raw_total_ms / mod_speed) if mod_speed > 0 else raw_total_ms
    playing = game_state == 2

    # ── Detect map/mod change ───────────────────────────────────
    if md5 and (
        md5 != state["last_md5"]
        or mod_speed != state["last_mod_speed"]
        or mod_label != state.get("last_mod_label", "")
    ):
        map_info = MapInfo(
            md5=md5,
            path=full_path,
            artist=artist,
            title=title,
            version=version,
            mapper=mapper,
            sr_official=float(sr_official),
            keycount=int(kc),
            mod_speed=mod_speed,
            mod_label=mod_label,
            bg_path=bg_path,
            music_time_ms=current_ms,
            music_playing=playing,
            total_time_ms=total_ms,
            game_state=game_state,
        )
        event_bus.emit(MAP_CHANGED, map_info)
        state["last_md5"] = md5
        state["last_mod_speed"] = mod_speed
        state["last_mod_label"] = mod_label

    # ── Music time (throttled in WS mode) ───────────────────────
    # Accuracy: read from gameplay during play and from resultsScreen on state 7
    gameplay_acc = None
    results_acc  = None
    gameplay = data.get("gameplay", {})
    results  = data.get("resultsScreen", {})
    if game_state == 2:
        raw_acc = gameplay.get("accuracy", None)
        if raw_acc is not None:
            gameplay_acc = float(raw_acc)
    elif game_state == 7:
        raw_acc = results.get("accuracy", None)
        if raw_acc is not None:
            results_acc = float(raw_acc)

    now = time.monotonic()
    if now - state.get("last_music_emit", 0) >= state.get("music_throttle", 0):
        event_bus.emit(MUSIC_TIME, {
            "ms": current_ms,
            "wall": time.time(),
            "playing": playing,
            "speed": mod_speed,
            "mod_label": mod_label,
            "md5": md5,
            "total_ms": total_ms,
            "game_state": game_state,
            "gameplay_accuracy": gameplay_acc,
            "results_accuracy":  results_acc,
        })
        state["last_music_emit"] = now


# ── WebSocket transport ────────────────────────────────────────────────────────


def _run_v2_ws(stop_event):
    def on_message(ws, msg):
        try:
            import json
            data = json.loads(msg)
            mods_array = data.get("play", {}).get("mods", {}).get("array")
            if isinstance(mods_array, list):
                speed, label = _parse_lazer_mods(mods_array)
                _v2_lazer_rate["speed"] = speed
                _v2_lazer_rate["label"] = label
        except Exception:
            pass

    _ws_ref = [None]
    def _shutdown_watch():
        stop_event.wait()
        ws = _ws_ref[0]
        if ws:
            try: ws.close()
            except Exception: pass

    threading.Thread(target=_shutdown_watch, daemon=True).start()

    while not stop_event.is_set():
        try:
            ws = _websocket_mod.WebSocketApp(
                "ws://127.0.0.1:24050/websocket/v2",
                on_message=on_message,
            )
            _ws_ref[0] = ws
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            pass
        if not stop_event.is_set():
            stop_event.wait(2)

def _run_ws(event_bus, stop_event):
    state = {
        "last_md5": "",
        "last_mod_speed": 1.0,
        "last_mod_label": "",
        "connected": False,
        "last_music_emit": 0,
        "music_throttle": _MUSIC_TIME_MIN_INTERVAL,
    }

    event_bus.emit(OVERLAY_STATE, {"state": STATE_WAITING_TOSU, "message": "Waiting for tosu..."})

    def on_open(ws):
        if not state["connected"]:
            state["connected"] = True
            event_bus.emit(TOSU_STATUS, {"connected": True})
            event_bus.emit(OVERLAY_STATE, {"state": STATE_IDLE, "message": "Connected to tosu"})
            logger.info("tosu connected (WebSocket)")

    def on_message(ws, msg):
        try:
            import json
            data = json.loads(msg)
            if not data.get("menu", {}).get("bm"):
                return
            _extract_and_emit(data, event_bus, state)
        except Exception:
            logger.exception("tosu_source WS message error")

    def on_close(ws, code, msg):
        if state["connected"]:
            state["connected"] = False
            event_bus.emit(TOSU_STATUS, {"connected": False})
            event_bus.emit(OVERLAY_STATE, {
                "state": STATE_WAITING_TOSU,
                "message": "Waiting for tosu...",
            })
            logger.info("tosu disconnected (WebSocket)")

    def on_error(ws, error):
        logger.debug("tosu WS error: %s", error)

    _ws_ref = [None]
    def _shutdown_watch():
        stop_event.wait()
        ws = _ws_ref[0]
        if ws:
            try: ws.close()
            except Exception: pass

    threading.Thread(target=_shutdown_watch, daemon=True).start()

    while not stop_event.is_set():
        try:
            ws = _websocket_mod.WebSocketApp(
                TOSU_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_close=on_close,
                on_error=on_error,
            )
            _ws_ref[0] = ws
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            logger.debug("tosu WS connection attempt failed")
        if not stop_event.is_set():
            state["connected"] = False
            stop_event.wait(2)


# ── HTTP polling fallback ──────────────────────────────────────────────────────

def _run_http(event_bus, stop_event, poll_interval):
    import requests

    state = {
        "last_md5": "",
        "last_mod_speed": 1.0,
        "last_mod_label": "",
        "connected": False,
        "last_music_emit": 0,
        "music_throttle": 0,  # no throttle needed — already limited by poll rate
    }

    event_bus.emit(OVERLAY_STATE, {"state": STATE_WAITING_TOSU, "message": "Waiting for tosu..."})

    while not stop_event.is_set():
        try:
            resp = requests.get(TOSU_JSON_URL, timeout=1.5)
            data = resp.json()

            if not state["connected"]:
                state["connected"] = True
                event_bus.emit(TOSU_STATUS, {"connected": True})
                event_bus.emit(OVERLAY_STATE, {"state": STATE_IDLE, "message": "Connected to tosu"})
                logger.info("tosu connected (HTTP)")

            _extract_and_emit(data, event_bus, state)

        except requests.RequestException:
            if state["connected"]:
                state["connected"] = False
                event_bus.emit(TOSU_STATUS, {"connected": False})
                event_bus.emit(OVERLAY_STATE, {
                    "state": STATE_WAITING_TOSU,
                    "message": "Waiting for tosu...",
                })
                logger.info("tosu disconnected (HTTP)")
        except Exception:
            logger.exception("tosu_source HTTP unexpected error")

        stop_event.wait(poll_interval)
