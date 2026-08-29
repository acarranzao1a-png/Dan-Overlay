"""
strain.py -- Biomechanical strain layer (original design and implementation).

Row model + strain streams with dual exponential decay (burst/sustain),
Shannon entropy over column distribution and mask transitions, weighted
quantile aggregation and section-based aggregation.

General physical principles (exponential decay; information entropy) applied
through an implementation built on the project's own parser. All taus,
weights and gates are calibratable parameters (BIO_CONFIG) fitted offline on
the project's own corpus (tune_offline.py), not copied from elsewhere.

The output is a "bio numeric" on the numeric difficulty scale (~0-20) that
the prototype engine projects through its rulers and weights as a 4th vector
(DP_Bio). No difficulty `if` gates: every gate is a continuous function.
"""

import math

# ── Calibratable configuration (values are starting points; the tuner varies them) ─

BIO_CONFIG = {
    "row_tolerance_ms": 2.0,
    "entropy_window_ms": 750.0,
    "nps_windows_ms": (250.0, 500.0, 1000.0, 4000.0),
    "section_ms": 400.0,
    "section_decay": 0.9,
    "section_ema_alpha": 0.15,
    "correction_clamp": 1.25,
    "raw_map": {"p02": 4.0, "p98": 7.5, "y0": -2.0, "y1": 20.0},
    # map bio numeric (0-21 raw scale) onto the engine SR scale (~1-14) before
    # projection through the skillset ruler (calibrated by the offline tuner)
    "bio_sr_map": {"p02": 2.0, "p98": 9.0, "y0": 1.0, "y1": 14.0},
    # streams: dual decay (burst/sustain) + blend
    "streams": {
        "speed":     {"burst_tau": 200.0,  "sustain_tau": 2500.0,  "burst_mix": 0.75},
        "hand":      {"burst_tau": 240.0,  "sustain_tau": 3000.0,  "burst_mix": 0.78},
        "jack":      {"burst_tau": 280.0,  "sustain_tau": 2500.0,  "burst_mix": 0.85},
        "chordjack": {"burst_tau": 260.0,  "sustain_tau": 3000.0,  "burst_mix": 0.80},
        "tech":      {"burst_tau": 450.0,  "sustain_tau": 3500.0,  "burst_mix": 0.70},
        "stamina":   {"burst_tau": 1200.0, "sustain_tau": 10000.0, "burst_mix": 0.58},
        "course":    {"burst_tau": 30000.0, "sustain_tau": 120000.0, "burst_mix": 0.35},
    },
    "stream_weights": {
        "speed": 0.22, "hand": 0.18, "jack": 0.16, "chordjack": 0.16,
        "tech": 0.12, "stamina": 0.11, "course": 0.05,
    },
    # r(dt) = min(cap, (base / max(16, dt + offset)) ** power)
    "r": {"base": 180.0, "offset": 40.0, "power": 1.08, "cap": 8.0},
    "r_same_col": {"base": 185.0, "offset": 35.0, "power": 1.18, "cap": 8.0},
    "r_fast_hand": {"base": 205.0, "offset": 45.0, "power": 1.05, "cap": 8.0},
    # input signal weights
    "speed_in": {"w_row": 0.55, "w_hand_max": 0.30, "w_hand_mean": 0.15},
    "jack_in": {"w_chord": 0.20, "w_anchor": 0.15, "anchor_ms": 220.0},
    "hand_in": {"w_base": 0.70, "w_rotation": 0.30, "r_hand": {"base": 180.0, "offset": 38.0, "power": 1.10, "cap": 8.0}},
    "chord_in": {"w_speed": 0.18, "w_same_hand": 0.22, "body_r": {"base": 150.0, "offset": 80.0, "power": 0.85, "cap": 8.0}},
    "chordjack_in": {"w_jack": 0.55, "w_overlap": 0.30, "w_hand": 0.15},
    "tech_in": {"w_chaos": 0.32, "w_entropy": 0.24, "w_transition": 0.24, "w_change": 0.20},
    "stamina_in": {"w_nps1k": 0.40, "w_nps4k": 0.35, "w_hand": 0.25, "hand_tau": 8000.0, "log_base": 24.0},
    "course_in": {"dur_gate": (90.0, 300.0), "break_damp": (0.006, 0.018), "w_break": 0.25},
    # stream aggregation
    "agg": {"q97": 0.30, "q90": 0.22, "tail": 0.18, "q75": 0.15, "power": 0.10, "q50": 0.05},
    "power_mean_p": 2.4,
    "tail_ratio": 0.04,
    # continuous corrections (gain 0 = disabled)
    "corrections": {
        "low_cj":     {"gain": 0.0, "chord": (0.48, 0.68), "overlap": (0.75, 1.25), "nps": (19.0, 23.0), "imbalance": (0.06, 0.12)},
        "high_stream": {"gain": 0.0, "rotation": (0.68, 0.86), "q10": (100.0, 130.0), "chord": (0.25, 0.42), "overlap": (0.65, 0.95)},
        "course_break": {"gain": 0.0, "dur": (240.0, 480.0), "break": (0.006, 0.018), "peak_gap": (0.35, 0.75), "nps": (12.0, 18.0)},
        "course_sustain": {"gain": 0.0, "dur": (240.0, 600.0), "break": (0.004, 0.012), "peak_gap": (0.15, 0.45), "nps": (15.0, 21.0)},
        "anchor_lift": {"gain": 0.0, "anchor": (0.18, 0.38), "fast_jack": (0.25, 0.55), "chord": (0.65, 0.85)},
        "hand_bias":  {"gain": 0.0, "bias": (0.25, 0.55), "nps": (12.0, 20.0)},
        "handstream_damp": {"gain": 0.0, "rotation": (0.60, 0.80), "overlap_inv": (0.60, 0.90), "chord": (0.30, 0.50)},
        "cj_over_damp":    {"gain": 0.0, "chord": (0.55, 0.75), "fast_jack_inv": (0.50, 0.70), "overlap": (0.40, 0.70)},
    },
}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _gate(x, a, b):
    """Rising gate: 0 below a, 1 above b (continuous)."""
    if b <= a:
        return 1.0 if x >= b else 0.0
    return _clamp((x - a) / (b - a), 0.0, 1.0)


