# primary_sr_bridge.py -- Wrapper for the primary SR engine in the pipeline
#
# Wraps the raw SR calculation and returns a stable payload of SR
# and structural components for the pipeline.

import os
import sys
import tempfile
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SR_CORE_DIR = os.path.join(_SRC_DIR, "03_engine_reference", "sr_core")

# Deferred import to avoid startup errors if numpy is missing
_sr_core_alg = None

# In-process cache: (abspath, mtime_ns, mod) -> result dict
_sr_cache: dict[tuple, dict] = {}

# ── Deterministic monotone SR surrogate for custom (non-native) rates ─────────
#
# Sunny's SR-vs-rate response is intrinsically non-monotonic *between* the
# native anchors (a "W" shape, verified with int and float-ms temp files).
# The previous implementation clamped every new value against a per-session
# registry of the rates already visited, which made the answer depend on the
# user's navigation order: the same 1.15x query returned SR 11.3209 (Iota)
# when 1.15x was visited first and SR 11.2347 (Theta) when 1.20x was visited
# first (measured, pipeline.analyze_map on a benchmark map).  The clamp is now
# a property of the BEATMAP, never of the session:
#
#   fixed rate grid -> raw SR per grid point (cached) -> isotonic (PAVA) fit
#   inside each native-anchor bracket, anchors pinned to their engine value
#   -> linear interpolation at the queried rate.
#
# The result is deterministic (same map + same rate => same value, always) and
# non-decreasing in rate by construction.  Native rates (0.75 / 1.0 / 1.5) keep
# the raw engine value untouched, so NM / HT / DT stay bit-identical.
_NATIVE_RATES = (0.75, 1.00, 1.50)
_NATIVE_RATE_MOD = {0.75: "HT", 1.00: "NM", 1.50: "DT"}
# Interior grid points per native-anchor bracket (fixed => deterministic).
_BRACKET_POINTS = {
    (0.75, 1.00): (0.90,),
    (1.00, 1.50): (1.10, 1.25, 1.40),
    (1.50, 2.00): (1.75,),
}
_curve_cache: dict[tuple, tuple] = {}
_raw_sr_cache: dict[tuple, float] = {}


def _sr_cache_key(file_path: str, mod: str, rate: float = 1.0) -> tuple:
    try:
        mtime = os.stat(file_path).st_mtime_ns
    except OSError:
        mtime = 0
    return (os.path.abspath(file_path), mtime, mod, round(rate, 3))


def _pava_monotone(values):
    """Pool-adjacent-violators: closest non-decreasing fit of *values*."""
    blocks = [[float(v)] for v in values]
    i = 0
    while i < len(blocks) - 1:
        if (sum(blocks[i]) / len(blocks[i])) > (sum(blocks[i + 1]) / len(blocks[i + 1])):
            blocks[i] = blocks[i] + blocks[i + 1]
            del blocks[i + 1]
            if i > 0:
                i -= 1
        else:
            i += 1
    out = []
    for b in blocks:
        out.extend([sum(b) / len(b)] * len(b))
    return out


def _is_native_rate(rate) -> bool:
    try:
        r = round(float(rate), 3)
    except (TypeError, ValueError):
        return False
    return any(abs(r - n) < 1e-9 for n in _NATIVE_RATES)


def _raw_sr_at_rate(file_path: str, rate: float) -> float:
    """Raw Sunny SR at an arbitrary rate (timing-scaled temp file, no clamp)."""
    key = _sr_cache_key(file_path, "NM", round(float(rate), 3))
    hit = _raw_sr_cache.get(key)
    if hit is not None:
        return hit
    alg = _import_sr_core()
    tmp = _scale_osu_timings(file_path, float(rate))
    try:
        sr_val, _corners, _graph, _components = alg.calculate(tmp, "NM")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    value = float(sr_val)
    _raw_sr_cache[key] = value
    return value


