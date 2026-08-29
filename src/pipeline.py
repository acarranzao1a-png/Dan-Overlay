# pipeline.py -- Main analysis pipeline: .osu -> estimated dan rank
#
# v3 architecture (2026-06):
#   Primary SR engine (algorithm.calculate) provides base SR.
#   Uses per-skillset SR interpolation for SR -> DP.
#   MinaCalc MSD is only a fallback and UI support (skillsets/roles).
#
# v3 replaces the 820-line KNN + Phi logic and 12 JSON configs with
# a direct skillset-calibrated boundary interpolation.

import concurrent.futures
import copy
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "02_runtime_bridge"))
sys.path.insert(0, os.path.join(_ROOT, "07_model"))
sys.path.insert(0, os.path.join(_ROOT, "08_isor_engine"))
sys.path.insert(0, os.path.join(_ROOT, "03_engine_reference", "sr_core"))

from minacalc_estimator import estimate as _minacalc_estimate
from celestial_estimator import estimate as _celestial_estimate
from celestial_estimator import fields_from_dp as _celestial_fields_from_dp
from signicial_estimator import estimate as _signicial_estimate
from signicial_estimator import fields_from_dp as _signicial_fields_from_dp
from shoegazer_estimator import estimate as _shoegazer_estimate
from shoegazer_estimator import fields_from_dp as _shoegazer_fields_from_dp
from ln_course_estimator import estimate as _ln_course_estimate
from ln_course_estimator import fields_from_dp as _ln_course_fields_from_dp

_PIPELINE_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="Pipeline-Worker")


def _error_payload(error, *, warnings=None):
    return {
        "error": error,
        "dp": None,
        "dan_label": None,
        "dan_short": None,
        "sublevel": None,
        "confidence": 0.0,
        "family": None,
        "primary_dan": None,
        "primary_role": None,
        "role_estimates": {},
        "composite_dan": None,
        "bottleneck_role": None,
        "is_generalist": False,
        "skillsets": {},
        "role_scores": {},
        "overall_msd": 0.0,
        "duration_s": 0,
        "note_count": 0,
        "warnings": list(warnings or []),
        "engine": None,
        "corrections": [],
        "ln_route": "rice",
        "ln_course": None,
    }


def _inject_sunny_components(debug, sr_result):
    """Attach Sunny SR component strains to the debug dict for the ui-7 skin.

    ``contracts.to_dict()`` exposes ``jbar_max``/``pbar_max``/``xbar_max``/
    ``abar_mean`` from ``debug["sr_result"]``; rank_engine's own debug dict
    does not carry them, so they are injected here from the raw SR output.
    """
    _debug = dict(debug or {})
    _raw = sr_result or {}
    _debug["sr_result"] = {
        "jbar_max":  float(_raw.get("jbar_max", 0.0) or 0.0),
        "pbar_max":  float(_raw.get("pbar_max", 0.0) or 0.0),
        "xbar_max":  float(_raw.get("xbar_max", 0.0) or 0.0),
        "abar_mean": float(_raw.get("abar_mean", 0.0) or 0.0),
    }
    return _debug


def _augment_features_with_msd(features, mina_result):
    """Inject MSD ratios into the feature dict for rank_engine consumption."""
    enriched = dict(features or {})
    if not isinstance(mina_result, dict):
        return enriched

    overall_msd = float(mina_result.get("overall_msd", 0.0) or 0.0)
    skillsets = dict(mina_result.get("skillsets") or {})
    if overall_msd <= 0.0 or not skillsets:
        return enriched

    ratio_map = {
        "handstream": "msd_handstream_ratio",
        "jackspeed": "msd_jackspeed_ratio",
        "chordjack": "msd_chordjack_ratio",
        "technical": "msd_technical_ratio",
        "stamina": "msd_stamina_ratio",
        "stream": "msd_stream_ratio",
    }
    for skill, feat_name in ratio_map.items():
        value = float(skillsets.get(skill, 0.0) or 0.0)
        if value > 0.0:
            enriched[feat_name] = value / overall_msd

    enriched["msd_overall"] = overall_msd
    if mina_result.get("primary_role"):
        enriched["msd_primary_role"] = mina_result["primary_role"]
    return enriched