def _inverse_gate(x, a, b):
    """Falling gate: 1 below a, 0 above b (continuous)."""
    return 1.0 - _gate(x, a, b)


def _strain_rate(dt, base, offset, power, cap):
    effective = max(16.0, dt + offset)
    value = (base / effective) ** power
    return min(cap, value) if math.isfinite(value) else 0.0


def _decay(state, input_val, dt, tau):
    delta = dt if dt > 0 else 0.0
    return state * math.exp(-delta / tau) + input_val


def _bitcount(mask):
    return bin(mask & 15).count("1")


def _entropy_from_counts(counts, total, normalizer):
    if total <= 0:
        return 0.0
    ent = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        ent -= p * math.log2(p)
    return _clamp(ent / normalizer, 0.0, 1.0)


def build_bio_rows(parsed_rows, tolerance_ms=2.0):
    """Rows from parser rows [{'t': ms, 'cols': (c, ...)}] merged at tolerance."""
    merged = []
    for r in parsed_rows:
        t = float(r["t"])
        cols = sorted(int(c) for c in r["cols"])
        if merged and abs(t - merged[-1]["t"]) <= tolerance_ms:
            prev = merged[-1]
            prev["cols"] = sorted(set(prev["cols"]) | set(cols))
        else:
            merged.append({"t": t, "cols": cols})
    rows = []
    for r in merged:
        mask = 0
        for c in r["cols"]:
            if 0 <= c <= 3:
                mask |= 1 << c
        if mask == 0:
            continue
        left = mask & 0b0011
        right = mask & 0b1100
        rows.append({
            "t": r["t"],
            "mask": mask,
            "row_size": _bitcount(mask),
            "left_count": _bitcount(left),
            "right_count": _bitcount(right),
            "hand_mask": [left, right],
        })
    return rows


