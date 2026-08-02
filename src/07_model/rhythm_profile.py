"""rhythm_profile.py — Pattern-based chart family classifier.

This classifier is based on the chart classification engine from
ManiaMapAnalyser (by Leo_Black).  The original bar-ratio classifier
(classifier.py) was unstable and misclassified charts at mid-tier SR
levels, so this pattern engine was adopted to improve calculation
accuracy.  It detects rhythmic textures (streams, jacks, chords,
coordination patterns) directly from note data and maps them to the
standard DanOverlay family taxonomy.

Unlike the bar-ratio classifier (classifier.py), this engine does NOT
depend on Sunny SR components (Jbar/Pbar/Xbar/Abar).  It works purely
from the parsed hit-object sequence, which makes it immune to SR
compression at mid-tier levels.
"""
from __future__ import annotations
from typing import List, Tuple, Dict, Optional, Set
import math
from collections import defaultdict


# ── Configuration ──────────────────────────────────────────────────
_PATTERN_CONFIG = {
    "stability_threshold": 5.0,
    "bpm_cluster_tolerance": 5.0,
    "important_cluster_ratio": 0.5,
    "jack_min_bpm": 90.0,
    "shield_max_beat_ratio": 0.25,
    "inverse_gap_tolerance_ms": 5.0,
    "inverse_min_filled_lanes": 3,
    "release_scan_rows": 4,
    "release_min_tail_rows": 4,
    "release_roll_points": 2,
    "release_full_match_rows": 5,
    "jack_context_window": 6,
    "jack_fallback_max_ms_per_beat": 185.0,
    "sv_speed_eps": 0.05,
    "sv_extreme_bpm_min": 20.0,
    "sv_extreme_bpm_max": 450.0,
    "sv_extreme_bpm_ratio": 4.0,
    "sv_amount_threshold": 2000.0,
}

# ── Rhythm names (maps to our family taxonomy) ─────────────────────
_PRIMARY_RHYTHM_WEIGHTS = {
    "linear_stream":   1.0 / 3.0,
    "harmonic_flow":    0.65,
    "anchor_burst":     0.90,
    "coordination":     0.75,
    "density":          0.90,
    "wildcard":         1.0,
}

# How pattern types map to our final families
_TEXTURE_TO_FAMILY = {
    "linear_stream":    "stream",
    "harmonic_flow":    "speed",
    "anchor_burst":     "jack",
    "coordination":     "tech",
    "density":          "stamina",
    "wildcard":         "tech",
}

# Specific sub-types and their family affinity
_SUB_TEXTURE_FAMILY = {
    # Stream subtypes
    "rolls":            "stream",
    "trills":           "tech",
    "mini_trills":      "tech",
    # Chord subtypes
    "chord_stream":     "speed",
    "split_trill":      "tech",
    "jump_trill":       "tech",
    "jumpstream":       "speed",
    "handstream":       "stamina",
    "double_jump":       "speed",
    "triple_jump":       "speed",
    "quad_stream":      "stamina",
    "light_chords":      "speed",
    "dense_chords":      "stamina",
    "chord_roll":       "tech",
    "brackets":         "tech",
    # Jack subtypes
    "long_jacks":        "jack",
    "chord_jacks":       "jack",
    "mini_jacks":        "jack",
    "gluts":            "jack",
    # Coordination
    "column_lock":      "tech",
    "shield":           "tech",
    "release":          "tech",
    # Density
    "inverse":          "tech",
    "js_density":       "speed",
    "hs_density":       "stamina",
    "ds_density":       "stamina",
    "dcs_density":      "stamina",
    "lcs_density":      "speed",
    # Wildcard
    "jack_wild":        "jack",
    "speed_wild":       "speed",
}


