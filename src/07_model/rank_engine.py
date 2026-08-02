# rank_engine.py -- Ranking engine v3: SR -> DP -> Dan label
#
# Architecture v3 (2026-06): Per-skillset SR means + linear interpolation
#   SR from the main engine + skillset detection (from family classifier)
#   -> select per-skillset SR ruler -> boundary interpolation -> DP -> label
#
# Calibration data (SR means per Dan) is loaded from config/sr_means.json.
# See that file for metadata (n_maps, calibration date, method).

import json
import math
import os

from resource_path import resource_path

# ── Dan ordering (20 dans: 1st-10th + Alpha-Kappa) ──────────────────

_DAN_ORDER = [
    "1st", "2nd", "3rd", "4th", "5th",
    "6th", "7th", "8th", "9th", "10th",
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
    "Zeta", "Eta", "Theta", "Iota", "Kappa",
]

_DAN_DISPLAY = {
    "1st": "1st Dan", "2nd": "2nd Dan", "3rd": "3rd Dan",
    "4th": "4th Dan", "5th": "5th Dan", "6th": "6th Dan",
    "7th": "7th Dan", "8th": "8th Dan", "9th": "9th Dan",
    "10th": "10th Dan",
    "Alpha": "Alpha", "Beta": "Beta", "Gamma": "Gamma",
    "Delta": "Delta", "Epsilon": "Epsilon",
    "Zeta": "Zeta", "Eta": "Eta", "Theta": "Theta",
    "Iota": "Iota", "Kappa": "Kappa",
}

# ── SR means per dan (loaded from config/sr_means.json) ─────────────