def compute_activity_stats(rows):
    if len(rows) < 2:
        return {"inactive_ms": 0.0, "break_count": 0, "active_duration_s": 1.0,
                "break_density": 0.0, "avg_nps": float(len(rows))}
    inactive_ms = 0.0
    break_count = 0
    for i in range(1, len(rows)):
        gap = rows[i]["t"] - rows[i - 1]["t"]
        if gap > 1000:
            inactive_ms += gap - 1000
            break_count += 1
    duration_ms = max(1.0, rows[-1]["t"] - rows[0]["t"] - inactive_ms)
    active_s = duration_ms / 1000.0
    return {
        "inactive_ms": inactive_ms,
        "break_count": break_count,
        "active_duration_s": active_s,
        "break_density": break_count / max(active_s / 60.0, 1.0),
        "avg_nps": len(rows) / max(active_s, 1.0),
    }


def compute_nps_rows(rows, windows):
    starts = [0] * len(windows)
    end = 0
    times = [r["t"] for r in rows]
    n = len(times)
    for i, row in enumerate(rows):
        while end < n and times[end] <= row["t"] + 1e-9:
            end += 1
        for w, window_ms in enumerate(windows):
            min_time = row["t"] - window_ms
            while starts[w] < n and times[starts[w]] <= min_time:
                starts[w] += 1
            row.setdefault("nps", {})[window_ms] = (end - starts[w]) / (window_ms / 1000.0)


