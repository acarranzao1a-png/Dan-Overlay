import datetime
import os
import re
import subprocess
import sys
import threading
from bisect import bisect_left, bisect_right
from pathlib import Path

from parser import parsear_osu_v2

_GEN_LOCK = threading.Lock()

# ── Density Calculation ──────────────────────────────────────────────────────

def _compute_nps_density(notes, mod_speed=1.0):
    if len(notes) < 2:
        return [], {"segment_ms": 0, "hop_ms": 0}

    if mod_speed and mod_speed > 0 and abs(float(mod_speed) - 1.0) > 1e-6:
        times = sorted(float(t) / float(mod_speed) for t, _col in notes)
    else:
        times = sorted(float(t) for t, _col in notes)

    t0       = times[0]
    tf       = times[-1]
    duration = max(1.0, tf - t0)
    note_count  = len(notes)
    # Default chart width for segment target calculation
    chart_width = 1800 - 80 - 80 

    target_segments = int(max(chart_width * 1.4, note_count * 0.70, duration / 55.0))
    target_segments = min(chart_width * 4, max(chart_width, target_segments))

    hop_ms     = int(max(24, min(90,  duration / max(1, target_segments))))
    segment_ms = int(max(120, min(320, hop_ms * 2.8)))

    results   = []
    seg_start = t0
    while seg_start <= tf + hop_ms:
        seg_end = seg_start + segment_ms
        count   = bisect_right(times, seg_end - 1) - bisect_left(times, seg_start)
        nps     = count / max(segment_ms / 1000.0, 1e-6)
        results.append((seg_start + segment_ms * 0.5, nps))
        seg_start += hop_ms

    return results, {"segment_ms": segment_ms, "hop_ms": hop_ms}


def _compute_dominant_nps(nps_data, density_meta):
    """Average NPS of the top quartile (top 25%) of the map.

    Sorts all active windows (NPS >= 5) by value, takes the
    top 25% weighted by hop_ms, and returns their average.
    Ignores rests and is resilient to isolated peaks.
    """
    if not nps_data:
        return 0.0

    hop_ms = float(density_meta.get("hop_ms", 50))
    active = [(nps, hop_ms) for _t, nps in nps_data if nps >= 5.0]
    if not active:
        return 0.0

    active.sort(key=lambda x: x[0])
    total_weight = sum(w for _, w in active)
    target = total_weight * 0.75  # descartar 75% inferior, tomar 25% superior

    accum = 0.0
    top_quartile = []
    for nps, w in active:
        accum += w
        if accum >= target:
            top_quartile.append((nps, w))

    if not top_quartile:
        return active[-1][0]

    sum_nps_w = sum(n * w for n, w in top_quartile)
    sum_w = sum(w for _, w in top_quartile)
    return sum_nps_w / max(sum_w, 1e-6)


# ── I/O ───────────────────────────────────────────────────────────────────────

def _get_output_dir():
    desktop = None
    if sys.platform.startswith("win"):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            desktop_path, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            desktop = Path(desktop_path)
        except Exception:
            pass

    if not desktop or not desktop.is_dir():
        desktop = Path.home() / "Desktop"

    output_dir = desktop / "DanOverlay Charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _sanitize_filename(name):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '_', str(name or '').strip())
    return value.strip('. ')[:140] or 'DanOverlay'


