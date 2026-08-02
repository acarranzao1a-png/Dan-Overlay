import math
import os
import sys
from collections import defaultdict

import numpy as np

# Ensure this package's directory is on sys.path so that the vendored
# osu_file_parser (Daniel's version, different from Sunny's) can be found.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import osu_file_parser as osu_parser

# --- Constants ---

BREAK_ZERO_THRESHOLD_MS = 400
GRAPH_RESAMPLE_INTERVAL_MS = 100
SMOOTH_SIGMA_MS = 800


# --- Helper Functions ---

def gaussian_filter1d(data, sigma, mode="constant", cval=0.0):
    kernel_radius = int(4 * sigma + 0.5)
    x = np.arange(-kernel_radius, kernel_radius + 1)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    if mode == "constant":
        padded = np.pad(data, kernel_radius, mode="constant", constant_values=cval)
    else:
        padded = np.pad(data, kernel_radius, mode=mode)
    return np.convolve(padded, kernel, mode="valid")


def cumulative_sum(x, f):
    """Vectorised exact cumulative integral of piecewise-constant f on sorted x."""
    F = np.zeros(len(x))
    F[1:] = np.cumsum(f[:-1] * np.diff(x))
    return F


def smooth_on_corners(x, f, window, scale=1.0, mode="sum"):
    """Vectorised sliding-window integral of piecewise-constant f."""
    x = np.asarray(x, dtype=float)
    f = np.asarray(f, dtype=float)
    F = cumulative_sum(x, f)

    a = np.clip(x - window, x[0], x[-1])
    b = np.clip(x + window, x[0], x[-1])

    def _query_vec(q_arr):
        idx = np.searchsorted(x, q_arr) - 1
        idx = np.clip(idx, 0, len(x) - 2)
        return F[idx] + f[idx] * (q_arr - x[idx])

    val = _query_vec(b) - _query_vec(a)

    if mode == "avg":
        span = b - a
        return np.where(span > 0, val / span, 0.0)
    return scale * val


def interp_values(new_x, old_x, old_vals):
    return np.interp(new_x, old_x, old_vals)


def step_interp(new_x, old_x, old_vals):
    indices = np.searchsorted(old_x, new_x, side="right") - 1
    indices = np.clip(indices, 0, len(old_vals) - 1)
    return old_vals[indices]


def rescale_high(sr):
    if sr <= 9:
        return sr
    return 9 + (sr - 9) / 1.2


# --- Preprocessing ---

def preprocess_file(file_path, mod):
    p_obj = osu_parser.parser(file_path)
    p_obj.process()
    p = p_obj.get_parsed_data()

    note_seq = []
    for i in range(len(p[1])):
        k = p[1][i]
        h = p[2][i]
        if mod == "DT":
            h = int(math.floor(h * 2 / 3))
        elif mod == "HT":
            h = int(math.floor(h * 4 / 3))
        note_seq.append((k, h))

    x = 0.3 * ((64.5 - math.ceil(p[5] * 3)) / 500) ** 0.5
    x = min(x, 0.6 * (x - 0.09) + 0.09)
    note_seq.sort(key=lambda tup: (tup[1], tup[0]))

    note_dict = defaultdict(list)
    for tup in note_seq:
        note_dict[tup[0]].append(tup)

    K = p[0]
    T = max(n[1] for n in note_seq) + 1

    # Build per-column lists indexed 0…K-1 (empty list for unused columns)
    note_seq_by_column = [note_dict.get(k, []) for k in range(K)]

    return x, K, T, note_seq, note_seq_by_column


# --- Corner Computation ---

def get_corners(T, note_seq):
    corners_base = set()
    for _, h in note_seq:
        corners_base.update([h, h + 501, h - 499, h + 1])
    corners_base.update([0, T])
    corners_base = sorted(s for s in corners_base if 0 <= s <= T)

    corners_A = set()
    for _, h in note_seq:
        corners_A.update([h, h + 1000, h - 1000])
    corners_A.update([0, T])
    corners_A = sorted(s for s in corners_A if 0 <= s <= T)

    all_corners = sorted(set(corners_base) | set(corners_A))
    return (
        np.array(all_corners, dtype=float),
        np.array(corners_base, dtype=float),
        np.array(corners_A, dtype=float),
    )


# --- Key Usage ---

