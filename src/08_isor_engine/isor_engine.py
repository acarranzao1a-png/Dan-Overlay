"""
isor_engine.py -- ISOR: Isotonic Strain Organic Residual.

Alternate dan-estimation engine for DanOverlay (osu!mania 4K rice).
Triangulates three continuous human-aligned difficulty vectors
(dp_sr, dp_choke, dp_msd), refines them with an isotonic-trained ridge
corrector (dual-band, benchmark-calibrated), and rescues the official
dan-ladder top scale with a continuous gate. Rate-aware and monotonic
in rate (isotonic SR clamp + native-anchor DP floor). Selectable as an
alternate engine in the overlay; the legacy engine stays untouched.
"""

import bisect
import concurrent.futures
import json
import math
import os
import sys
from collections import defaultdict
import numpy as np

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src", "02_runtime_bridge"))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src", "07_model"))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src", "03_engine_reference", "sr_core"))

from parser import parsear_osu_v2
from validator import validate_domain
from feature_extractor import extract_features
from primary_sr_bridge import analyze_primary_sr
from classifier import classify_family
from rhythm_profile import classify_from_parsed
from minacalc_bridge import calc as calculate_msd
from strain import BIO_CONFIG, build_bio_rows, biomech_numeric

_ISOR_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="ISOR-Worker")

# ── Dan Definitions ───────────────────────────────────────────────────────────

DAN_ORDER = [
    "1st", "2nd", "3rd", "4th", "5th",
    "6th", "7th", "8th", "9th", "10th",
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
    "Zeta", "Eta", "Theta", "Iota", "Kappa"
]

DAN_DISPLAY = {
    "1st": "1st Dan", "2nd": "2nd Dan", "3rd": "3rd Dan",
    "4th": "4th Dan", "5th": "5th Dan", "6th": "6th Dan",
    "7th": "7th Dan", "8th": "8th Dan", "9th": "9th Dan",
    "10th": "10th Dan",
    "Alpha": "Alpha", "Beta": "Beta", "Gamma": "Gamma",
    "Delta": "Delta", "Epsilon": "Epsilon",
    "Zeta": "Zeta", "Eta": "Eta", "Theta": "Theta",
    "Iota": "Iota", "Kappa": "Kappa",
}

SUBLEVEL_QUINTILES = [
    (0.00, 0.20, "Low"),
    (0.20, 0.40, "Mid-Low"),
    (0.40, 0.60, "Mid"),
    (0.60, 0.80, "Mid-High"),
    (0.80, 1.00, "High"),
]

# ── 1. Decoupled Canonical SR Means (1st to Kappa) ───────────────────────────

SKILLSET_SR_MEANS = {
    "jack": {
        "1st": 2.34, "2nd": 2.35, "3rd": 3.17, "4th": 3.48, "5th": 3.98,
        "6th": 4.75, "7th": 4.97, "8th": 5.84, "9th": 5.85, "10th": 6.30,
        "Alpha": 6.45, "Beta": 6.78, "Gamma": 6.95, "Delta": 7.85, "Epsilon": 8.76,
        "Zeta": 9.35, "Eta": 10.38, "Theta": 10.96, "Iota": 12.27, "Kappa": 13.13
    },
    "speed": {
        "1st": 2.94, "2nd": 3.50, "3rd": 3.78, "4th": 4.16, "5th": 4.86,
        "6th": 5.10, "7th": 5.25, "8th": 5.45, "9th": 5.70, "10th": 6.00,
        "Alpha": 6.55, "Beta": 6.80, "Gamma": 7.45, "Delta": 7.76, "Epsilon": 9.16,
        "Zeta": 9.55, "Eta": 10.05, "Theta": 10.67, "Iota": 11.16, "Kappa": 12.05
    },
    "stamina": {
        "1st": 3.38, "2nd": 3.48, "3rd": 3.79, "4th": 4.69, "5th": 5.23,
        "6th": 5.65, "7th": 5.75, "8th": 6.15, "9th": 6.26, "10th": 6.45,
        "Alpha": 6.58, "Beta": 6.88, "Gamma": 7.35, "Delta": 7.85, "Epsilon": 8.92,
        "Zeta": 9.60, "Eta": 9.96, "Theta": 10.81, "Iota": 11.66, "Kappa": 12.41
    },
    "tech": {
        "1st": 2.84, "2nd": 3.08, "3rd": 3.09, "4th": 3.90, "5th": 4.18,
        "6th": 4.50, "7th": 5.43, "8th": 5.69, "9th": 6.31, "10th": 6.55,
        "Alpha": 6.62, "Beta": 6.85, "Gamma": 7.30, "Delta": 8.17, "Epsilon": 9.22,
        "Zeta": 9.60, "Eta": 10.25, "Theta": 10.64, "Iota": 11.69, "Kappa": 12.10
    },
    "general": {
        "1st": 2.94, "2nd": 3.23, "3rd": 3.51, "4th": 4.16, "5th": 4.71,
        "6th": 5.12, "7th": 5.36, "8th": 5.80, "9th": 6.00, "10th": 6.25,
        "Alpha": 6.50, "Beta": 6.80, "Gamma": 7.35, "Delta": 7.85, "Epsilon": 9.00,
        "Zeta": 9.40, "Eta": 10.13, "Theta": 10.74, "Iota": 11.68, "Kappa": 12.25
    }
}

# ── 2. Canonical Choke Point 10s NPS Benchmarks by Skillset ───────────────────

SKILLSET_CHOKE_MEANS = {
    "speed": {
        "1st": 11.5, "2nd": 13.0, "3rd": 14.5, "4th": 16.0, "5th": 18.0,
        "6th": 18.5, "7th": 19.2, "8th": 19.8, "9th": 20.4, "10th": 21.0,
        "Alpha": 25.2, "Beta": 26.5, "Gamma": 28.0, "Delta": 30.0, "Epsilon": 31.8,
        "Zeta": 35.0, "Eta": 36.5, "Theta": 41.5, "Iota": 45.0, "Kappa": 49.0
    },
    "stamina": {
        "1st": 12.9, "2nd": 15.4, "3rd": 15.5, "4th": 17.8, "5th": 23.0,
        "6th": 20.6, "7th": 22.3, "8th": 23.5, "9th": 24.5, "10th": 24.0,
        "Alpha": 24.4, "Beta": 25.5, "Gamma": 28.5, "Delta": 31.4, "Epsilon": 34.0,
        "Zeta": 38.6, "Eta": 42.7, "Theta": 40.3, "Iota": 45.9, "Kappa": 50.0
    },
    "jack": {
        "1st": 10.5, "2nd": 12.0, "3rd": 10.5, "4th": 13.1, "5th": 14.3,
        "6th": 14.4, "7th": 17.9, "8th": 19.5, "9th": 20.5, "10th": 24.8,
        "Alpha": 24.8, "Beta": 26.5, "Gamma": 27.2, "Delta": 31.0, "Epsilon": 34.0,
        "Zeta": 35.2, "Eta": 39.1, "Theta": 45.0, "Iota": 49.3, "Kappa": 53.7
    },
    "tech": {
        "1st": 10.5, "2nd": 12.0, "3rd": 10.5, "4th": 13.1, "5th": 14.3,
        "6th": 14.4, "7th": 17.9, "8th": 19.5, "9th": 20.5, "10th": 21.8,
        "Alpha": 22.5, "Beta": 23.8, "Gamma": 26.0, "Delta": 26.8, "Epsilon": 29.8,
        "Zeta": 36.0, "Eta": 39.2, "Theta": 39.3, "Iota": 42.4, "Kappa": 46.6
    },
    "general": {
        "1st": 11.5, "2nd": 13.5, "3rd": 14.5, "4th": 16.0, "5th": 18.5,
        "6th": 19.5, "7th": 20.5, "8th": 21.5, "9th": 22.5, "10th": 22.8,
        "Alpha": 24.2, "Beta": 25.0, "Gamma": 27.0, "Delta": 30.0, "Epsilon": 32.5,
        "Zeta": 35.5, "Eta": 38.5, "Theta": 42.0, "Iota": 46.0, "Kappa": 50.5
    }
}