def _open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def generate_chart_from_state(runtime_state, state_lock=None):
    """
    Called when the user triggers a chart export.
    Computes the NPS math and returns the payload + metadata
    for the JS frontend to render via HTML/Canvas.
    """
    if not _GEN_LOCK.acquire(blocking=False):
        return {"status": "busy", "message": "Already generating an image"}

    try:
        if state_lock is not None:
            with state_lock:
                map_info        = runtime_state.get("map_info")
                analysis_result = runtime_state.get("analysis_result")
        else:
            map_info        = runtime_state.get("map_info")
            analysis_result = runtime_state.get("analysis_result")

        if map_info is None or not getattr(map_info, "path", ""):
            return {"status": "error", "message": "No map loaded"}

        osu_path = Path(map_info.path)
        if not osu_path.is_file():
            return {"status": "error", "message": f"File not found: {osu_path}"}

        parsed = parsear_osu_v2(
            str(osu_path),
            output_keycount=4,
            include_ln_tails=False,
            enforce_mode_mania=True,
        )
        if parsed.get("rejected"):
            return {"status": "error", "message": "Parser rejected the map"}

        notes = parsed.get("notes") or []
        if len(notes) < 8:
            return {"status": "error", "message": "Map does not have enough notes"}

        nps_data, density_meta = _compute_nps_density(
            notes,
            mod_speed=getattr(map_info, "mod_speed", 1.0) or 1.0,
        )
        if not nps_data:
            return {"status": "error", "message": "Could not compute NPS density"}

        # ── Resolve analysis metadata for the chart ──────────────────
        dan_short = ""
        dan_sublevel = ""
        family = ""
        overall_msd = 0.0
        skillsets = {}

        if analysis_result is not None:
            dan_short = getattr(analysis_result, "dan_short", "") or ""
            dan_sublevel = getattr(analysis_result, "sublevel", "") or ""
            family = getattr(analysis_result, "family", "") or ""
            overall_msd = float(getattr(analysis_result, "overall_msd", 0.0) or 0.0)
            skillsets = dict(getattr(analysis_result, "skillsets", {}) or {})

        # If no skillsets from analysis, try MinaCalc directly
        if not skillsets:
            try:
                from minacalc_bridge import calc as calc_skillsets
                scores = calc_skillsets(
                    str(osu_path),
                    rate=getattr(map_info, "mod_speed", 1.0) or 1.0,
                )
                if isinstance(scores, dict):
                    if overall_msd <= 0.0:
                        overall_msd = float(scores.get("overall", 0.0) or 0.0)
                    skillsets = {
                        k: float(scores.get(k, 0.0) or 0.0)
                        for k in ("stream", "jumpstream", "handstream",
                                  "jackspeed", "chordjack", "technical", "stamina")
                    }
            except Exception:
                pass

        # Compute dominant NPS (histogram mode, time-weighted, ignores rests)
        dominant_nps = _compute_dominant_nps(nps_data, density_meta)

        # Build the payload — returned to JS for client-side rendering.
        # We do NOT call evaluate_js() here because this function runs
        # inside a JS→Python callback; calling evaluate_js() inside it
        # would deadlock the pywebview UI thread.
        chart_payload = {
            "type": "render_export_chart",
            "nps_data": nps_data,
            "density_meta": density_meta,
            "dominant_nps": round(dominant_nps, 1),
            "dan_short": dan_short,
            "dan_sublevel": dan_sublevel,
            "family": family,
            "overall_msd": overall_msd,
            "skillsets": skillsets,
            "parsed_meta": {
                "bpm": parsed.get("bpm", 0),
                "od": parsed.get("od", 0),
                "hp": parsed.get("hp", 0),
                "note_count": parsed.get("note_count", 0),
                "ln_count": parsed.get("ln_count", 0),
                "drain_time_s": parsed.get("drain_time_s", 0),
                "total_time_ms": getattr(map_info, "total_time_ms", 0) or 0,
                "sr_official": getattr(map_info, "sr_official", 0.0) or 0.0,
                "creator": parsed.get("metadata", {}).get("creator", ""),
                "artist": parsed.get("metadata", {}).get("artist", ""),
                "title": parsed.get("metadata", {}).get("title", ""),
                "version": parsed.get("metadata", {}).get("version", ""),
            },
        }

        # Return payload so JS can call renderExportChart() itself.
        # This avoids the pywebview deadlock that would occur if we
        # called evaluate_js() from inside a JS→Python callback.
        return {
            "status": "ok",
            "payload": chart_payload,
            "message": "Rendering chart in the browser...",
        }

    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    finally:
        _GEN_LOCK.release()