def get_key_usage(K, T, note_seq, base_corners):
    key_usage = {k: np.zeros(len(base_corners), dtype=bool) for k in range(K)}
    for k, h in note_seq:
        start = max(h - 150, 0)
        end = min(h + 150, T - 1)
        li = np.searchsorted(base_corners, start, side="left")
        ri = np.searchsorted(base_corners, end, side="left")
        key_usage[k][li:ri] = True
    return key_usage


def get_key_usage_400(K, T, note_seq, base_corners):
    key_usage_400 = {k: np.zeros(len(base_corners), dtype=float) for k in range(K)}
    for k, h in note_seq:
        start = max(h, 0)
        li = np.searchsorted(base_corners, start - 400, side="left")
        ri = np.searchsorted(base_corners, start + 400, side="left")
        mid = np.searchsorted(base_corners, start, side="left")

        key_usage_400[k][mid] += 3.75
        for idx_range in [np.arange(li, mid), np.arange(mid + 1, ri)]:
            key_usage_400[k][idx_range] += 3.75 - 3.75 / 400 ** 2 * (base_corners[idx_range] - start) ** 2
    return key_usage_400


# --- Difficulty Components ---

def compute_anchor(K, key_usage_400, base_corners):
    counts = np.stack([key_usage_400[k] for k in range(K)], axis=1)
    counts = np.sort(counts, axis=1)[:, ::-1]

    nonzero_mask = counts > 0
    n_nz = nonzero_mask.sum(axis=1)

    c0 = counts[:, :-1]
    c1 = counts[:, 1:]
    safe_c0 = np.where(c0 > 0, c0, 1.0)
    ratio = np.where(c0 > 0, c1 / safe_c0, 0.0)
    weight = 1 - 4 * (0.5 - ratio) ** 2

    pair_valid = nonzero_mask[:, :-1] & nonzero_mask[:, 1:]
    walk = np.sum(np.where(pair_valid, c0 * weight, 0.0), axis=1)
    max_walk = np.sum(np.where(pair_valid, c0, 0.0), axis=1)

    raw_anchor = np.where(n_nz > 1, walk / np.maximum(max_walk, 1e-9), 0.0)
    return 1 + np.minimum(raw_anchor - 0.18, 5 * (raw_anchor - 0.22) ** 3)


def compute_Jbar(K, T, x, note_seq_by_column, base_corners):
    def jack_nerfer(delta):
        return 1 - 7e-5 * (0.15 + np.abs(delta - 0.08)) ** (-4)

    J_ks = {k: np.zeros(len(base_corners)) for k in range(K)}
    delta_ks = {k: np.full(len(base_corners), 1e9) for k in range(K)}

    for k in range(K):
        notes = note_seq_by_column[k]
        if len(notes) < 2:
            continue
        starts = np.array([n[1] for n in notes[:-1]], dtype=float)
        ends = np.array([n[1] for n in notes[1:]], dtype=float)
        deltas = 0.001 * (ends - starts)
        vals = deltas ** -1 * (deltas + 0.11 * x ** 0.25) ** -1 * jack_nerfer(deltas)

        for start, end, delta, val in zip(starts, ends, deltas, vals):
            li = np.searchsorted(base_corners, start, side="left")
            ri = np.searchsorted(base_corners, end, side="left")
            if ri > li:
                J_ks[k][li:ri] = val
                delta_ks[k][li:ri] = delta

    Jbar_ks = {
        k: smooth_on_corners(base_corners, J_ks[k], window=500, scale=0.001, mode="sum")
        for k in range(K)
    }

    Jbar_stack = np.stack([Jbar_ks[k] for k in range(K)], axis=0)
    delta_stack = np.stack([delta_ks[k] for k in range(K)], axis=0)
    weights = 1.0 / delta_stack
    num = np.sum(np.maximum(Jbar_stack, 0) ** 5 * weights, axis=0)
    den = np.sum(weights, axis=0)
    Jbar = (num / np.maximum(den, 1e-9)) ** 0.2

    return delta_ks, Jbar