# ── Ruler monotonicity sanitization ────────────────────────────────────────────
# Non-monotonic canonical means break interpolate_ruler(): the midpoint
# boundary scheme produces zero-width or inverted zones.  For example the
# jack/tech choke rulers carry 3rd = 10.5 < 2nd = 12.0, which collapses the
# 2nd zone so a 10.5 NPS map interpolates to ~1.5 DP (1st Dan) instead of 3rd.
# Stamina carries 5th = 23.0 > 6th = 20.6, inflating the 5th zone to
# 20.4-21.8 NPS and dragging maps far below their tier.  We fit the closest
# monotone sequence (pool-adjacent-violators) and enforce strictness with a
# minimal epsilon bump, preserving the empirical values as much as possible.

def _isotonic_monotone(values):
    """Pool-adjacent-violators: closest non-decreasing fit of *values*."""
    blocks = [[v] for v in values]
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(blocks) - 1:
            mean_i = sum(blocks[i]) / len(blocks[i])
            mean_j = sum(blocks[i + 1]) / len(blocks[i + 1])
            if mean_i > mean_j:
                blocks[i] = blocks[i] + blocks[i + 1]
                del blocks[i + 1]
                changed = True
            else:
                i += 1
    flat = []
    for b in blocks:
        flat.extend([sum(b) / len(b)] * len(b))
    out = []
    for v in flat:
        if out and v <= out[-1]:
            v = out[-1] + 0.005
        out.append(v)
    return out


def _sanitize_ruler(means_dict):
    """Return a strictly monotone copy of a {dan: value} ruler."""
    values = [float(means_dict[d]) for d in DAN_ORDER]
    mono = _isotonic_monotone(values)
    return {d: round(mono[i], 3) for i, d in enumerate(DAN_ORDER)}


SKILLSET_CHOKE_MEANS = {
    sk: _sanitize_ruler(ruler)
    for sk, ruler in SKILLSET_CHOKE_MEANS.items()
}


def _report_ruler_health(name, means_dict):
    """Report (do not modify) non-monotonic rulers used by the triangulation."""
    vals = [means_dict[d] for d in DAN_ORDER]
    bad = [i + 1 for i in range(1, len(vals)) if vals[i] <= vals[i - 1]]
    if bad:
        print(f"[prototype] WARNING: {name} non-monotonic at positions {bad}")


for _sk_name, _sk_ruler in SKILLSET_SR_MEANS.items():
    _report_ruler_health(f"SKILLSET_SR_MEANS[{_sk_name}]", _sk_ruler)

# ── 3. Canonical MinaCalc MSD Benchmarks (1st to Kappa) ────────────────────────

MSD_MEANS = {
    "1st": 13.5, "2nd": 15.5, "3rd": 16.8, "4th": 18.5, "5th": 20.5,
    "6th": 22.0, "7th": 23.5, "8th": 24.8, "9th": 25.8, "10th": 26.8,
    "Alpha": 27.5, "Beta": 28.5, "Gamma": 30.5, "Delta": 33.0, "Epsilon": 36.0,
    "Zeta": 37.8, "Eta": 40.5, "Theta": 43.5, "Iota": 46.5, "Kappa": 50.0
}

_report_ruler_health("MSD_MEANS", MSD_MEANS)


def _sigmoid(x, k=1.0, x0=0.0):
    z = k * (x - x0)
    z = max(-50.0, min(50.0, z))
    return 1.0 / (1.0 + math.exp(-z))


# ── Dynamic continuous triangulation weights ──────────────────────────────────
# Static weights (0.50/0.30/0.20) treat every map alike, but each vector has
# blind spots: the Choke ruler is flat at low densities (10.5 NPS spans
# 1st-3rd Dan in jack/tech), and the SR vector dominates when the choke
# signal carries no information.  The weights are therefore smooth functions
# of the signals themselves:
#
#   w_sr   rises when the choke vector is flat (low NPS) AND raw SR carries
#          ranking signal (SR > ~3.0) — the 3rd Dan dead-zone fix.
#   w_msd  rises when SR and Choke disagree by more than ~1.2 DP, letting the
#          independent MinaCalc projection break the tie.
#
# All transitions are sigmoids (no hard gates), and weights are always
# renormalized to sum to 1.0.

_W_BASE_SR = 0.50
_W_BASE_CHOKE = 0.30
_W_BASE_MSD = 0.20
_W_SR_FLAT_GAIN = 0.25
_W_SR_CAP = 0.80
_W_SR_FLAT_K = 1.0
_W_SR_FLAT_X0 = 13.0
_W_SR_SIGNAL_K = 2.0
_W_SR_SIGNAL_X0 = 3.0
_W_MSD_AGREE_GAIN = 0.15
_W_MSD_CAP = 0.35
_W_MSD_AGREE_K = 2.0
_W_MSD_AGREE_X0 = 1.2
_W_CHOKE_FLOOR = 0.05

# ── Continuous BPM frequency factor (pure speed) ──────────────────────────────
# Speed 8th-10th packs differ by only 0.4-1.2 NPS in choke density (19.8-21.0)
# but by 200 -> 220 BPM in rhythmic frequency.  The choke dimension cannot
# separate them, so a smooth BPM term modulates the SR for pure single-note
# streams.  The stream_purity sigmoid is the gate: jacks, stamina jumpstreams
# and tech maps have low purity and receive ~0 boost.

_BPM_GAIN = 0.06
_BPM_PURITY_K = 20.0
_BPM_PURITY_X0 = 0.85
_BPM_K = 0.08
_BPM_X0 = 200.0