def _compute_primary_rank_result(osu_path, mod="NM", strict_domain=False, mina_result=None,
                                  *, parsed=None, domain=None, features=None, rate=None):
    """Primary SR path: SR engine -> per-skillset interpolation.

    MinaCalc data is injected into features for potential future use but
    does not affect the primary DP calculation.

    When *parsed*, *domain*, and *features* are supplied by the caller,
    the redundant .osu parse is skipped.
    """
    from primary_sr_bridge import analyze_primary_sr
    from classifier import classify_family
    from rhythm_profile import classify_from_parsed as classify_parsed
    from rank_engine import compute_rank

    error = None

    if parsed is None:
        from parser import parsear_osu_v2
        from validator import validate_domain as _validate
        from feature_extractor import extract_features as _extract

        try:
            parsed = parsear_osu_v2(osu_path, enforce_mode_mania=True)
        except Exception as exc:
            return {"error": f"parse_error: {exc}", "dp": None, "dan_label": None}

        if parsed.get("rejected"):
            return {
                "error": "domain_rejected",
                "reason": "non_4k_or_invalid",
                "dp": None,
                "dan_label": None,
                "warnings": parsed.get("warnings", []),
            }

        domain = _validate(parsed)
        if strict_domain and not domain.get("valid", True):
            return {
                "error": "domain_out_of_range",
                "dp": None,
                "dan_label": None,
                "domain": domain,
            }

        features = _extract(parsed)

    features = _augment_features_with_msd(features, mina_result)

    sr_result = analyze_primary_sr(osu_path, mod=mod, rate=rate)
    if not sr_result.get("success", False):
        return {
            "error": f"primary_sr_error: {sr_result.get('error')}",
            "dp": None,
            "dan_label": None,
            "dan_short": None,
            "sublevel": None,
            "confidence": 0.0,
            "family": None,
            "sr": 0.0,
            "corrections": [],
            "domain": domain,
            "features": features,
        }

    # ── Hybrid classifier selection ─────────────────────────────────
    # Rhythm profile classifier excels in mid-tier (SR < 7.0) where the
    # Sunny algorithm compresses adjacent tiers.  The bar-ratio classifier
    # is more stable in high-tier (SR >= 7.0) where pattern compression
    # at extreme BPMs causes rhythm misclassification (stamina -> speed).
    _sr_gate = float(sr_result.get("sr", 0.0) or 0.0)
    if _sr_gate < 7.0:
        classification = classify_parsed(parsed)
        if classification.get("confidence", 0.0) < 0.10:
            classification = classify_family(sr_result, features, domain)
    else:
        classification = classify_family(sr_result, features, domain)
    rank = compute_rank(sr_result, features, classification, domain, msd=(mina_result or {}).get("skillsets") or {})

    return {
        "dp":             rank["dp"],
        "dan_label":      rank["dan_label"],
        "dan_short":      rank["dan_short"],
        "sublevel":       rank["sublevel"],
        "confidence":     rank["confidence"],
        "sr":             rank["sr"],
        "family":         rank["family"],
        "corrections":    rank["corrections"],
        "domain":         domain,
        "features":       features,
        "primary_sr":     sr_result,
        "classification": classification,
        "debug":          _inject_sunny_components(rank.get("debug", {}), sr_result),
        "error":          error,
        "warnings":       parsed.get("warnings", []) + domain.get("warnings", []),
        "duration_s":     float(domain.get("drain_time_s", 0.0) or 0.0),
        "note_count":     int(domain.get("note_count", 0) or 0),
        "peak_nps":       float(features.get("nps_p90", 0.0) or 0.0),
        "nps_curve":      features.get("nps_curve", []),
    }


def _merge_primary_and_mina(primary_result, mina_result):
    """Merge primary SR ranking with MinaCalc data for UI display.

    The primary DP comes from the SR ruler path using the Sunny-based family
    classifier.  After both parallel tasks complete, MinaCalc skillsets are
    used to cross-check that family and — if they signal a different one with
    sufficient confidence — recompute DP with the correct per-skillset ruler.

    This corrects the most common mislabels (jack ↔ stamina) without sacrificing
    the parallel execution speed.
    """
    from rank_engine import _msd_to_family, recompute_dp_for_family

    merged = dict(primary_result)
    merged["engine"] = "sr_ruler_v3"

    if not isinstance(mina_result, dict) or mina_result.get("dp") is None:
        return merged

    warnings = list(primary_result.get("warnings", []))
    warnings.extend(x for x in mina_result.get("warnings", []) if x not in warnings)

    debug = dict(primary_result.get("debug") or {})
    mina_dp = float(mina_result.get("dp", 0.0) or 0.0)
    debug["mina_reference"] = {
        "dp": round(mina_dp, 3),
        "confidence": round(float(mina_result.get("confidence", 0.0) or 0.0), 3),
        "family": str(mina_result.get("family", "") or ""),
    }

    merged.update({
        "warnings": warnings,
        "debug": debug,
        "overall_msd": float(mina_result.get("overall_msd", 0.0) or 0.0),
        "primary_role": mina_result.get("primary_role"),
        "primary_dan": mina_result.get("primary_dan"),
        "role_estimates": mina_result.get("role_estimates") or {},
        "composite_dan": mina_result.get("composite_dan"),
        "bottleneck_role": mina_result.get("bottleneck_role"),
        "is_generalist": bool(mina_result.get("is_generalist", False)),
        "role_breakdown_text": mina_result.get("role_breakdown_text", ""),
        "skillsets": mina_result.get("skillsets") or {},
        "role_scores": mina_result.get("role_scores") or {},
    })

    # ── Marathon / long-map SR correction ─────────────────────────────────────
    # Must run here (not inside compute_rank) because MSD skillsets are only
    # available after both parallel tasks complete.
    # Reference: SR inflation measured on 6th–10th Reform Marathon Pack maps
    # (all ~7-9 min, reading 1-2 dans higher than individually-housed songs).
    # Inflation tapers to ≈0 at SR ≥7.0 (Alpha+), so upper-tier marathons
    # that are correctly calibrated are unaffected.
    sunny_family = primary_result.get("family", "hybrid")
    msd_skillsets = mina_result.get("skillsets") or {}
    _dur_s = float(primary_result.get("duration_s", 0.0) or 0.0)
    if _dur_s > 300.0 and msd_skillsets:
        _mj  = max(float(msd_skillsets.get("jackspeed",  0) or 0),
                   float(msd_skillsets.get("chordjack",  0) or 0))
        _ms  = max(float(msd_skillsets.get("stream",     0) or 0),
                   float(msd_skillsets.get("jumpstream", 0) or 0))
        _mt  = float(msd_skillsets.get("technical", 0) or 0)
        _mst = (0.7 * float(msd_skillsets.get("stamina",     0) or 0)
                + 0.3 * float(msd_skillsets.get("handstream", 0) or 0))
        _tot = _mj + _ms + _mt + _mst
        if _tot > 1.0 and max(_mj, _ms, _mt, _mst) / _tot < 0.45:
            _sr = float(merged.get("sr", 0.0))
            _excess_min = (_dur_s - 300.0) / 60.0
            _raw_corr = min(0.65, _excess_min * 0.080)
            if _sr >= 7.00:
                _taper = 0.0
            elif _sr >= 6.50:
                _taper = 1.0 - (_sr - 6.50) / 0.50
            else:
                _taper = 1.0
            _mara_corr = _raw_corr * _taper
            if _mara_corr > 0.005:
                from rank_engine import sr_to_dp, dp_to_label, dp_to_sublevel
                _fam = merged.get("family") or sunny_family
                _sk  = {"jack": "jack", "speed": "speed",
                        "stamina": "stamina", "tech": "tech"}.get(_fam)
                _new_dp = round(sr_to_dp(_sr - _mara_corr, skillset=_sk), 2)
                if _new_dp < float(merged.get("dp", 99.0)):
                    merged["dp"] = _new_dp
                    merged["dan_label"], merged["dan_short"] = dp_to_label(_new_dp)
                    merged["sublevel"] = dp_to_sublevel(_new_dp)
                    _corrs = list(merged.get("corrections") or [])
                    _corrs.append(f"marathon_duration_penalty:-{_mara_corr:.3f}")
                    merged["corrections"] = _corrs

    return merged


