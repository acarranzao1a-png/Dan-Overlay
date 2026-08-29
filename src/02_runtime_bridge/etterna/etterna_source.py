"""
etterna_source.py — Runtime bridge for Etterna / StepMania 5.x.

Monitors Etterna's state files in the `Save/` folder:
  - DanOverlayBridge.txt (or DanielBridge.txt as fallback): Selected chart, difficulty, rate, MSD.
  - DanOverlayGameplay.txt (or DanielGameplay.txt): Active playback position during play.
  - DanOverlayMenu.txt (or DanielMenu.txt): Music preview position in song select.

Emits:
  - MAP_CHANGED : MapInfo instance when song, difficulty, or rate changes.
  - MUSIC_TIME  : Live playback / preview position for real-time density graphs.
"""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

from events import (
    MAP_CHANGED, MUSIC_TIME, OVERLAY_STATE,
)
from contracts import MapInfo, STATE_IDLE, STATE_ANALYZING, STATE_WAITING_TOSU

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.06  # ~16 Hz polling for smooth gameplay tracking

# Known bridge filenames (primary DanOverlay names with legacy fallback)
_BRIDGE_NAMES = ("DanOverlayBridge.txt", "DanielBridge.txt")
_GAMEPLAY_NAMES = ("DanOverlayGameplay.txt", "DanielGameplay.txt")
_EVAL_NAMES = ("DanOverlayEval.txt", "DanielEval.txt")
_MENU_NAMES = ("DanOverlayMenu.txt", "DanielMenu.txt")