# ── Continuous chord-mass anchor (Alpha/Beta boundary) ────────────────────────
# At the same SR, chord mass differentiates tiers: 10th Dan uses jumpstreams,
# Alpha introduces hands, and Speed Alpha (pure stream, ~0% hands) must read
# below Tech Beta (chordstream, >25% hands).  A SIGNED smooth hand_ratio term
# (sigmoid centred at the neutral hand level) nudges low-hand maps down and
# high-hand maps up.

_CHORD_GAIN = 0.35
_CHORD_K = 25.0
_CHORD_X0 = 0.12

# ── Tuned continuous gains (offline calibration, 151-map corpus) ───────────────

_BURST_GAIN = 0.08      # burst SR modulation (reduced: inflates 10th-Alpha jacks)
_JACK2_GAIN = 0.05      # concentrated-jack SR modulation (reduced, same reason)
_DAMP_GAIN = 0.20       # low-tier floor damper strength
_STREAM_STAM_THR = 0.35 # stream family: jump_ratio >= thr -> stamina ruler
_HYBRID_STAM_THR = 0.35 # hybrid family: jump_ratio >= thr -> stamina ruler
_STAM_FAM_THR = 0.25    # stamina family: below this jump_ratio the map is pure-speed
_JD_JACK_THR = 0.15     # structural jack rescue: jack_density >= thr -> jack ruler

# ── Continuous marathon fatigue saturation ────────────────────────────────────
# Uninterrupted handstream marathons (e.g. Angel Dust, 4.5 min) inflate the
# Sunny L5 aggregate: constant density never lets the accumulator decay, so
# the SR reads far above the per-finger demand.  A smooth duration sigmoid
# combined with a consistency factor (1 - density_cv/ref) damps only long,
# constant-density charts; short or varied maps are untouched.

_MARA_CAP = 0.08
_MARA_DUR_K = 0.02
_MARA_DUR_X0 = 200.0
_MARA_CV_REF = 0.4
_FATIGUE_TOTAL_CAP = 0.12


# ── Feature Extraction ────────────────────────────────────────────────────────

def extract_choke_and_local_strains(notes, drain_s, window_ms=10000, stride_ms=250):
    if not notes or drain_s <= 0:
        return {
            "choke_10s_nps": 0.0,
            "mean_nps": 0.0,
            "burst_ratio": 1.0,
            "min_col_delta_ms": 9999.0,
            "jack_burst_density": 0.0
        }

    times = [n[0] for n in notes]
    t_min = times[0]
    t_max = times[-1]
    total_notes = len(notes)
    mean_nps = total_notes / max(drain_s, 1.0)
    n_times = len(times)

    # 10s Rolling Peak Window (linear two-pointer sliding window O(W + N))
    max_notes_window = 0
    t = t_min
    left_idx = 0
    right_idx = 0
    while t <= t_max:
        lo = t
        hi = t + window_ms
        while left_idx < n_times and times[left_idx] < lo:
            left_idx += 1
        while right_idx < n_times and times[right_idx] <= hi:
            right_idx += 1
        c = right_idx - left_idx
        if c > max_notes_window:
            max_notes_window = c
        t += stride_ms

    choke_10s_nps = max_notes_window / (window_ms / 1000.0)
    burst_ratio = choke_10s_nps / max(mean_nps, 1.0)

    # Per-column repetition
    by_col = defaultdict(list)
    for t_val, c_val in notes:
        by_col[c_val].append(t_val)

    col_deltas = []
    jack_burst_count = 0
    for c_val, t_list in by_col.items():
        t_sorted = sorted(t_list)
        for i in range(1, len(t_sorted)):
            dt = t_sorted[i] - t_sorted[i-1]
            col_deltas.append(dt)
            if dt <= 120.0:
                jack_burst_count += 1

    min_col_delta = min(col_deltas) if col_deltas else 9999.0
    jack_burst_density = jack_burst_count / max(total_notes, 1.0)

    return {
        "choke_10s_nps": round(choke_10s_nps, 2),
        "mean_nps": round(mean_nps, 2),
        "burst_ratio": round(burst_ratio, 3),
        "min_col_delta_ms": round(min_col_delta, 1),
        "jack_burst_density": round(jack_burst_density, 3)
    }


# ── Continuous Interpolator Primitive ─────────────────────────────────────────

def _build_ruler_boundaries(mean_dict):
    means = [mean_dict[d] for d in DAN_ORDER]
    n = len(means)
    boundaries = []
    for i in range(n):
        if i > 0:
            lo = (means[i - 1] + means[i]) / 2.0
        else:
            lo = means[0] - (means[1] - means[0]) / 2.0

        if i < n - 1:
            hi = (means[i] + means[i + 1]) / 2.0
        else:
            hi = means[-1] + (means[-1] - means[-2]) / 2.0

        boundaries.append((lo, hi, float(i + 1)))
    return boundaries

_RULER_BOUNDARIES_CACHE = {}


def interpolate_ruler(val, mean_dict):
    """Converts any continuous scalar metric into a 1.0-20.99 DP coordinate."""
    dict_id = id(mean_dict)
    boundaries = _RULER_BOUNDARIES_CACHE.get(dict_id)
    if boundaries is None:
        boundaries = _build_ruler_boundaries(mean_dict)
        _RULER_BOUNDARIES_CACHE[dict_id] = boundaries

    if val < boundaries[0][0]:
        t = max(0.0, (val - (boundaries[0][0] - 1.0)) / 1.0)
        return 1.0 + t * 0.20

    if val >= boundaries[-1][1]:
        return 20.99

    for lo, hi, dp_base in boundaries:
        if lo <= val < hi:
            t = (val - lo) / max(hi - lo, 1e-6)
            return dp_base + t

    return 20.0


# ── Triangulated Multidimensional Engine ──────────────────────────────────────

# Biomechanical strain layer (4th vector). Off by default: the tuned
# triangulation stays untouched until DP_Bio weights are calibrated.
_BIO_ENABLED = False
_BIO_W_BASE = 0.15

# ── Ridge error-corrector (calibrated offline on the VSRG benchmark) ──────────
# dp_final = dp_base + clamp(ridge(bio + msd-role features), ±cap).
# The deployed model (vsrg_ridge_model.json) is a dual-band ridge: the high
# model is fit on the 11-17+ band (98 features, feature_set sustain_v1) and
# the low model on the 1-10.5 band with official dan-pack augmentation. The
# 80/20 stratified split is used only to REPORT holdout error; the shipped
# coefficients are the full fit on each band. Generalization is measured
# separately on the official dan-pack and practice-pack corpora.
_RIDGE_ENABLED = True
_RIDGE_CAP = 1.0

