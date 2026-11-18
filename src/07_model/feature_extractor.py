# feature_extractor.py -- Structural features of a chart from parsed dict
# Input:  dict de parsear_osu_v2()
# Output: dict containing features for classifier + rank_engine

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict


def _nps_windows(notes, window_ms=500, stride_ms=250):
    """Compute NPS in overlapping windows across the chart.

    Uses a two-pointer sliding window for pure O(n + m) linear total.
    Returns list of (center_ms, nps) for all windows with at least 1 note.
    """
    if not notes:
        return []
    times = [nt for nt, _ in notes]
    t_min = times[0]
    t_max = times[-1]
    half = window_ms // 2
    duration_s = window_ms / 1000.0
    results = []
    n = len(times)
    left_idx = 0
    right_idx = 0
    t = t_min
    while t <= t_max:
        lo = t - half
        hi = t + half
        while left_idx < n and times[left_idx] < lo:
            left_idx += 1
        while right_idx < n and times[right_idx] <= hi:
            right_idx += 1
        count = right_idx - left_idx
        nps = count / duration_s if duration_s > 0 else 0.0
        results.append((t, nps))
        t += stride_ms
    return results


def _cv(values):
    """Coefficient of variation (std/mean, 0 if mean ≈ 0)."""
    if len(values) < 2:
        return 0.0
    mu = sum(values) / len(values)
    if mu < 1e-6:
        return 0.0
    var = sum((v - mu) ** 2 for v in values) / len(values)
    return math.sqrt(var) / mu