# ── LN family heuristic ─────────────────────────────────────────────────────

def _classify_ln_family(features: dict) -> str:
    """Lightweight heuristic: classify LN subfamily from structural features.

    Since we use the global SR ruler for rank estimation, the family label is
    cosmetic only (tells the user *what kind* of LN map they're playing).
    """
    ln_ratio     = float(features.get("ln_ratio", 0) or 0)
    sim_hold     = float(features.get("simultaneous_hold", 0) or 0)
    release_dens = float(features.get("release_density", 0) or 0)
    ln_cv        = float(features.get("ln_duration_cv", 0) or 0)
    hold_chord   = float(features.get("hold_chord_ratio", 0) or 0)

    # Speed/Density: high release frequency + high LN presence
    if release_dens > 3.5 and ln_ratio > 0.50:
        return "speed_density"

    # Inverse: near-pure LN charts with heavy overlap
    if ln_ratio > 0.85 and sim_hold > 0.30:
        return "inverse"

    # Jack/Technical: mixed rice+LN, high duration variety
    if ln_ratio < 0.55 and ln_cv > 0.50:
        return "jack_technical"

    # Default: all-round / hybrid LN
    return "allround"


def _monotonic_floor(lo_res, hi_res, dp_to_label, dp_to_sublevel, fields_fns, dp_key):
    """Floor *hi_res* against *lo_res* so results never decrease with rate.

    The Sunny formula is intrinsically non-monotonic in rate (W-shape), so
    native anchors can be inverted (e.g. SR at DT 1.5 < SR at NM).  Flooring
    the hi anchor keeps the interpolated/extrapolated curve monotonic across
    the native boundary instead of dipping; labels are re-derived from the
    floored DP.
    """
    hi = dict(hi_res)
    dp_floored = False
    for _f in ("dp", "sr"):
        _v_lo = float(lo_res.get(_f, 0.0) or 0.0)
        _v_hi = float(hi.get(_f, 0.0) or 0.0)
        if _v_hi < _v_lo:
            hi[_f] = _v_lo
            if _f == "dp":
                dp_floored = True
    if dp_floored:
        _dp = float(hi.get("dp", 0.0) or 0.0)
        if _dp > 0:
            _label, _short = dp_to_label(_dp)
            hi["dan_label"] = _label
            hi["dan_short"] = _short
            hi["sublevel"] = dp_to_sublevel(_dp)
    for _mk in ("celestial", "signicial", "shoegazer", "ln_course"):
        _m_lo = lo_res.get(_mk)
        _m_hi = hi.get(_mk)
        if isinstance(_m_lo, dict) and isinstance(_m_hi, dict):
            _dpk = dp_key[_mk]
            _a = float(_m_lo.get(_dpk, 0.0) or 0.0)
            _b = float(_m_hi.get(_dpk, 0.0) or 0.0)
            if _b < _a:
                hi[_mk] = dict(_m_hi)
                hi[_mk][_dpk] = round(_a, 3)
                hi[_mk].update(fields_fns[_mk](_a))
    return hi