_RIDGE_MODEL = None
if _RIDGE_ENABLED:
    _data_dir = os.path.join(os.path.dirname(_THIS_DIR), "03_data")
    _candidate_paths = [
        os.path.join(_data_dir, "vsrg_ridge_model.json"),
        os.path.join(_THIS_DIR, "vsrg_ridge_model.json"),
        os.path.join(os.path.dirname(os.path.dirname(_THIS_DIR)), "config", "vsrg_ridge_model.json"),
    ]
    if getattr(sys, "frozen", False):
        _candidate_paths.insert(0, os.path.join(sys._MEIPASS, "config", "vsrg_ridge_model.json"))
    for _rp in _candidate_paths:
        if os.path.exists(_rp):
            try:
                with open(_rp, encoding="utf-8") as _f:
                    _RIDGE_MODEL = json.load(_f)
                break
            except Exception:
                _RIDGE_MODEL = None


_RIDGE_STREAM_NAMES = ["speed", "hand", "jack", "chordjack", "tech", "stamina", "course"]
_RIDGE_STAT_KEYS = ["chord_rate", "three_rate", "overlap_rate", "rotation_rate",
                    "fast_jack_rate", "anchor_rate", "hand_bias", "avg_nps",
                    "active_duration_s"]

    # sustain_v1 block: sustained-density and timing-texture features, appended
    # only when the loaded model declares feature_set="sustain_v1" (backward
    # compatible with 83-feature models).
_RIDGE_SUSTAIN_KEYS = (
    "nps1k_q50", "nps1k_q75", "nps1k_q90",
    "nps4k_q50", "nps4k_q75", "nps4k_q90",
    "nps1k_flatness", "log_nps1k_mean",
    "dt_row_q25", "dt_row_q50", "dt_row_q75",
    "dt_hand_q25", "dt_hand_median",
    "dt_same_q25", "dt_same_median",
)

    # sustain_v2 block: skillset(routing) x centered-signal interactions.
    # Centering constants match the offline trainer.
_RIDGE_SUSTAIN_V2_KEYS = (
    "g_jack_npsq75", "g_jack_dtrow",
    "g_speed_npsq75", "g_speed_dtrow",
    "g_stam_npsq75", "g_stam_dtrow",
    "g_tech_npsq75", "g_tech_dtrow",
)
_RIDGE_SUSTAIN_CENTER_NPS_Q75 = 19.5
_RIDGE_SUSTAIN_CENTER_DT_ROW = 90.0


def _ridge_feature_vector(bio_res, msd_dict, sunny_strains=None, purity=0.0, subrank=None):
    """Build the feature vector exactly as in tune_offline._ridge_feats."""
    feats = bio_res or {}
    summaries = feats.get("summaries", {})
    streams = feats.get("streams", {})
    streams_q97 = feats.get("streams_q97", {})
    stats = feats.get("stats", {})
    keys = _RIDGE_STREAM_NAMES
    
    v = []
    for k in keys:
        if k in summaries and isinstance(summaries[k], dict):
            v.append(float(summaries[k].get("aggregate", 0.0) or 0.0))
        else:
            v.append(float(streams.get(k, 0.0) or 0.0))
            
    jack_agg = summaries.get("jack", {}).get("aggregate", 0.0) if isinstance(summaries.get("jack"), dict) else float(streams.get("jack", 0.0) or 0.0)
    chordjack_agg = summaries.get("chordjack", {}).get("aggregate", 0.0) if isinstance(summaries.get("chordjack"), dict) else float(streams.get("chordjack", 0.0) or 0.0)
    speed_agg = summaries.get("speed", {}).get("aggregate", 0.0) if isinstance(summaries.get("speed"), dict) else float(streams.get("speed", 0.0) or 0.0)
    stamina_agg = summaries.get("stamina", {}).get("aggregate", 0.0) if isinstance(summaries.get("stamina"), dict) else float(streams.get("stamina", 0.0) or 0.0)

    log_raw = math.log1p(max(0.0, feats.get("raw_agg", 0.0) or 0.0))
    v.append(log_raw)
    for k in _RIDGE_STAT_KEYS:
        v.append(float(stats.get(k, 0.0) or 0.0))
    for k in keys:
        if k in summaries and isinstance(summaries[k], dict):
            v.append(float(summaries[k].get("q97", 0.0) or 0.0))
        else:
            v.append(float(streams_q97.get(k, 0.0) or 0.0))
    msd = msd_dict or {}
    roles = {
        "msd_jack": max(float(msd.get("jackspeed", 0.0) or 0.0), float(msd.get("chordjack", 0.0) or 0.0)),
        "msd_speed": max(float(msd.get("stream", 0.0) or 0.0), float(msd.get("jumpstream", 0.0) or 0.0)),
        "msd_stamina": 0.7 * float(msd.get("stamina", 0.0) or 0.0) + 0.3 * float(msd.get("handstream", 0.0) or 0.0),
        "msd_tech": float(msd.get("technical", 0.0) or 0.0),
    }
    total = sum(roles.values()) or 1.0
    v += [roles[k] / total for k in ["msd_jack", "msd_speed", "msd_stamina", "msd_tech"]]
    sun = sunny_strains or {}
    v += [float(sun.get(k, 0.0) or 0.0) for k in ["jbar_max", "pbar_max", "xbar_max", "abar_mean"]]
    v += [float(msd.get("overall", 0.0) or 0.0)] + [
        float(msd.get(k, 0.0) or 0.0) for k in
        ["stream", "jumpstream", "handstream", "stamina", "jackspeed", "chordjack", "technical"]]
    v += [
        float(stats.get("chord_rate", 0.0) or 0.0) * float(stats.get("fast_jack_rate", 0.0) or 0.0),
        float(stats.get("overlap_rate", 0.0) or 0.0) * float(stats.get("rotation_rate", 0.0) or 0.0),
        jack_agg / (chordjack_agg + 1e-6),
        speed_agg * float(purity or 0.0),
        float(stats.get("anchor_imbalance", 0.0) or 0.0),
        float(stats.get("peak_to_sustain_gap", 0.0) or 0.0),
        float(stats.get("break_density", 0.0) or 0.0),
        # 8 new physical interactions
        float(stats.get("fast_jack_rate", 0.0) or 0.0) * (100.0 / (float(stats.get("same_hand_q10", 0.0) or 0.0) + 10.0)),
        float(stats.get("rotation_rate", 0.0) or 0.0) * float(subrank.get("ti", 0.0) or 0.0),
        float(subrank.get("burst_ratio", 1.0) or 1.0) * float(stats.get("peak_to_sustain_gap", 0.0) or 0.0),
        float(stats.get("avg_nps", 0.0) or 0.0) * float(subrank.get("dur", 0.0) or 0.0) / 60.0,
        float(subrank.get("quad", 0.0) or 0.0) * float(subrank.get("hand", 0.0) or 0.0),
        float(stats.get("rotation_rate", 0.0) or 0.0) * (1.0 - float(stats.get("overlap_rate", 0.0) or 0.0)),
        float(subrank.get("choke", 0.0) or 0.0) / (float(stats.get("avg_nps", 0.0) or 0.0) + 1.0),
        abs(float(subrank.get("dp_sr", 0.0) or 0.0) - float(subrank.get("dp_msd", 0.0) or 0.0)),
    ]
    # sub-ranking projections (weak estimators)
    sub = subrank or {}
    dp_sr = float(sub.get("dp_sr", 0.0) or 0.0)
    dp_choke = float(sub.get("dp_choke", 0.0) or 0.0)
    dp_msd = float(sub.get("dp_msd", 0.0) or 0.0)
    mod_sr = float(sub.get("mod_sr", 0.0) or 0.0)
    raw_sr = float(sub.get("raw_sr", 0.0) or 0.0)
    jbar = float(sun.get("jbar_max", 0.0) or 0.0)
    pbar = float(sun.get("pbar_max", 0.0) or 0.0)
    msd_overall = float(msd.get("overall", 0.0) or 0.0)

    # 12 non-linear cross-projections
    v += [
        math.sqrt(max(0.0, log_raw)),
        log_raw ** 2,
        raw_sr / (dp_sr + 1e-6),
        dp_choke / (dp_msd + 1e-6),
        mod_sr - raw_sr,
        (dp_sr + dp_choke + dp_msd) / 3.0,
        max(0.0, dp_msd - dp_sr),
        max(0.0, dp_sr - dp_msd),
        max(0.0, dp_choke - dp_sr),
        abs(jbar - pbar),
        jbar / (pbar + 1e-6),
        msd_overall / (raw_sr * 3.5 + 1e-6),
    ]
    # 6 fatigue / high-BPM features
    bpm_val = float(sub.get("bpm", 180.0) or 180.0)
    bpm_excess = max(0.0, bpm_val - 240.0) / 100.0
    v += [
        bpm_excess,
        bpm_excess * stamina_agg,
        bpm_excess * speed_agg,
        stamina_agg / (dp_choke + 1e-6),
        jack_agg / (dp_choke + 1e-6),
        speed_agg / (dp_sr + 1e-6),
    ]
    # 4 dedicated rate-mod and duration stamina features
    purity_val = float(purity or 0.0)
    dur_val = float(sub.get("dur", 120.0) or 120.0)
    avg_nps = float(stats.get("avg_nps", 0.0) or 0.0)
    v += [
        (dp_choke - dp_sr) * purity_val,
        (dp_msd - dp_sr) * purity_val,
        math.log1p(max(0.0, dur_val)) / math.log1p(180.0),
        bpm_val / (avg_nps * 12.0 + 1e-6),
    ]
    v += [dp_sr, dp_choke, dp_msd, mod_sr, raw_sr]
    q10 = float(stats.get("same_hand_q10", 0.0) or 0.0)
    v += [max(0.0, min(1.0, (q10 - 60.0) / 40.0))]
    fs = (_RIDGE_MODEL or {}).get("feature_set")
    if fs in ("sustain_v1", "sustain_v2"):
        v += [float(stats.get(k, 0.0) or 0.0) for k in _RIDGE_SUSTAIN_KEYS]
    if fs == "sustain_v2":
        sk = str((subrank or {}).get("sk_key", "") or "")
        nps_q75 = float(stats.get("nps1k_q75", 0.0) or 0.0)
        dt_row = float(stats.get("dt_row_q50", 0.0) or 0.0)
        for tag in ("jack", "speed", "stamina", "tech"):
            oh = 1.0 if sk == tag else 0.0
            v += [oh * (nps_q75 - _RIDGE_SUSTAIN_CENTER_NPS_Q75) / 10.0,
                  oh * (dt_row - _RIDGE_SUSTAIN_CENTER_DT_ROW) / 100.0]
    return v


