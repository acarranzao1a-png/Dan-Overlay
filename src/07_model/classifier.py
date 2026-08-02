# classifier.py -- Chart family detection using Sunny internals + features
# Familias: stream, jack, tech, speed, stamina, hybrid
# Does not use MSD — only Sunny components + structural features

import json
import os
import sys

from resource_path import resource_path

_CONFIG_DIR = resource_path("config")

_HYBRID_STREAM_THRESHOLD = 0.85
_HYBRID_JACK_THRESHOLD = 0.10
_HYBRID_CV_THRESHOLD = 0.30
_HYBRID_XBAR_THRESHOLD = 0.30
_HYBRID_COEFF = 0.025
_HYBRID_MIN = 0.97
_HYBRID_MAX = 1.10


def _load_family_profiles():
    path = os.path.join(_CONFIG_DIR, "family_profiles.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _clamp(value, low, high):
    return max(low, min(high, value))


def _tech_hybrid_factor(stream_purity, jack_density, density_cv, xbar_max_norm):
    """Small multiplicative bonus for mixed-tech patterns.

    Kept local so family classification no longer depends on the old legacy
    helper module.
    """
    stream_excess = max(0.0, stream_purity - _HYBRID_STREAM_THRESHOLD)
    jack_excess = max(0.0, jack_density - _HYBRID_JACK_THRESHOLD)
    cv_signal = max(0.0, density_cv - _HYBRID_CV_THRESHOLD)
    xbar_signal = max(0.0, xbar_max_norm - _HYBRID_XBAR_THRESHOLD)

    hybrid_signal = (
        stream_excess * 1.5
        + jack_excess * 2.0
        + cv_signal * 1.2
        + xbar_signal * 1.0
    )
    factor = 1.0 + _HYBRID_COEFF * hybrid_signal
    return max(_HYBRID_MIN, min(_HYBRID_MAX, factor))


def _classify_tech_subtype(features, sunny_result, profiles_cfg):
    """Recover a lightweight tech subtype split inspired by the legacy project.

    The old project differentiated chaos/control/hybrid tech. We do not have the
    full legacy strain skillsets here, so this uses current structural proxies.
    """
    subtype_cfg = (profiles_cfg or {}).get("tech_subtypes", {})

    transition_var = float(features.get("transition_var", 0.0) or 0.0)
    density_cv = float(features.get("density_cv", 0.0) or 0.0)
    jump_ratio = float(features.get("jump_ratio", 0.0) or 0.0)
    hand_ratio = float(features.get("hand_ratio", 0.0) or 0.0)
    anchor_ratio = float(features.get("anchor_ratio", 0.0) or 0.0)
    chord_complexity = float(features.get("chord_complexity", 0.0) or 0.0)
    nps_active_cv = float(features.get("nps_active_cv", 0.0) or 0.0)
    stream_purity = float(features.get("stream_purity", 0.0) or 0.0)

    jbar_max = float(sunny_result.get("jbar_max", 0.0) or 0.0)
    pbar_max = float(sunny_result.get("pbar_max", 0.0) or 0.0)
    xbar_max = float(sunny_result.get("xbar_max", 0.0) or 0.0)
    bar_total = jbar_max + pbar_max + 1.0
    tech_dom = xbar_max / (xbar_max + bar_total) if (xbar_max + bar_total) > 0 else 0.0

    chaos_floor = float(subtype_cfg.get("chaos_transition_floor", 0.38))
    control_hand_floor = float(subtype_cfg.get("control_hand_floor", 0.10))
    control_chord_floor = float(subtype_cfg.get("control_chord_floor", 0.18))

    chaos_score = (
        transition_var * 42.0
        + density_cv * 26.0
        + nps_active_cv * 20.0
        + tech_dom * 18.0
        - anchor_ratio * 10.0
    )
    control_score = (
        hand_ratio * 45.0
        + jump_ratio * 10.0
        + chord_complexity * 12.0
        + tech_dom * 15.0
        + max(0.0, 1.0 - density_cv) * 8.0
        + anchor_ratio * 6.0
    )
    hybrid_score = (
        tech_dom * 22.0
        + jump_ratio * 14.0
        + density_cv * 10.0
        + transition_var * 10.0
        + max(0.0, 0.9 - abs(stream_purity - 0.45)) * 5.0
    )

    ranked = sorted(
        {
            "chaos_tech": chaos_score,
            "control_tech": control_score,
            "hybrid_tech": hybrid_score,
        }.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )
    subtype = ranked[0][0]
    top_score = ranked[0][1]
    second_score = ranked[1][1]
    total = max(sum(score for _, score in ranked), 1e-9)
    confidence = _clamp((top_score - second_score) / max(total * 0.18, 1.0), 0.15, 1.0)

    # Legacy-inspired guardrails so subtype labels do not fire too loosely.
    if subtype == "chaos_tech" and transition_var < chaos_floor:
        subtype = "hybrid_tech"
        confidence = min(confidence, 0.45)
    elif subtype == "control_tech" and hand_ratio < control_hand_floor and chord_complexity < control_chord_floor:
        subtype = "hybrid_tech"
        confidence = min(confidence, 0.45)

    return {
        "subtype": subtype,
        "confidence": round(confidence, 3),
        "scores": {name: round(score, 2) for name, score in ranked},
    }


def classify_family(sunny_result, features, domain_info=None):
    """Classifies the chart family based on Sunny internals + features.

    Parameters
    ----------
    sunny_result : dict
        Output from sunny_analyze() — sr, jack_ratio, jbar_max, pbar_max, etc.
    features : dict
        Extracted features — chord density, jack_density, stream_purity,
        density_cv, transition_var, nps stats, etc.
    domain_info : dict, optional
        Output from validate_domain() — bpm, drain_time_s, etc.

    Returns
    -------
    dict containing:
        family      : str — "stream"|"jack"|"tech"|"speed"|"stamina"|"hybrid"
        confidence  : float — 0-1 confidence score
        scores      : dict — score per family
        reason      : str — short reason string
    """
    profiles_cfg = _load_family_profiles()
    get_s = lambda k, d=0.0: float(sunny_result.get(k, d) or d)
    get_f = lambda k, d=0.0: float(features.get(k, d) or d)
    get_d = lambda k, d=0.0: float((domain_info or {}).get(k, d) or d)

    bpm = get_d("bpm", get_f("bpm", 0.0))
    drain_s = get_d("drain_time_s", get_f("duration_s", 0.0))

    # Sunny internals
    jack_ratio = get_s("jack_ratio")
    jbar_max = get_s("jbar_max")
    pbar_max = get_s("pbar_max")
    xbar_max = get_s("xbar_max")
    abar_mean = get_s("abar_mean")
    d93 = get_s("d93")
    d83 = get_s("d83")
    d_weighted_mean = get_s("d_weighted_mean")
    sr = get_s("sr")

    # Bar dominance ratios — Sunny bars are the most reliable family signals
    bar_total = jbar_max + pbar_max + 1.0
    jack_dom = jbar_max / bar_total           # 0-1: jack pressure dominance (Jbar > Pbar → jack)
    stream_dom = pbar_max / bar_total         # 0-1: stream pressure dominance
    tech_dom = xbar_max / (xbar_max + bar_total) if (xbar_max + bar_total) > 0 else 0.0
    peak_ratio = d93 / max(d83, 0.01) if d83 > 0.1 else 1.0  # burst vs sustained

    # Feature stats
    stream_purity = get_f("stream_purity")   # fraction of single-note rows; HIGH for both jack AND stream
    jack_ratio_broad = get_f("jack_ratio", 0.0)                      # same-col hits ≤180ms (broad)
    jack_density = get_f("jack_density", jack_ratio_broad)           # same-col hits ≤120ms (strict)
    vibro_density = get_f("vibro_density", get_f("vibro_ratio", 0.0))
    density_cv = min(2.0, get_f("density_cv"))   # cap to prevent degenerate charts blowing up tech score
    transition_var = get_f("transition_var")
    jump_ratio = get_f("jump_ratio")
    hand_ratio = get_f("hand_ratio")
    quad_ratio = get_f("quad_ratio")

    # NPS profile stats
    nps_p90 = get_f("nps_p90")
    nps_sustained = get_f("nps_sustained_top30")
    nps_active_ratio = get_f("nps_active_ratio")
    nps_active_cv = get_f("nps_active_cv")

    # ─── Derived signals ────────────────────────────────────────────────────
    chord_fraction = jump_ratio + hand_ratio + quad_ratio
    anchor_ratio = get_f("anchor_ratio", 0.0)
    pattern_irregularity = get_f("pattern_irregularity", 0.0)
    timing_irregularity = get_f("timing_irregularity", 0.0)

    # Repetitiveness via transition_var (mean Jaccard distance between rows).
    # Jack/chordjack maps: tv < 0.83 (repetitive column patterns).
    # Non-jack maps: tv > 0.85 (diverse column transitions).
    # Steeper curve: 1.0 at tv ≤ 0.705, 0 at tv ≥ 0.83.
    rep_margin = max(0.0, 0.83 - transition_var)
    is_repetitive = min(1.0, rep_margin * 12.0)  # steeper: 1.0@tv≤0.747, 0@tv≥0.83

    # BPM-aware jack excess (broad jack_ratio minus expected baseline)
    if bpm > 0:
        quarter_ms = 60000.0 / bpm
        jack_baseline = min(0.9, max(0.0, 1.0 - quarter_ms / 250.0))
    else:
        jack_baseline = 0.3
    jack_excess = max(0.0, jack_ratio_broad - jack_baseline)

    # BPM signal for speed (capped to prevent extreme BPM dominance)
    bpm_signal = min(1.5, max(0.0, bpm - 140.0) / 80.0)

    # --- Score computation per family ---

    # ─── Jack ────────────────────────────────────────────────────────────────
    # Chordjack: repetitive patterns + chords + jack_density.
    # Key signal: is_repetitive (low transition_var).
    # chord_fraction is a POSITIVE jack signal — chordjacks have lots of chords.
    jack_score = (
        is_repetitive * 50.0                    # repetitive = jack/chordjack
        + jack_density * 45.0                   # strict ≤120ms
        + chord_fraction * 20.0                 # chordjacks HAVE chords
        + jack_excess * 15.0                    # BPM-normalized broad excess
        + vibro_density * 20.0                  # vibro is extreme jack
        + anchor_ratio * 15.0                   # column anchoring
        + jack_dom * 10.0                       # Sunny Jbar
    )

    # ─── Stream ──────────────────────────────────────────────────────────────
    # Pure streams: high stream_purity, minimal chords, regular density.
    stream_score = (
        stream_purity * 45.0                    # single-note dominant
        + max(0.0, 1.0 - chord_fraction * 3.0) * 15.0  # penalize chords
        - chord_fraction * 12.0                 # direct chord anti-signal
        + stream_dom * 20.0                     # Pbar from Sunny
        + max(0.0, 1.0 - density_cv) * 15.0    # regular density
        + max(0.0, 0.5 - jack_density) * 10.0  # not jack-like
    )

    # ─── Tech ────────────────────────────────────────────────────────────────
    # Tech = dumpstream, speedjacks, irregular patterns.
    # HIGH density_cv is THE signal. Pattern diversity + entropy variation.
    tech_score = (
        density_cv * 55.0                       # irregular density = primary tech signal
        + pattern_irregularity * 25.0           # entropy variation across windows
        + nps_active_cv * 20.0                  # NPS variation in active sections
        + tech_dom * 20.0                       # Xbar from Sunny
        + transition_var * 12.0                 # diverse patterns (not repetitive)
        + chord_fraction * 8.0                  # some mixed chord content
    )

    # ─── Speed ───────────────────────────────────────────────────────────────
    # Speed = fast regular streams (singles). Anti-chord, anti-irregular.
    # Multiplicative gates prevent speed from winning on chord-heavy or
    # density-irregular maps (those are stamina or tech respectively).
    speed_raw = (
        bpm_signal * 42.0                       # BPM is primary speed signal
        + stream_purity * 22.0                  # stream-like singles
        + max(0.0, 1.0 - density_cv) * 10.0    # regular density
        + max(0.0, peak_ratio - 1.02) * 12.0   # burst peaks
    )
    speed_chord_gate = max(0.25, 1.0 - chord_fraction * 1.8)   # 1.0@0%, 0.25@42%+
    speed_regularity = max(0.5, 1.0 - max(0.0, density_cv - 0.30) * 2.5)  # penalize high dcv
    speed_score = speed_raw * speed_chord_gate * speed_regularity

    # ─── Stamina ─────────────────────────────────────────────────────────────
    # Stamina = jumpstream/handstream/quadstream over LONG drain.
    # Requires: meaningful chord content + meaningful drain time.
    # Anti-signals: high stream_purity (that's speed/stream, not stamina),
    #               repetitive patterns (that's jack, not stamina).
    drain_gate = max(0.0, drain_s - 60.0) / 120.0   # 0 below 60s, 1.0 at 180s
    short_penalty = max(0.0, 1.0 - drain_s / 90.0)
    chord_req = min(1.0, max(0.0, chord_fraction - 0.15) / 0.20)  # 0@≤15%, 1.0@35%+
    stamina_raw = (
        drain_gate * 28.0                       # long drain (gated at 60s+)
        + chord_fraction * 25.0                 # jumpstream/handstream content
        - stream_purity * 20.0                  # penalize stream-pure (not stamina)
        + nps_active_ratio * 12.0               # sustained activity
        + max(0.0, 1.0 - density_cv) * 8.0     # consistent difficulty
        + nps_sustained * 0.3                   # sustained NPS bonus
        + min(1.0, drain_s / 150.0) * 12.0     # secondary drain
    )
    stamina_score = stamina_raw * chord_req * max(0.4, 1.0 - short_penalty * 0.5)
    # Penalize repetitive patterns (that's jack territory, not stamina)
    if is_repetitive > 0.15:
        stamina_score *= max(0.3, 1.0 - is_repetitive * 0.7)

    scores = {
        "stream": stream_score,
        "jack": jack_score,
        "tech": tech_score,
        "speed": speed_score,
        "stamina": stamina_score,
    }

    # Sort by score
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_family = ranked[0][0]
    top_score = ranked[0][1]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    # Confidence: gap between top and second
    gap = top_score - second_score
    total = sum(s for _, s in ranked)
    if total > 0:
        dominance = top_score / total
    else:
        dominance = 0.0

    # If no clear winner, fall back to hybrid
    confidence = min(1.0, gap / max(total * 0.10, 1.0))
    if confidence < 0.15:
        family = "hybrid"
        confidence = max(0.1, confidence)
    else:
        family = top_family

    # Post-classification tiebreak: stream/hybrid → tech when density is
    # irregular (dcv > 0.35) and tech score is within 75% of stream.
    # High density_cv is fundamentally anti-stream, indicating tech patterns.
    if family in ("hybrid", "stream") and density_cv > 0.35:
        tech_s = scores.get("tech", 0)
        stream_s = scores.get("stream", 0)
        if tech_s > 0 and stream_s > 0 and tech_s / stream_s > 0.75:
            family = "tech"
            confidence = max(confidence, 0.3)

    # Post-classification tiebreak: stream → speed for single-note fast charts.
    # At moderate+ BPM (≥155), high stream_purity + low chords = "dense stream"
    # which the user defines as "speed", not generic "stream".
    if family == "stream" and bpm >= 155 and stream_purity > 0.70 and chord_fraction < 0.30:
        speed_s = scores.get("speed", 0)
        stream_s = scores.get("stream", 0)
        if speed_s > 0 and stream_s > 0 and speed_s / stream_s > 0.35:
            family = "speed"
            confidence = max(confidence, 0.25)

    # Post-classification tiebreak: Marathon anti-jack guardrail.
    # Marathons (>15k notes) inherently accumulate high jack-like stats due to duration,
    # but they are fundamentally stamina/hybrid tests. Jack ruler inflates their SR.
    total_notes_eff = float(sunny_result.get("total_notes_eff", 0) or 0)
    if family == "jack" and total_notes_eff > 15000:
        family = "stamina" if scores.get("stamina", 0) > scores.get("tech", 0) else "hybrid"
        confidence = min(confidence, 0.5)

    # Post-classification tiebreak: long maps with chords -> stamina.
    # Maps classified as stream or tech that are long (>120s drain) with
    # significant chord content (>25% chord fraction) are often mislabeled
    # stamina marathons.  When stamina is within 85% of the winner, prefer it.
    if family in ("stream", "tech") and drain_s > 120 and chord_fraction > 0.25:
        stamina_s = scores.get("stamina", 0)
        stream_s = scores.get("stream", 0)
        tech_s = scores.get("tech", 0)
        if stamina_s > 0 and stamina_s > max(stream_s, tech_s) * 0.85:
            family = "stamina"
            confidence = max(confidence, 0.35)

    # Post-classification: rescue tech maps using timing irregularity.
    # Dumpstream/irregular tech maps have irregular row timing (high CV of
    # inter-row gaps) combined with moderate jack density and chords.
    # This is a direct indicator that MMA uses — not inferrable from density.
    if family not in ("tech", "jack") and timing_irregularity > 0.4:
        if jack_density > 0.08 and 0.15 < chord_fraction < 0.55 and 0.40 < stream_purity < 0.85:
            tech_s = scores.get("tech", 0)
            winner_s = scores.get(family, 0)
            if tech_s > 0 and winner_s > 0 and tech_s > winner_s * 0.75:
                family = "tech"
                confidence = max(confidence, 0.35)

    subtype_info = None
    if family == "tech":
        subtype_info = _classify_tech_subtype(features, sunny_result, profiles_cfg)
    elif family == "hybrid" and tech_score >= top_score * 0.85:
        subtype_info = _classify_tech_subtype(features, sunny_result, profiles_cfg)

    subtype_label = subtype_info["subtype"] if subtype_info else "generic"
    reason = (
        f"{family} (score={top_score:.1f}, gap={gap:.1f}, "
        f"jack_ratio={jack_ratio_broad:.2f}, jack_density={jack_density:.2f}, stream_purity={stream_purity:.2f}, "
        f"density_cv={density_cv:.2f}, bpm={bpm:.0f}, drain={drain_s:.0f}s, subtype={subtype_label})"
    )

    return {
        "family": family,
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 2) for k, v in scores.items()},
        "subtype": subtype_label,
        "subtype_confidence": subtype_info["confidence"] if subtype_info else 0.0,
        "subtype_scores": subtype_info["scores"] if subtype_info else {},
        "reason": reason,
    }