def compute_bio_curve(rows, cfg):
    streams_cfg = cfg["streams"]
    stream_names = list(cfg["stream_weights"].keys())
    states = {name: {"burst": 0.0, "sustain": 0.0} for name in stream_names}
    series = {name: [] for name in stream_names}

    r_cfg = cfg["r"]
    r_same = cfg["r_same_col"]
    r_fast = cfg["r_fast_hand"]
    r_hand = cfg["hand_in"]["r_hand"]
    body_r = cfg["chord_in"]["body_r"]

    last_col_time = [float("nan")] * 4
    last_hand_time = [float("nan")] * 2
    prev_hand_mask = [0, 0]
    hand_stamina = [0.0, 0.0]

    col_counts = [0] * 4
    dt_same_vals = []
    dt_hand_vals = []
    local_raw = []

    mask_counts = [0] * 16
    transition_counts = [0] * 256
    active_transitions = set()
    queue = []
    queue_head = 0
    mask_total = 0
    transition_total = 0

    prev_row_time = rows[0]["t"] - 1000 if rows else 0.0
    prev_dt_row = 1000.0
    prev_mask = 0

    dt_row_vals = []

    left_load = right_load = 0.0
    chord_rows = three_rows = 0
    overlap_events_total = 0
    rotation_total = 0
    eligible_hand = 0
    anchor_strength_total = 0.0
    fast_jack_strength_total = 0.0
    dt_hand_count = 0

    activity = compute_activity_stats(rows)
    windows = list(cfg["nps_windows_ms"])
    compute_nps_rows(rows, windows)

    for row in rows:
        t = row["t"]
        dt_row = max(1.0, t - prev_row_time)
        dt_row_vals.append(dt_row)
        mask = row["mask"]
        left = row["hand_mask"][0]
        right = row["hand_mask"][1]
        hand_masks = [left, right]

        dt_hand = [float("nan"), float("nan")]
        rotation = [0, 0]
        overlap_row = 0
        for h in range(2):
            if hand_masks[h] == 0:
                continue
            if math.isfinite(last_hand_time[h]):
                dt_hand[h] = max(1.0, t - last_hand_time[h])
                dt_hand_vals.append(dt_hand[h])
                dt_hand_count += 1
                eligible_hand += 1
                if prev_hand_mask[h] != 0 and (hand_masks[h] & prev_hand_mask[h]) == 0:
                    rotation[h] = 1.0
                    rotation_total += 1
                if (hand_masks[h] & prev_hand_mask[h]) != 0:
                    overlap_row += 1
        same_hand_overlap = overlap_row / 2.0
        overlap_events_total += same_hand_overlap

        dt_same = [float("nan")] * 4
        jack_max = 0.0
        anchor_row = 0.0
        for c in range(4):
            if (mask & (1 << c)) == 0:
                continue
            col_counts[c] += 1
            if math.isfinite(last_col_time[c]):
                dt_same[c] = max(1.0, t - last_col_time[c])
                dt_same_vals.append(dt_same[c])
                anchor_row = max(anchor_row, _inverse_gate(dt_same[c], cfg["jack_in"]["anchor_ms"], cfg["jack_in"]["anchor_ms"] + 40.0))
                fast_jack_strength_total += _inverse_gate(dt_same[c], 120.0, 150.0)
                jack_max = max(jack_max, _strain_rate(dt_same[c], r_same["base"], r_same["offset"], r_same["power"], r_same["cap"]))
        anchor_strength_total += anchor_row

        left_load += row["left_count"]
        right_load += row["right_count"]
        if row["row_size"] >= 2:
            chord_rows += 1
        if row["row_size"] >= 3:
            three_rows += 1

        mask_counts[mask] += 1
        mask_total += 1
        transition_code = -1
        if prev_mask:
            transition_code = (prev_mask << 4) | mask
            transition_counts[transition_code] += 1
            transition_total += 1
            active_transitions.add(transition_code)
        queue.append((t, mask, transition_code))
        while queue_head < len(queue) and queue[queue_head][0] < t - cfg["entropy_window_ms"]:
            old_t, old_mask, old_code = queue[queue_head]
            mask_counts[old_mask] -= 1
            mask_total -= 1
            if old_code >= 0:
                transition_counts[old_code] -= 1
                if transition_counts[old_code] == 0:
                    active_transitions.discard(old_code)
                transition_total -= 1
            queue_head += 1

        # Fast entropy over active non-zero subsets
        if mask_total > 0:
            ent_m = 0.0
            for m in range(16):
                c = mask_counts[m]
                if c > 0:
                    p = c / mask_total
                    ent_m -= p * math.log2(p)
            entropy_mask = _clamp(ent_m / 4.0, 0.0, 1.0)
        else:
            entropy_mask = 0.0

        if transition_total > 0 and active_transitions:
            ent_t = 0.0
            for code in active_transitions:
                c = transition_counts[code]
                if c > 0:
                    p = c / transition_total
                    ent_t -= p * math.log2(p)
            entropy_transition = _clamp(ent_t / 8.0, 0.0, 1.0)
        else:
            entropy_transition = 0.0

        row_chord = (row["row_size"] - 1) / 3.0
        same_hand_chord = (max(0, row["left_count"] - 1) + max(0, row["right_count"] - 1)) / 2.0

        hand_rates = []
        for h in range(2):
            if hand_masks[h] == 0:
                continue
            hdt = dt_hand[h] if math.isfinite(dt_hand[h]) else 1000.0
            rate = _strain_rate(hdt, r_hand["base"], r_hand["offset"], r_hand["power"], r_hand["cap"])
            hand_rates.append(rate)
            hand_stamina[h] = _decay(hand_stamina[h], rate, hdt, cfg["stamina_in"]["hand_tau"])
        for h in range(2):
            if hand_masks[h] == 0:
                hand_stamina[h] = _decay(hand_stamina[h], 0.0, dt_row, cfg["stamina_in"]["hand_tau"])

        hand_max = max(hand_rates) if hand_rates else 0.0
        hand_mean = sum(hand_rates) / len(hand_rates) if hand_rates else 0.0

        speed_in = (
            cfg["speed_in"]["w_row"] * _strain_rate(dt_row, r_cfg["base"], r_cfg["offset"], r_cfg["power"], r_cfg["cap"])
            + cfg["speed_in"]["w_hand_max"] * hand_max
            + cfg["speed_in"]["w_hand_mean"] * hand_mean
        )
        jack_in = jack_max * (1.0 + cfg["jack_in"]["w_chord"] * row_chord + cfg["jack_in"]["w_anchor"] * anchor_row)
        hand_in = 0.0
        for h in range(2):
            if hand_masks[h] == 0:
                continue
            hdt = dt_hand[h] if math.isfinite(dt_hand[h]) else 1000.0
            base_rate = _strain_rate(hdt, r_hand["base"], r_hand["offset"], r_hand["power"], r_hand["cap"])
            fast_rate = _strain_rate(hdt, r_fast["base"], r_fast["offset"], r_fast["power"], r_fast["cap"])
            hand_in = max(hand_in, cfg["hand_in"]["w_base"] * base_rate + cfg["hand_in"]["w_rotation"] * rotation[h] * fast_rate)

        body = max(0, row["row_size"] - 2) * _strain_rate(dt_row, body_r["base"], body_r["offset"], body_r["power"], body_r["cap"])
        chord_in = row_chord * (1.0 + cfg["chord_in"]["w_speed"] * speed_in) + cfg["chord_in"]["w_same_hand"] * same_hand_chord + body
        chordjack_in = row_chord * (
            cfg["chordjack_in"]["w_jack"] * jack_in
            + cfg["chordjack_in"]["w_overlap"] * same_hand_overlap
            + cfg["chordjack_in"]["w_hand"] * hand_in
        )
        rhythm_chaos = min(2.0, abs(math.log2((dt_row + 24.0) / (prev_dt_row + 24.0)))) / 2.0 if prev_mask else 0.0
        tech_in = (
            cfg["tech_in"]["w_chaos"] * rhythm_chaos
            + cfg["tech_in"]["w_entropy"] * entropy_mask
            + cfg["tech_in"]["w_transition"] * entropy_transition
            + cfg["tech_in"]["w_change"] * (1.0 if mask != prev_mask else 0.0)
        )
        nps1k = row["nps"].get(1000.0, 0.0) or 0.0
        nps4k = row["nps"].get(4000.0, 0.0) or 0.0
        log_base = cfg["stamina_in"]["log_base"]
        stamina_in = (
            cfg["stamina_in"]["w_nps1k"] * math.log1p(nps1k) / math.log(log_base)
            + cfg["stamina_in"]["w_nps4k"] * math.log1p(nps4k) / math.log(log_base)
            + cfg["stamina_in"]["w_hand"] * max(hand_stamina)
        )
        d1, d2 = cfg["course_in"]["dur_gate"]
        b1, b2 = cfg["course_in"]["break_damp"]
        course_in = stamina_in * _gate(activity["active_duration_s"], d1, d2) * (1.0 - cfg["course_in"]["w_break"] * _gate(activity["break_density"], b1, b2))

        inputs = {
            "speed": speed_in, "hand": hand_in, "jack": jack_in, "chordjack": chordjack_in,
            "tech": tech_in, "stamina": stamina_in, "course": course_in,
        }
        for name in stream_names:
            sc = streams_cfg[name]
            st = states[name]
            st["burst"] = _decay(st["burst"], inputs[name], dt_row, sc["burst_tau"])
            st["sustain"] = _decay(st["sustain"], inputs[name], dt_row, sc["sustain_tau"])
            series[name].append(sc["burst_mix"] * st["burst"] + (1.0 - sc["burst_mix"]) * st["sustain"])

        raw = sum(cfg["stream_weights"][name] * series[name][-1] for name in stream_names)
        local_raw.append(raw)

        for c in range(4):
            if (mask & (1 << c)) != 0:
                last_col_time[c] = t
        for h in range(2):
            if hand_masks[h] != 0:
                last_hand_time[h] = t
                prev_hand_mask[h] = hand_masks[h]

        prev_row_time = t
        prev_dt_row = dt_row
        prev_mask = mask

    if local_raw:
        sorted_raw = sorted(local_raw)
        q97_local = _quantile(sorted_raw, 0.97)
        q75_local = _quantile(sorted_raw, 0.75)
        peak_to_sustain_gap = _clamp((q97_local - q75_local) / max(q97_local, 1e-6), 0.0, 1.0)
    else:
        peak_to_sustain_gap = 0.0

    # ── Sustained-density and timing-texture summary ──────────────────────────────
    # Rolling-NPS and interval percentiles expose the sustained density level
    # (flatness) and the speed texture so the meta-layer can condition its
    # correction. Continuous functions only.
    nps1k_sorted = sorted((row.get("nps", {}).get(1000.0, 0.0) or 0.0) for row in rows)
    nps4k_sorted = sorted((row.get("nps", {}).get(4000.0, 0.0) or 0.0) for row in rows)
    q50_1k = _quantile(nps1k_sorted, 0.50)
    q75_1k = _quantile(nps1k_sorted, 0.75)
    q90_1k = _quantile(nps1k_sorted, 0.90)
    q97_1k = _quantile(nps1k_sorted, 0.97)
    log_nps_vals = [math.log1p(max(0.0, v)) / math.log(cfg["stamina_in"]["log_base"]) for v in nps1k_sorted]
    dt_row_sorted = sorted(dt_row_vals)
    dt_hand_sorted = sorted(dt_hand_vals)
    dt_same_sorted = sorted(dt_same_vals)
    sustain_stats = {
        "nps1k_q50": q50_1k,
        "nps1k_q75": q75_1k,
        "nps1k_q90": q90_1k,
        "nps4k_q50": _quantile(nps4k_sorted, 0.50),
        "nps4k_q75": _quantile(nps4k_sorted, 0.75),
        "nps4k_q90": _quantile(nps4k_sorted, 0.90),
        "nps1k_flatness": _clamp(q50_1k / max(q97_1k, 1e-6), 0.0, 1.0),
        "log_nps1k_mean": sum(log_nps_vals) / max(len(log_nps_vals), 1),
        "dt_row_q25": _quantile(dt_row_sorted, 0.25),
        "dt_row_q50": _quantile(dt_row_sorted, 0.50),
        "dt_row_q75": _quantile(dt_row_sorted, 0.75),
        "dt_hand_q25": _quantile(dt_hand_sorted, 0.25),
        "dt_hand_median": _quantile(dt_hand_sorted, 0.50),
        "dt_same_q25": _quantile(dt_same_sorted, 0.25),
        "dt_same_median": _quantile(dt_same_sorted, 0.50),
    }

    stats = {
        **activity,
        "chord_rate": chord_rows / max(len(rows), 1),
        "three_rate": three_rows / max(len(rows), 1),
        "overlap_rate": overlap_events_total / max(len(rows), 1),
        "rotation_rate": rotation_total / max(eligible_hand, 1),
        "same_hand_q10": _quantile(sorted(dt_hand_vals), 0.10) if dt_hand_vals else 0.0,
        "fast_jack_rate": fast_jack_strength_total / max(len(dt_same_vals), 1),
        "anchor_rate": anchor_strength_total / max(len(rows), 1),
        "anchor_imbalance": (max(col_counts) - min(col_counts)) / max(len(rows), 1) if rows else 0.0,
        "hand_bias": abs(left_load - right_load) / max(left_load, right_load, 1e-6),
        "peak_to_sustain_gap": peak_to_sustain_gap,
        **sustain_stats,
    }
    return {"series": series, "local_raw": local_raw, "stats": stats, "n_rows": len(rows)}