_RIDGE_HIGH_MEAN = None
_RIDGE_HIGH_SCALE = None
_RIDGE_HIGH_BETA = None
_RIDGE_LOW_MEAN = None
_RIDGE_LOW_SCALE = None
_RIDGE_LOW_BETA = None
_RIDGE_SINGLE_MEAN = None
_RIDGE_SINGLE_SCALE = None
_RIDGE_SINGLE_BETA = None

if _RIDGE_MODEL:
    if _RIDGE_MODEL.get("dual"):
        _h = _RIDGE_MODEL["high"]
        _l = _RIDGE_MODEL["low"]
        _RIDGE_HIGH_MEAN = np.array(_h["mean"], dtype=float)
        _RIDGE_HIGH_SCALE = np.array(_h["scale"], dtype=float)
        _RIDGE_HIGH_BETA = np.array(_h["beta"], dtype=float)
        _RIDGE_LOW_MEAN = np.array(_l["mean"], dtype=float)
        _RIDGE_LOW_SCALE = np.array(_l["scale"], dtype=float)
        _RIDGE_LOW_BETA = np.array(_l["beta"], dtype=float)
    else:
        _RIDGE_SINGLE_MEAN = np.array(_RIDGE_MODEL.get("mean", []), dtype=float)
        _RIDGE_SINGLE_SCALE = np.array(_RIDGE_MODEL.get("scale", []), dtype=float)
        _RIDGE_SINGLE_BETA = np.array(_RIDGE_MODEL.get("beta", []), dtype=float)


def apply_ridge_correction(dp_base, bio_res, msd_dict, sunny_strains=None, purity=0.0, subrank=None):
    """Return (dp_corrected, correction) applying the calibrated ridge."""
    if not _RIDGE_ENABLED or not _RIDGE_MODEL or not bio_res:
        return dp_base, 0.0
    try:
        v = np.array(_ridge_feature_vector(bio_res, msd_dict, sunny_strains, purity, subrank), dtype=float)
        if _RIDGE_MODEL.get("dual") and _RIDGE_HIGH_BETA is not None:
            xh = (v - _RIDGE_HIGH_MEAN) / _RIDGE_HIGH_SCALE
            corr_h = float(np.clip(xh @ _RIDGE_HIGH_BETA, -_RIDGE_CAP, _RIDGE_CAP))

            xl = (v - _RIDGE_LOW_MEAN) / _RIDGE_LOW_SCALE
            corr_l = float(np.clip(xl @ _RIDGE_LOW_BETA, -_RIDGE_CAP, _RIDGE_CAP))

            gate = _sigmoid(dp_base, k=4.0, x0=10.0)
            correction = gate * corr_h + (1.0 - gate) * corr_l
            return round(dp_base + correction, 2), round(correction, 3)
        elif _RIDGE_SINGLE_BETA is not None:
            if v.shape[0] != len(_RIDGE_SINGLE_BETA):
                return dp_base, 0.0
            x = (v - _RIDGE_SINGLE_MEAN) / _RIDGE_SINGLE_SCALE
            correction = float(np.clip(x @ _RIDGE_SINGLE_BETA, -_RIDGE_CAP, _RIDGE_CAP))
            return round(dp_base + correction, 2), round(correction, 3)
        return dp_base, 0.0
    except Exception:
        return dp_base, 0.0


