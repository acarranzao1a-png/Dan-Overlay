# primary_sr_bridge.py -- Wrapper for the primary SR engine in the pipeline
#
# Wraps the raw SR calculation and returns a stable payload of SR
# and structural components for the pipeline.

import os
import sys
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SR_CORE_DIR = os.path.join(_SRC_DIR, "03_engine_reference", "sr_core")

# Deferred import to avoid startup errors if numpy is missing
_sr_core_alg = None

# In-process cache: (abspath, mtime_ns, mod) -> result dict
_sr_cache: dict[tuple, dict] = {}

# Per-map rate -> SR registry for monotonicity enforcement.  The custom-rate
# temp file quantizes hit times to integer ms, which can inject ~±0.07 SR of
# noise at dense maps — enough to flip a dan near a narrow boundary.  We keep
# the last computed SR per (map, mod, rate) and enforce SR non-decreasing in
# rate via isotonic smoothing so 1.49x can never rank higher than 1.5x.
_mono_registry: dict[tuple, dict] = {}


def _sr_cache_key(file_path: str, mod: str, rate: float = 1.0) -> tuple:
    try:
        mtime = os.stat(file_path).st_mtime_ns
    except OSError:
        mtime = 0
    return (os.path.abspath(file_path), mtime, mod, round(rate, 3))


def _mono_key(file_path: str, mod: str) -> tuple:
    try:
        mtime = os.stat(file_path).st_mtime_ns
    except OSError:
        mtime = 0
    return (os.path.abspath(file_path), mtime, mod)


def _enforce_monotonic_sr(file_path: str, mod: str, rate: float, sr: float) -> float:
    """Isotonic CLAMP over the per-map rate->SR registry.

    The Sunny algorithm's SR-vs-rate response is intrinsically non-monotonic
    (a "W" shape) under timing scaling — verified with both integer-ms and
    float-ms temp files, so it is not quantization noise.  We therefore
    enforce monotonicity by clamping every computed SR against the rates
    already seen for this (map, mod):

      - SR(rate) must be >= the max SR of any LOWER rate seen (floor)
      - SR(rate) must be <= the min SR of any HIGHER rate seen (ceiling)

    This guarantees that, no matter the order the user slides the lazer
    rate slider, a higher rate NEVER shows a lower SR than a lower rate
    (and vice versa).  The raw value is preserved when it is consistent
    with everything seen so far — only violators are clamped.
    """
    if rate is None:
        return sr
    key = _mono_key(file_path, mod)
    reg = _mono_registry.setdefault(key, {})

    r = round(float(rate), 3)
    reg[r] = sr

    # floor = max SR of all known lower rates
    floor_sr = 0.0
    for x, v in reg.items():
        if x < r and v > floor_sr:
            floor_sr = v
    # ceiling = min SR of all known higher rates
    ceil_sr = float("inf")
    for x, v in reg.items():
        if x > r and v < ceil_sr:
            ceil_sr = v

    clamped = sr
    if clamped < floor_sr:
        clamped = floor_sr
    if clamped > ceil_sr:
        clamped = ceil_sr

    # Store the clamped value so later comparisons use consistent data.
    reg[r] = clamped

    # Cap registry size per map (rates are visited densely; keep last 64)
    if len(reg) > 64:
        for stale in sorted(reg)[:-64]:
            del reg[stale]

    return float(clamped)


def _import_sr_core():
    global _sr_core_alg
    if _sr_core_alg is not None:
        return _sr_core_alg

    if _SR_CORE_DIR not in sys.path:
        sys.path.insert(0, _SR_CORE_DIR)

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
            # ── Custom rate: interpolate between the two nearest native
            # rates instead of scaling the .osu timings.  The native SRs
            # are computed with the engine's own mod paths (HT/NM/DT),
            # which are monotonic; linear interpolation between them is
            # monotonic by construction and immune to the engine's W
            # response to scaled timings.
            _native = {}
            for _nm, _nr in (("HT", 0.75), ("NM", 1.0), ("DT", 1.5)):
                _nkey = _sr_cache_key(file_path, _nm, _nr)
                if _nkey not in _sr_cache:
                    _nres = analyze_primary_sr(file_path, mod=_nm, rate=None)
                    _sr_cache[_nkey] = _nres
                _native[_nr] = _sr_cache[_nkey]
            
            _r = float(rate)
            _anchors = sorted(_native.keys())
            if _r <= _anchors[0]:
                _lo_k, _hi_k = _anchors[0], _anchors[1]
                _t = 0.0
            elif _r >= _anchors[-1]:
                _lo_k, _hi_k = _anchors[-2], _anchors[-1]
                _t = 1.0 + (_r - _anchors[-1]) / max(_anchors[-1] - _anchors[-2], 1e-9)
            else:
                for i in range(len(_anchors) - 1):
                    if _anchors[i] <= _r <= _anchors[i + 1]:
                        _lo_k, _hi_k = _anchors[i], _anchors[i + 1]
                        break
                _t = (_r - _lo_k) / max(_hi_k - _lo_k, 1e-9)
            
            _lo_res = _native[_lo_k]
            _hi_res = _native[_hi_k]
            _interp_anchor = (_lo_k, _hi_k, round(float(_lo_res.get("sr", 0.0) or 0.0), 4), round(float(_hi_res.get("sr", 0.0) or 0.0), 4))
            _interpolated = True
            
            # Interpolate SR and all structural components proportionally.
            _interp = {}
            for _field in ("sr", "jack_ratio", "jbar_max", "pbar_max", "xbar_max", "abar_mean",
                           "jbar_share", "pbar_share", "xbar_share", "total_notes_eff"):
                _v_lo = float(_lo_res.get(_field, 0.0) or 0.0)
                _v_hi = float(_hi_res.get(_field, 0.0) or 0.0)
                _interp[_field] = round(_v_lo + _t * (_v_hi - _v_lo), 4) if _field != "total_notes_eff" else int(round(_v_lo + _t * (_v_hi - _v_lo)))
            
            result = {
                "sr": _interp["sr"],
                "jack_ratio": _interp["jack_ratio"],
                "jbar_max": _interp["jbar_max"],
                "pbar_max": _interp["pbar_max"],
                "xbar_max": _interp["xbar_max"],
                "abar_mean": _interp["abar_mean"],
                "rbar_max": 0.0,
                "d93": 0.0,
                "d83": 0.0,
                "d_weighted_mean": 0.0,
                "total_notes_eff": _interp["total_notes_eff"],
                "jbar_share": _interp["jbar_share"],
                "pbar_share": _interp["pbar_share"],
                "xbar_share": _interp["xbar_share"],
                "strain_graph": _lo_res.get("strain_graph"),
                "success": True,
                "error": None,
                "interpolated_rate": True,
                "interp_anchor": _interp_anchor,
            }
            _sr_cache[key] = result
            return result

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
            "sr": round(float(SR), 4),
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