def _load_parsed_chart(file_path: str, difficulty: str = "") -> dict:
    """Parses .osu, .sm, or .ssc into the unified DanOverlay chart dict."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".sm", ".ssc"):
        try:
            from etterna import parse_simfile
        except ImportError:
            from etterna.sm_parser import parse_simfile
        return parse_simfile(file_path, difficulty=difficulty)
    from parser import parsear_osu_v2
    return parsear_osu_v2(file_path, enforce_mode_mania=True)


def _ensure_osu_path_for_c_engines(file_path: str, parsed: dict | None = None, difficulty: str = "") -> tuple[str, bool]:
    """Ensures a valid .osu path for C++/C# binary engines (Sunny SR & MinaCalc).
    If file_path is already .osu, returns (file_path, False).
    If .sm or .ssc, writes a temporary .osu and returns (temp_path, True).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".osu":
        return file_path, False

    if parsed is None:
        parsed = _load_parsed_chart(file_path, difficulty=difficulty)

    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".osu")
    bpm = parsed.get("bpm", 120.0) or 120.0
    beat_len = 60000.0 / bpm if bpm > 0 else 500.0
    ln_map = {}
    for ev in parsed.get("note_events", []):
        if ev.get("event_type") == "ln_start" and ev.get("ln_end_ms"):
            ln_map[(ev["time_ms"], ev["col"])] = ev["ln_end_ms"]

    lines = [
        "osu file format v14\n\n[General]\nMode: 3\n\n[Difficulty]\nCircleSize: 4\nOverallDifficulty: 8\n\n[TimingPoints]\n",
        f"0,{beat_len:.4f},4,2,0,0,1,0\n\n[HitObjects]\n"
    ]
    for t_ms, col in parsed.get("notes", []):
        x = int(col * 128 + 64)
        if (t_ms, col) in ln_map:
            end_ms = ln_map[(t_ms, col)]
            lines.append(f"{x},192,{t_ms},128,0,{end_ms}:0:0:0:0:\n")
        else:
            lines.append(f"{x},192,{t_ms},1,0,0:0:0:0:\n")

    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return tmp_path, True


def _analyze_map_isor(osu_path, mod="NM", strict_domain=False, rate=None, difficulty: str = ""):
    """Execution path for the ISOR engine (Isotonic Strain Organic Residual)."""
    from validator import validate_domain
    from isor_engine import analyze_beatmap_isor
    from feature_extractor import extract_features

    try:
        parsed = _load_parsed_chart(osu_path, difficulty=difficulty)
    except Exception as exc:
        return _error_payload(f"parse_error: {exc}")

    if parsed.get("rejected"):
        return _error_payload(
            "domain_rejected",
            warnings=parsed.get("warnings", []),
        )

    domain = validate_domain(parsed)
    if strict_domain and not domain.get("valid", True):
        return _error_payload("domain_out_of_range")

    # If 7K or LN-dominant (LN ratio > 0.18), use the specialized 7K/LN legacy logic
    _ln_route = str(domain.get("ln_route", "rice") or "rice")
    if domain.get("is_7k") or _ln_route == "ln":
        res = _analyze_map_impl_inner(osu_path, mod=mod, strict_domain=strict_domain, rate=rate)
        if isinstance(res, dict):
            res["engine"] = "isor"
        return res

    # 4K Rice beatmap: run ISOR
    engine_path, is_temp = _ensure_osu_path_for_c_engines(osu_path, parsed)
    try:
        raw_isor = analyze_beatmap_isor(engine_path, mod=mod, rate=rate, parsed=parsed, domain=domain)
        if not raw_isor or raw_isor.get("error"):
            return _error_payload(raw_isor.get("error") if raw_isor else "isor_analysis_failed")
    except Exception as exc:
        return _error_payload(f"isor_error: {exc}")
    finally:
        if is_temp and os.path.exists(engine_path):
            try:
                os.remove(engine_path)
            except OSError:
                pass

    features = raw_isor.get("features") or extract_features(parsed)
    msd_res = raw_isor.get("msd") or {}
    sunny_strains = raw_isor.get("sunny_strains") or {}
    raw_sr = float(raw_isor.get("raw_sr", 0.0) or 0.0)
    family = str(raw_isor.get("family", "hybrid") or "hybrid")

    # Build MSD skillset dict for roles/ui
    _overall_msd = float(msd_res.get("overall", 0.0) or 0.0) if isinstance(msd_res, dict) else 0.0
    _skillsets = {}
    if isinstance(msd_res, dict):
        for k in ("stream", "jumpstream", "handstream", "stamina", "jackspeed", "chordjack", "technical"):
            if k in msd_res:
                _skillsets[k] = float(msd_res[k])

    # Rate adjusted map stats
    _MOD_RATE = {"HT": 0.75, "DT": 1.5, "NC": 1.5, "NM": 1.0}
    _effective_bpm_rate = rate if rate is not None else _MOD_RATE.get(mod, 1.0)
    _raw_bpm = float(features.get("bpm", 0.0) or 0.0)
    _raw_min = float(parsed.get("bpm_min", _raw_bpm) or _raw_bpm)
    _raw_max = float(parsed.get("bpm_max", _raw_bpm) or _raw_bpm)
    _raw_common = float(parsed.get("bpm_common", _raw_bpm) or _raw_bpm)

    # Derive auxiliary ladders: ISOR exclusively supports Reform and Celestial
    from celestial_estimator import estimate_from_isor_dp as _celestial_from_isor_dp

    cel_obj = _celestial_from_isor_dp(raw_isor.get("dp", 0.0))
    celestial_res = cel_obj.to_dict() if cel_obj is not None else None
    signicial_res = None
    shoegazer_res = None

    # Sunny debug structure
    debug = {
        "sr_result": {
            "jbar_max": float(sunny_strains.get("jbar_max", 0.0) or 0.0),
            "pbar_max": float(sunny_strains.get("pbar_max", 0.0) or 0.0),
            "xbar_max": float(sunny_strains.get("xbar_max", 0.0) or 0.0),
            "abar_mean": float(sunny_strains.get("abar_mean", 0.0) or 0.0),
        },
        "isor": {
            "weights": raw_isor.get("weights", {}),
            "dp_sr": raw_isor.get("dp_sr"),
            "dp_choke": raw_isor.get("dp_choke"),
            "dp_msd": raw_isor.get("dp_msd"),
            "dp_bio": raw_isor.get("dp_bio"),
            "bio_numeric": raw_isor.get("bio_numeric"),
            "sk_key": raw_isor.get("sk_key"),
            "ridge_correction": raw_isor.get("ridge_correction", 0.0),
            "modulated_sr": raw_isor.get("modulated_sr"),
        }
    }

    _drain_s = float(domain.get("drain_time_s", 0.0) or 0.0)
    _note_count = int(domain.get("note_count", 0) or 0)
    _avg_nps = (_note_count / _drain_s) if _drain_s > 0 else 0.0

    return {
        "engine": "isor",
        "dp": raw_isor["dp"],
        "dan_label": raw_isor["dan_label"],
        "dan_short": raw_isor["dan_short"],
        "sublevel": raw_isor["sublevel"],
        "confidence": float(raw_isor.get("family_confidence", 1.0) or 1.0),
        "sr": raw_sr,
        "family": family,
        "mod": mod or "NM",
        "corrections": [f"isor_ridge:{raw_isor.get('ridge_correction', 0.0):+.3f}"] if raw_isor.get("ridge_correction") else [],
        "nps": round(_avg_nps, 1),
        "peak_nps": float(features.get("nps_p90", 0.0) or 0.0),
        "nps_curve": features.get("nps_curve", []),
        "duration_s": _drain_s,
        "note_count": _note_count,
        "warnings": parsed.get("warnings", []) + domain.get("warnings", []),
        "error": None,
        "debug": debug,
        "overall_msd": _overall_msd,
        "primary_role": family,
        "role_estimates": {},
        "skillsets": _skillsets,
        "composite_dan": "",
        "bottleneck_role": "",
        "is_generalist": False,
        "role_breakdown_text": "",
        "celestial": celestial_res,
        "signicial": signicial_res,
        "shoegazer": shoegazer_res,
        "ln_course": None,
        "ln_route": _ln_route,
        "strain_graph": raw_isor.get("strain_graph"),
        "bpm": round(_raw_bpm * _effective_bpm_rate, 1),
        "bpm_min": int(round(_raw_min * _effective_bpm_rate)),
        "bpm_max": int(round(_raw_max * _effective_bpm_rate)),
        "bpm_common": int(round(_raw_common * _effective_bpm_rate)),
        "od": round(float(parsed.get("od", 0.0) or 0.0), 1),
    }