def extract_features(parsed):
    """Extracts structural features from a parsed dict.

    Parameters
    ----------
    parsed : dict
        Output from parsear_osu_v2().

    Returns
    -------
    dict containing keys:
        stream_purity       float  — fraction of 1-note rows
        jump_ratio          float  — fraction of 2-note rows
        hand_ratio          float  — fraction of 3-note rows
        quad_ratio          float  — fraction of 4-note rows
        jack_ratio          float  — fraction of notes that are jacks (same col, ≤180ms)
        jack_density        float  — fraction of notes that are strict jacks (≤120ms)
        vibro_density       float  — fraction of notes that are vibros (≤80ms)
        anchor_ratio        float  — column usage variance indicator
        minijack_ratio      float  — minijacks in the 100-200ms range
        density_cv          float  — CV of NPS in 500ms windows
        transition_var      float  — mean variance of active column changes
        nps_p90             float  — windowed NPS 90th percentile
        nps_sustained_top30 float  — mean NPS of the top 30% densest windows
        nps_active_ratio    float  — fraction of windows with NPS > 2.0
        nps_active_cv       float  — CV of NPS in active windows (NPS > 2.0)
        bpm                 float  — from parsed dict
        duration_s          float  — drain_time_s from parsed dict
    """
    notes = parsed.get("notes", [])  # [(time_ms, col), ...]
    rows = parsed.get("rows", [])    # [{"t": ms, "cols": (c1,...)}]
    bpm = float(parsed.get("bpm", 120.0) or 120.0)
    drain_s = float(parsed.get("drain_time_s", 0.0) or 0.0)
    note_count = len(notes)
    row_count = len(rows)

    # Sort notes by time
    notes_sorted = sorted(notes, key=lambda n: n[0])

    # ── Row-based chord ratios ──────────────────────────────────────

    if row_count > 0:
        sizes = [len(r["cols"]) for r in rows]
        stream_purity = sum(1 for s in sizes if s == 1) / row_count
        jump_ratio = sum(1 for s in sizes if s == 2) / row_count
        hand_ratio = sum(1 for s in sizes if s == 3) / row_count
        quad_ratio = sum(1 for s in sizes if s >= 4) / row_count
    else:
        stream_purity = jump_ratio = hand_ratio = quad_ratio = 0.0

    # ── Jack detection (per-column consecutive pair analysis) ──────

    # Group notes by column
    by_col = defaultdict(list)
    for t, c in notes_sorted:
        by_col[int(c)].append(int(t))

    jack_threshold_ms = 180       # broad jack: same col ≤ 180ms
    jack_strict_ms = 120          # dense jack: ≤ 120ms
    vibro_threshold_ms = 80       # vibro: ≤ 80ms

    jack_hits = 0
    jack_strict_hits = 0
    vibro_hits = 0
    minijack_hits = 0
    total_pairs = 0

    for col, times in by_col.items():
        col_sorted = sorted(times)
        for i in range(1, len(col_sorted)):
            gap = col_sorted[i] - col_sorted[i - 1]
            total_pairs += 1
            if gap <= vibro_threshold_ms:
                vibro_hits += 1
                jack_strict_hits += 1
                jack_hits += 1
            elif gap <= jack_strict_ms:
                jack_strict_hits += 1
                jack_hits += 1
            elif gap <= jack_threshold_ms:
                jack_hits += 1
            if 100 <= gap <= 200:
                minijack_hits += 1

    if note_count > 0 and total_pairs > 0:
        jack_ratio = jack_hits / total_pairs
        jack_density = jack_strict_hits / total_pairs
        vibro_density = vibro_hits / total_pairs
    else:
        jack_ratio = jack_density = vibro_density = 0.0

    minijack_ratio = minijack_hits / max(total_pairs, 1)

    # ── Anchor ratio (dominant column excess) ─────────────────────

    if note_count > 0:
        col_counts = {c: len(ts) for c, ts in by_col.items()}
        max_col_count = max(col_counts.values()) if col_counts else 0
        num_cols = len(col_counts) or 4
        expected_per_col = note_count / num_cols
        # Anchor ratio: how much the dominant column exceeds equal distribution
        anchor_ratio = max(0.0, (max_col_count - expected_per_col) / max(note_count, 1))
    else:
        anchor_ratio = 0.0

    # ── Transition variance (column layout complexity) ─────────────

    if len(rows) >= 2:
        transition_diffs = []
        for i in range(1, len(rows)):
            prev_cols = set(rows[i - 1]["cols"])
            curr_cols = set(rows[i]["cols"])
            union = len(prev_cols | curr_cols)
            inter = len(prev_cols & curr_cols)
            # Jaccard distance: 1 - overlap/union
            if union > 0:
                transition_diffs.append(1.0 - inter / union)
        transition_var = sum(transition_diffs) / len(transition_diffs) if transition_diffs else 0.0
    else:
        transition_var = 0.0

    # ── NPS windows (density profile) ─────────────────────────────

    nps_data = _nps_windows(notes_sorted, window_ms=500, stride_ms=250)
    nps_values = [v for _, v in nps_data] if nps_data else [0.0]

    # Downsample NPS time-series for the overlay density chart (max 200 points)
    _NPS_CHART_MAX = 200
    if nps_data and len(nps_data) > _NPS_CHART_MAX:
        _step = len(nps_data) / _NPS_CHART_MAX
        nps_curve = [[int(nps_data[int(i * _step)][0]), round(nps_data[int(i * _step)][1], 2)]
                     for i in range(_NPS_CHART_MAX)]
    else:
        nps_curve = [[int(ms), round(v, 2)] for ms, v in nps_data] if nps_data else []

    density_cv = _cv(nps_values)

    nps_sorted = sorted(nps_values)
    if nps_sorted:
        p90_idx = int(0.90 * len(nps_sorted))
        nps_p90 = nps_sorted[min(p90_idx, len(nps_sorted) - 1)]
        p50_idx = int(0.50 * len(nps_sorted))
        nps_p50 = nps_sorted[min(p50_idx, len(nps_sorted) - 1)]
        p95_idx = int(0.95 * len(nps_sorted))
        nps_p95 = nps_sorted[min(p95_idx, len(nps_sorted) - 1)]
    else:
        nps_p90 = nps_p50 = nps_p95 = 0.0

    top30_cutoff = int(0.70 * len(nps_sorted))
    top30_vals = nps_sorted[top30_cutoff:] if nps_sorted else []
    nps_sustained_top30 = sum(top30_vals) / len(top30_vals) if top30_vals else 0.0

    active_threshold = 2.0
    active_vals = [v for v in nps_values if v > active_threshold]
    nps_active_ratio = len(active_vals) / max(len(nps_values), 1)
    nps_active_cv = _cv(active_vals) if len(active_vals) >= 2 else 0.0

    # ── Phase 2 composite features ────────────────────────────────

    # stamina_index: sustained NPS normalized by SR proxy, × log(duration)
    # Raw sustained_nps × duration is too correlated with SR (r=0.93).
    # Normalizing by nps_p90 makes it a "sustained effort fraction" independent of absolute NPS.
    # High stamina_index = long map with uniformly high density (stamina demand)
    if drain_s > 0 and nps_p90 > 0:
        sustained_fraction = nps_sustained_top30 / nps_p90  # how sustained vs peak (~0.7-1.0)
        stamina_index = sustained_fraction * math.log(1 + drain_s / 90.0)
    else:
        stamina_index = 0.0

    # burst_ratio: nps_p95 / nps_p50 — captures how "spikey" the density profile is
    burst_ratio = nps_p95 / max(nps_p50, 0.01)

    # pattern_irregularity: CV of per-window column entropy
    # High = patterns change frequently (tech), Low = consistent patterns (stream/jack)
    _WINDOW_ENTROPY_MS = 2000
    _ENTROPY_STRIDE_MS = 1000
    if notes_sorted and drain_s > 0:
        t_min = notes_sorted[0][0]
        t_max = notes_sorted[-1][0]
        entropies = []
        t = t_min
        ni = 0  # running note index
        n_notes = len(notes_sorted)
        while t <= t_max:
            lo = t
            hi = t + _WINDOW_ENTROPY_MS
            # Advance start pointer
            while ni < n_notes and notes_sorted[ni][0] < lo:
                ni += 1
            # Count notes per column in this window
            col_counts_w = [0, 0, 0, 0]
            total_w = 0
            for j in range(ni, n_notes):
                nt, nc = notes_sorted[j]
                if nt > hi:
                    break
                c_int = int(nc)
                if 0 <= c_int <= 3:
                    col_counts_w[c_int] += 1
                    total_w += 1
            if total_w >= 4:  # minimum notes for meaningful entropy
                # Shannon entropy over column distribution
                h = 0.0
                for cnt in col_counts_w:
                    if cnt > 0:
                        p = cnt / total_w
                        h -= p * math.log2(p)
                entropies.append(h)
            t += _ENTROPY_STRIDE_MS
        pattern_irregularity = _cv(entropies) if len(entropies) >= 2 else 0.0
    else:
        pattern_irregularity = 0.0

    # timing_irregularity: CV of inter-row time gaps
    # Tech/dumpstream maps have irregular gaps between rows (notes don't fall
    # on a consistent beat grid), while stream/stamina/speed have steady gaps.
    # High CV = irregular timing = strong tech signal.
    if row_count >= 3:
        row_times = [r["t"] for r in rows]
        inter_row_gaps = [row_times[i] - row_times[i - 1] for i in range(1, len(row_times))]
        timing_irregularity = _cv(inter_row_gaps) if inter_row_gaps else 0.0
    else:
        timing_irregularity = 0.0

    # chord_complexity: fraction of 3+ note rows × density amplification during chords
    # Captures handstream/dense chordjack signal orthogonal to SR
    frac_chords_3plus = hand_ratio + quad_ratio
    if frac_chords_3plus > 0 and row_count > 0 and nps_values:
        # Average NPS during rows with 3+ notes
        chord_times = set()
        for r in rows:
            if len(r["cols"]) >= 3:
                chord_times.add(r["t"])
        if chord_times:
            # Find NPS windows that overlap with chord timestamps
            nps_during_chords = []
            overall_nps_mean = sum(nps_values) / len(nps_values)
            for center_t, nps_val in nps_data:
                lo = center_t - 250
                hi = center_t + 250
                if any(lo <= ct <= hi for ct in chord_times):
                    nps_during_chords.append(nps_val)
            if nps_during_chords and overall_nps_mean > 0:
                density_amp = sum(nps_during_chords) / len(nps_during_chords) / overall_nps_mean
                chord_complexity = frac_chords_3plus * (1 + density_amp)
            else:
                chord_complexity = frac_chords_3plus
        else:
            chord_complexity = 0.0
    else:
        chord_complexity = 0.0

    return {
        "stream_purity":       round(stream_purity, 4),
        "jump_ratio":          round(jump_ratio, 4),
        "hand_ratio":          round(hand_ratio, 4),
        "quad_ratio":          round(quad_ratio, 4),
        "jack_ratio":          round(jack_ratio, 4),
        "jack_density":        round(jack_density, 4),
        "vibro_density":       round(vibro_density, 4),
        "anchor_ratio":        round(anchor_ratio, 4),
        "minijack_ratio":      round(minijack_ratio, 4),
        "density_cv":          round(density_cv, 4),
        "transition_var":      round(transition_var, 4),
        "nps_p50":             round(nps_p50, 3),
        "nps_p90":             round(nps_p90, 3),
        "nps_p95":             round(nps_p95, 3),
        "nps_sustained_top30": round(nps_sustained_top30, 3),
        "nps_active_ratio":    round(nps_active_ratio, 4),
        "nps_active_cv":       round(nps_active_cv, 4),
        "bpm":                 round(bpm, 2),
        "duration_s":          round(drain_s, 2),
        # Phase 2 composite features
        "stamina_index":       round(stamina_index, 4),
        "burst_ratio":         round(burst_ratio, 4),
        "pattern_irregularity": round(pattern_irregularity, 4),
        "timing_irregularity": round(timing_irregularity, 4),
        "chord_complexity":    round(chord_complexity, 4),
        "nps_curve":           nps_curve,
        # LN features (from note_events)
        **_extract_ln_features(parsed),
        # Column-level movement features (4K)
        **_extract_motion_features(parsed),
        # Multi-resolution, peak, per-hand and ergonomic blocks
        **_extract_multiscale(parsed),
        **_extract_peak_stats(parsed),
        **_extract_per_hand(parsed),
        **_extract_ergonomics(parsed),
    }