def compute_Xbar(K, T, x, note_seq_by_column, active_columns, base_corners):
    cross_matrix = [
        [-1],
        [0.075, 0.075],
        [0.125, 0.05, 0.125],
        [0.125, 0.125, 0.125, 0.125],
        [0.175, 0.25, 0.05, 0.25, 0.175],
        [0.175, 0.25, 0.175, 0.175, 0.25, 0.175],
        [0.225, 0.35, 0.25, 0.05, 0.25, 0.35, 0.225],
        [0.225, 0.35, 0.25, 0.225, 0.225, 0.25, 0.35, 0.225],
        [0.275, 0.45, 0.35, 0.25, 0.05, 0.25, 0.35, 0.45, 0.275],
        [0.275, 0.45, 0.35, 0.25, 0.275, 0.275, 0.25, 0.35, 0.45, 0.275],
        [0.325, 0.55, 0.45, 0.35, 0.25, 0.05, 0.25, 0.35, 0.45, 0.55, 0.325],
    ]
    cross_coeff = cross_matrix[K]
    X_ks = {k: np.zeros(len(base_corners)) for k in range(K + 1)}
    fast_cross = {k: np.zeros(len(base_corners)) for k in range(K + 1)}

    for k in range(K + 1):
        if k == 0:
            notes_in_pair = note_seq_by_column[0]
        elif k == K:
            notes_in_pair = note_seq_by_column[K - 1]
        else:
            notes_in_pair = sorted(
                note_seq_by_column[k - 1] + note_seq_by_column[k], key=lambda t: t[1]
            )

        for i in range(1, len(notes_in_pair)):
            start = notes_in_pair[i - 1][1]
            end = notes_in_pair[i][1]
            li = np.searchsorted(base_corners, start, side="left")
            ri = np.searchsorted(base_corners, end, side="left")
            if ri <= li:
                continue

            delta = 0.001 * (notes_in_pair[i][1] - notes_in_pair[i - 1][1])
            val = 0.16 * max(x, delta) ** -2

            left_inactive = (k - 1) not in active_columns[li] and (k - 1) not in active_columns[ri]
            right_inactive = k not in active_columns[li] and k not in active_columns[ri]
            if left_inactive or right_inactive:
                val *= 1 - cross_coeff[k]

            X_ks[k][li:ri] = val
            fast_cross[k][li:ri] = max(0, 0.4 * max(delta, 0.06, 0.75 * x) ** -2 - 80)

    # Vectorised X_base: replaces O(corners * K) Python loop with numpy ops
    X_ks_arr = np.stack([X_ks[k] for k in range(K + 1)], axis=0)   # (K+1, corners)
    coeff_arr = np.array(cross_coeff)[:, np.newaxis]                 # (K+1, 1)
    X_base = np.sum(X_ks_arr * coeff_arr, axis=0)                   # (corners,)

    fc_arr = np.stack([fast_cross[k] for k in range(K + 1)], axis=0)
    for k in range(K):
        X_base += np.sqrt(fc_arr[k] * cross_coeff[k] * fc_arr[k + 1] * cross_coeff[k + 1])

    return smooth_on_corners(base_corners, X_base, window=500, scale=0.001, mode="sum")


def compute_Pbar(K, T, x, note_seq, anchor, base_corners):
    def stream_booster(delta):
        bpm = np.clip(7.5 / delta, 0, 420)
        primary = 0.10 / (1 + np.exp(-0.06 * (bpm - 175)))
        secondary = np.where(
            (bpm >= 200) & (bpm <= 350),
            0.30 * (1 - np.exp(-0.02 * (bpm - 200))),
            0.0,
        )
        return 1 + primary + secondary

    P_step = np.zeros(len(base_corners))

    for i in range(len(note_seq) - 1):
        h_l = note_seq[i][1]
        h_r = note_seq[i + 1][1]
        delta_time = h_r - h_l

        if delta_time < 1e-9:
            spike = 1000 * (0.02 * (4 / x - 24)) ** 0.25
            li = np.searchsorted(base_corners, h_l, side="left")
            ri = np.searchsorted(base_corners, h_l, side="right")
            if ri > li:
                P_step[li:ri] += spike
            continue

        li = np.searchsorted(base_corners, h_l, side="left")
        ri = np.searchsorted(base_corners, h_r, side="left")
        if ri <= li:
            continue

        delta = 0.001 * delta_time
        b_val = stream_booster(delta)
        base_inc = (0.08 * x ** -1 * (1 - 24 * x ** -1 * (x / 6) ** 2)) ** 0.25

        if delta < 2 * x / 3:
            inc = delta ** -1 * (0.08 * x ** -1 * (1 - 24 * x ** -1 * (delta - x / 2) ** 2)) ** 0.25 * max(b_val, 1)
        else:
            inc = delta ** -1 * base_inc * max(b_val, 1)

        seg_anchor = anchor[li:ri]
        P_step[li:ri] += np.minimum(inc * seg_anchor, np.maximum(inc, inc * 2 - 10))

    return smooth_on_corners(base_corners, P_step, window=500, scale=0.001, mode="sum")