def analyze_map(osu_path, mod="NM", strict_domain=False, rate=None, engine=None, difficulty: str = ""):
    """Estimate the Dan rank using the core pipeline runtime logic.

    Parameters
    ----------
    osu_path : str
        Path to the .osu file.
    mod : str
        Active mods (DT, HT, etc.).
    strict_domain : bool
        If True, returns error if the beatmap is outside standard constraints.
    rate : float or None
        Custom rate (e.g. from lazer). If None, mod default rate is used.
    engine : str or None
        "isor" (default) or "legacy".
    difficulty : str
        Target difficulty name/version (e.g. for StepMania .sm/.ssc simfiles).

    Returns
    -------
    dict
        Structured analysis payload for the overlay.
    """
    _engine = str(engine or "isor").lower().strip()

    # ── Custom lazer clock rates (Legacy path) ───────────────────────
    if _engine == "legacy" and rate is not None:
        _r = round(float(rate), 4)
        _NATIVE = (0.75, 1.0, 1.5)

        if _r not in _NATIVE:
            _lo, _hi = None, None
            if _r < _NATIVE[0]:
                # Extrapolate below HT (0.75x) against the 0.75-1.0 segment so
                # lazer rates like 0.43x/0.5x keep following the rate (t goes negative).
                _lo, _hi = _NATIVE[0], _NATIVE[1]
                _t = (_r - _lo) / max(_hi - _lo, 1e-9)
            elif _r > _NATIVE[-1]:
                _lo, _hi = _NATIVE[-2], _NATIVE[-1]
                _t = 1.0 + (_r - _hi) / max(_hi - _lo, 1e-9)
            else:
                for i in range(len(_NATIVE) - 1):
                    if _NATIVE[i] <= _r <= _NATIVE[i + 1]:
                        _lo, _hi = _NATIVE[i], _NATIVE[i + 1]
                        break
                _t = (_r - _lo) / max(_hi - _lo, 1e-9)

            _res_lo = analyze_map(osu_path, mod=mod, strict_domain=strict_domain, rate=_lo, engine="legacy", difficulty=difficulty)
            _res_hi = analyze_map(osu_path, mod=mod, strict_domain=strict_domain, rate=_hi, engine="legacy", difficulty=difficulty)
            if isinstance(_res_lo, dict) and isinstance(_res_hi, dict) \
                    and _res_lo.get("dp") is not None and _res_hi.get("dp") is not None:
                from rank_engine import dp_to_label, dp_to_sublevel

                _interp_result = dict(_res_lo)
                _NUMERIC = [
                    "dp", "sr", "overall_msd", "confidence",
                    "bpm", "bpm_min", "bpm_max", "bpm_common", "od",
                ]
                for _f in _NUMERIC:
                    _v_lo = float(_res_lo.get(_f, 0.0) or 0.0)
                    _v_hi = float(_res_hi.get(_f, 0.0) or 0.0)
                    _interp_result[_f] = round(max(0.0, _v_lo + _t * (_v_hi - _v_lo)), 2)

                _dp_val = round(max(0.5, _res_lo.get("dp", 0.0) + _t * (_res_hi.get("dp", 0.0) - _res_lo.get("dp", 0.0))), 2)
                _interp_result["dp"] = _dp_val
                _label, _short = dp_to_label(_dp_val)
                _interp_result["dan_label"] = _label
                _interp_result["dan_short"] = _short
                _interp_result["sublevel"] = dp_to_sublevel(_dp_val)

                # Interpolate alternative-mode estimates (celestial etc.)
                _fields_fns = {
                    "celestial": _celestial_fields_from_dp,
                    "signicial": _signicial_fields_from_dp,
                    "shoegazer": _shoegazer_fields_from_dp,
                    "ln_course": _ln_course_fields_from_dp,
                }
                _dp_key = {
                    "celestial": "dp_celestial",
                    "signicial": "dp_signicial",
                    "shoegazer": "dp_shoegazer",
                    "ln_course": "dp_ln",
                }
                for _mk in ("celestial", "signicial", "shoegazer", "ln_course"):
                    _m_lo = _res_lo.get(_mk)
                    _m_hi = _res_hi.get(_mk)
                    if isinstance(_m_lo, dict) and isinstance(_m_hi, dict):
                        _interp_result[_mk] = dict(_m_lo)
                        for _mf in ("dp_celestial", "dp_signicial", "dp_shoegazer", "dp_ln", "confidence"):
                            if _mf in _m_lo and _mf in _m_hi:
                                _a = float(_m_lo.get(_mf, 0.0) or 0.0)
                                _b = float(_m_hi.get(_mf, 0.0) or 0.0)
                                _interp_result[_mk][_mf] = round(max(0.0, _a + _t * (_b - _a)), 2)
                        _dpf = _interp_result[_mk].get(_dp_key[_mk])
                        if _dpf is not None:
                            _interp_result[_mk].update(_fields_fns[_mk](float(_dpf)))

                _interp_result["custom_rate_interpolated"] = True
                return _interp_result

    return _analyze_map_impl(osu_path, mod=mod, strict_domain=strict_domain, rate=rate, engine=_engine, difficulty=difficulty)