def _bracket_for(rate: float):
    """Native-anchor bracket containing *rate* (rates outside are clamped)."""
    r = min(max(float(rate), _NATIVE_RATES[0]), 2.00)
    lower = max([n for n in _NATIVE_RATES if n <= r + 1e-9], default=_NATIVE_RATES[0])
    upper = min([n for n in _NATIVE_RATES if n > lower + 1e-9], default=2.00)
    return lower, upper


def _monotone_curve(file_path: str, lower: float, upper: float) -> tuple:
    """Isotonic SR curve over one native-anchor bracket (cached per map)."""
    try:
        mtime = os.stat(file_path).st_mtime_ns
    except OSError:
        mtime = 0
    key = (os.path.abspath(file_path), mtime, lower, upper)
    hit = _curve_cache.get(key)
    if hit is not None:
        return hit

    rates = [lower] + list(_BRACKET_POINTS.get((lower, upper), ())) + [upper]
    vals = []
    for r in rates:
        if _is_native_rate(r):
            anchor_mod = _NATIVE_RATE_MOD[round(r, 2)]
            anchor = analyze_primary_sr(file_path, mod=anchor_mod, rate=None)
            vals.append(float(anchor.get("sr", 0.0) or 0.0))
        else:
            vals.append(_raw_sr_at_rate(file_path, r))

    fitted = _pava_monotone(vals)
    # Pin the bracket ends to the engine's own anchor values, then re-isotonize
    # the interior inside [start, end]: the curve stays non-decreasing and still
    # passes through the native anchors exactly.
    lo_val = vals[0]
    hi_val = max(vals[-1], lo_val)
    interior = [min(max(v, lo_val), hi_val) for v in fitted[1:-1]]
    fitted = [lo_val] + (_pava_monotone(interior) if interior else []) + [hi_val]
    curve = (tuple(rates), tuple(fitted))
    _curve_cache[key] = curve
    return curve


def _enforce_monotonic_sr(file_path: str, mod: str, rate: float, sr: float) -> float:
    """Deterministic, order-independent monotone SR for a playback rate.

    Native rates (0.75 / 1.0 / 1.5) return the raw engine value untouched, so
    NM / HT / DT are bit-identical to the engine.  A custom rate is resolved on
    the map's isotonic curve, so the answer depends only on the beatmap and the
    rate — never on which rates were queried earlier in the session.
    """
    if rate is None:
        return sr
    if _is_native_rate(rate):
        return sr
    r = float(rate)
    lower, upper = _bracket_for(r)
    rates, vals = _monotone_curve(file_path, lower, upper)
    if r <= rates[0]:
        return float(vals[0])
    if r >= rates[-1]:
        return float(vals[-1])
    for i in range(len(rates) - 1):
        if rates[i] <= r <= rates[i + 1]:
            span = rates[i + 1] - rates[i]
            t = 0.0 if span <= 0 else (r - rates[i]) / span
            return float(vals[i] * (1.0 - t) + vals[i + 1] * t)
    return float(vals[-1])


def _import_sr_core():
    global _sr_core_alg
    if _sr_core_alg is not None:
        return _sr_core_alg

    if _SR_CORE_DIR not in sys.path:
        sys.path.insert(0, _SR_CORE_DIR)

    try:
        import algorithm as _alg
        _sr_core_alg = _alg
    except ImportError:
        try:
            from sr_core import algorithm as _alg
            _sr_core_alg = _alg
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "sr_core_algorithm",
                os.path.join(_SR_CORE_DIR, "algorithm.py"),
            )
            _alg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_alg)
            _sr_core_alg = _alg

    return _sr_core_alg


_EMPTY_RESULT = {
    "sr": 0.0,
    "jbar_max": 0.0,
    "pbar_max": 0.0,
    "xbar_max": 0.0,
    "abar_mean": 0.0,
    "jack_ratio": 0.0,
    "d93": 0.0,
    "d83": 0.0,
    "d_weighted_mean": 0.0,
    "total_notes_eff": 0.0,
    "jbar_share": 0.0,
    "pbar_share": 0.0,
    "xbar_share": 0.0,
    "rbar_max": 0.0,
    "success": False,
    "error": None,
}