def compute_triangulated_rank(raw_sr, sunny_strains, choke_info, msd_dict, family, conf, features_ref=None, bio_numeric=None):
    """Triangulates SR, Choke Point 10s NPS, and MinaCalc MSD into human DP."""
    choke_nps = choke_info.get("choke_10s_nps", 0.0)
    burst_ratio = choke_info.get("burst_ratio", 1.0)
    jbar_max = float(sunny_strains.get("jbar_max", 0.0) or 0.0)

    # 1. Modulated SR Calculation (Organic Burst & Jack Strain)
    burst_activation = _sigmoid(burst_ratio, k=5.0, x0=1.35)
    jbar_intensity = _sigmoid(jbar_max, k=0.08, x0=60.0)
    delta_burst = _BURST_GAIN * burst_activation * jbar_intensity

    if family in ("jack", "tech", "hybrid") and jbar_max > 55.0:
        jack_factor = _sigmoid(jbar_max, k=0.10, x0=70.0)
        delta_jack = _JACK2_GAIN * jack_factor * min(1.0, choke_info.get("jack_burst_density", 0.0) * 2.0)
    else:
        delta_jack = 0.0

    if burst_ratio < 1.15 and raw_sr > 9.5 and family in ("tech", "jack"):
        fatigue_spike = _sigmoid(raw_sr, k=2.0, x0=9.7) * (1.15 - burst_ratio) * 0.40
        fatigue_spike = min(0.06, fatigue_spike)
    else:
        fatigue_spike = 0.0

    # Marathon handstream saturation (continuous, any family)
    duration_s = float(features_ref.get("duration_s", 0.0) or 0.0) if features_ref else 0.0
    density_cv = float(features_ref.get("density_cv", 0.0) or 0.0) if features_ref else 0.0
    mara_dur_sig = _sigmoid(duration_s, k=_MARA_DUR_K, x0=_MARA_DUR_X0)
    cv_pen = 1.0 - min(1.0, density_cv / _MARA_CV_REF)
    delta_marathon = _MARA_CAP * mara_dur_sig * cv_pen
    delta_fatigue = min(_FATIGUE_TOTAL_CAP, fatigue_spike + delta_marathon)

    # Continuous BPM frequency factor for pure streams (speed 8th-10th fix)
    stream_purity = float(features_ref.get("stream_purity", 0.0) or 0.0) if features_ref else 0.0
    bpm_val = float(features_ref.get("bpm", 0.0) or 0.0) if features_ref else 0.0
    delta_bpm = (
        _BPM_GAIN
        * _sigmoid(stream_purity, k=_BPM_PURITY_K, x0=_BPM_PURITY_X0)
        * _sigmoid(bpm_val, k=_BPM_K, x0=_BPM_X0)
    )

    taper = max(0.25, 1.0 - max(0.0, raw_sr - 9.0) * 0.12)
    delta_burst *= taper
    delta_jack *= taper
    delta_bpm *= taper

    mod_sr = raw_sr * (1.0 + delta_burst + delta_jack + delta_bpm - delta_fatigue)

    # 2. Map Pattern Family to Canonical Skillset Ruler
    jump_ratio = float(features_ref.get("jump_ratio", 0.0) or 0.0) if features_ref else 0.0
    jack_density = float(features_ref.get("jack_density", 0.0) or 0.0) if features_ref else 0.0
    fam_lower = str(family).lower()

    if "jack" in fam_lower or jbar_max > 55.0:
        sk_key = "jack"
    elif "tech" in fam_lower or "ln" in fam_lower:
        sk_key = "tech"
    elif jack_density >= _JD_JACK_THR:
        # Structural jack rescue: dense same-column repetition overrides the
        # classifier label (low-tier jack maps are often read as stream/stamina).
        sk_key = "jack"
    elif fam_lower in ("stream", "speed"):
        sk_key = "stamina" if jump_ratio >= _STREAM_STAM_THR else "speed"
    elif fam_lower in ("chordstream", "stamina"):
        sk_key = "stamina" if jump_ratio >= _STAM_FAM_THR else "speed"
    else:
        sk_key = "stamina" if jump_ratio >= _HYBRID_STAM_THR else "general"

    sr_ruler = SKILLSET_SR_MEANS.get(sk_key, SKILLSET_SR_MEANS["general"])
    choke_ruler = SKILLSET_CHOKE_MEANS.get(sk_key, SKILLSET_CHOKE_MEANS["general"])

    dp_sr = interpolate_ruler(mod_sr, sr_ruler)
    dp_choke = interpolate_ruler(choke_nps, choke_ruler)

    # MinaCalc Dominant Projection
    if msd_dict and isinstance(msd_dict, dict) and "overall" in msd_dict:
        dominant_msd = float(msd_dict.get("overall", 0.0) or 0.0)
        dp_msd = interpolate_ruler(dominant_msd, MSD_MEANS)
        has_msd = True
    else:
        dp_msd = dp_sr
        has_msd = False

    # 3. Dynamic Triangulation Weights (continuous weight modulation)
    dp_bio = None
    if _BIO_ENABLED and bio_numeric is not None and bio_numeric > 0.0:
        dp_bio = interpolate_ruler(bio_numeric, sr_ruler)
    if has_msd:
        choke_flat = _sigmoid(_W_SR_FLAT_X0 - choke_nps, k=_W_SR_FLAT_K, x0=0.0)
        sr_signal = _sigmoid(raw_sr - _W_SR_SIGNAL_X0, k=_W_SR_SIGNAL_K, x0=0.0)
        w_sr = _W_BASE_SR + _W_SR_FLAT_GAIN * choke_flat * sr_signal
        w_sr = min(_W_SR_CAP, w_sr)

        disagree = _sigmoid(abs(dp_sr - dp_choke) - _W_MSD_AGREE_X0, k=_W_MSD_AGREE_K, x0=0.0)
        w_msd = _W_BASE_MSD + _W_MSD_AGREE_GAIN * disagree
        w_msd = min(_W_MSD_CAP, w_msd)

        w_bio = _BIO_W_BASE if dp_bio is not None else 0.0
        w_choke = max(_W_CHOKE_FLOOR, 1.0 - w_sr - w_msd - w_bio)
        _w_total = w_sr + w_choke + w_msd + w_bio
        w_sr /= _w_total
        w_choke /= _w_total
        w_msd /= _w_total
        w_bio = w_bio / _w_total if w_bio else 0.0
    else:
        w_sr = 0.60
        w_choke = 0.40
        w_msd = 0.0
        w_bio = 0.0

    raw_combined_dp = w_sr * dp_sr + w_choke * dp_choke + w_msd * dp_msd
    if dp_bio is not None and w_bio > 0.0:
        raw_combined_dp += w_bio * dp_bio

    # 4. Continuous Low-Tier Floor Damper (1st-3rd Dan)
    # Compresses variance in low-density maps (NPS < 16.0) where simple jumpstreams over-project
    if raw_combined_dp <= 4.5 and choke_nps < 18.0:
        low_density_factor = _sigmoid(16.0 - choke_nps, k=0.5, x0=2.0)
        dp_damped = raw_combined_dp - _DAMP_GAIN * low_density_factor * max(0.0, raw_combined_dp - 1.5)
        raw_combined_dp = max(1.0, dp_damped)

    # 5. Continuous Alpha / Beta Boundary Anchor
    # Smooth continuous transition based on Choke NPS and chord mass
    hand_ratio = float(features_ref.get("hand_ratio", 0.0) or 0.0) if features_ref else 0.0
    if 9.8 <= raw_combined_dp <= 12.8:
        # Alpha transition signal
        alpha_signal = _sigmoid(choke_nps, k=3.0, x0=25.2) * _sigmoid(hand_ratio, k=20.0, x0=0.15)
        raw_combined_dp += 0.20 * alpha_signal

        # Beta transition signal (Choke >= 27.2 NPS)
        beta_signal = _sigmoid(choke_nps, k=3.0, x0=27.2)
        raw_combined_dp += 0.25 * beta_signal

        # Chord-mass differentiation (signed: low hands step back, hands push up)
        chord_signal = _sigmoid(hand_ratio, k=_CHORD_K, x0=_CHORD_X0) - 0.5
        raw_combined_dp += _CHORD_GAIN * chord_signal

    final_dp = round(raw_combined_dp, 2)
    tier_idx = min(len(DAN_ORDER) - 1, max(0, int(final_dp) - 1))
    dan_label = DAN_DISPLAY.get(DAN_ORDER[tier_idx], DAN_ORDER[tier_idx])

    # Derive Quintile Sublevel
    frac = round(final_dp - math.floor(final_dp), 2)
    sublevel = "High"
    for q_lo, q_hi, label in SUBLEVEL_QUINTILES:
        if q_lo <= frac <= q_hi:
            sublevel = label
            break

    return {
        "dp": final_dp,
        "dan_label": dan_label,
        "sublevel": sublevel,
        "mod_sr": round(mod_sr, 4),
        "dp_sr": round(dp_sr, 2),
        "dp_choke": round(dp_choke, 2),
        "dp_msd": round(dp_msd, 2),
        "dp_bio": round(dp_bio, 2) if dp_bio is not None else None,
        "sk_key": sk_key,
        "weights": {"w_sr": round(w_sr, 3), "w_choke": round(w_choke, 3), "w_msd": round(w_msd, 3), "w_bio": round(w_bio, 3)}
    }