# ── Full-result cache for _analyze_map_impl ────────────────────────
_impl_cache: dict[tuple, dict] = {}
_IMPL_CACHE_MAX = 96


def _analyze_map_impl(osu_path, mod="NM", strict_domain=False, rate=None, engine="isor", difficulty: str = ""):
    try:
        _mtime = os.stat(osu_path).st_mtime_ns
    except OSError:
        _mtime = 0
    _key = (
        os.path.abspath(osu_path),
        str(difficulty or ""),
        _mtime,
        mod,
        bool(strict_domain),
        round(float(rate) if rate is not None else 1.0, 4),
        str(engine).lower(),
    )
    _hit = _impl_cache.get(_key)
    if _hit is not None:
        return copy.deepcopy(_hit)

    if str(engine).lower() == "isor":
        _result = _analyze_map_isor(osu_path, mod=mod, strict_domain=strict_domain, rate=rate, difficulty=difficulty)
    else:
        _result = _analyze_map_impl_inner(osu_path, mod=mod, strict_domain=strict_domain, rate=rate, difficulty=difficulty)
        if isinstance(_result, dict):
            _result["engine"] = "legacy"

    if isinstance(_result, dict):
        _impl_cache[_key] = copy.deepcopy(_result)
        if len(_impl_cache) > _IMPL_CACHE_MAX:
            _impl_cache.pop(next(iter(_impl_cache)))

    return _result