def find_etterna_root(configured_path: str | None = None) -> Path | None:
    """Finds the Etterna root directory."""
    if configured_path:
        p = Path(configured_path).expanduser().resolve()
        if p.is_dir() and ((p / "Themes").is_dir() or (p / "Save").is_dir()):
            return p

    try:
        try:
            from etterna.etterna_installer import find_running_etterna_root, find_all_etterna_roots
        except ImportError:
            try:
                from etterna_installer import find_running_etterna_root, find_all_etterna_roots
            except ImportError:
                from .etterna_installer import find_running_etterna_root, find_all_etterna_roots

        running = find_running_etterna_root()
        if running:
            return running

        # Check if process is alive via tasklist / subprocess
        is_process_alive = False
        try:
            import subprocess
            CREATE_NO_WINDOW = 0x08000000
            res = subprocess.run(
                ["tasklist", "/NH"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=CREATE_NO_WINDOW,
            )
            out = res.stdout.lower()
            if "etterna" in out or "stepmania" in out:
                is_process_alive = True
        except Exception:
            pass

        if is_process_alive:
            all_roots = find_all_etterna_roots(configured_path)
            for r in all_roots:
                if (r / "Themes").is_dir() or (r / "Save").is_dir():
                    return r
    except Exception as exc:
        logger.debug("find_etterna_root error: %s", exc)

    return None


def _read_kv_file(path: Path) -> dict[str, str] | None:
    """Read key=value state file into a dictionary."""
    if not path.is_file():
        return None
    try:
        data = {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
        return data
    except Exception:
        return None


def _resolve_step_file(raw_path: str, song_dir: str, etterna_root: Path) -> Path | None:
    """Resolves step_file path whether absolute, relative to song_dir, or relative to Etterna."""
    if not raw_path:
        return None

    clean_raw = raw_path.lstrip("/\\")
    clean_song_dir = song_dir.lstrip("/\\") if song_dir else ""

    p = Path(raw_path)
    if p.is_file():
        return p.resolve()

    candidates = [
        etterna_root / clean_raw,
        etterna_root / "Songs" / clean_raw,
        etterna_root / clean_song_dir / Path(clean_raw).name,
        etterna_root / "Songs" / clean_song_dir / Path(clean_raw).name,
    ]

    if song_dir:
        sd = Path(song_dir)
        candidates.extend([
            sd / Path(clean_raw).name,
            sd / clean_raw,
            etterna_root / sd / Path(clean_raw).name,
            etterna_root / "Songs" / sd / Path(clean_raw).name,
        ])

    for c in candidates:
        try:
            if c.is_file():
                return c.resolve()
        except Exception:
            continue

    return None


def _find_bg_file(song_dir_path: Path | None, step_file_path: Path | None = None) -> str:
    """Find background art image in the song directory."""
    if not song_dir_path or not song_dir_path.is_dir():
        return ""

    # 1. Check #BACKGROUND: in .sm / .ssc simfile header
    if step_file_path and step_file_path.is_file():
        try:
            with open(step_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read(8192)
            match = re.search(r"#BACKGROUND\s*:\s*(.*?);", content, re.IGNORECASE)
            if match and match.group(1).strip():
                bg_name = match.group(1).strip()
                cand = song_dir_path / bg_name
                if cand.is_file():
                    return str(cand.resolve())
        except Exception:
            pass

    # 2. Check standard filenames
    for name in ("bg.jpg", "bg.png", "bg.jpeg", "background.jpg", "background.png", "background.jpeg"):
        candidate = song_dir_path / name
        if candidate.is_file():
            return str(candidate.resolve())

    # 3. Check any image file with 'bg' in the stem name
    for f in song_dir_path.iterdir():
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and "bg" in f.stem.lower():
            return str(f.resolve())

    # 4. Find the largest image in the song directory (ignoring banner / cdtitle / icons)
    candidates = []
    for f in song_dir_path.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            stem_lower = f.stem.lower()
            if stem_lower in ("bn", "banner", "cdtitle", "disc", "jacket") or "banner" in stem_lower or "cdtitle" in stem_lower:
                continue
            try:
                candidates.append((f.stat().st_size, f))
            except OSError:
                pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return str(candidates[0][1].resolve())

    return ""


def _find_banner_file(song_dir_path: Path | None, step_file_path: Path | None = None) -> str:
    """Find banner art image in the song directory."""
    if not song_dir_path or not song_dir_path.is_dir():
        return ""

    # 1. Check #BANNER: in .sm / .ssc simfile header
    if step_file_path and step_file_path.is_file():
        try:
            with open(step_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read(8192)
            match = re.search(r"#BANNER\s*:\s*(.*?);", content, re.IGNORECASE)
            if match and match.group(1).strip():
                bn_name = match.group(1).strip()
                cand = song_dir_path / bn_name
                if cand.is_file():
                    return str(cand.resolve())
        except Exception:
            pass

    # 2. Check standard banner filenames
    for name in ("bn.png", "bn.jpg", "bn.jpeg", "banner.png", "banner.jpg", "banner.jpeg", "bn.webp", "banner.webp"):
        cand = song_dir_path / name
        if cand.is_file():
            return str(cand.resolve())

    # 3. Check any image file with 'bn' or 'banner' in the stem name
    for f in song_dir_path.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            stem_lower = f.stem.lower()
            if "banner" in stem_lower or "bn" in stem_lower:
                return str(f.resolve())

    return ""


def _find_audio_file(song_dir_path: Path | None, step_file_path: Path | None = None) -> str:
    """Find the song's audio track (.mp3 / .ogg / .wav / .flac)."""
    if not song_dir_path or not song_dir_path.is_dir():
        return ""

    if step_file_path and step_file_path.is_file():
        try:
            with open(step_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read(8192)
            match = re.search(r"#MUSIC\s*:\s*(.*?);", content, re.IGNORECASE)
            if match and match.group(1).strip():
                music_name = match.group(1).strip()
                cand = song_dir_path / music_name
                if cand.is_file():
                    return str(cand.resolve())
        except Exception:
            pass

    for f in song_dir_path.iterdir():
        if f.is_file() and f.suffix.lower() in (".mp3", ".ogg", ".wav", ".flac"):
            return str(f.resolve())
    return ""


def _extract_charter(step_file_path: Path | None, fallback_desc: str = "") -> str:
    """Extract charter name from #CREDIT tag in simfile, falling back to description."""
    if step_file_path and step_file_path.is_file():
        try:
            with open(step_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read(8192)
            match = re.search(r"#CREDIT\s*:\s*(.*?);", content, re.IGNORECASE)
            if match and match.group(1).strip():
                return match.group(1).strip()
        except Exception:
            pass

    if fallback_desc:
        clean = fallback_desc.strip()
        if not clean.lower().startswith("difficulty_") and clean.lower() not in ("challenge", "hard", "medium", "easy", "beginner", "edit"):
            return clean
    return ""


def run(event_bus, stop_event, configured_root: str | None = None, poll_interval: float = POLL_INTERVAL_S):
    """Main Etterna bridge polling loop. Runs in a background daemon thread."""
    logger.info("etterna_source: starting monitoring thread")

    try:
        try:
            from etterna.etterna_installer import auto_install_all
        except ImportError:
            try:
                from etterna_installer import auto_install_all
            except ImportError:
                from .etterna_installer import auto_install_all
        auto_install_all(configured_root)
    except Exception as exc:
        logger.warning("etterna_source: auto-installer error: %s", exc)

    was_etterna_running = False
    last_bridge_key = None
    last_music_emit_time = 0.0
    last_total_time_ms = 0
    last_first_note_audio_ms = 0.0
    last_eval_ts = None
    last_playing_state = False
    gameplay_session_start_wall = None
    gameplay_session_start_sec = 0.0
    cached_root = None
    last_root_check = 0.0

    while not stop_event.is_set():
        try:
            now_check = time.perf_counter()
            if cached_root is None or now_check - last_root_check >= 1.5:
                cached_root = find_etterna_root(configured_root)
                last_root_check = now_check
            etterna_root = cached_root

            if not etterna_root:
                if was_etterna_running:
                    was_etterna_running = False
                    logger.info("etterna_source: Etterna process exited")
                    last_bridge_key = None
                    last_eval_ts = None
                    last_playing_state = False
                    gameplay_session_start_wall = None
                    event_bus.emit(OVERLAY_STATE, {
                        "state": STATE_WAITING_TOSU,
                        "message": "Waiting for game...",
                        "game": "idle",
                    })
                time.sleep(1.0)
                continue

            if not was_etterna_running:
                was_etterna_running = True
                logger.info("etterna_source: Etterna process detected at %s", etterna_root)
                save_dir = etterna_root / "Save"
                if save_dir.is_dir():
                    for name in _EVAL_NAMES:
                        ev = _read_kv_file(save_dir / name)
                        if ev and ev.get("timestamp"):
                            last_eval_ts = ev.get("timestamp")
                            break

            save_dir = etterna_root / "Save"
            if not save_dir.is_dir():
                time.sleep(0.5)
                continue

            # 1. Check Bridge state file
            bridge_data = None
            for name in _BRIDGE_NAMES:
                bridge_data = _read_kv_file(save_dir / name)
                if bridge_data:
                    break

            if bridge_data:
                title = bridge_data.get("title", "")
                artist = bridge_data.get("artist", "")
                song_dir = bridge_data.get("song_dir", "")
                step_file_raw = bridge_data.get("step_file", "")
                difficulty = bridge_data.get("difficulty", "")
                meter = bridge_data.get("meter", "")
                description = bridge_data.get("description", "")
                rate_str = bridge_data.get("rate", "1.0")

                try:
                    rate = round(float(rate_str), 4)
                except ValueError:
                    rate = 1.0

                resolved_step = _resolve_step_file(step_file_raw, song_dir, etterna_root)
                step_path_str = str(resolved_step) if resolved_step else step_file_raw

                current_key = (step_path_str, difficulty, meter, description, rate)

                if current_key != last_bridge_key and resolved_step and resolved_step.is_file():
                    last_bridge_key = current_key
                    mod_label = f"{rate:.2f}x" if abs(rate - 1.0) > 1e-4 else "NM"
                    bg_path = _find_bg_file(resolved_step.parent, resolved_step)
                    banner_path = _find_banner_file(resolved_step.parent, resolved_step)
                    audio_path = _find_audio_file(resolved_step.parent, resolved_step)
                    charter = _extract_charter(resolved_step, description)

                    pack = ""
                    if len(resolved_step.parents) >= 2:
                        cand_pack = resolved_step.parents[1].name
                        if cand_pack.lower() not in ("songs", "songs_current", "tests", "etterna maps", "test", "d:", "c:", ""):
                            pack = cand_pack
                    elif song_dir:
                        parts = Path(song_dir).parts
                        if len(parts) >= 2 and parts[0].lower() in ("songs", "songs_current"):
                            pack = parts[1]

                    # Quick drain duration from simfile
                    total_time_ms = 0
                    first_note_audio_ms = 0.0
                    try:
                        try:
                            from etterna.sm_parser import parse_simfile
                        except ImportError:
                            try:
                                from sm_parser import parse_simfile
                            except ImportError:
                                from .sm_parser import parse_simfile
                        parsed_sm = parse_simfile(str(resolved_step), difficulty=difficulty, meter=meter)
                        drain_s = float(parsed_sm.get("drain_time_s", 0.0) or 0.0)
                        if drain_s > 0:
                            total_time_ms = int(round(drain_s * 1000.0 / rate))
                        notes = parsed_sm.get("notes") or []
                        offset_ms = float(parsed_sm.get("offset", 0.0) or 0.0) * 1000.0
                        first_note_audio_ms = offset_ms + (float(notes[0][0]) if notes else 0.0)
                    except Exception:
                        pass

                    last_total_time_ms = total_time_ms
                    last_first_note_audio_ms = first_note_audio_ms

                    map_info = MapInfo(
                        md5=f"etterna_{resolved_step.stem}_{difficulty}_{meter}",
                        path=str(resolved_step),
                        artist=artist,
                        title=title,
                        version=f"[{difficulty} {meter}]".strip() if (difficulty or meter) else description,
                        mapper=charter,
                        sr_official=0.0,
                        keycount=4,
                        mod_speed=rate,
                        mod_label=mod_label,
                        bg_path=bg_path,
                        banner_path=banner_path,
                        audio_path=audio_path,
                        total_time_ms=total_time_ms,
                        pack=pack,
                        game="etterna",
                    )
                    logger.info("etterna_source: selected chart -> %s - %s [%s] (charter: %s)", artist, title, map_info.version, charter)
                    event_bus.emit(MAP_CHANGED, map_info)
                    event_bus.emit(OVERLAY_STATE, {
                        "state": "ready",
                        "message": f"Etterna: {title}",
                        "game": "etterna",
                    })

            # 2. Check Evaluation state file (ScreenEvaluation results screen)
            eval_data = None
            for name in _EVAL_NAMES:
                eval_data = _read_kv_file(save_dir / name)
                if eval_data:
                    break

            if eval_data and eval_data.get("state") == "7":
                eval_ts = eval_data.get("timestamp", "")
                if eval_ts and eval_ts != last_eval_ts:
                    last_eval_ts = eval_ts
                    last_playing_state = False
                    try:
                        eval_acc = float(eval_data.get("accuracy", 0.0) or 0.0)
                    except ValueError:
                        eval_acc = 0.0
                    eval_failed = (eval_data.get("failed") == "1")
                    eval_grade = eval_data.get("grade", "")

                    logger.info("etterna_source: Evaluation results detected -> acc=%.2f%% failed=%s grade=%s", eval_acc, eval_failed, eval_grade)
                    event_bus.emit(MUSIC_TIME, {
                        "ms": last_total_time_ms,
                        "total_ms": last_total_time_ms,
                        "playing": False,
                        "wall": time.perf_counter(),
                        "game_state": 3 if eval_failed else 7,
                        "gameplay_accuracy": eval_acc,
                        "results_accuracy": eval_acc,
                        "game": "etterna",
                    })

            # 3. Check Gameplay state file (ScreenGameplay playing / position)
            gameplay_data = None
            for name in _GAMEPLAY_NAMES:
                gameplay_data = _read_kv_file(save_dir / name)
                if gameplay_data:
                    break

            if gameplay_data:
                is_playing = (gameplay_data.get("playing") == "1")
                try:
                    music_s = float(gameplay_data.get("music_seconds", 0.0) or 0.0)
                except ValueError:
                    music_s = 0.0

                now_wall = time.perf_counter()
                if is_playing:
                    if not last_playing_state:
                        last_playing_state = True
                        gameplay_session_start_wall = now_wall
                        gameplay_session_start_sec = music_s

                    # Advance music time smoothly during active gameplay
                    elapsed_wall = now_wall - (gameplay_session_start_wall or now_wall)
                    cur_music_ms = int((gameplay_session_start_sec + elapsed_wall * rate) * 1000)

                    if now_wall - last_music_emit_time >= 0.05:
                        last_music_emit_time = now_wall
                        event_bus.emit(MUSIC_TIME, {
                            "ms": cur_music_ms,
                            "total_ms": last_total_time_ms,
                            "playing": True,
                            "wall": now_wall,
                            "game_state": 2,
                            "game": "etterna",
                        })
                elif last_playing_state:
                    last_playing_state = False
                    gameplay_session_start_wall = None
                    event_bus.emit(MUSIC_TIME, {
                        "ms": int(music_s * 1000),
                        "total_ms": last_total_time_ms,
                        "playing": False,
                        "wall": now_wall,
                        "game_state": 0,
                        "game": "etterna",
                    })

            time.sleep(poll_interval)

        except Exception:
            logger.exception("etterna_source: unexpected error in poll loop")
            time.sleep(1.0)