# ── Multi-resolution, peak, per-hand and ergonomic blocks ───────────────────
#
# The engine's remaining error is dispersion rather than offset: its bias is
# effectively zero while its exact rate lags the reference by several points.
# Narrowing dispersion needs signals the density statistics above do not carry,
# so these four blocks describe the chart at resolutions and from viewpoints the
# aggregate features cannot express:
#
#   multiscale   the same pattern statistics at four resolutions, reduced by a
#                peak percentile, because the hardest section sets the tier
#   peak         the shape of the per-second density distribution
#   per_hand     a chart is as hard as its weaker hand
#   ergonomics   what the fingers do: travel between columns, holds, cutting


def _row_arrays(parsed):
    rows = sorted((parsed.get("rows") or []), key=lambda r: r.get("t") or 0)
    times = [float(r.get("t") or 0.0) for r in rows]
    cols = [tuple(sorted(r.get("cols") or ())) for r in rows]
    return times, cols


def _pct(values, q):
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((q / 100.0) * (len(s) - 1)))))
    return float(s[idx])


def _extract_multiscale(parsed):
    """Pattern statistics at four resolutions, reduced by a peak percentile."""
    out = {}
    times, cols = _row_arrays(parsed)
    n = len(cols)
    scales = (8, 16, 32, 64)
    if n < 64:
        for w in scales:
            for name in ("chord", "jack", "hand", "anchor", "dens"):
                out["ms%d_%s_p95" % (w, name)] = 0.0
                out["ms%d_%s_p50" % (w, name)] = 0.0
        return out
    for w in scales:
        stride = max(1, w // 2)
        chord_v, jack_v, hand_v, anc_v, dens_v = [], [], [], [], []
        pairs = w - 1
        for s in range(0, n - w + 1, stride):
            seg = cols[s:s + w]
            chord_v.append(sum(len(c) for c in seg) / w)
            shared = 0
            anchor = 0
            for a, b in zip(seg, seg[1:]):
                if set(a) & set(b):
                    shared += 1
                    if a != b:
                        anchor += 1
            jack_v.append(shared / pairs)
            anc_v.append(anchor / pairs)
            hand_v.append(sum(1 for c in seg if len(c) >= 3) / w)
            dt = (times[s + w - 1] - times[s]) / 1000.0
            dens_v.append(sum(len(c) for c in seg) / dt if dt > 0.02 else 0.0)
        for name, vals in (("chord", chord_v), ("jack", jack_v), ("hand", hand_v),
                           ("anchor", anc_v), ("dens", dens_v)):
            out["ms%d_%s_p95" % (w, name)] = round(_pct(vals, 95), 4)
            out["ms%d_%s_p50" % (w, name)] = round(_pct(vals, 50), 4)
    return out


def _extract_peak_stats(parsed):
    """Shape of the per-second density distribution."""
    out = {"peak_p50": 0.0, "peak_p90": 0.0, "peak_p95": 0.0, "peak_p98": 0.0,
           "peak_max": 0.0, "peak_cv": 0.0, "peak_top10": 0.0, "peak_p95_over_mean": 0.0}
    times, cols = _row_arrays(parsed)
    if len(times) < 60:
        return out
    first, last = times[0], times[-1]
    span = (last - first) / 1000.0
    if span < 5.0:
        return out
    buckets = [0.0] * int(span) + [0.0]
    for t, c in zip(times, cols):
        idx = int((t - first) / 1000.0)
        if 0 <= idx < len(buckets):
            buckets[idx] += len(c)
    active = [b for b in buckets if b > 0]
    if len(active) < 10:
        return out
    mean = sum(active) / len(active)
    sd = math.sqrt(sum((b - mean) ** 2 for b in active) / len(active))
    total = sum(active)
    top = max(1, len(active) // 10)
    out["peak_p50"] = round(_pct(active, 50), 3)
    out["peak_p90"] = round(_pct(active, 90), 3)
    out["peak_p95"] = round(_pct(active, 95), 3)
    out["peak_p98"] = round(_pct(active, 98), 3)
    out["peak_max"] = round(max(active), 3)
    out["peak_cv"] = round(sd / mean, 4) if mean > 0 else 0.0
    out["peak_top10"] = round(sum(sorted(active)[-top:]) / total, 4) if total > 0 else 0.0
    out["peak_p95_over_mean"] = round(_pct(active, 95) / mean, 4) if mean > 0 else 0.0
    return out


def _extract_per_hand(parsed):
    """Left/right split: a chart is as hard as its weak hand."""
    keys = ("ph_dens_l", "ph_dens_r", "ph_chord_l", "ph_chord_r",
            "ph_jack_l", "ph_jack_r", "ph_imbalance", "ph_weak_dens",
            "ph_strong_dens", "ph_weak_jack", "ph_weak_chord",
            "ph_switch_rate", "ph_weak_over_strong")
    out = {k: 0.0 for k in keys}
    times, cols = _row_arrays(parsed)
    n = len(cols)
    if n < 60:
        return out
    span = (times[-1] - times[0]) / 1000.0
    if span < 5.0:
        return out
    notes_l = notes_r = chord_l = chord_r = 0
    jack_l = jack_r = switches = 0
    prev_l = prev_r = None
    for c in cols:
        left = [x for x in c if x < 2]
        right = [x for x in c if x >= 2]
        notes_l += len(left)
        notes_r += len(right)
        if len(left) >= 2:
            chord_l += 1
        if len(right) >= 2:
            chord_r += 1
        if prev_l is not None and set(left) & prev_l:
            jack_l += 1
        if prev_r is not None and set(right) & prev_r:
            jack_r += 1
        prev_l, prev_r = set(left), set(right)
        if left and right:
            continue
    for a, b in zip(cols, cols[1:]):
        if a and b and (a[0] < 2) != (b[0] < 2):
            switches += 1
    dens_l = notes_l / span
    dens_r = notes_r / span
    out["ph_dens_l"] = round(dens_l, 3)
    out["ph_dens_r"] = round(dens_r, 3)
    out["ph_chord_l"] = round(chord_l / n, 4)
    out["ph_chord_r"] = round(chord_r / n, 4)
    denom = max(1, n - 1)
    out["ph_jack_l"] = round(jack_l / denom, 4)
    out["ph_jack_r"] = round(jack_r / denom, 4)
    tot = notes_l + notes_r
    out["ph_imbalance"] = round(abs(notes_l - notes_r) / tot, 4) if tot else 0.0
    out["ph_weak_dens"] = round(min(dens_l, dens_r), 3)
    out["ph_strong_dens"] = round(max(dens_l, dens_r), 3)
    out["ph_weak_jack"] = round(min(out["ph_jack_l"], out["ph_jack_r"]), 4)
    out["ph_weak_chord"] = round(min(out["ph_chord_l"], out["ph_chord_r"]), 4)
    out["ph_switch_rate"] = round(switches / denom, 4)
    strong = max(dens_l, dens_r)
    out["ph_weak_over_strong"] = round(min(dens_l, dens_r) / strong, 4) if strong > 0 else 0.0
    return out


def _extract_ergonomics(parsed):
    """What the fingers do: travel between columns, holds, cutting."""
    keys = ("erg_travel_mean", "erg_travel_p95", "erg_travel_max",
            "erg_cut_rate", "erg_hold_ratio", "erg_release_density",
            "erg_same_col_rate", "erg_adjacent_rate")
    out = {k: 0.0 for k in keys}
    times, cols = _row_arrays(parsed)
    singles = [c[0] for c in cols if len(c) == 1]
    if len(singles) < 25:
        return out
    steps = [abs(b - a) for a, b in zip(singles, singles[1:])]
    if not steps:
        return out
    out["erg_travel_mean"] = round(sum(steps) / len(steps), 4)
    out["erg_travel_p95"] = round(_pct(steps, 95), 4)
    out["erg_travel_max"] = round(max(steps), 4)
    out["erg_cut_rate"] = round(sum(1 for s in steps if s >= 2) / len(steps), 4)
    out["erg_same_col_rate"] = round(sum(1 for s in steps if s == 0) / len(steps), 4)
    out["erg_adjacent_rate"] = round(sum(1 for s in steps if s == 1) / len(steps), 4)
    span = (times[-1] - times[0]) / 1000.0
    total = len(parsed.get("notes") or [])
    if span > 1.0 and total > 0:
        holds = int(parsed.get("ln_count") or 0)
        out["erg_hold_ratio"] = round(holds / total, 4)
        out["erg_release_density"] = round(holds / span, 4)
    return out


# ── Motion features ────────────────────────────────────────────────────────
#
# Adapted from mania-hub (https://github.com/aleju03/mania-hub), file
# algorithms/classification/motion-features.ts.
# MIT licence, copyright (c) 2026 aleju03.
#
# These describe what the hands do between consecutive rows, which aggregate
# density statistics cannot: two charts with identical NPS and stream purity can
# still be a cross-hand trill pattern and a plain stream.
#
# The window constants are kept identical to the reference so the definitions
# stay comparable.  No model, weight or output from that project is used here.

_MOTION_MIN_GAP_MS = 25.0
_MOTION_MAX_GAP_MS = 400.0
_MOTION_MIN_ROWS = 24
_MOTION_PACE_QUANTILE = 0.25
_MOTION_PACE_SLACK = 1.6
_MOTION_PACE_CONTEXT = 8
# Interval ratios that read as musical subdivisions of the beat.  Anything
# outside these is a rhythm break, which is one of tech's signatures.
_MOTION_MUSICAL_RATIOS = (1.0, 2.0, 0.5, 1.5, 2.0 / 3.0, 3.0, 1.0 / 3.0, 4.0, 0.25)

_MOTION_KEYS = (
    "motion_same_hand", "motion_minijack", "motion_anchor",
    "motion_one_hand_trill", "motion_cross_trill", "motion_roll4",
    "motion_rhythm_break", "motion_chord_swing", "motion_density_swing",
)


def _motion_hand(column):
    """0 for the left hand, 1 for the right (4K only)."""
    return 0 if column < 2 else 1


def _motion_ratio_is_musical(ratio):
    for target in _MOTION_MUSICAL_RATIOS:
        if abs(ratio - target) <= target * 0.08:
            return True
    return False


def _motion_at_pace(gaps):
    """Which gaps are played 'at pace', so slow sections do not dilute ratios.

    A gap counts when the local median gap sits within 1.6x the 25th percentile
    of all gaps: the chart is compared against its own fast sections, not
    against a global average.
    """
    if not gaps:
        return []
    valid = sorted(g for g in gaps if 0 < g <= _MOTION_MAX_GAP_MS)
    if not valid:
        return [False] * len(gaps)
    pace = valid[min(len(valid) - 1, int(len(valid) * _MOTION_PACE_QUANTILE))]
    limit = pace * _MOTION_PACE_SLACK
    out = []
    for i in range(len(gaps)):
        lo = max(0, i - _MOTION_PACE_CONTEXT)
        hi = min(len(gaps) - 1, i + _MOTION_PACE_CONTEXT)
        around = [gaps[j] for j in range(lo, hi + 1)
                  if 0 < gaps[j] <= _MOTION_MAX_GAP_MS]
        if not around:
            out.append(False)
            continue
        around.sort()
        out.append(around[len(around) // 2] <= limit)
    return out


def _extract_motion_features(parsed):
    """Hand/foot movement shares for 4K.  Zeros when not applicable."""
    out = {key: 0.0 for key in _MOTION_KEYS}
    try:
        if int(parsed.get("keycount_output") or 0) != 4:
            return out
    except (TypeError, ValueError):
        return out
    rows = sorted((parsed.get("rows") or []), key=lambda r: r.get("t") or 0)
    if len(rows) < _MOTION_MIN_ROWS:
        return out

    times = [float(r.get("t") or 0.0) for r in rows]
    cols = [tuple(sorted(r.get("cols") or ())) for r in rows]
    n = len(rows)
    gaps = [times[i + 1] - times[i] for i in range(n - 1)]
    in_pace = _motion_at_pace(gaps)

    def weight(gap):
        return 1.0 / max(gap, _MOTION_MIN_GAP_MS)

    pair_w = same_hand_w = minijack_w = anchor_w = chord_swing_w = 0.0
    trip_w = trill_w = cross_trill_w = 0.0
    quad_w = roll4_w = 0.0
    rhythm_w = rhythm_break_w = 0.0

    for i in range(n - 1):
        gap = gaps[i]
        if gap <= 0 or gap > _MOTION_MAX_GAP_MS or not in_pace[i]:
            continue
        w = weight(gap)
        a, b = cols[i], cols[i + 1]
        pair_w += w
        if len(a) != len(b):
            chord_swing_w += w
        if len(a) == 1 and len(b) == 1:
            ca, cb = a[0], b[0]
            if ca == cb:
                minijack_w += w
            elif _motion_hand(ca) == _motion_hand(cb):
                same_hand_w += w
        elif set(a) & set(b):
            identical = len(a) == len(b) and a == b
            if not identical:
                anchor_w += w

    for i in range(n - 2):
        g0, g1 = gaps[i], gaps[i + 1]
        if g0 <= 0 or g1 <= 0 or g0 > _MOTION_MAX_GAP_MS or g1 > _MOTION_MAX_GAP_MS:
            continue
        if not in_pace[i]:
            continue
        w = weight(max(g0, g1))
        rhythm_w += w
        if not _motion_ratio_is_musical(g1 / g0):
            rhythm_break_w += w
        a, b, c = cols[i], cols[i + 1], cols[i + 2]
        if len(a) != 1 or len(b) != 1 or len(c) != 1:
            continue
        trip_w += w
        ca, cb, cc = a[0], b[0], c[0]
        if ca == cc and ca != cb:
            if _motion_hand(ca) == _motion_hand(cb):
                trill_w += w
            else:
                cross_trill_w += w

    for i in range(n - 3):
        gs = (gaps[i], gaps[i + 1], gaps[i + 2])
        if any(g <= 0 or g > _MOTION_MAX_GAP_MS for g in gs) or not in_pace[i]:
            continue
        window = cols[i:i + 4]
        if any(len(c) != 1 for c in window):
            continue
        w = weight(max(gs))
        quad_w += w
        series = [c[0] for c in window]
        steps = [series[k + 1] - series[k] for k in range(3)]
        if all(s == 1 for s in steps) or all(s == -1 for s in steps):
            roll4_w += w

    first, last = times[0], times[-1]
    seconds = max(1, int(math.ceil((last - first) / 1000.0)))
    per_second = [0] * seconds
    for i in range(n):
        idx = min(seconds - 1, int((times[i] - first) / 1000.0))
        per_second[idx] += len(cols[i])
    active = [v for v in per_second if v > 0]
    if active:
        mean = sum(active) / len(active)
        if mean > 0:
            variance = sum((v - mean) ** 2 for v in active) / len(active)
            out["motion_density_swing"] = round(math.sqrt(variance) / mean, 4)

    def share(numerator, denominator):
        return round(numerator / denominator, 4) if denominator > 0 else 0.0

    out["motion_same_hand"] = share(same_hand_w, pair_w)
    out["motion_minijack"] = share(minijack_w, pair_w)
    out["motion_anchor"] = share(anchor_w, pair_w)
    out["motion_one_hand_trill"] = share(trill_w, trip_w)
    out["motion_cross_trill"] = share(cross_trill_w, trip_w)
    out["motion_roll4"] = share(roll4_w, quad_w)
    out["motion_rhythm_break"] = share(rhythm_break_w, rhythm_w)
    out["motion_chord_swing"] = share(chord_swing_w, pair_w)
    return out


# ── LN features ────────────────────────────────────────────────────────────

def _extract_ln_features(parsed):
    """Extract LN-specific structural features for LN family classification.

    These features are always computed (cheap) so the pipeline
    can route to the LN estimator without re-parsing the file.

    Keys:
        ln_ratio            float  — fraction of objects that are LNs
        hold_occupancy      float  — fraction of chart time covered by active holds
        ln_duration_mean_ms float  — mean LN hold duration in ms
        ln_duration_cv      float  — CV of LN hold durations (variety of hold lengths)
        simultaneous_hold   float  — fraction of LN starts that overlap ≥1 other active hold
        release_density     float  — ln_end events per second of drain time
        hold_chord_ratio    float  — fraction of LN starts in chord rows (≥2 simultaneous)
    """
    note_events = parsed.get("note_events", [])
    ln_ratio = float(parsed.get("ln_ratio", 0.0) or 0.0)
    drain_s = float(parsed.get("drain_time_s", 0.0) or 0.0)

    ln_starts = [e for e in note_events if e.get("event_type") == "ln_start"]

    if not ln_starts or drain_s < 1.0:
        return {
            "ln_ratio": round(ln_ratio, 4),
            "hold_occupancy": 0.0,
            "ln_duration_mean_ms": 0.0,
            "ln_duration_cv": 0.0,
            "simultaneous_hold": 0.0,
            "release_density": 0.0,
            "hold_chord_ratio": 0.0,
        }

    # Hold durations
    durations = [e["duration_ms"] for e in ln_starts if e.get("duration_ms", 0) > 0]
    ln_duration_mean_ms = sum(durations) / len(durations) if durations else 0.0
    ln_duration_cv = _cv(durations) if len(durations) >= 2 else 0.0

    # Hold occupancy: fraction of chart time with ≥1 active hold
    # Use a timeline sweep approach
    first_ms = parsed["notes"][0][0] if parsed.get("notes") else 0
    last_ms = parsed["notes"][-1][0] if parsed.get("notes") else 0
    chart_span_ms = max(last_ms - first_ms, 1)

    occupied_ms = 0
    events_sorted = []
    for e in ln_starts:
        s = e.get("ln_start_ms", 0)
        end = e.get("ln_end_ms", 0)
        if end > s:
            events_sorted.append((s, 1))
            events_sorted.append((end, -1))
    events_sorted.sort(key=lambda x: (x[0], x[1]))

    active = 0
    seg_start = 0
    for t, delta in events_sorted:
        if active > 0 and t > seg_start:
            occupied_ms += t - seg_start
        active += delta
        seg_start = t

    hold_occupancy = min(1.0, occupied_ms / chart_span_ms)

    # Simultaneous holds: fraction of LN starts that overlap another active hold
    # Sort starts by time and track active intervals
    starts_by_time = sorted(ln_starts, key=lambda e: e.get("ln_start_ms", 0))
    simultaneous_count = 0
    active_ends = []  # sorted list of end times of currently active holds
    for e in starts_by_time:
        s = e.get("ln_start_ms", 0)
        # Remove expired holds
        active_ends = [end for end in active_ends if end > s]
        if active_ends:
            simultaneous_count += 1
        active_ends.append(e.get("ln_end_ms", 0))
        active_ends.sort()
    simultaneous_hold = simultaneous_count / len(starts_by_time)

    # Release density: ln_end events per second
    ln_ends = [e for e in note_events if e.get("event_type") == "ln_end"]
    release_density = len(ln_ends) / drain_s if drain_s > 0 else 0.0

    # Hold-chord ratio: fraction of LN starts that share a row with another LN start
    from collections import Counter
    start_times = [e.get("ln_start_ms", 0) for e in ln_starts]
    time_counts = Counter(start_times)
    chorded = sum(1 for t in start_times if time_counts[t] >= 2)
    hold_chord_ratio = chorded / len(start_times) if start_times else 0.0

    return {
        "ln_ratio": round(ln_ratio, 4),
        "hold_occupancy": round(hold_occupancy, 4),
        "ln_duration_mean_ms": round(ln_duration_mean_ms, 1),
        "ln_duration_cv": round(ln_duration_cv, 4),
        "simultaneous_hold": round(simultaneous_hold, 4),
        "release_density": round(release_density, 3),
        "hold_chord_ratio": round(hold_chord_ratio, 4),
    }
