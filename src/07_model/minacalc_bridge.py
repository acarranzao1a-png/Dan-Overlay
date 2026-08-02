"""minacalc_bridge.py — Python wrapper for msd.exe (MinaCalc MSD).

Parses a .osu file, converts hit objects to Etterna row format, and pipes
them to msd.exe via stdin. Returns a dict of 8 MSD skillset scores.
Results are cached by (path, mtime, rate) so the same map is only computed
once per session.

Public API
----------
    is_available() -> bool
    calc(osu_path, rate=1.0, goal=0.96, mode="ssr") -> dict | None
    dominant_skillset(scores) -> str
    derive_family(scores) -> str

Note: goal and mode are accepted for API compatibility but are not forwarded
to msd.exe, which computes pure MSD regardless of goal/mode.
"""

import json
import os
import subprocess
import sys

# ── Locate the binary ─────────────────────────────────────────────────────────

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))


def _find_cli() -> str | None:
    """Return the path to msd.exe, or None if not found."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: binary is packaged via --add-data and lands in
        # sys._MEIPASS (the extraction folder in both --onefile and --onedir).
        base = sys._MEIPASS
        candidates = [
            os.path.join(base, "msd.exe"),
            os.path.join(base, "msd"),
        ]
    else:
        # Development: binary lives at tools/bin/ from the repository root.
        candidates = [
            os.path.join(_REPO_ROOT, "tools", "bin", "msd.exe"),
            os.path.join(_REPO_ROOT, "tools", "bin", "msd"),
        ]

    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            return norm
    return None


_CLI_PATH: str | None = _find_cli()

# ── In-process cache ──────────────────────────────────────────────────────────

_cache: dict[tuple, dict] = {}  # (abspath, mtime_ns, rate) -> result


def _cache_key(osu_path: str, rate: float) -> tuple:
    try:
        mtime = os.stat(osu_path).st_mtime_ns
    except OSError:
        mtime = 0
    return (os.path.abspath(osu_path), mtime, rate)


# ── .osu → Etterna rows conversion ───────────────────────────────────────────

def _parse_osu_rows(
    osu_path: str, rate: float = 1.0
) -> tuple[list[dict], int, float] | None:
    """Parse a .osu file and return (rows, note_count, duration_s).

    Returns None if the file is unreadable or not a 4K mania map.
    Hit object timestamps are scaled by *rate* (e.g. rate=1.5 for DT).
    Long note releases are encoded in the end-time field and do not appear
    as separate hit objects in osu! format, so no special filtering is needed.
    """
    keycount = 0
    in_difficulty_section = False
    in_hitobjects_section = False
    raw_hits: list[tuple[int, int]] = []  # (x_pixel, time_ms)

    try:
        with open(osu_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()

                # Section headers
                if line.startswith("[") and line.endswith("]"):
                    in_difficulty_section = line == "[Difficulty]"
                    in_hitobjects_section = line == "[HitObjects]"
                    continue

                if in_difficulty_section and line.startswith("CircleSize:"):
                    try:
                        keycount = int(float(line.split(":", 1)[1].strip()))
                    except (ValueError, IndexError):
                        pass
                    continue

                if in_hitobjects_section and line:
                    parts = line.split(",")
                    if len(parts) < 4:
                        continue
                    try:
                        raw_hits.append((int(parts[0]), int(parts[2])))
                    except (ValueError, IndexError):
                        continue
    except OSError:
        return None

    if keycount not in (4, 7) or not raw_hits:
        return None

    # Build Etterna rows: combine simultaneous notes into a bitmask.
    # Rate adjustment: higher rate → notes arrive sooner → divide timestamps.
    column_width = 512.0 / keycount
    rows: dict[float, int] = {}
    for x, raw_ms in raw_hits:
        time_s = round((raw_ms / rate) / 1000.0, 4)
        column = min(int(x // column_width), keycount - 1)
        rows[time_s] = rows.get(time_s, 0) | (1 << column)

    etterna_rows = [{"notes": rows[t], "time": t} for t in sorted(rows)]
    times = list(sorted(rows))
    duration_s = (times[-1] - times[0]) if len(times) >= 2 else 0.0

    return etterna_rows, len(raw_hits), duration_s


# ── Public API ────────────────────────────────────────────────────────────────

_SKILLSET_KEYS = (
    "overall", "stream", "jumpstream", "handstream",
    "stamina", "jackspeed", "chordjack", "technical",
)


def is_available() -> bool:
    """Return True if msd.exe is present and executable."""
    return _CLI_PATH is not None


def calc(osu_path: str, rate: float = 1.0, goal: float = 0.96,
         mode: str = "ssr") -> dict | None:
    """Run MinaCalc MSD on *osu_path* and return the skillset score dict.

    Returns None on any error (binary not found, parse failure, non-4K map,
    subprocess failure, or unexpected output format).

    The returned dict contains:
        overall, stream, jumpstream, handstream, stamina,
        jackspeed, chordjack, technical  (all float, MSD values)
        duration_s  (float, seconds)
        note_count  (int)

    Parameters *goal* and *mode* are accepted for API compatibility but are
    not forwarded to msd.exe, which always computes pure MSD.

    Custom rates (anything other than HT 0.75x / NM 1.0x / DT 1.5x) are
    linearly interpolated between the two nearest native rates, because
    scaling the .osu timestamps for msd.exe produces a non-monotonic MSD
    response (verified — the same "W" the Sunny engine shows).  Native
    anchors are monotonic by construction, so interpolation keeps the MSD
    skillsets monotonic in rate for every mode that consumes them.
    """
    if _CLI_PATH is None:
        return None

    _r = round(float(rate), 4)
    _NATIVE = (0.75, 1.0, 1.5)
    if _r in _NATIVE:
        return _calc_native(osu_path, _r)

    # Custom rate: interpolate between the two nearest native anchors.
    if _r < _NATIVE[0]:
        lo, hi = _NATIVE[0], _NATIVE[1]
        t = 0.0
    elif _r > _NATIVE[-1]:
        lo, hi = _NATIVE[-2], _NATIVE[-1]
        t = 1.0 + (_r - hi) / max(hi - lo, 1e-9)
    else:
        lo, hi = None, None
        for i in range(len(_NATIVE) - 1):
            if _NATIVE[i] <= _r <= _NATIVE[i + 1]:
                lo, hi = _NATIVE[i], _NATIVE[i + 1]
                break
        t = (_r - lo) / max(hi - lo, 1e-9)

    res_lo = _calc_native(osu_path, lo)
    res_hi = _calc_native(osu_path, hi)
    if res_lo is None or res_hi is None:
        return None

    out = {}
    for k, v_lo in res_lo.items():
        if k in ("duration_s", "note_count"):
            out[k] = v_lo
            continue
        v_hi = float(res_hi.get(k, v_lo) or v_lo)
        out[k] = round(float(v_lo) + t * (v_hi - float(v_lo)), 4)

    key = _cache_key(osu_path, rate)
    _cache[key] = out
    return out


def _calc_native(osu_path: str, rate: float) -> dict | None:
    """Compute MSD at a native rate only (0.75 / 1.0 / 1.5)."""
    key = _cache_key(osu_path, rate)
    if key in _cache:
        return _cache[key]

    parsed = _parse_osu_rows(osu_path, rate)
    if parsed is None:
        return None

    etterna_rows, note_count, duration_s = parsed

    _no_window = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    try:
        result = subprocess.run(
            [_CLI_PATH],
            input=json.dumps(etterna_rows),
            capture_output=True,
            text=True,
            timeout=30,
            **_no_window,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or "error" in data:
        return None

    # Normalize to lowercase keys for consistency
    data = {k.lower(): v for k, v in data.items()}

    if not any(k in data for k in _SKILLSET_KEYS):
        return None

    data["duration_s"] = duration_s
    data["note_count"] = note_count

    _cache[key] = data
    return data


def dominant_skillset(scores: dict) -> str:
    """Return the name of the highest non-overall skillset."""
    skills = ["stream", "jumpstream", "handstream", "stamina",
              "jackspeed", "chordjack", "technical"]
    return max(skills, key=lambda k: scores.get(k, 0.0))


def derive_family(scores: dict) -> str:
    """Map MinaCalc dominant skillset to a family label used by the overlay."""
    dom = dominant_skillset(scores)
    overall = scores.get("overall", 0.0)
    if overall == 0:
        return "hybrid"

    mapping = {
        "technical":   "tech",
        "chordjack":   "jack",
        "jackspeed":   "jack",
        "handstream":  "stamina",
        "stamina":     "stamina",
        "stream":      "stream",
        "jumpstream":  "stream",
    }
    base_family = mapping.get(dom, "hybrid")

    # Blend check: if the top two skillsets are close, call it hybrid
    skills = ["stream", "jumpstream", "handstream", "stamina",
              "jackspeed", "chordjack", "technical"]
    vals = sorted([scores.get(s, 0.0) for s in skills], reverse=True)
    if len(vals) >= 2 and vals[0] > 0:
        gap = (vals[0] - vals[1]) / vals[0]
        if gap < 0.08:
            return "hybrid"

    return base_family