def compute_Abar(K, T, x, note_seq_by_column, active_columns, delta_ks, A_corners, base_corners):
    dks = {k: np.zeros(len(base_corners)) for k in range(K - 1)}
    for i in range(len(base_corners)):
        cols = active_columns[i]
        for j in range(len(cols) - 1):
            k0, k1 = cols[j], cols[j + 1]
            dks[k0][i] = abs(delta_ks[k0][i] - delta_ks[k1][i]) + 0.4 * max(
                0, max(delta_ks[k0][i], delta_ks[k1][i]) - 0.11
            )

    A_step = np.ones(len(A_corners))
    bc_idx = np.clip(np.searchsorted(base_corners, A_corners), 0, len(base_corners) - 1)

    for i in range(len(A_corners)):
        idx = bc_idx[i]
        cols = active_columns[idx]
        for j in range(len(cols) - 1):
            k0, k1 = cols[j], cols[j + 1]
            d_val = dks[k0][idx]
            dk0, dk1 = delta_ks[k0][idx], delta_ks[k1][idx]
            if d_val < 0.02:
                A_step[i] *= min(0.75 + 0.5 * max(dk0, dk1), 1)
            elif d_val < 0.07:
                A_step[i] *= min(0.65 + 5 * d_val + 0.5 * max(dk0, dk1), 1)

    return smooth_on_corners(A_corners, A_step, window=250, mode="avg")


def compute_C_and_Ks(K, T, note_seq, key_usage, base_corners):
    note_hit_times = np.array(sorted(n[1] for n in note_seq), dtype=float)

    lo = np.searchsorted(note_hit_times, base_corners - 500, side="left")
    hi = np.searchsorted(note_hit_times, base_corners + 500, side="left")
    C_step = (hi - lo).astype(float)

    Ks_step = np.maximum(
        np.stack([key_usage[k] for k in range(K)], axis=0).sum(axis=0), 1
    ).astype(float)

    return C_step, Ks_step


# --- Graph Post-Processing ---

def _apply_proximity_envelope(all_corners, D_all, note_seq):
    if not note_seq:
        return D_all.copy()

    note_times = np.sort(np.array([float(h) for _, h in note_seq]))
    PROXIMITY_FADE_MS = 500.0

    idx = np.searchsorted(note_times, all_corners)
    d_after = np.abs(note_times[np.clip(idx, 0, len(note_times) - 1)] - all_corners)
    d_before = np.abs(note_times[np.clip(idx - 1, 0, len(note_times) - 1)] - all_corners)
    d = np.minimum(d_after, d_before)

    envelope = 0.5 * (1.0 + np.cos(np.pi * np.clip(d / PROXIMITY_FADE_MS, 0.0, 1.0)))
    return D_all * envelope


def smooth_D_for_graph(all_corners, D_all, note_seq):
    note_times = np.array(sorted(float(h) for _, h in note_seq), dtype=float)

    t_start = float(all_corners[0])
    t_end = float(all_corners[-1])
    uniform_t = np.arange(t_start, t_end + GRAPH_RESAMPLE_INTERVAL_MS, GRAPH_RESAMPLE_INTERVAL_MS, dtype=float)

    if len(note_times) > 0:
        idx = np.searchsorted(note_times, uniform_t)
        idx_after = np.clip(idx, 0, len(note_times) - 1)
        idx_before = np.clip(idx - 1, 0, len(note_times) - 1)
        dist = np.minimum(np.abs(uniform_t - note_times[idx_before]), np.abs(uniform_t - note_times[idx_after]))
        break_mask = dist > BREAK_ZERO_THRESHOLD_MS
    else:
        break_mask = np.zeros(len(uniform_t), dtype=bool)

    uniform_D = np.interp(uniform_t, all_corners, D_all)
    uniform_D[break_mask] = 0.0

    sigma_samples = SMOOTH_SIGMA_MS / GRAPH_RESAMPLE_INTERVAL_MS
    uniform_result = gaussian_filter1d(uniform_D, sigma=sigma_samples, mode="constant", cval=0.0)
    uniform_result[break_mask] = 0.0

    return np.interp(all_corners, uniform_t, uniform_result)


# --- Main Entry Points ---

