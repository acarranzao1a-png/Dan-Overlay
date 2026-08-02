# bridge.py — Sole JS caller.  Subscribes to events, serialises payloads,
# and forwards them to overlay.js via window.evaluate_js().
# NO other module should call evaluate_js.

import json
import logging
import base64
import os
import threading

from events import (
    TOSU_STATUS, MAP_CHANGED, MUSIC_TIME,
    ANALYSIS_STARTED, ANALYSIS_COMPLETE, ANALYSIS_ERROR,
    AUDIO_BANDS, NOTIFICATION, OVERLAY_STATE,
)
from contracts import STATE_WAITING_TOSU, STATE_IDLE, STATE_ANALYZING, STATE_ERROR

logger = logging.getLogger(__name__)


class OverlayBridge:
    """Single point of Python → JS communication.

    Receives events from the bus and translates them into typed JSON
    payloads for ``window.__overlayFromPython()``.
    """

    def __init__(self, window, event_bus):
        self._window = window
        self._bus = event_bus
        self._alive = True
        self._lock = threading.Lock()

        # Last-known state for page reloads (skin switch resync)
        self._last_tosu_connected = None      # bool | None
        self._last_map_payload: dict | None = None
        self._last_analysis_payload: dict | None = None

        # Queue: buffer events until the page confirms it's ready.
        self._ready = False
        self._queue: list[dict] = []

        # Subscribe to all events this bridge cares about
        event_bus.subscribe(TOSU_STATUS, self._on_tosu_status)
        event_bus.subscribe(MAP_CHANGED, self._on_map_changed)
        event_bus.subscribe(MUSIC_TIME, self._on_music_time)
        event_bus.subscribe(ANALYSIS_STARTED, self._on_analysis_started)
        event_bus.subscribe(ANALYSIS_COMPLETE, self._on_analysis_complete)
        event_bus.subscribe(ANALYSIS_ERROR, self._on_analysis_error)
        event_bus.subscribe(AUDIO_BANDS, self._on_audio_bands)
        event_bus.subscribe(NOTIFICATION, self._on_notification)
        event_bus.subscribe(OVERLAY_STATE, self._on_overlay_state)

    # ── JS transport ────────────────────────────────────────────────

    def _send(self, payload, *, _retry=False):
        if not self._alive:
            return
        # If the JS side isn't ready yet, buffer and return.
        if not self._ready:
            with self._lock:
                if not self._ready:
                    self._queue.append(dict(payload))
                    return
        # evaluate_js runs OUTSIDE the lock so that shutdown() — which acquires
        # the same lock — can never deadlock while a background thread is blocked
        # inside a WebView2 JS dispatch call.
        try:
            js = "window.__overlayFromPython(" + json.dumps(payload, ensure_ascii=False) + ");"
            self._window.evaluate_js(js)
        except Exception:
            payload_type = payload.get("type", "unknown") if isinstance(payload, dict) else type(payload).__name__
            logger.exception("bridge _send failed for payload type %s", payload_type)

    def _flush_queue(self):
        """Flush buffered payloads to JS now that the page is ready."""
        with self._lock:
            q = self._queue[:]
            self._queue.clear()
        if not q:
            return
        import time
        for p in q:
            self._send(p)
            time.sleep(0.005)  # small gap between batched sends

    def mark_ready(self):
        """Call from overlay_host once the page DOM has finished loading."""
        if self._ready:
            return
        self._ready = True
        self._flush_queue()

    # ── Event handlers ──────────────────────────────────────────────

    def _on_tosu_status(self, data):
        self._last_tosu_connected = data["connected"]
        if data["connected"]:
            self._send({"type": "state", "state": STATE_IDLE, "message": "Connected to tosu"})
        else:
            self._send({"type": "state", "state": STATE_WAITING_TOSU, "message": "Waiting for tosu..."})

    def resync(self):
        """Re-send last known tosu + map + analysis state to a freshly-loaded page."""
        if self._last_tosu_connected is True:
            self._send({"type": "state", "state": STATE_IDLE, "message": "Connected to tosu"})
        elif self._last_tosu_connected is False:
            self._send({"type": "state", "state": STATE_WAITING_TOSU, "message": "Waiting for tosu..."})

        if self._last_map_payload:
            self._send(self._last_map_payload)

        if self._last_analysis_payload is not None:
            # Small delay so the map transition animation that map_info triggers
            # has time to start before the analysis result arrives and fills it in.
            import time
            time.sleep(0.15)
            self._send(self._last_analysis_payload)

    def save_chart(self, base64_image: str, map_name: str) -> dict:
        """Called by JS to save the generated HTML chart to the Desktop."""
        try:
            import datetime
            import base64
            from chart_export import _get_output_dir, _sanitize_filename, _open_file

            # Remove data URI header if present
            if "," in base64_image:
                base64_image = base64_image.split(",", 1)[1]

            img_data = base64.b64decode(base64_image)
            base_name = _sanitize_filename(map_name or "DanOverlay_Export")
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = _get_output_dir()
            path = output_dir / f"{base_name}_{stamp}.png"

            with open(path, "wb") as f:
                f.write(img_data)

            opened = _open_file(str(path))
            msg = "Chart saved and opened" if opened else f"Saved to:\\n{path}"
            return {"status": "ok", "message": msg}
        except Exception as e:
            logger.error(f"Error saving chart from JS: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _on_map_changed(self, map_info):
        bg_data = ""
        if map_info.bg_path:
            try:
                with open(map_info.bg_path, "rb") as f:
                    raw = f.read()
                # Skip very large files (>5 MB) to avoid flooding evaluate_js.
                # Files between 2-5 MB are sent as base64; larger ones fall back
                # to the tosu HTTP endpoint on the JS side (has_bg flag).
                if len(raw) <= 5_000_000:
                    ext = os.path.splitext(map_info.bg_path)[1].lower().lstrip(".")
                    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
                    bg_data = f"data:{mime};base64," + base64.b64encode(raw).decode()
            except Exception:
                logger.debug("bridge: could not read bg file %s", map_info.bg_path)

        payload = {
            "type": "map_info",
            "artist": map_info.artist,
            "title": map_info.title,
            "version": map_info.version,
            "mapper": map_info.mapper,
            "sr_official": map_info.sr_official,
            "current_ms": map_info.music_time_ms,
            "total_ms": map_info.total_time_ms,
            "game_state": map_info.game_state,
            "md5": map_info.md5,
            "mod_label": map_info.mod_label,
            "bg_data": bg_data,
            # True when a bg file exists even if it was too large to inline.
            # JS uses this to decide whether to fall back to the tosu endpoint.
            "has_bg": bool(map_info.bg_path),
        }
        self._last_map_payload = payload
        self._send(payload)

    def _on_music_time(self, data):
        self._send({
            "type": "music_time",
            "ms": data["ms"],
            "total_ms": data.get("total_ms", 0),
            "playing": data["playing"],
            "game_state": data.get("game_state", 0),
            "gameplay_accuracy": data.get("gameplay_accuracy"),
            "results_accuracy":  data.get("results_accuracy"),
        })

    def _on_analysis_started(self, data):
        self._send({"type": "state", "state": STATE_ANALYZING, "message": "Computing..."})

    def _on_analysis_complete(self, result):
        # result is an AnalysisResult dataclass — use its to_dict()
        payload = result.to_dict()
        self._last_analysis_payload = payload
        self._send(payload)

    def _on_analysis_error(self, data):
        self._send({
            "type": "state",
            "state": STATE_ERROR,
            "message": data.get("error", "Unknown error"),
        })

    def _on_audio_bands(self, data):
        self._send({
            "type": "visualizer",
            "bands": data.get("bands"),
            "active": data.get("active", False),
        })

    def _on_notification(self, data):
        self._send({"type": "notification", "message": data.get("message", "")})

    def _on_overlay_state(self, data):
        self._send({"type": "state", "state": data["state"], "message": data.get("message", "")})

    # ── Lifecycle ───────────────────────────────────────────────────

    def shutdown(self):
        """Stop sending to JS (call before window disposal)."""
        with self._lock:
            self._alive = False
        # Silence the pywebview logger so that any in-flight evaluate_js()
        # calls that hit a disposed WebView2 do not spam stderr.
        # The logger name is 'pywebview' (not the module path).
        import logging as _logging
        _logging.getLogger("pywebview").setLevel(_logging.CRITICAL)
