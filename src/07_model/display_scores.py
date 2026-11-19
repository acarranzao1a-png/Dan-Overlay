"""display_scores.py — extra difficulty numbers shown in the overlay.

These values are **presentation only**.  The engine keeps using `msd.exe` for
`dp_msd`, which carries 20 % of the physics triangulation and one of the four
model projections; swapping that source would invalidate the rice model's
calibration.  This module talks to two separate binaries instead:

  tools/bin/msd527.exe     MinaCalc v527, the version Etterna ships
  tools/bin/qsr/qsr.exe    Quaver Skill Rating

Both are optional.  Every failure path returns None, so a missing binary, a
missing .NET runtime or a truncated conversion degrades to "no extra number"
rather than to a wrong one.
"""

import json
import os
import re
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))


def _bin_dir() -> str:
    """Where the display binaries live, dev tree or PyInstaller bundle.

    build.bat ships msd527.exe as a loose binary next to msd.exe and the qsr
    folder as a data directory, mirroring how minacalc_bridge finds its own CLI.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.join(_REPO, "tools", "bin")


def _msd527_path() -> str:
    return os.path.join(_bin_dir(), "msd527.exe")


def _qsr_path() -> str:
    return os.path.join(_bin_dir(), "qsr", "qsr.exe")


# Backwards-compatible aliases used below.
_MSD527 = _msd527_path()
_QSR = _qsr_path()

# Enough for a cold start of the .NET runtime on a slow disk.
_QSR_TIMEOUT = 20
_MSD_TIMEOUT = 20

# Short-lived cache so a burst of analyses for the same map costs one call.
_CACHE_TTL = 30.0
_cache: dict = {}

_MODE_KEYS = ("display_metric", "displayMetric")
_DEFAULT_MODE = "both"
_settings_cache = {"at": 0.0, "mode": _DEFAULT_MODE}


def _settings_path() -> str:
    base = os.environ.get("APPDATA")
    if base:
        return os.path.join(base, "DanOverlay", "settings.json")
    return os.path.join(os.path.expanduser("~"), ".danoverlay", "settings.json")


def display_mode() -> str:
    """One of "both", "msd", "qsr" or "off".  Unknown values fall back to both."""
    now = time.monotonic()
    if now - _settings_cache["at"] < 5.0:
        return _settings_cache["mode"]
    mode = _DEFAULT_MODE
    try:
        with open(_settings_path(), encoding="utf-8") as fh:
            saved = json.load(fh)
        # The frontend writes camelCase, older files used snake_case.
        for key in _MODE_KEYS:
            raw = saved.get(key)
            if isinstance(raw, str) and raw.lower() in ("both", "msd", "qsr", "off"):
                mode = raw.lower()
                break
    except (OSError, ValueError):
        pass
    _settings_cache["mode"] = mode
    _settings_cache["at"] = now
    return mode


def _stat_key(path: str, rate: float) -> tuple:
    try:
        st = os.stat(path)
        return (os.path.abspath(path), st.st_mtime_ns, round(float(rate), 4))
    except OSError:
        return (os.path.abspath(path), 0, round(float(rate), 4))


def _cached(key: tuple, producer):
    hit = _cache.get(key)
    if hit and (time.monotonic() - hit[0]) < _CACHE_TTL:
        return hit[1]
    value = producer()
    _cache[key] = (time.monotonic(), value)
    if len(_cache) > 64:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    return value


def _no_window() -> dict:
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def _count_hit_objects(osu_path: str) -> int:
    """Hit objects in the file, used to detect a truncated conversion."""
    total = 0
    inside = False
    try:
        with open(osu_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("["):
                    inside = line == "[HitObjects]"
                    continue
                if inside and line and line.count(":") >= 4:
                    total += 1
    except OSError:
        return 0
    return total


def qsr(osu_path: str) -> dict | None:
    """Quaver Skill Rating, or None when it cannot be trusted."""
    if not os.path.isfile(_QSR):
        return None

    def run():
        try:
            proc = subprocess.run(
                [_QSR, osu_path],
                capture_output=True, text=True, timeout=_QSR_TIMEOUT, **_no_window(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        try:
            data = json.loads(proc.stdout)
            value = float(data["qsr"])
            notes = int(data.get("notes", 0))
            valid = bool(data.get("valid", False))
        except (ValueError, KeyError, TypeError):
            return None
        if not valid or value <= 0.0:
            return None
        # The converter truncates silently on some inputs; a rating computed from
        # a fraction of the chart is worse than no rating at all.
        expected = _count_hit_objects(osu_path)
        if expected and notes < 0.9 * expected:
            return None
        return {"qsr": round(value, 2), "notes": notes}

    return _cached(("qsr",) + _stat_key(osu_path, 1.0), run)


def msd527(osu_path: str, rate: float = 1.0, goal: float = 0.93, mode: str = "ssr") -> dict | None:
    """MinaCalc v527 skillsets, or None when the binary is unavailable."""
    if not os.path.isfile(_MSD527):
        return None

    def run():
        try:
            from minacalc_bridge import _parse_osu_rows
        except ImportError:
            return None
        parsed = _parse_osu_rows(osu_path, rate)
        if parsed is None:
            return None
        rows, _notes, _duration = parsed
        if not rows:
            return None
        try:
            proc = subprocess.run(
                [_MSD527, str(goal), mode],
                input=json.dumps(rows), capture_output=True, text=True,
                timeout=_MSD_TIMEOUT, **_no_window(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        try:
            data = json.loads(proc.stdout)
            return {k: round(float(v), 2) for k, v in data.items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)}
        except (ValueError, TypeError):
            return None

    return _cached(("msd527", goal, mode) + _stat_key(osu_path, rate), run)


def collect(osu_path: str, rate: float = 1.0) -> dict:
    """Everything the overlay may want to show, honouring the user's choice."""
    mode = display_mode()
    out = {"display_metric": mode, "display_msd": None, "display_qsr": None}
    if mode in ("both", "msd"):
        out["display_msd"] = msd527(osu_path, rate)
    if mode in ("both", "qsr"):
        out["display_qsr"] = qsr(osu_path)
    return out
