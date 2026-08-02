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
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "02_runtime_bridge"))
sys.path.insert(0, os.path.join(_ROOT, "07_model"))
sys.path.insert(0, os.path.join(_ROOT, "03_engine_reference", "sr_core"))

from minacalc_estimator import estimate as _minacalc_estimate
from celestial_estimator import estimate as _celestial_estimate
from signicial_estimator import estimate as _signicial_estimate
from shoegazer_estimator import estimate as _shoegazer_estimate
from ln_course_estimator import estimate as _ln_course_estimate


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
    import logging as _logging
    _log_sig = (mod, rate, round(rank.get("dp", 0.0), 2))
    if getattr(_compute_primary_rank_result, "_last_log_sig", None) != _log_sig:
        _compute_primary_rank_result._last_log_sig = _log_sig
        _logging.getLogger("danoverlay").warning(
            "pipeline DIAG: mod=%s rate=%s sr=%.4f dp=%.2f dan=%s sub=%s fam=%s conf=%.2f corr=%s",
            mod, rate, sr_result.get("sr", 0.0), rank.get("dp", 0.0),
            rank.get("dan_short", "?"), rank.get("sublevel", "?"),
            classification.get("family", "?"), classification.get("confidence", 0.0),
            rank.get("corrections", []),
        )

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
        "debug":          rank.get("debug", {}),
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


def analyze_map(osu_path, mod="NM", strict_domain=False, rate=None):
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

    Returns
    -------
    dict
        Structured analysis payload for the overlay.
    """
    # ── Custom-rate interpolation of the FINAL result ──────────────
    # The Sunny SR and MinaCalc MSD are interpolated natively, but the
    # final DP can still be non-monotonic because the MSD family override
    # re-routes the DP through a per-skillset ruler whose family flips
    # with the rate.  Computing the full result at the nearest native
    # rates and interpolating the final fields is monotonic by
    # construction and universal (4K, 7K, LN, all alternative modes).
    if rate is not None:
        _r = round(float(rate), 4)
        _NATIVE = (0.75, 1.0, 1.5)
        if _r not in _NATIVE:
            _lo, _hi = None, None
            if _r < _NATIVE[0]:
                _lo, _hi, _t = _NATIVE[0], _NATIVE[1], 0.0
            elif _r > _NATIVE[-1]:
                _lo, _hi = _NATIVE[-2], _NATIVE[-1]
                _t = 1.0 + (_r - _hi) / max(_hi - _lo, 1e-9)
            else:
                for i in range(len(_NATIVE) - 1):
                    if _NATIVE[i] <= _r <= _NATIVE[i + 1]:
                        _lo, _hi = _NATIVE[i], _NATIVE[i + 1]
                        break
                _t = (_r - _lo) / max(_hi - _lo, 1e-9)

            _res_lo = analyze_map(osu_path, mod=mod, strict_domain=strict_domain, rate=_lo)
            _res_hi = analyze_map(osu_path, mod=mod, strict_domain=strict_domain, rate=_hi)
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
                    _interp_result[_f] = round(_v_lo + _t * (_v_hi - _v_lo), 2)

                # Dan label/sublevel derived from interpolated DP
                _interp_result["dp"] = round(_res_lo.get("dp", 0.0) + _t * (_res_hi.get("dp", 0.0) - _res_lo.get("dp", 0.0)), 2)
                _label, _short = dp_to_label(_interp_result["dp"])
                _interp_result["dan_label"] = _label
                _interp_result["dan_short"] = _short
                _interp_result["sublevel"] = dp_to_sublevel(_interp_result["dp"])

                # Interpolate alternative-mode estimates (celestial etc.)
                for _mk in ("celestial", "signicial", "shoegazer", "ln_course"):
                    _m_lo = _res_lo.get(_mk)
                    _m_hi = _res_hi.get(_mk)
                    if isinstance(_m_lo, dict) and isinstance(_m_hi, dict):
                        _interp_result[_mk] = dict(_m_lo)
                        for _mf in ("dp_celestial", "dp_signicial", "dp_shoegazer", "dp_ln", "confidence"):
                            if _mf in _m_lo and _mf in _m_hi:
                                _a = float(_m_lo.get(_mf, 0.0) or 0.0)
                                _b = float(_m_hi.get(_mf, 0.0) or 0.0)
                                _interp_result[_mk][_mf] = round(_a + _t * (_b - _a), 2)

                _interp_result["custom_rate_interpolated"] = True
                return _interp_result

    return _analyze_map_impl(osu_path, mod=mod, strict_domain=strict_domain, rate=rate)


def _analyze_map_impl(osu_path, mod="NM", strict_domain=False, rate=None):
    """Core pipeline implementation (no custom-rate interpolation)."""
    from parser import parsear_osu_v2
    from validator import validate_domain
    from feature_extractor import extract_features

    # ── Parse .osu once (shared by both engines) ───────────────────
    try:
        parsed = parsear_osu_v2(osu_path, enforce_mode_mania=True)
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
            "error": None
        }

    features = extract_features(parsed)

    # ── Run MinaCalc + Primary SR in parallel ──────────────────────
    def _safe_mina():
        try:
            _MOD_RATE = {"HT": 0.75, "DT": 1.5, "NC": 1.5}
            effective_rate = rate if rate is not None else _MOD_RATE.get(mod, 1.0)
            return _minacalc_estimate(osu_path, rate=effective_rate, features=features)
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        mina_future = pool.submit(_safe_mina)
        primary_future = pool.submit(
            _compute_primary_rank_result,
            osu_path, mod, strict_domain, None,
            parsed=parsed, domain=domain, features=features, rate=rate,
        )
        primary_core = primary_future.result()
        mina = mina_future.result()

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
        import logging as _logging
        _m_sig = (mod, rate, round(merged.get("dp", 0.0), 2))
        if getattr(analyze_map, "_last_merge_log", None) != _m_sig:
            analyze_map._last_merge_log = _m_sig
            _logging.getLogger("danoverlay").warning(
                "pipeline MERGE-DIAG: mod=%s rate=%s primary_dp=%.2f primary_dan=%s -> merged_dp=%.2f merged_dan=%s sub=%s fam=%s corr=%s msd_override=%s",
                mod, rate,
                primary_core.get("dp", 0.0), primary_core.get("dan_short", "?"),
                merged.get("dp", 0.0), merged.get("dan_short", "?"),
                merged.get("sublevel", "?"), merged.get("family", "?"),
                merged.get("corrections", []),
                (merged.get("debug") or {}).get("msd_family_override"),
            )
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