def _quantile(sorted_vals, q):
    if len(sorted_vals) == 0:
        return 0.0
    t = q * (len(sorted_vals) - 1)
    lo = int(t)
    hi = min(len(sorted_vals) - 1, lo + 1)
    w = t - lo
    return float(sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w)


def _summarize(values, cfg):
    if not values:
        return {"aggregate": 0.0}
    import numpy as np
    sorted_vals = np.sort(np.asarray(values, dtype=float))
    n = len(sorted_vals)
    q50 = _quantile(sorted_vals, 0.50)
    q75 = _quantile(sorted_vals, 0.75)
    q90 = _quantile(sorted_vals, 0.90)
    q97 = _quantile(sorted_vals, 0.97)
    tail_count = max(1, math.ceil(n * cfg["tail_ratio"]))
    tail_mean = float(np.mean(sorted_vals[n - tail_count:]))
    p = cfg["power_mean_p"]
    power_mean = float(np.mean(sorted_vals ** p) ** (1.0 / p))
    agg = (cfg["agg"]["q97"] * q97 + cfg["agg"]["q90"] * q90
           + cfg["agg"]["tail"] * tail_mean + cfg["agg"]["q75"] * q75
           + cfg["agg"]["power"] * power_mean + cfg["agg"]["q50"] * q50)
    return {"q50": q50, "q75": q75, "q90": q90, "q97": q97,
            "tail_mean": tail_mean, "power_mean": power_mean, "aggregate": agg}