# ── Direction detection ────────────────────────────────────────────
def _hands_per_side(key_count: int) -> int:
    """Number of keys assigned to left hand for a given key-mode."""
    if key_count == 3: return 2
    if key_count == 4: return 2
    if key_count == 5: return 3
    if key_count == 6: return 3
    if key_count == 7: return 4
    if key_count == 8: return 4
    if key_count == 9: return 5
    if key_count == 10: return 5
    return max(1, key_count // 2)


def _is_same_hand(col_a: int, col_b: int, split: int) -> bool:
    if abs(col_a - col_b) != 1:
        return False
    return (col_a < split) == (col_b < split)


def _detect_flow(prev_cols: List[int], cur_cols: List[int]) -> Tuple[str, bool]:
    """Determine direction of movement and whether it is a roll."""
    if not prev_cols or not cur_cols:
        return "none", False
    pl, pr = prev_cols[0], prev_cols[-1]
    cl, cr = cur_cols[0], cur_cols[-1]
    dl, dr = cl - pl, cr - pr

    if dl > 0:
        direction = "right" if dr > 0 else "inward"
    elif dl < 0:
        direction = "left" if dr < 0 else "outward"
    elif dr < 0:
        direction = "inward"
    elif dr > 0:
        direction = "outward"
    else:
        direction = "none"

    is_roll = pl > cr or pr < cl
    return direction, is_roll


# ── Beat-frame construction (port of primitives.js) ────────────────
def _build_beat_frames(notes: List[Dict], key_count: int, bpm_timeline: List[Dict]) -> List[Dict]:
    """Convert raw notes into beat-frames with timing and column metadata.

    Each note dict must have: col (0-indexed column), time (ms), kind
    (one of 'tap', 'hold_head', 'hold_body', 'hold_tail').
    """
    if not notes:
        return []

    first_time = notes[0]["time"]
    left_keys = _hands_per_side(key_count)

    def _ms_per_beat_at(time_ms: float) -> float:
        if not bpm_timeline:
            return 500.0
        current = bpm_timeline[0].get("ms_per_beat", 500.0)
        for item in bpm_timeline:
            if item["time"] > time_ms:
                break
            current = item.get("ms_per_beat", 500.0)
        return current

    # Build first row from first note
    first_data = notes[0].get("data", [])
    previous_cols = [
        k for k in range(key_count)
        if k < len(first_data) and first_data[k] in ("tap", "hold_head")
    ]
    if not previous_cols:
        return []

    previous_time = first_time
    frames = []
    idx = 0

    for item in notes[1:]:
        t = item["time"]
        row_data = item.get("data", [])
        idx += 1

        tap_cols, head_cols, body_cols, tail_cols = [], [], [], []
        for k in range(key_count):
            if k >= len(row_data):
                continue
            kind = row_data[k]
            if kind == "tap":
                tap_cols.append(k)
            elif kind == "hold_head":
                head_cols.append(k)
            elif kind == "hold_body":
                body_cols.append(k)
            elif kind == "hold_tail":
                tail_cols.append(k)

        active_cols = tap_cols + head_cols
        if not active_cols and not head_cols and not body_cols and not tail_cols:
            continue

        direction = "none"
        is_roll = False
        jacks = 0

        if active_cols:
            direction, is_roll = _detect_flow(previous_cols, active_cols)
            prev_set = set(previous_cols)
            jacks = sum(1 for c in active_cols if c in prev_set)

        frames.append({
            "index": idx,
            "offset_ms": t - first_time,
            "ms_per_beat": (t - previous_time) * 4.0,
            "beat_length": _ms_per_beat_at(t),
            "active_count": len(active_cols),
            "jack_count": jacks,
            "direction": direction,
            "is_roll": is_roll,
            "key_count": key_count,
            "left_keys": left_keys,
            "head_cols": head_cols,
            "body_cols": body_cols,
            "tail_cols": tail_cols,
            "tap_cols": tap_cols,
            "raw_cols": active_cols,
        })

        if active_cols:
            previous_cols = active_cols
        previous_time = t

    return frames


# ── Pattern detectors ──────────────────────────────────────────────
def _detect_stream(frames: List[Dict]) -> int:
    """Linear stream: 5 consecutive single notes, no jacks, different start/end col."""
    if len(frames) < 5:
        return 0
    a, b, c, d, e = frames[:5]
    if (a["active_count"] == 1 and a["jack_count"] == 0 and
        b["active_count"] == 1 and b["jack_count"] == 0 and
        c["active_count"] == 1 and c["jack_count"] == 0 and
        d["active_count"] == 1 and d["jack_count"] == 0 and
        e["active_count"] == 1 and e["jack_count"] == 0):
        if a["raw_cols"][0] != e["raw_cols"][0]:
            return 5
    return 0


def _detect_anchor_burst(frames: List[Dict]) -> int:
    """Jack/anchor: first frame has same-column repeats at moderate speed."""
    if not frames:
        return 0
    f0 = frames[0]
    return 1 if f0["jack_count"] > 1 and f0["ms_per_beat"] < 2000 else 0


def _detect_harmonic_flow(frames: List[Dict]) -> int:
    """Chordstream: multi-note without jacks, followed by more chord content."""
    if len(frames) < 4:
        return 0
    a, b, c, d = frames[:4]
    if (a["active_count"] > 1 and a["jack_count"] == 0 and
        b["jack_count"] == 0 and c["jack_count"] == 0 and d["jack_count"] == 0):
        if b["active_count"] > 1 or c["active_count"] > 1 or d["active_count"] > 1:
            return 4
    return 0


def _detect_coordination(frames: List[Dict]) -> int:
    """LN-coordination: frame has hold-related activity."""
    if not frames:
        return 0
    a = frames[0]
    return 1 if a["head_cols"] or a["body_cols"] or a["tail_cols"] else 0


def _detect_density(frames: List[Dict]) -> int:
    """Dense-LN: starts with hold head."""
    if not frames:
        return 0
    return 1 if frames[0]["head_cols"] else 0


def _detect_wildcard(frames: List[Dict]) -> int:
    """Wildcard-LN: starts with hold head (same as density at core level)."""
    return _detect_density(frames)


# ── Specific subtype detectors (4K) ────────────────────────────────
def _sub_long_jacks(frames: List[Dict]) -> int:
    if len(frames) < 5: return 0
    a, b, c, d, e = frames[:5]
    if a["jack_count"] > 0 and b["jack_count"] > 0 and c["jack_count"] > 0 and d["jack_count"] > 0 and e["jack_count"] > 0:
        for col in a["raw_cols"]:
            if col in b["raw_cols"] and col in c["raw_cols"] and col in d["raw_cols"] and col in e["raw_cols"]:
                return 5
    return 0


def _sub_chord_jacks(frames: List[Dict]) -> int:
    if len(frames) < 2: return 0
    a, b = frames[:2]
    if a["active_count"] > 2 and b["active_count"] > 1 and b["jack_count"] >= 1:
        if b["active_count"] < a["active_count"] or b["jack_count"] < b["active_count"]:
            return 2
    return 0


def _sub_mini_jacks(frames: List[Dict]) -> int:
    if len(frames) < 2: return 0
    a, b = frames[:2]
    return 2 if a["jack_count"] > 0 and b["jack_count"] == 0 else 0


def _sub_handstream(frames: List[Dict]) -> int:
    if len(frames) < 4: return 0
    a, b, c, d = frames[:4]
    return 4 if a["active_count"] == 3 and a["jack_count"] == 0 and b["jack_count"] == 0 and c["jack_count"] == 0 and d["jack_count"] == 0 else 0


def _sub_jumpstream(frames: List[Dict]) -> int:
    if len(frames) < 4: return 0
    a, b, c, d = frames[:4]
    if a["active_count"] == 2 and a["jack_count"] == 0 and b["active_count"] == 1 and b["jack_count"] == 0 and c["jack_count"] == 0 and d["jack_count"] == 0:
        if c["active_count"] < 3 and d["active_count"] < 3: return 4
    return 0


def _sub_jump_trill(frames: List[Dict]) -> int:
    if len(frames) < 4: return 0
    a, b, c, d = frames[:4]
    return 4 if a["active_count"] == 2 and b["active_count"] == 2 and c["active_count"] == 2 and d["active_count"] == 2 and b["is_roll"] and c["is_roll"] and d["is_roll"] else 0


def _sub_split_trill(frames: List[Dict]) -> int:
    if len(frames) < 3: return 0
    a, b, c = frames[:3]
    return 3 if a["active_count"] == 2 and b["active_count"] == 2 and c["active_count"] == 2 and b["jack_count"] == 0 and c["jack_count"] == 0 and not b["is_roll"] and not c["is_roll"] else 0


def _sub_gluts(frames: List[Dict]) -> int:
    if len(frames) < 3: return 0
    a, b, c = frames[:3]
    if b["jack_count"] == 1 and c["jack_count"] == 1:
        for col in a["raw_cols"]:
            if col in b["raw_cols"] and col in c["raw_cols"]: return 0
        return 3
    return 0


def _sub_quad_stream(frames: List[Dict]) -> int:
    if len(frames) < 4: return 0
    a, _, c, d = frames[:4]
    return 4 if a["active_count"] == 4 and c["jack_count"] == 0 and d["jack_count"] == 0 else 0


def _sub_roll(frames: List[Dict]) -> int:
    if len(frames) < 3: return 0
    a, b, c = frames[:3]
    if a["active_count"] == 1 and b["active_count"] == 1 and c["active_count"] == 1:
        left = a["direction"] == "left" and b["direction"] == "left" and c["direction"] == "left"
        right = a["direction"] == "right" and b["direction"] == "right" and c["direction"] == "right"
        if left or right: return 3
    return 0


def _sub_trill(frames: List[Dict]) -> int:
    if len(frames) < 4: return 0
    a, b, c, d = frames[:4]
    if b["jack_count"] == 0 and c["jack_count"] == 0 and d["jack_count"] == 0:
        if str(a["raw_cols"]) == str(c["raw_cols"]) and str(b["raw_cols"]) == str(d["raw_cols"]):
            return 4
    return 0


def _sub_mini_trill(frames: List[Dict]) -> int:
    if len(frames) < 4: return 0
    a, b, c, d = frames[:4]
    if b["jack_count"] == 0 and c["jack_count"] == 0:
        if str(a["raw_cols"]) == str(c["raw_cols"]) and str(b["raw_cols"]) != str(d["raw_cols"]):
            return 4
    return 0


def _sub_column_lock(frames: List[Dict]) -> int:
    if len(frames) < 3: return 0
    split = frames[0]["left_keys"]
    ln_col = frames[0]["head_cols"][0] if frames[0]["head_cols"] else None
    if ln_col is None: return 0
    adj_cols = [c for c in [ln_col - 1, ln_col + 1] if 0 <= c < frames[0]["key_count"] and _is_same_hand(ln_col, c, split)]
    if not adj_cols: return 0
    for adj in adj_cols:
        hits = []
        for row in frames[:8]:
            if ln_col in row["body_cols"] and adj in row["tap_cols"]:
                hits.append(row["offset_ms"])
        if len(hits) < 3: continue
        bpms = [15000.0 / (hits[i+1] - hits[i]) if hits[i+1] > hits[i] else 90.0 for i in range(len(hits)-1)]
        if bpms and max(bpms) >= _PATTERN_CONFIG["jack_min_bpm"]:
            return 3
    return 0


def _sub_shield(frames: List[Dict]) -> int:
    if len(frames) < 2: return 0
    a, b = frames[:2]
    dt = b["offset_ms"] - a["offset_ms"]
    beat_limit = b["beat_length"] * _PATTERN_CONFIG["shield_max_beat_ratio"]
    if dt < 0 or dt > beat_limit: return 0
    for col in a["tap_cols"]:
        if col in b["head_cols"]: return 2
    for col in a["tail_cols"]:
        if col in b["tap_cols"]: return 2
    return 0


# ── Pattern matching engine ────────────────────────────────────────
_PRIMARY_DETECTORS = [
    ("linear_stream", _detect_stream),
    ("harmonic_flow", _detect_harmonic_flow),
    ("anchor_burst", _detect_anchor_burst),
    ("coordination", _detect_coordination),
    ("density", _detect_density),
    ("wildcard", _detect_wildcard),
]

_SPECIFIC_4K = {
    "linear_stream":   [("rolls", _sub_roll), ("trills", _sub_trill), ("mini_trills", _sub_mini_trill)],
    "harmonic_flow":   [("handstream", _sub_handstream), ("split_trill", _sub_split_trill), ("jump_trill", _sub_jump_trill), ("jumpstream", _sub_jumpstream)],
    "anchor_burst":    [("long_jacks", _sub_long_jacks), ("quad_stream", _sub_quad_stream), ("gluts", _sub_gluts), ("chord_jacks", _sub_chord_jacks), ("mini_jacks", _sub_mini_jacks)],
    "coordination":    [("column_lock", _sub_column_lock), ("shield", _sub_shield)],
    # Additional specific detectors can go here
    "density":         [],
    "wildcard":        [],
}


def _extract_textures(frames: List[Dict], key_count: int, total_ms: float) -> List[Dict]:
    """Scan beat-frames and extract all texture matches (port of findPatterns/find)."""
    remaining = list(frames)
    results = []
    specific_map = _SPECIFIC_4K if key_count == 4 else {}

    while remaining:
        for rhythm_name, detector in _PRIMARY_DETECTORS:
            n = detector(remaining)
            if n == 0:
                continue

            sub_list = specific_map.get(rhythm_name, [])
            best_match = (n, None)
            for sub_name, sub_fn in sub_list:
                m = sub_fn(remaining)
                if m > best_match[0]:
                    best_match = (m, sub_name)

            matched_len, matched_sub = best_match
            if matched_len <= 0:
                matched_len = n

            segment = remaining[:matched_len]
            mean_mpb = sum(s["ms_per_beat"] for s in segment) / len(segment)
            mixed = not all(abs(s["ms_per_beat"] - mean_mpb) < _PATTERN_CONFIG["stability_threshold"] for s in segment)

            start_ms = segment[0]["offset_ms"]
            end_ms = (remaining[matched_len]["offset_ms"]) if matched_len < len(remaining) else total_ms

            results.append({
                "rhythm": rhythm_name,
                "sub_texture": matched_sub,
                "is_volatile": mixed,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "ms_per_beat": 0.0 if (rhythm_name == "density" and matched_sub == "inverse") else mean_mpb,
            })

        remaining = remaining[1:]

    return results


# ── Clustering (BPM groups) ────────────────────────────────────────
def _bundle_textures(textures: List[Dict]) -> List[Tuple[Dict, Dict]]:
    """Group texture observations into BPM-timbre bundles (port of clustering)."""
    stable_groups = []
    volatile_groups = {}

    def _add_stable(mpb: float):
        for g in stable_groups:
            if abs(g["anchor_mpb"] - mpb) < _PATTERN_CONFIG["bpm_cluster_tolerance"]:
                g["sum_mpb"] += mpb
                g["count"] += 1
                return g
        g = {"anchor_mpb": mpb, "sum_mpb": mpb, "count": 1, "bpm": 0}
        stable_groups.append(g)
        return g

    def _add_volatile(rhythm: str, mpb: float):
        if rhythm not in volatile_groups:
            volatile_groups[rhythm] = {"sum_mpb": mpb, "count": 1, "bpm": 0}
        else:
            volatile_groups[rhythm]["sum_mpb"] += mpb
            volatile_groups[rhythm]["count"] += 1
        return volatile_groups[rhythm]

    pairs = []
    for tx in textures:
        if tx["is_volatile"]:
            c = _add_volatile(tx["rhythm"], tx["ms_per_beat"])
        else:
            c = _add_stable(tx["ms_per_beat"])
        pairs.append((tx, c))

    for g in stable_groups:
        avg = g["sum_mpb"] / max(g["count"], 1)
        g["bpm"] = round(60000.0 / avg) if avg > 0 else 0
    for v in volatile_groups.values():
        avg = v["sum_mpb"] / max(v["count"], 1)
        v["bpm"] = round(60000.0 / avg) if avg > 0 else 0

    return pairs


def _profile_bundles(pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
    """Summarize texture bundles into importance-ranked profiles (port of specificClusters)."""
    groups = defaultdict(lambda: {"items": [], "bpm": 0, "rhythm": "", "is_volatile": False})

    for tx, cluster in pairs:
        key = f"{tx['rhythm']}@@{tx['is_volatile']}@@{cluster.get('bpm', 0)}"
        groups[key]["items"].append(tx)
        groups[key]["rhythm"] = tx["rhythm"]
        groups[key]["is_volatile"] = tx["is_volatile"]
        groups[key]["bpm"] = cluster.get("bpm", 0)

    profiles = []
    for key, g in groups.items():
        starts_ends = sorted([(it["start_ms"], it["end_ms"]) for it in g["items"]])
        total_duration = 0
        if starts_ends:
            cur_start, cur_end = starts_ends[0]
            for s, e in starts_ends[1:]:
                if cur_end < e:
                    total_duration += (cur_end - cur_start)
                    cur_start, cur_end = s, e
                else:
                    cur_end = max(cur_end, e)
            total_duration += (cur_end - cur_start)

        n_total = len(g["items"])
        sub_counter = defaultdict(int)
        for it in g["items"]:
            if it["sub_texture"]:
                sub_counter[it["sub_texture"]] += 1
        sub_textures = sorted(sub_counter.items(), key=lambda x: x[1], reverse=True)
        sub_textures = [(name, cnt / n_total) for name, cnt in sub_textures]

        dominant_sub = sub_textures[0][0] if sub_textures else None
        weight = _PRIMARY_RHYTHM_WEIGHTS.get(g["rhythm"], 1.0)

        profiles.append({
            "rhythm": g["rhythm"],
            "sub_textures": sub_textures,
            "dominant_sub": dominant_sub,
            "weight": weight,
            "bpm": g["bpm"],
            "is_volatile": g["is_volatile"],
            "coverage_ms": total_duration,
            "importance": total_duration * weight * max(1, g["bpm"]),
        })

    profiles.sort(key=lambda p: p["importance"], reverse=True)
    return profiles


# ── Public API ─────────────────────────────────────────────────────
def profile_rhythms(notes: List[Dict], key_count: int, bpm_timeline: List[Dict] = None,
                    total_ms: float = 0) -> List[Dict]:
    """Full pipeline: notes → beat frames → textures → bundles → profiles."""
    if not bpm_timeline:
        bpm_timeline = []
    frames = _build_beat_frames(notes, key_count, bpm_timeline)
    if not frames:
        return []

    true_total = total_ms or (notes[-1]["time"] - notes[0]["time"]) if notes else 60000
    textures = _extract_textures(frames, key_count, true_total)
    paired = _bundle_textures(textures)
    profiles = _profile_bundles(paired)

    # Prune dominated profiles
    filtered = []
    for p in profiles:
        dominated = False
        for other in profiles:
            if other["rhythm"] == p["rhythm"] and other["coverage_ms"] * 0.5 > p["coverage_ms"] and other["bpm"] > p["bpm"]:
                dominated = True
                break
        if not dominated:
            filtered.append(p)

    # Cap per rhythm type
    capped = []
    rhythm_counts = defaultdict(int)
    for p in filtered:
        if rhythm_counts[p["rhythm"]] < 3:
            capped.append(p)
            rhythm_counts[p["rhythm"]] += 1
    capped.sort(key=lambda p: p["importance"], reverse=True)
    return capped


def classify_texture_profile(profiles: List[Dict], key_count: int,
                             bpm: float = 0.0, drain_s: float = 0.0) -> Dict:
    """Map rhythm profiles to DanOverlay family taxonomy.

    Returns the same dict shape as classifier.classify_family():
        {family, confidence, scores, subtype, subtype_scores, reason}
    """
    if not profiles:
        return {
            "family": "hybrid", "confidence": 0.0,
            "scores": {"jack": 0, "speed": 0, "stamina": 0, "tech": 0, "stream": 0},
            "subtype": "generic", "subtype_scores": {}, "reason": "no patterns detected"
        }

    # Important profiles (Importance >= 50% of top)
    top_importance = profiles[0]["importance"]
    important = [p for p in profiles if p["importance"] / max(top_importance, 1) > _PATTERN_CONFIG["important_cluster_ratio"]]

    primary = important[0] if important else profiles[0]
    secondary = important[1] if len(important) > 1 else None

    # Map primary rhythm to family
    primary_family = _TEXTURE_TO_FAMILY.get(primary["rhythm"], "hybrid")
    if primary["dominant_sub"] and primary["dominant_sub"] in _SUB_TEXTURE_FAMILY:
        primary_family = _SUB_TEXTURE_FAMILY[primary["dominant_sub"]]

    # Determine if hybrid
    is_hybrid = False
    if secondary and secondary["dominant_sub"]:
        sec_family = _SUB_TEXTURE_FAMILY.get(secondary["dominant_sub"], _TEXTURE_TO_FAMILY.get(secondary["rhythm"], "hybrid"))
        if sec_family != primary_family:
            is_hybrid = True

    is_tech = primary["is_volatile"] or (is_hybrid and primary["bpm"] < 150)
    if primary["dominant_sub"] in ("trills", "mini_trills", "split_trill", "jump_trill", "chord_roll", "brackets", "column_lock", "shield", "inverse"):
        is_tech = True

    # Build final family
    if is_hybrid and is_tech:
        family = "tech"
    elif is_hybrid:
        family = "hybrid"
    elif is_tech:
        family = "tech"
    else:
        family = primary_family

    # ── BPM-aware stamina correction ───────────────────────────────
    # Sustained high-BPM streams are structurally indistinguishable from
    # speed maps at the pattern level, but the defining characteristic of
    # stamina is sustained density over long duration.  Official DDMythical
    # stamina marathons sit at BPM 200-240 with 100s+ drain, while pure
    # speed maps have shorter bursts.  Misclassifying these as speed
    # overpredicts by 1-2 tiers (speed ruler means are lower per tier).
    if family in ("speed", "stream") and bpm > 200.0 and drain_s > 100.0:
        family = "stamina"
        if primary_family in ("speed", "stream"):
            primary_family = "stamina"

    # Confidence: how dominant the primary is
    total_importance = sum(p["importance"] for p in profiles[:5]) + 1
    confidence = min(1.0, round(primary["importance"] / total_importance, 2))

    # Scores for each family
    scores = {"jack": 0, "speed": 0, "stamina": 0, "tech": 0, "stream": 0}
    for p in important[:5]:
        fam = _TEXTURE_TO_FAMILY.get(p["rhythm"], "hybrid")
        if p["dominant_sub"] and p["dominant_sub"] in _SUB_TEXTURE_FAMILY:
            fam = _SUB_TEXTURE_FAMILY[p["dominant_sub"]]
        scores[fam] += p["importance"] / max(total_importance, 1) * 100

    # Scale scores to 0-100 range
    max_score = max(scores.values()) or 1
    scores = {k: round(v / max_score * 100, 1) for k, v in scores.items()}

    subtype_scores = {}
    for p in important[:5]:
        for sub_name, ratio in p.get("sub_textures", []):
            if sub_name not in subtype_scores:
                subtype_scores[sub_name] = 0
            subtype_scores[sub_name] += ratio * 100

    subtype = primary["dominant_sub"] or "generic"
    reason = f"primary rhythm: {primary['rhythm']} ({primary.get('dominant_sub', 'none')}), bpm: {primary['bpm']}"

    return {
        "family": family,
        "confidence": confidence,
        "scores": scores,
        "subtype": subtype,
        "subtype_scores": subtype_scores,
        "reason": reason,
    }


# ── Drop-in adapter for the pipeline ───────────────────────────────
_NOTE_KIND_MAP = {
    "normal": "tap",
    "hold_head": "hold_head",
    "hold_body": "hold_body",
    "hold_tail": "hold_tail",
}


def classify_from_parsed(parsed: Dict) -> Dict:
    """Thin wrapper: parse parser.py output → rhythm profiles → family dict.

    Accepts the dict returned by parsear_osu_v2() and returns the same
    {family, confidence, scores, ...} shape as classifier.classify_family().
    """
    raw_notes = parsed.get("notes", [])
    key_count = parsed.get("key_count", 4)

    # Extract BPM timeline
    bpm_timeline = []
    for tp in parsed.get("timing_points", []):
        bpm_timeline.append({
            "time": float(tp.get("time", 0) or 0),
            "ms_per_beat": float(tp.get("ms_per_beat", 500) or 500),
        })

    # Convert notes to beat-frame format
    if not raw_notes:
        return {
            "family": "hybrid", "confidence": 0.0,
            "scores": {"jack": 0, "speed": 0, "stamina": 0, "tech": 0, "stream": 0},
            "subtype": "generic", "subtype_scores": {}, "reason": "no notes"
        }

    first_time = float(raw_notes[0][0] if isinstance(raw_notes[0], tuple) else raw_notes[0].get("time", 0) or 0)
    last_time = first_time

    beat_notes = []
    for n in raw_notes:
        if isinstance(n, tuple):
            t = float(n[0] or 0)
            col = int(n[1] or 0) if len(n) >= 2 else 0
            kind = str(n[2] or "tap") if len(n) >= 3 else "tap"
        else:
            t = float(n.get("time", 0) or 0)
            col = int(n.get("column", 0) or 0)
            kind = str(n.get("type", "normal") or "normal")
        mapped_kind = _NOTE_KIND_MAP.get(kind, "tap")

        # Build data row for this timestamp
        existing = None
        for bn in beat_notes:
            if bn["time"] == t:
                existing = bn
                break
        if existing:
            while len(existing["data"]) <= col:
                existing["data"].append(None)
            existing["data"][col] = mapped_kind
        else:
            data = [None] * (col + 1)
            data[col] = mapped_kind
            beat_notes.append({"time": t, "data": data})
        last_time = max(last_time, t)

    # Ensure all data arrays have length key_count
    for bn in beat_notes:
        while len(bn["data"]) < key_count:
            bn["data"].append(None)

    total_ms = (last_time - first_time) or 60000

    profiles = profile_rhythms(beat_notes, key_count, bpm_timeline, total_ms)
    _bpm = float(parsed.get("bpm", 0.0) or 0.0)
    _drain = float(parsed.get("drain_time_s", 0.0) or 0.0)
    return classify_texture_profile(profiles, key_count, bpm=_bpm, drain_s=_drain)
