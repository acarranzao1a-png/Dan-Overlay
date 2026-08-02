# feature_extractor.py -- Structural features of a chart from parsed dict
# Input:  dict de parsear_osu_v2()
# Output: dict containing features for classifier + rank_engine

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict


def _nps_windows(notes, window_ms=500, stride_ms=250):
    """Compute NPS in overlapping windows across the chart.

    Uses bisect for O(n + m) total instead of O(n * m) brute force.
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
    t = t_min
    while t <= t_max:
        lo = t - half
        hi = t + half
        count = bisect_right(times, hi) - bisect_left(times, lo)
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
        while t <= t_max:
            lo = t
            hi = t + _WINDOW_ENTROPY_MS
            # Count notes per column in this window
            col_counts_w = defaultdict(int)
            total_w = 0
            # Use running index for efficiency
            for j in range(ni, len(notes_sorted)):
                nt, nc = notes_sorted[j]
                if nt < lo:
                    continue
                if nt > hi:
                    break
                col_counts_w[int(nc)] += 1
                total_w += 1
            if total_w >= 4:  # minimum notes for meaningful entropy
                # Shannon entropy over column distribution
                h = 0.0
                for cnt in col_counts_w.values():
                    if cnt > 0:
                        p = cnt / total_w
                        h -= p * math.log2(p)
                entropies.append(h)
            t += _ENTROPY_STRIDE_MS
            # Advance running index
            while ni < len(notes_sorted) and notes_sorted[ni][0] < lo:
                ni += 1
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
    }


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