# ── Full Prototype Pipeline ───────────────────────────────────────────────────

def analyze_beatmap_prototype(osu_path, mod="NM", rate=None, parsed=None, domain=None):
    """Analyze one map with the prototype engine.

    mod: "NM" | "DT" | "HT" | "NC" (NC == DT rate).
    rate: custom lazer clock rate (0.5-2.0) or None for the mod's native rate.
    The SR bridge enforces non-decreasing SR in rate (isotonic clamp, per-map
    registry), so a higher rate never shows a lower difficulty.
    """
    if not os.path.exists(osu_path):
        return {"error": "file_not_found"}

    if parsed is None:
        parsed = parsear_osu_v2(osu_path, enforce_mode_mania=True)
    if parsed.get("rejected"):
        return {"error": "rejected_domain"}

    if domain is None:
        domain = validate_domain(parsed)
    drain_s = float(domain.get("drain_time_s", 0.0) or 0.0)
    notes = parsed.get("notes", [])

    _rate_msd = float(rate) if rate else {"HT": 0.75, "DT": 1.5, "NC": 1.5, "NM": 1.0}.get(mod, 1.0)

    # Parallel ingestion: Run Sunny SR, MinaCalc MSD, Feature extraction, and Biomech strain concurrently
    fut_sunny = _ISOR_POOL.submit(analyze_primary_sr, osu_path, mod=mod, rate=rate)
    fut_msd = _ISOR_POOL.submit(calculate_msd, osu_path, rate=_rate_msd)
    fut_feat = _ISOR_POOL.submit(extract_features, parsed)

    def _run_bio():
        try:
            bio_rows = build_bio_rows(parsed.get("rows", []), BIO_CONFIG["row_tolerance_ms"])
            bio_res = biomech_numeric(bio_rows, BIO_CONFIG)
            return bio_res, float(bio_res.get("bio_numeric", 0.0) or 0.0)
        except Exception:
            return None, 0.0

    fut_bio = _ISOR_POOL.submit(_run_bio)
    choke_info = extract_choke_and_local_strains(notes, drain_s)

    sunny_res = fut_sunny.result()
    msd_res = fut_msd.result() or {}
    features = fut_feat.result()
    bio_res, bio_numeric = fut_bio.result()

    if not sunny_res.get("success"):
        return {"error": f"sunny_error: {sunny_res.get('error')}"}

    raw_sr = float(sunny_res.get("sr", 0.0))
    sunny_strains = {
        "jbar_max": float(sunny_res.get("jbar_max", 0.0)),
        "pbar_max": float(sunny_res.get("pbar_max", 0.0)),
        "xbar_max": float(sunny_res.get("xbar_max", 0.0)),
        "abar_mean": float(sunny_res.get("abar_mean", 0.0))
    }

    # 4. Pattern Classification (Using robust cosine profile matching)
    sr_gate = raw_sr
    if sr_gate < 7.0:
        classification = classify_from_parsed(parsed)
        if classification.get("confidence", 0.0) < 0.10:
            classification = classify_family(sunny_res, features, domain)
    else:
        classification = classify_family(sunny_res, features, domain)

    family = classification.get("family", "hybrid")
    conf = classification.get("confidence", 0.70)

    # 5. Multidimensional Triangulation
    triang = compute_triangulated_rank(raw_sr, sunny_strains, choke_info, msd_res, family, conf,
                                       features_ref=features, bio_numeric=bio_numeric)

    # 5b. Calibrated ridge error-corrector (holdout-trained on the VSRG benchmark).
    # Gates: (1) LN-dominant charts keep the uncorrected ranking (out of the