def _section_aggregate(rows, local_raw, cfg):
    if not rows or not local_raw:
        return 0.0
    first_t = rows[0]["t"]
    section_max = {}
    smoothed = local_raw[0]
    for i, row in enumerate(rows):
        section = max(0, int((row["t"] - first_t) / cfg["section_ms"]))
        raw = local_raw[i]
        smoothed += cfg["section_ema_alpha"] * (raw - smoothed)
        section_max[section] = max(section_max.get(section, 0.0), smoothed)
    values = sorted((v for v in section_max.values() if v > 0), reverse=True)
    if not values:
        return 0.0
    weight = 1.0
    total = 0.0
    weight_total = 0.0
    for v in values:
        total += v * weight
        weight_total += weight
        weight *= cfg["section_decay"]
    return total / weight_total


def compute_corrections(stats, cfg):
    c = cfg["corrections"]
    total = 0.0
    details = {}
    for name, spec in c.items():
        gain = spec.get("gain", 0.0)
        if gain == 0.0:
            details[name] = 0.0
            continue
        val = 1.0
        if "chord" in spec:
            val *= _gate(stats["chord_rate"], *spec["chord"])
        if "overlap" in spec:
            val *= _gate(stats["overlap_rate"], *spec["overlap"])
        if "overlap_inv" in spec:
            val *= _inverse_gate(stats["overlap_rate"], *spec["overlap_inv"])
        if "nps" in spec:
            val *= (1.0 - _gate(stats["avg_nps"], *spec["nps"]))
        if "imbalance" in spec:
            val *= (1.0 - _gate(stats["anchor_imbalance"], *spec["imbalance"]))
        if "rotation" in spec:
            val *= _gate(stats["rotation_rate"], *spec["rotation"])
        if "q10" in spec:
            val *= _inverse_gate(stats["same_hand_q10"], *spec["q10"])
        if "dur" in spec:
            val *= _gate(stats["active_duration_s"], *spec["dur"])
        if "break" in spec:
            val *= _gate(stats["break_density"], *spec["break"])
        if "peak_gap" in spec:
            val *= _gate(stats["peak_to_sustain_gap"], *spec["peak_gap"])
        if "anchor" in spec:
            val *= _gate(stats["anchor_rate"], *spec["anchor"])
        if "fast_jack" in spec:
            val *= _gate(stats["fast_jack_rate"], *spec["fast_jack"])
        if "fast_jack_inv" in spec:
            val *= _inverse_gate(stats["fast_jack_rate"], *spec["fast_jack_inv"])
        if "bias" in spec:
            val *= _gate(stats["hand_bias"], *spec["bias"])
        details[name] = gain * val
        total += details[name]
    return {"details": details, "total": _clamp(total, -cfg["correction_clamp"], cfg["correction_clamp"])}