def calculate(file_path, mod):
    x, K, T, note_seq, note_seq_by_column = preprocess_file(file_path, mod)
    all_corners, base_corners, A_corners = get_corners(T, note_seq)

    key_usage = get_key_usage(K, T, note_seq, base_corners)
    active_columns = [[k for k in range(K) if key_usage[k][i]] for i in range(len(base_corners))]
    key_usage_400 = get_key_usage_400(K, T, note_seq, base_corners)
    anchor = compute_anchor(K, key_usage_400, base_corners)

    delta_ks, Jbar = compute_Jbar(K, T, x, note_seq_by_column, base_corners)
    Jbar = interp_values(all_corners, base_corners, Jbar)

    Xbar = compute_Xbar(K, T, x, note_seq_by_column, active_columns, base_corners)
    Xbar = interp_values(all_corners, base_corners, Xbar)

    Pbar = compute_Pbar(K, T, x, note_seq, anchor, base_corners)
    Pbar = interp_values(all_corners, base_corners, Pbar)

    Abar = compute_Abar(K, T, x, note_seq_by_column, active_columns, delta_ks, A_corners, base_corners)
    Abar = interp_values(all_corners, A_corners, Abar)

    C_step, Ks_step = compute_C_and_Ks(K, T, note_seq, key_usage, base_corners)
    C_arr = step_interp(all_corners, base_corners, C_step)
    Ks_arr = step_interp(all_corners, base_corners, Ks_step)

    S_all = (
        (0.4 * (Abar ** (3 / Ks_arr) * np.minimum(Jbar, 8 + 0.85 * Jbar)) ** 1.5) +
        (0.6 * (Abar ** (2 / 3) * (0.8 * Pbar)) ** 1.5)
    ) ** (2 / 3)
    T_all = (Abar ** (3 / Ks_arr) * Xbar) / (Xbar + S_all + 1)
    D_all = 2.7 * (S_all ** 0.5) * (T_all ** 1.5) + S_all * 0.27

    gaps = np.empty_like(all_corners, dtype=float)
    gaps[0] = (all_corners[1] - all_corners[0]) / 2.0
    gaps[-1] = (all_corners[-1] - all_corners[-2]) / 2.0
    gaps[1:-1] = (all_corners[2:] - all_corners[:-2]) / 2.0

    effective_weights = C_arr * gaps
    sorted_indices = np.argsort(D_all)
    D_sorted = D_all[sorted_indices]
    w_sorted = effective_weights[sorted_indices]

    cum_weights = np.cumsum(w_sorted)
    norm_cum_weights = cum_weights / cum_weights[-1]

    target_percentiles = np.array([0.945, 0.935, 0.925, 0.915, 0.845, 0.835, 0.825, 0.815])
    indices = np.searchsorted(norm_cum_weights, target_percentiles, side="left")

    percentile_93 = np.mean(D_sorted[indices[:4]])
    percentile_83 = np.mean(D_sorted[indices[4:8]])
    weighted_mean = (np.sum(D_sorted ** 5 * w_sorted) / np.sum(w_sorted)) ** 0.2

    SR = 0.88 * percentile_93 * 0.25 + 0.94 * percentile_83 * 0.2 + weighted_mean * 0.55
    total_notes = len(note_seq)
    SR *= total_notes / (total_notes + 60)
    SR = rescale_high(SR) * 0.975

    D_pre = _apply_proximity_envelope(all_corners, D_all, note_seq)
    D_graph = smooth_D_for_graph(all_corners, D_pre, note_seq)

    return (
        SR,
        all_corners,
        D_graph,
        {
            "Pressing Intensity": Pbar,
            "Unevenness": Abar,
            "Same-Column Pressure": Jbar,
            "Cross-Column Pressure": Xbar,
        },
    )


def factor_averages(times, factors):
    times = np.asarray(times, dtype=float)
    names = list(factors.keys())
    matrix = np.stack([factors[n] for n in names], axis=0)
    integrals = np.trapezoid(matrix, times, axis=1)
    duration = times[-1] - times[0]
    return {n: float(integrals[i] / duration) for i, n in enumerate(names)}


def parse_hitobjects(file_path, mod="NM"):
    p_obj = osu_parser.parser(file_path)
    p_obj.process()
    p = p_obj.get_parsed_data()

    hitobjects = []
    for i in range(len(p[1])):
        x = p[1][i]
        time = p[2][i]
        if mod == "DT":
            time *= 2 / 3
        elif mod == "HT":
            time *= 4 / 3
        hitobjects.append({"x": x, "time": time})

    return hitobjects