#        corrected scope);
    #        (2) the model was trained on the 11-17+ band, so low-band charts
    #        (dp_base < 10.5) are not corrected (out-of-domain residuals).
    # Optional calibrated linear base (lin_base): the three projections are
    # recombined with per-skillset least-squares coefficients fitted on the
    # 11-17+ band (human criterion), blended C1 with the organic triangulation
    # via a sigmoid on the original base. Global and continuous.
    base = triang["dp"]
    if _RIDGE_MODEL and _RIDGE_MODEL.get("lin_base"):
        _lb = _RIDGE_MODEL["lin_base"]
        _coef = _lb.get(triang["sk_key"]) or _lb.get("general")
        _base_lin = (_coef[0] + _coef[1] * triang["dp_sr"] + _coef[2] * triang["dp_choke"]
                     + _coef[3] * triang["dp_msd"])
        _blend = _RIDGE_MODEL.get("lin_blend", {"k": 8.0, "x0": 11.0})
        _w = _sigmoid(triang["dp"], k=float(_blend.get("k", 8.0)), x0=float(_blend.get("x0", 11.0)))
        base = _w * _base_lin + (1.0 - _w) * triang["dp"]

    # Top-scale gate (continuous, C0): the VSRG benchmark never grades above
    # ~18.6 DP, so the lin_base blend compresses the official dan ladder at
    # the top (Zeta-Kappa packs live at 19.5-20.5 DP). Above the benchmark's
    # reachable range the base returns to the canonical SR ruler projection
    # (dp_sr), lifted only as far as the official Kappa threshold (20.2 DP),
    # so maps already past it are never overshot. Zero effect below 18.8 DP
    # (every VSRG benchmark map stays untouched).
    _GATE_LO, _GATE_HI, _TOP_TARGET = 18.8, 19.2, 20.2
    if base > _GATE_LO:
        _gt = min(1.0, (base - _GATE_LO) / (_GATE_HI - _GATE_LO))
        _gt = 0.5 * (1.0 - math.cos(math.pi * _gt))
        _lift = min(0.6, max(0.0, _TOP_TARGET - triang["dp_sr"]))
        base = _gt * (triang["dp_sr"] + _lift) + (1.0 - _gt) * base

    dp_ridge, ridge_corr = base, 0.0
    _ln_ratio = float(domain.get("ln_ratio", 0.0) or 0.0)
    # Dual models declare a low-band corrector; the high-band gate (>= 10.5)
    # opens only in that case (same LN protection).
    _dual_low = bool(_RIDGE_MODEL and _RIDGE_MODEL.get("dual"))
    if _ln_ratio <= 0.18 and (base >= 10.5 or (_dual_low and base >= 1.2)):
        _purity = float(features.get("stream_purity", 0.0) or 0.0)
        _subrank = {
            "sk_key": triang.get("sk_key", ""),
            "dp_sr": triang["dp_sr"], "dp_choke": triang["dp_choke"],
            "dp_msd": triang["dp_msd"], "mod_sr": triang["mod_sr"], "raw_sr": raw_sr,
            "ti": float(features.get("timing_irregularity", 0.0) or 0.0),
            "burst_ratio": float(choke_info.get("burst_ratio", 1.0) or 1.0),
            "dur": float(drain_s),
            "quad": float(features.get("quad_ratio", 0.0) or 0.0),
            "hand": float(features.get("hand_ratio", 0.0) or 0.0),
            "choke": float(choke_info.get("choke_10s_nps", 0.0) or 0.0),
            "msd_overall": float(msd_res.get("overall", 0.0) or 0.0) if msd_res else 0.0,
            "bpm": float(parsed.get("bpm", 0.0)),
        }
        dp_ridge, ridge_corr = apply_ridge_correction(base, bio_res, msd_res,
                                                      sunny_strains=sunny_strains, purity=_purity,
                                                      subrank=_subrank)
    # Top cap (continuous): the official ladder ends at Kappa (DP 20.5); the
    # dual/ridge stack may extrapolate slightly beyond it, so the final DP is
    # bounded there. No VSRG benchmark map is affected (max ~18.6 DP).
    dp_ridge = min(dp_ridge, 20.5)

    # Monotonicity floor (ported from the legacy pipeline): the Sunny
    # response can dip ("W" shape) at custom lazer rates, so the final DP is
    # floored against the nearest lower native anchor (0.75 / 1.0 / 1.5) to
    # keep the dan non-decreasing with the rate. Native rates are untouched.
    if rate is not None and round(float(rate), 4) not in (0.75, 1.0, 1.5):
        _r_val = round(float(rate), 4)
        if _r_val > 0.75:
            if _r_val >= 1.5:
                _anchor = 1.5
            elif _r_val >= 1.0:
                _anchor = 1.0
            else:
                _anchor = 0.75
            _res_a = analyze_beatmap_prototype(osu_path, mod="NM", rate=_anchor, parsed=parsed, domain=domain)
            if "error" not in _res_a and _res_a.get("dp") is not None:
                dp_ridge = max(dp_ridge, _res_a["dp"])
        else:
            # For rates below 0.75x, ensure it does not overshoot 0.75x while scaling downwards
            _res_a = analyze_beatmap_prototype(osu_path, mod="NM", rate=0.75, parsed=parsed, domain=domain)
            if "error" not in _res_a and _res_a.get("dp") is not None:
                dp_ridge = min(dp_ridge, _res_a["dp"])

    triang["dp"] = round(dp_ridge, 2)
    triang["ridge_correction"] = ridge_corr
    
    _tier_idx = min(len(DAN_ORDER) - 1, max(0, int(triang["dp"]) - 1))
    triang["dan_short"] = DAN_ORDER[_tier_idx]
    triang["dan_label"] = DAN_DISPLAY.get(DAN_ORDER[_tier_idx], DAN_ORDER[_tier_idx])
    
    _frac = round(triang["dp"] - math.floor(triang["dp"]), 2)
    _sublevel = "High"
    for q_lo, q_hi, label in SUBLEVEL_QUINTILES:
        if q_lo <= _frac <= q_hi:
            _sublevel = label
            break
    triang["sublevel"] = _sublevel

    return {
        "title": parsed.get("title", "Unknown"),
        "version": parsed.get("version", "Unknown"),
        "bpm": float(parsed.get("bpm", 0.0)),
        "drain_s": drain_s,
        "note_count": int(domain.get("note_count", 0)),
        "family": family,
        "family_confidence": conf,
        "raw_sr": raw_sr,
        "modulated_sr": triang["mod_sr"],
        "dp": triang["dp"],
        "dp_sr": triang["dp_sr"],
        "dp_choke": triang["dp_choke"],
        "dp_msd": triang["dp_msd"],
        "dp_bio": triang.get("dp_bio"),
        "bio_numeric": round(bio_numeric, 4) if bio_numeric else None,
        "sk_key": triang.get("sk_key", ""),
        "weights": triang.get("weights", {}),
        "dan_label": triang["dan_label"],
        "dan_short": triang["dan_short"],
        "sublevel": triang["sublevel"],
        "ridge_correction": triang.get("ridge_correction", 0.0),
        "choke_info": choke_info,
        "sunny_strains": sunny_strains,
        "strain_graph": sunny_res.get("strain_graph"),
        "msd": msd_res,
        "features": features
    }


# Public API alias
analyze_beatmap_isor = analyze_beatmap_prototype