def _load_sr_means():
    """Load SR means from config/sr_means.json.

    Returns (general_means, skillset_means) where:
        general_means: dict[str, float] — 20 dans
        skillset_means: dict[str, dict[str, float]] — 4 families × 20 dans
    """
    path = os.path.join(resource_path("config"), "sr_means.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["general"], data["skillsets"]

_GENERAL_SR_MEANS, _SKILLSET_SR_MEANS = _load_sr_means()

# ── Sublevel tiers ───────────────────────────────────────────────────
# Ranges are inclusive at the upper bound: 0-20, 21-40, 41-60, 61-80, 81-99
# so a DP ending in .40 is unambiguously Mid-Low (never 50/50 with Mid).

_SUBLEVEL_LABELS = [
    (0.00, 0.20, "Low"),
    (0.20, 0.40, "Mid-Low"),
    (0.40, 0.60, "Mid"),
    (0.60, 0.80, "Mid-High"),
    (0.80, 1.00, "High"),
]

# ── LN confidence multipliers ────────────────────────────────────────

_LN_CONFIDENCE_MULT = {
    "high": 1.0,
    "degraded": 0.75,
    "gray": 0.45,
    "out_of_domain": 0.15,
}

# ── Ruler cache ──────────────────────────────────────────────────────

_ruler_cache = {}


def _get_ruler(skillset=None):
    """Get the SR->DP ruler for a given skillset.

    Returns list of (sr_mean, dp_int) sorted by dp.
    Uses per-skillset means for Alpha-Epsilon when available,
    falls back to General means for all other dans.
    """
    cache_key = skillset or "__general__"
    if cache_key in _ruler_cache:
        return _ruler_cache[cache_key]

    overrides = _SKILLSET_SR_MEANS.get(skillset, {}) if skillset else {}

    table = []
    for i, dan_name in enumerate(_DAN_ORDER):
        dp = i + 1
        sr = overrides.get(dan_name, _GENERAL_SR_MEANS[dan_name])
        table.append((sr, dp))

    # Enforce strict monotonicity
    for i in range(1, len(table)):
        if table[i][0] <= table[i - 1][0]:
            table[i] = (table[i - 1][0] + 0.01, table[i][1])

    _ruler_cache[cache_key] = table
    return table


def _precompute_boundaries(ruler):
    """Compute midpoint boundaries between adjacent dan means.

    Each dan occupies the SR range from the midpoint to its lower neighbor
    to the midpoint to its upper neighbor (Daniel's boundary approach).

    Returns list of (lower_sr, upper_sr, dp_int).
    """
    means = [sr for sr, dp in ruler]
    n = len(means)
    boundaries = []

    for i in range(n):
        if i > 0:
            lower = (means[i - 1] + means[i]) / 2.0
        else:
            gap = means[1] - means[0] if n > 1 else 1.0
            lower = means[0] - gap / 2.0

        if i < n - 1:
            upper = (means[i] + means[i + 1]) / 2.0
        else:
            gap = means[-1] - means[-2] if n > 1 else 1.0
            upper = means[-1] + gap / 2.0

        boundaries.append((lower, upper, ruler[i][1]))

    return boundaries


# ── Core: SR -> DP ───────────────────────────────────────────────────

def sr_to_dp(sr, skillset=None):
    """Convert SR to DP using per-skillset ruler + linear interpolation.

    This is the core of the v3 ranking system, replacing KNN + Phi.
    Within each dan's boundary zone, the fractional part maps linearly
    from 0.0 (at lower boundary) to 1.0 (at upper boundary), giving a
    continuous DP value that naturally yields sub-tiers.

    Parameters
    ----------
    sr : float
        Star Rating from the primary SR path.
    skillset : str or None
        "jack", "speed", "stamina", "tech", or None for general ruler.

    Returns
    -------
    float : DP on 1-20 scale, clamped to [0.5, 20.5].
    """
    ruler = _get_ruler(skillset)
    boundaries = _precompute_boundaries(ruler)

    # Below first boundary
    if sr < boundaries[0][0]:
        return max(0.5, float(boundaries[0][2]))

    # Above last boundary
    if sr >= boundaries[-1][1]:
        return min(20.99, float(boundaries[-1][2]) + 0.99)

    # Find which boundary the SR falls in
    for lower, upper, dp_int in boundaries:
        if lower <= sr < upper:
            t = (sr - lower) / max(upper - lower, 1e-6)
            return float(dp_int) + t
    return float(boundaries[-1][2])


# ── DP -> Labels ─────────────────────────────────────────────────────

def dp_to_label(dp):
    """Dan label from DP value. Returns (display_label, short_label)."""
    idx = max(0, min(len(_DAN_ORDER) - 1, int(dp) - 1))
    short = _DAN_ORDER[idx]
    return _DAN_DISPLAY.get(short, short), short


def dp_to_sublevel(dp):
    """Sublevel string (Low, Mid-Low, Mid, Mid-High, High) from DP fraction."""
    frac = round(dp - math.floor(dp), 2) if dp >= 1 else 0.0
    # Inclusive upper bound: frac <= hi (0.20 -> Low, 0.40 -> Mid-Low, ...).
    # frac rounded to 2 decimals to avoid float drift (1.60 - 1 = 0.6000000000000001).
    for lo, hi, label in _SUBLEVEL_LABELS:
        if lo <= frac <= hi:
            return label
    return "High"


def _jack_peak_bonus(sr_result, family):
    """Compensate peak-heavy jack charts that raw Sunny SR compresses.

    The raw SR scalar is dominated by sustained percentiles and can underrate
    charts with very large same-column pressure spikes. Official Zeta jack maps
    such as Vertex Beta fall into that bucket: they show Zeta-level Jbar peaks
    but land below the Epsilon/Zeta boundary on raw SR alone.

    We keep the raw Sunny SR untouched and add a small ranking-only bonus when
    the chart is already classified as jack and its Jbar peak exceeds the
    measured Epsilon ceiling by a meaningful margin.
    """
    if family != "jack":
        return 0.0

    # Marathon maps (6000+ notes) are hybrid, not pure jack.
    # Their high jbar comes from duration, not concentrated column pressure.
    # Skip the bonus for marathon-length maps to prevent over-ranking.
    # total_notes_eff = len(D_graph): Vertex Beta=6624, Las Avispas=9458,
    # marathons=26232-69746.  Threshold 15000 gives 1.6x margin.
    total_notes = float(sr_result.get("total_notes_eff", 0) or 0)
    if total_notes > 15000:
        return 0.0

    jbar_max = float(sr_result.get("jbar_max", 0.0) or 0.0)
    sr_val = float(sr_result.get("sr", 0.0) or 0.0)

    # The SR algorithm compresses pure jack maps (e.g., Vertex Beta or Las Avispas).
    # This compression depends on the map's tier. We scale the bonus start (peak_start)
    # and intensity (peak_scale) based on raw SR to handle all tiers properly.
    # ── 2026-05 recalibration: lowered peaks because jack ruler means were
    # recalibrated downward from official DDMythical medians, reducing the
    # per-dan gap.  The old bonus targets were calibrated for wider gaps.
    if sr_val >= 11.0:
        peak_start = 64.5
        peak_scale = 0.031
        peak_cap = 0.35 if sr_val < 12.0 else 0.20
    elif sr_val >= 9.0:
        # ── 2026-05 recalibration for Zeta tier: lowered peak_start from 64.5
        # to 58.0 because official Zeta maps with moderate jack pressure
        # (Jbar 55-69) were falling 1-2 Dans below their labels.  Emik and
        # GBThaumiel both independently confirmed this gap.  peak_scale lowered
        # to 0.020 and cap to 0.25 to avoid over-correcting non-jack Zeta maps.
        peak_start = 58.0
        peak_scale = 0.020
        peak_cap = 0.25
    elif sr_val >= 7.0:
        peak_start = 50.0
        peak_scale = 0.020
        peak_cap = 0.30
    else:
        peak_start = 48.0
        peak_scale = 0.015
        peak_cap = 0.20

    return min(peak_cap, max(0.0, jbar_max - peak_start) * peak_scale)


# ── MSD-based family detection ───────────────────────────────────────
#
# MinaCalc's per-skillset MSD values are more reliable than Sunny internals
# for identifying chart family — especially for the jack/stamina distinction
# where the Sunny-based classifier frequently mislabels maps.
#
# Individual skillsets are compressed with the same 4-role logic used by the
# MinaCalc estimator itself:
#   jack    = max(jackspeed, chordjack)
#   speed   = max(stream, jumpstream)
#   stamina = 0.7 * stamina + 0.3 * handstream
#   tech    = technical
#
# The dominant group then overrides the Sunny-derived family used to select
# the per-skillset SR ruler in compute_rank().


def _msd_to_family(msd_dict, sunny_family=None):
    """Derive chart family from MinaCalc skillset MSD values.

    Compresses the 7 raw skillsets into the same 4 role scores used by the
    MinaCalc estimator and returns the dominant family, or None when the signal
    is too ambiguous to override the Sunny-based classifier.

    Decision rule:
        - Generic case: require a clearly dominant role.
        - Known ambiguity pairs get targeted tie-breaks:
                * jack ↔ stamina
                * stream → speed
                * hybrid → dominant role
        - Tech override is only allowed when the technical role clearly beats the
            role that Sunny picked; this avoids tech maps being swallowed by mixed
            stamina/stream sums while still rescuing obvious false jack calls.
    """
    if not msd_dict:
        return None

    groups = {
        "jack": max(
            float(msd_dict.get("jackspeed", 0.0) or 0.0),
            float(msd_dict.get("chordjack", 0.0) or 0.0),
        ),
        "speed": max(
            float(msd_dict.get("stream", 0.0) or 0.0),
            float(msd_dict.get("jumpstream", 0.0) or 0.0),
        ),
        "stamina": (
            0.7 * float(msd_dict.get("stamina", 0.0) or 0.0)
            + 0.3 * float(msd_dict.get("handstream", 0.0) or 0.0)
        ),
        "tech": float(msd_dict.get("technical", 0.0) or 0.0),
    }
    groups = {fam: val for fam, val in groups.items() if val > 0.0}

    if not groups:
        return None

    total = sum(groups.values())
    if total < 1.0:
        return None

    ranked = sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
    top_fam, top_val = ranked[0]
    second_fam = ranked[1][0] if len(ranked) > 1 else None
    second_val = ranked[1][1] if len(ranked) > 1 else 0.0

    dominance = top_val / total                              # share of total
    margin_ratio = (top_val - second_val) / top_val         # relative lead
    sunny_role = "speed" if sunny_family == "stream" else sunny_family
    sunny_val = float(groups.get(sunny_role, 0.0) or 0.0)

    # Reject pure hybrids — no single family stands out
    if dominance < 0.26:
        return None

    # Hybrid / unknown: let MSD choose the role if there is any decent lead.
    if sunny_family in (None, "", "hybrid") and (dominance >= 0.30 or margin_ratio >= 0.04):
        return top_fam

    # Soft signal for the main confusion pair the user called out.
    if sunny_family in ("jack", "stamina") and top_fam in ("jack", "stamina") and margin_ratio >= 0.02:
        return top_fam

    # Sunny's generic stream bucket can be sharpened into speed when MSD agrees.
    if sunny_family == "stream" and top_fam == "speed" and margin_ratio >= 0.01:
        return top_fam

    # Rescue obvious false jack / stamina / stream calls when the technical role
    # is clearly ahead of what Sunny selected.
    if top_fam == "tech" and sunny_family not in (None, "", "hybrid", "tech"):
        if sunny_val > 0.0 and top_val >= sunny_val * 1.20:
            return top_fam

    # When Sunny said tech but MSD's top family is jack, apply the same
    # soft-pair logic used for jack↔stamina.  Speedjacks / chordjacks are
    # systematically misread as chaos_tech by the feature classifier.
    if sunny_family == "tech" and top_fam == "jack" and margin_ratio >= 0.02:
        return top_fam

    # Generic strong signal: only use when the lead is genuinely clear.
    if dominance >= 0.34 and margin_ratio >= 0.08:
        return top_fam

    return None


def recompute_dp_for_family(sr, sr_result_for_bonus, family):
    """Recompute DP and labels using a given family (for MSD-based overrides).

    Parameters
    ----------
    sr : float
        Raw SR from the primary engine (before any bonus).
    sr_result_for_bonus : dict
        sr_result dict — needs ``jbar_max`` for the jack peak bonus.
    family : str
        Overriding family name.

    Returns
    -------
    dict with dp, dan_label, dan_short, sublevel, family, ranking_sr.
    """
    _F2S = {
        "jack": "jack", "speed": "speed",
        "stamina": "stamina", "tech": "tech",
        # Stream charts should use the speed ruler, not the generic ruler.
        "stream": "speed", "hybrid": None,
    }
    skillset = _F2S.get(family)
    jack_bonus = _jack_peak_bonus(sr_result_for_bonus or {}, family)
    ranking_sr = sr + jack_bonus
    dp = round(sr_to_dp(ranking_sr, skillset=skillset), 2)
    label, short = dp_to_label(dp)
    sublevel = dp_to_sublevel(dp)
    return {
        "dp": dp,
        "dan_label": label,
        "dan_short": short,
        "sublevel": sublevel,
        "beyond": dp > 20.5,
        "family": family,
        "ranking_sr": round(ranking_sr, 4),
    }


# ── Main ranking function ────────────────────────────────────────────

def compute_rank(sr_result, features, classification, domain_info, msd=None):
    """Compute final ranking: SR -> DP -> label.

    Uses per-skillset SR rulers when the family classifier identifies
    a dominant skillset, otherwise falls back to the general ruler.

    Parameters
    ----------
    sr_result : dict
        Output from the SR bridge — must contain 'sr'.
    features : dict
        Extracted chart features.
    classification : dict
        classify_family() output — family, confidence, scores.
    domain_info : dict
        validate_domain() output.
    msd : dict, optional
        MinaCalc skillset data (reserved for future use).

    Returns
    -------
    dict with dp, dan_label, dan_short, sublevel, confidence, sr, family,
    corrections, debug.
    """
    sr = float(sr_result.get("sr", 0.0) or 0.0)
    family = classification.get("family", "hybrid")
    family_confidence = float(classification.get("confidence", 0.0))

    # Map family to per-skillset ruler key
    _FAMILY_TO_SKILLSET = {
        "jack": "jack",
        "speed": "speed",
        "stamina": "stamina",
        "tech": "tech",
        # Stream is speed-biased and calibrates better with the speed ruler.
        "stream": "speed",
        "hybrid": None,
    }
    # ── Confidence gate: only use per-skillset ruler when the
    # classifier is sufficiently confident.  Low-confidence family
    # assignments default to the general ruler, which is calibrated
    # from official DDMythical medians and avoids the per-skillset
    # mean inflation that affects some tiers.
    if family_confidence >= 0.50:
        skillset = _FAMILY_TO_SKILLSET.get(family)
    else:
        skillset = None

    # ── Speedjack / Peak-jack universal rescue ───────────────────────────────
    # Speedjack charts (same-column notes alternating across columns at high BPM)
    # are systematically underrated by the SR algorithm because Jbar pressure is
    # split per-column.  The physical fingerprint is objective:
    #
    #   jbar_max >= 70   : Epsilon jack maps top out ~56; only Zeta+ peak-jacks
    #                       reach this zone regardless of classifier output.
    #
    #   jbar_share >= 0.55 : Jbar must strongly dominate the component budget.
    #                        Marathon maps accumulate high jbar over long durations
    #                        but their jbar_share stays moderate (0.43-0.53) because
    #                        sustained pressing (pbar) is also high.  A 0.55 threshold
    #                        cleanly separates true speedjacks from long stamina maps.
    #
    #   pbar_max < 55     : True speedjacks have LOW distributed pressing because
    #                        their demand is concentrated in jack bursts, not sustained.
    #                        Marathons have pbar > 50 from continuous play.
    #
    # When ALL THREE conditions hold, the chart IS a speedjack and MUST use the jack
    # ruler with full peak compensation.  This fires before the jack_peak_bonus
    # so the stronger two-stage correction always wins over the base bonus.
    #
    # Two-stage correction (same as the pipeline.py tech→jack path):
    #   stage 1 – _jack_peak_bonus  (same-column peak compression, ≤0.55)
    #   stage 2 – supplemental extra (ruler-mismatch underestimation, ≤0.65)
    _SJ_JBAR_FLOOR  = 70.0
    _SJ_SHARE_FLOOR  = 0.55
    _SJ_PBAR_CEIL    = 55.0
    _sj_jbar  = float(sr_result.get("jbar_max",   0.0) or 0.0)
    _sj_share = float(sr_result.get("jbar_share",  0.0) or 0.0)
    _sj_pbar  = float(sr_result.get("pbar_max",    0.0) or 0.0)
    _is_speedjack = (_sj_jbar >= _SJ_JBAR_FLOOR and _sj_share >= _SJ_SHARE_FLOOR and _sj_pbar < _SJ_PBAR_CEIL and sr < 10.5)

    corrections = []
    jack_bonus = 0.0
    stamina_bonus = 0.0

    if _is_speedjack:
        # Force jack ruler path — classifier-independent
        jack_bonus = _jack_peak_bonus(sr_result, "jack")       # stage 1 (same-column)
        _sj_extra  = min(0.65, max(0.0, _sj_jbar - 72.0) * 0.060) # stage 2 (ruler-mismatch)
        _sj_total  = jack_bonus + _sj_extra
        ranking_sr = sr + _sj_total
        dp = sr_to_dp(ranking_sr, skillset="jack")
        skillset = "jack"
        corrections.append(f"speedjack_rescue:+{round(_sj_total, 3)}")
    else:
        # Normal path: per-family peak bonus
        jack_bonus = _jack_peak_bonus(sr_result, family)
        
        # Stamina high-BPM rescue
        bpm = float((domain_info or {}).get("bpm", (features or {}).get("bpm", 0.0)) or 0.0)
        drain_s = float((domain_info or {}).get("drain_time_s", 0.0) or 0.0)

        if family == "stamina" and bpm >= 240.0 and drain_s >= 120.0:
            # High speed stamina maps (like Lazorbeamz) are systematically underrated
            # by the Sunny algorithm when they have sustained single-note streams
            # at high BPM. Marathon/survival maps with varied chord patterns and
            # high density variation are CORRECTLY rated by the general formula —
            # their high BPM doesn't indicate SR underestimation.
            #
            # Gate 1: Stream purity — sustained single-note stream dominance.
            #   Lazorbeamz has ~0.55; EXTRA-GAMMA marathon has ~0.35.
            # Gate 2: Chord fraction — chords inflate cross-column pressure (Xbar).
            #   Lazorbeamz has ~0.25; EXTRA-GAMMA has ~0.45. Low chord = SR hole.
            # Gate 3: Density CV — high variation means the algorithm catches the
            #   difficulty spikes. Consistent stream maps have low CV and slip through.
            #   Lazorbeamz has ~0.25 (consistent); EXTRA-GAMMA has ~0.40 (varied).
            _sp = float(features.get("stream_purity", 0.0) or 0.0)
            _jr = float(features.get("jump_ratio", 0.0) or 0.0)
            _hr = float(features.get("hand_ratio", 0.0) or 0.0)
            _qr = float(features.get("quad_ratio", 0.0) or 0.0)
            _chord = _jr + _hr + _qr
            _dcv = float(features.get("density_cv", 0.0) or 0.0)
            
            if _sp >= 0.40 and _chord <= 0.40 and _dcv <= 0.30:
                stamina_bonus = min(0.20, (bpm - 240.0) * 0.005)
                
                # Boundary-aware ceiling: if the bonus would push the result across
                # more than one tier boundary, reduce it. Single-tier crossings are
                # expected for genuinely underrated maps (e.g. Lazorbeamz: 10th→Alpha).
                # Two-tier jumps indicate the rescue is over-correcting.
                _dp_no = sr_to_dp(sr + jack_bonus, skillset=skillset)
                for _ in range(3):
                    _dp_yes = sr_to_dp(sr + jack_bonus + stamina_bonus, skillset=skillset)
                    if int(_dp_yes) - int(_dp_no) >= 2:
                        stamina_bonus = round(stamina_bonus * 0.5, 4)
                    else:
                        break

        ranking_sr = sr + jack_bonus + stamina_bonus
        if jack_bonus > 0.0:
            corrections.append(f"jack_peak_bonus:+{jack_bonus:.3f}")
        if stamina_bonus > 0.0:
            corrections.append(f"stamina_rescue:+{stamina_bonus:.3f}")
            
        dp = sr_to_dp(ranking_sr, skillset=skillset)

    # Confidence
    note_count = int((domain_info or {}).get("note_count", 0))
    note_confidence = min(1.0, note_count / 200.0)
    ln_confidence = (domain_info or {}).get("ln_confidence", "high")
    ln_mult = _LN_CONFIDENCE_MULT.get(ln_confidence, 1.0)

    overall_confidence = family_confidence * ln_mult * note_confidence
    overall_confidence = round(min(1.0, overall_confidence), 3)

    # Labels
    dp = round(dp, 2)
    dan_label, dan_short = dp_to_label(dp)
    sublevel = dp_to_sublevel(dp)

    debug = {
        "sr": round(sr, 4),
        "ranking_sr": round(ranking_sr, 4),
        "jack_peak_bonus": round(jack_bonus, 4),
        "stamina_rescue_bonus": round(stamina_bonus, 4),

        "skillset_ruler": skillset or "general",
        "family": family,
        "family_confidence": round(family_confidence, 3),
        "ln_confidence": ln_confidence,
        "ln_multiplier": ln_mult,
        "note_confidence": round(note_confidence, 3),
        "formula_version": 3,
    }

    return {
        "dp": dp,
        "dan_label": dan_label,
        "dan_short": dan_short,
        "sublevel": sublevel,
        "beyond": dp > 20.5,
        "confidence": overall_confidence,
        "sr": round(sr, 4),
        "family": family,
        "corrections": corrections,
        "debug": debug,
    }


def reload_config():
    """Reload SR means from JSON and clear ruler cache.

    Call this after re-running calibration to pick up new sr_means.json
    values without restarting the overlay session.
    """
    global _GENERAL_SR_MEANS, _SKILLSET_SR_MEANS
    _GENERAL_SR_MEANS, _SKILLSET_SR_MEANS = _load_sr_means()
    _ruler_cache.clear()