def biomech_numeric(rows, cfg=None):
    """Full pipeline: rows -> curve -> aggregated numeric (~0-20 scale)."""
    cfg = cfg if cfg is not None else BIO_CONFIG
    if not rows:
        return {"bio_numeric": 1.0, "raw_agg": 0.0, "details": {}}
    curve = compute_bio_curve(rows, cfg)
    weighted_agg = 0.0
    summaries = {}
    for name in cfg["stream_weights"]:
        s = _summarize(curve["series"][name], cfg)
        summaries[name] = s
        weighted_agg += cfg["stream_weights"][name] * s["aggregate"]
    section_agg = _section_aggregate(rows, curve["local_raw"], cfg)
    raw_agg = 0.80 * weighted_agg + 0.20 * section_agg
    log_raw = math.log1p(max(0.0, raw_agg))
    rm = cfg["raw_map"]
    pre_numeric = _clamp(rm["y0"] + (log_raw - rm["p02"]) / max(1e-9, rm["p98"] - rm["p02"]) * (rm["y1"] - rm["y0"]), -2.5, 21.0)
    corrections = compute_corrections(curve["stats"], cfg)
    numeric = _clamp(pre_numeric + corrections["total"], -2.0, 20.0)
    return {
        "bio_numeric": round(numeric, 4),
        "pre_numeric": round(pre_numeric, 4),
        "raw_agg": round(raw_agg, 4),
        "correction_total": round(corrections["total"], 4),
        "corrections": corrections["details"],
        "summaries": summaries,
        "stats": curve["stats"],
    }