def _scale_osu_timings(file_path: str, rate: float) -> str:
    """Create a temp .osu with hit times scaled for a custom clock rate.

    A rate mod (DT/HT/custom) makes notes arrive faster/slower, so the
    effective note times are divided by the rate (the engine's own DT mod
    applies ``h * 2/3``, i.e. ``h / 1.5``).  We pre-scale the .osu hit times
    by ``1/rate`` (same approach as ManiaMapAnalyser / huismetbenen) and run
    the engine with mod="NM", which yields the TRUE engine SR at that rate.
    """
    lines = []
    section = None
    with open(file_path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            stripped = line.strip()
            if stripped.startswith("["):
                section = stripped
                lines.append(line)
                continue
            if section == "[HitObjects]" and stripped and not stripped.startswith("//"):
                parts = stripped.split(",")
                if len(parts) >= 3:
                    try:
                        t = float(parts[2]) / rate
                        parts[2] = str(int(round(t)))
                    except ValueError:
                        pass
                lines.append(",".join(parts))
                continue
            lines.append(line)

    fd, tmp = tempfile.mkstemp(suffix=".osu", prefix="danoverlay_rate_")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return tmp


def analyze_primary_sr(file_path, mod="NM", rate=None):
    """Run the primary SR algorithm on an .osu file.

    Parameters
    ----------
    file_path : str
        Path to the .osu file.
    mod : str
        "NM" | "DT" | "HT" | "NC"  (NC is treated as DT, same 1.5x rate)
    rate : float or None
        Custom speed rate from Lazer. If specified and not standard,
        we create a temporary scaled .osu file for algorithm.py.

    Returns
    -------
    dict with sr, component maxes, success flag, and error string.
    """
    _core_mod = "DT" if mod == "NC" else mod
    
    _MOD_RATE = {"HT": 0.75, "DT": 1.5, "NC": 1.5, "NM": 1.0}
    standard_rate = _MOD_RATE.get(_core_mod, 1.0)
    
    # ── Custom lazer clock rates ────────────────────────────────────
    # The Sunny algorithm is natively monotonic at its STANDARD rates
    # (HT 0.75x < NM 1.0x < DT 1.5x) — verified.  But scaling the .osu
    # timings for a custom rate (e.g. 1.49x) and re-running the engine
    # produces a non-monotonic "W" response (verified with int and round
    # truncation, and with float-ms files — it is intrinsic to the fixed
    # ±500ms windows in the algorithm).  Forcing monotonicity on top of
    # that with clamps freezes the display at one value.
    #
    # Correct approach: only the standard rates come from the engine.
    # A custom rate is linearly interpolated between the two nearest
    # native rates (HT/NM/DT), which is monotonic by construction and
    # always consistent with the engine's own values.
    if rate is not None:
        _r = round(float(rate), 3)
        if _r == 1.0:
            is_standard_rate = True
            native_mod = "NM"
            native_rate = 1.0
        elif _r == 0.75:
            is_standard_rate = True
            native_mod = "HT"
            native_rate = 0.75
        elif _r == 1.5:
            is_standard_rate = True
            native_mod = "DT"
            native_rate = 1.5
        else:
            is_standard_rate = False
            native_mod = _core_mod
            native_rate = standard_rate
    else:
        # Stable: no explicit rate, use the mod's own scaling.
        is_standard_rate = True
        native_mod = _core_mod
        native_rate = standard_rate
    
    effective_rate = native_rate
    _interpolated = False
    _interp_anchor = None

    # Cache hit: same file + same mod + same rate.
    # For interpolated custom rates the key must carry the REAL rate,
    # otherwise 1.1x and 1.9x would collide on the native anchor key.
    _rate_for_key = float(rate) if not is_standard_rate else effective_rate
    key = _sr_cache_key(file_path, native_mod, _rate_for_key)
    if key in _sr_cache:
        return dict(_sr_cache[key])

    try:
        import numpy as np
        alg = _import_sr_core()
        
        target_path = file_path
        target_mod = native_mod
        temp_file = None
        
        if not is_standard_rate:
            # ── Custom lazer rate: scale the .osu timings to the target rate
            # and run the engine directly (same approach as ManiaMapAnalyser /
            # huismetbenen).  This yields the TRUE engine SR at the custom
            # rate instead of a linear interpolation between native anchors,
            # which systematically underrates mid rates (the engine's SR-vs-
            # rate curve is not linear: e.g. 8.73 @ 1.25x vs 10.10 @ 1.5x).
            # The pipeline's final-result interpolation keeps the DP monotonic
            # on top of this raw SR.
            temp_file = _scale_osu_timings(file_path, _r)
            target_path = temp_file
            target_mod = "NM"
            _interp_anchor = None
            _interpolated = False

        try:
            SR, all_corners, D_graph, components = alg.calculate(target_path, target_mod)
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

        Pbar = components.get("Pressing Intensity", np.array([0.0]))
        Abar = components.get("Unevenness", np.array([0.0]))
        Jbar = components.get("Same-Column Pressure", np.array([0.0]))
        Xbar = components.get("Cross-Column Pressure", np.array([0.0]))

        jbar_max = float(np.max(Jbar)) if len(Jbar) > 0 else 0.0
        pbar_max = float(np.max(Pbar)) if len(Pbar) > 0 else 0.0
        xbar_max = float(np.max(Xbar)) if len(Xbar) > 0 else 0.0
        abar_mean = float(np.mean(Abar)) if len(Abar) > 0 else 0.0

        # Component share ratios (structural fingerprint)
        comp_total = jbar_max + pbar_max + xbar_max + 1.0
        jbar_share = jbar_max / comp_total
        pbar_share = pbar_max / comp_total
        xbar_share = xbar_max / comp_total

        # Jack ratio approximation
        j_mean = jbar_max
        nj_mean = pbar_max + xbar_max
        jack_ratio = j_mean / max(j_mean + nj_mean, 1e-9)

        # Strain graph for real-time density display (ui-3 skin)
        # Sample D_graph to max 300 points for lightweight JSON transfer
        if D_graph is not None and len(D_graph) > 1:
            n = len(D_graph)
            if n > 300:
                indices = np.round(np.linspace(0, n - 1, 300)).astype(int)
                strain_sampled = [round(float(D_graph[i]), 4) for i in indices]
                times_sampled = [round(float(all_corners[i]), 2) for i in indices]
            else:
                strain_sampled = [round(float(v), 4) for v in D_graph]
                times_sampled = [round(float(t), 2) for t in all_corners]
            strain_graph = {"values": strain_sampled, "times": times_sampled}
        else:
            strain_graph = None

        result = {
            "sr": round(_enforce_monotonic_sr(file_path, native_mod, _rate_for_key, float(SR)), 4),
            "jack_ratio": round(jack_ratio, 4),
            "jbar_max": round(jbar_max, 4),
            "pbar_max": round(pbar_max, 4),
            "xbar_max": round(xbar_max, 4),
            "abar_mean": round(abar_mean, 4),
            "rbar_max": 0.0,
            "d93": 0.0,
            "d83": 0.0,
            "d_weighted_mean": 0.0,
            "total_notes_eff": int(len(D_graph)) if D_graph is not None else 0,
            "jbar_share": round(jbar_share, 4),
            "pbar_share": round(pbar_share, 4),
            "xbar_share": round(xbar_share, 4),
            "strain_graph": strain_graph,
            "success": True,
            "error": None,
        }
        _sr_cache[key] = result
        return result

    except Exception as exc:
        result = dict(_EMPTY_RESULT)
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