def _analyze_map_impl_inner(osu_path, mod="NM", strict_domain=False, rate=None, difficulty: str = ""):
    """Core pipeline implementation (no custom-rate interpolation)."""
    from validator import validate_domain
    from feature_extractor import extract_features

    # ── Parse chart once (shared by both engines) ───────────────────
    try:
        parsed = _load_parsed_chart(osu_path, difficulty=difficulty)
    except Exception as exc:
        return _error_payload(f"parse_error: {exc}")

    if parsed.get("rejected"):
        return _error_payload(
            "domain_rejected",
            warnings=parsed.get("warnings", []),
        )

    domain = validate_domain(parsed)
    if strict_domain and not domain.get("valid", True):
        return _error_payload("domain_out_of_range")

    if domain.get("is_7k"):
        import json
        from primary_sr_bridge import analyze_primary_sr as sr_analyze
        from resource_path import resource_path
        
        try:
            # Use the same bridge as the 4K path so custom lazer clock
            # rates (1.01x-2.0x, 0.5x-0.99x) scale the hit timings via a
            # temporary .osu.  The raw algo_calc call ignored `rate`,
            # so NC/DT custom rates were visually recognised but
            # factually ignored when estimating the dan.
            algo_res = sr_analyze(osu_path, mod=mod, rate=rate)
            if not algo_res.get("success", False):
                return _error_payload(f"7k_algorithm_error: {algo_res.get('error')}")
            sr = float(algo_res.get("sr", 0.0) or 0.0)
        except Exception as exc:
            return _error_payload(f"7k_algorithm_error: {exc}")
            
        try:
            with open(resource_path("config", "sr_means_7k.json"), "r", encoding="utf-8") as f:
                means_7k = json.load(f)["general"]
        except Exception as exc:
            return _error_payload(f"7k_config_error: {exc}")
            
        tier_order = ["0th", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th",
                      "Gamma", "Azimuth", "Zenith", "Stellium"]
        
        medians = [means_7k[t]["median"] for t in tier_order]
        
        # Precompute boundaries as midpoints between adjacent medians (Reform-style)
        boundaries = []
        for i in range(len(medians) - 1):
            lo = (medians[i] + medians[i+1]) / 2
            if i + 2 < len(medians):
                hi = (medians[i+1] + medians[i+2]) / 2
            else:
                hi = medians[i+1] + (medians[i+1] - medians[i])
            boundaries.append((lo, hi, i))
        
        best_idx = None
        dp_7k = 0.0
        beyond = False
        
        if sr < boundaries[0][0]:
            best_idx = 0
            dp_7k = 0.0
        elif sr >= boundaries[-1][1]:
            best_idx = len(tier_order) - 1
            lo_sr = boundaries[-1][0]
            hi_sr = max(boundaries[-1][1], sr + 0.01)
            t = (sr - lo_sr) / (hi_sr - lo_sr) if hi_sr > lo_sr else 0.5
            dp_7k = float(best_idx) + t
            beyond = True
        else:
            for lo, hi, idx in boundaries:
                if lo <= sr < hi:
                    t = (sr - lo) / (hi - lo) if hi > lo else 0.5
                    dp_7k = float(idx) + t
                    best_idx = idx
                    break
        
        if best_idx is None:
            best_idx = 11
            dp_7k = 11.0
        
        best_tier = tier_order[best_idx]
        dp_7k = round(dp_7k, 2)
        
        # Sublevel: Low 0-20, Mid-Low 21-40, Mid 41-60, Mid-High 61-80, High 81-99
        dp_frac = round(dp_7k - int(dp_7k), 2)
        if dp_frac <= 0.20: sub = "Low"
        elif dp_frac <= 0.40: sub = "Mid-Low"
        elif dp_frac <= 0.60: sub = "Mid"
        elif dp_frac <= 0.80: sub = "Mid-High"
        else: sub = "High"
        
        # Add " Dan" suffix for numeric tiers (0th-10th) to match overlay palette keys
        if best_tier in ("0th", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"):
            best_tier += " Dan"
        
        if beyond:
            best_tier = "Beyond Stellium"
            sub = "Beyond"
        
        # Calculate bpm properly (rate-adjusted like the 4K path)
        _mod_rate_map = {"HT": 0.75, "DT": 1.5, "NC": 1.5, "NM": 1.0}
        _eff_rate = rate if rate is not None else _mod_rate_map.get(mod, 1.0)
        bpm_val = float(parsed.get("bpm_common", 0.0) or parsed.get("bpm", 0.0) or 0.0) * _eff_rate
        bpm_common_raw = float(parsed.get("bpm_common", bpm_val) or bpm_val) * _eff_rate
        
        return {
            "mode": "7k",
            "tier_7k": best_tier,
            "sublevel_7k": sub,
            "dp_7k": dp_7k,
            "sr": round(sr, 2),
            "bpm": round(bpm_val, 1),
            "bpm_min": int(round(float(parsed.get("bpm_min", bpm_common_raw) or bpm_common_raw) * _eff_rate)),
            "bpm_max": int(round(float(parsed.get("bpm_max", bpm_common_raw) or bpm_common_raw) * _eff_rate)),
            "bpm_common": int(round(bpm_common_raw)),
            "od": round(float(parsed.get("od", 0.0) or 0.0), 1),
            "note_count": int(domain.get("note_count", 0)),
            "duration_s": float(domain.get("drain_time_s", 0.0)),
            "warnings": [],
            "debug": _inject_sunny_components({}, algo_res),
            "error": None
        }

    features = extract_features(parsed)

    engine_path, is_temp = _ensure_osu_path_for_c_engines(osu_path, parsed)

    # ── Run MinaCalc + Primary SR in parallel ──────────────────────
    def _safe_mina():
        try:
            _MOD_RATE = {"HT": 0.75, "DT": 1.5, "NC": 1.5}
            effective_rate = rate if rate is not None else _MOD_RATE.get(mod, 1.0)
            return _minacalc_estimate(engine_path, rate=effective_rate, features=features)
        except Exception:
            return None

    def _safe_celestial(mina_result, primary_sr=None, family_hint=None):
        """Derive Celestial estimate using primary SR + MSD skillsets."""
        try:
            if not isinstance(mina_result, dict):
                return None
            skillsets = mina_result.get("skillsets")
            if not skillsets:
                return None
            result = _celestial_estimate(skillsets, sr=primary_sr, family_hint=family_hint)
            return result.to_dict() if result is not None else None
        except Exception:
            return None

    def _safe_signicial(mina_result, primary_sr=None, family_hint=None):
        """Derive Signicial estimate using primary SR + MSD skillsets."""
        try:
            if not isinstance(mina_result, dict):
                return None
            skillsets = mina_result.get("skillsets")
            if not skillsets:
                return None
            result = _signicial_estimate(skillsets, sr=primary_sr, family_hint=family_hint)
            return result.to_dict() if result is not None else None
        except Exception:
            return None

    def _safe_shoegazer(mina_result, primary_sr=None, family_hint=None):
        """Derive Shoegazer estimate using primary SR + MSD skillsets."""
        try:
            if not isinstance(mina_result, dict):
                return None
            skillsets = mina_result.get("skillsets")
            if not skillsets:
                return None
            result = _shoegazer_estimate(skillsets, sr=primary_sr)
            return result.to_dict() if result is not None else None
        except Exception:
            return None

    def _safe_ln_course(mina_result, primary_sr=None, ln_family=None, features=None):
        """Derive LN Course estimate using primary SR + MSD skillsets."""
        try:
            if not isinstance(mina_result, dict):
                return None
            skillsets = mina_result.get("skillsets")
            if not skillsets:
                return None
            family = ln_family or "allround"
            result = _ln_course_estimate(skillsets, sr=primary_sr, ln_family=family, features=features)
            return result.to_dict() if result is not None else None
        except Exception:
            return None

    try:
        mina_future = _PIPELINE_POOL.submit(_safe_mina)
        primary_future = _PIPELINE_POOL.submit(
            _compute_primary_rank_result,
            engine_path, mod, strict_domain, None,
            parsed=parsed, domain=domain, features=features, rate=rate,
        )
        primary_core = primary_future.result()
        mina = mina_future.result()
    finally:
        if is_temp and os.path.exists(engine_path):
            try:
                os.remove(engine_path)
            except OSError:
                pass

    primary_ok = isinstance(primary_core, dict) and primary_core.get("dp") is not None

    # ── Map-level BPM stats (shared by primary and MinaCalc fallback) ──
    _MOD_RATE = {"HT": 0.75, "DT": 1.5, "NC": 1.5, "NM": 1.0}
    _effective_bpm_rate = rate if rate is not None else _MOD_RATE.get(mod, 1.0)
    _raw_bpm = float(features.get("bpm", 0.0) or 0.0)
    _raw_min = float(parsed.get("bpm_min", _raw_bpm) or _raw_bpm)
    _raw_max = float(parsed.get("bpm_max", _raw_bpm) or _raw_bpm)
    _raw_common = float(parsed.get("bpm_common", _raw_bpm) or _raw_bpm)
    
    if primary_ok:
        merged = _merge_primary_and_mina(primary_core, mina)
        _primary_sr = float(primary_core.get("sr", 0.0) or 0.0) or None
        _family = str(primary_core.get("family", "") or "")
        merged["celestial"]  = _safe_celestial(mina, primary_sr=_primary_sr, family_hint=_family)
        merged["signicial"]  = _safe_signicial(mina, primary_sr=_primary_sr, family_hint=_family)
        merged["shoegazer"]  = _safe_shoegazer(mina, primary_sr=_primary_sr, family_hint=_family)

        # ── LN Course auto-route ──────────────────────────────────────
        _ln_route = str(domain.get("ln_route", "rice") or "rice")
        merged["ln_route"] = _ln_route
        if _ln_route == "ln":
            _ln_family = _classify_ln_family(features)
            merged["ln_course"] = _safe_ln_course(
                mina, primary_sr=_primary_sr,
                ln_family=_ln_family, features=features,
            )
        else:
            merged["ln_course"] = None

        # ── Map-level stats (from .osu file, rate-adjusted) ────────────
        merged["bpm"]        = round(_raw_bpm * _effective_bpm_rate, 1)
        merged["bpm_min"]    = int(round(_raw_min * _effective_bpm_rate))
        merged["bpm_max"]    = int(round(_raw_max * _effective_bpm_rate))
        merged["bpm_common"] = int(round(_raw_common * _effective_bpm_rate))
        merged["od"]  = round(float(parsed.get("od",  0.0) or 0.0), 1)

        # ── Strain graph for ui-3 real-time density display ──────────
        _sr_raw = primary_core.get("primary_sr") or {}
        merged["strain_graph"] = _sr_raw.get("strain_graph")

        return merged

    # Fallback: MinaCalc estimation (subprocess to msd.exe, 100-500ms)
    if isinstance(mina, dict):
        mina["error"] = None
    mina_ok = isinstance(mina, dict) and mina.get("dp") is not None
    if mina_ok:
        mina.setdefault("warnings", []).append("primary_sr_path_unavailable")
        mina["engine"] = "minacalc_fallback"
        mina["celestial"] = _safe_celestial(mina)  # no SR in fallback path
        mina["signicial"] = _safe_signicial(mina)  # no SR in fallback path
        mina["shoegazer"] = _safe_shoegazer(mina)  # no SR in fallback path
        mina["ln_route"]  = str(domain.get("ln_route", "rice") or "rice")
        mina["ln_course"] = None
        mina["bpm"]        = round(_raw_bpm * _effective_bpm_rate, 1)
        mina["bpm_min"]    = int(round(_raw_min * _effective_bpm_rate))
        mina["bpm_max"]    = int(round(_raw_max * _effective_bpm_rate))
        mina["bpm_common"] = int(round(_raw_common * _effective_bpm_rate))
        mina["od"]  = round(float(parsed.get("od",  0.0) or 0.0), 1)
        if mina["ln_route"] == "ln":
            _ln_family = _classify_ln_family(features)
            mina["ln_course"] = _safe_ln_course(
                mina, ln_family=_ln_family, features=features,
            )
        return mina

    return _error_payload(
        primary_core.get("error") if isinstance(primary_core, dict) else "analysis_unavailable",
        warnings=["minacalc_cli_or_config_missing", "primary_sr_path_failed"],
    )
