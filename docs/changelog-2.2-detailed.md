# DanOverlay 2.2 — Calculation Pipeline & Detection Fixes (Detailed)

## Overview

Seven changes across the overlay's calculation pipeline, parser, and display layer. Every fix in this release was driven by user reports — thanks to everyone who took the time to document edge cases.

---

## 1. 7K: Nearest-Neighbour → Boundary Interpolation

### Problem

The 7K system selected a tier by finding whichever stored median was closest to the map's star rating. For maps whose star rating fell near the edge between two tiers' ranges, this could pick the wrong tier entirely. Four specific maps were reported where the displayed tier and sublevel did not match the expected difficulty.

**Before — nearest-neighbour by median distance:**
```python
For each tier:
    dist = abs(sr - tier.median)
    if dist < best_dist → pick this tier

pos = (sr - tier.min) / (tier.max - tier.min)
dp  = tier_base + pos * 0.99
```
- Ambiguous when `sr` is near the intersection of two tiers' ranges
- The `* 0.99` multiplier guaranteed the DP fraction never reached 1.0
- Sublevels derived from `pos` could contradict the DP display

**After — boundary interpolation (midpoints between adjacent medians), same as Reform:**

```python
medians = sorted list of all tier medians
for each adjacent pair (median[i], median[i+1]):
    lo = (median[i] + median[i+1]) / 2
    hi = (median[i+1] + median[i+2]) / 2
    boundary = (lo, hi, tier_index)

find boundary where lo <= sr < hi:
    t = (sr - lo) / (hi - lo)
    dp = tier_index + t
```

No nearest-neighbour, no `* 0.99`, no ambiguity. The tier is determined purely by which boundary bracket the SR falls into, just like Reform, Celestial, Signicial, Shoegazer, and LN Course.

<div align="center">
<img width="4445" height="1840" alt="Cafe Product and Complement-2026-07-02-220045" src="https://github.com/user-attachments/assets/f9d97c21-9a9d-4d66-a7e5-49603daef3ed" />
</div>

---

## 2. Celestial & LN Course DP Cap

### Problem

The Celestial estimator capped its DP at `min(35.5, dp_raw)`. The LN Course estimator capped at `min(16.5, dp)`. Both caps limited the DP fraction to 0.50, meaning neither mode could ever show a "High" sublevel (which requires 0.80–1.00). The corresponding `dp_beyond` checks on the SR→DP path used 35.99 and 16.99 respectively — the caps were simply inconsistent with their own upper bounds.

| Mode | Before (max fraction) | After (max fraction) | Sublevels available |
|------|----------------------|---------------------|-------------------|
| Celestial | 0.50 (35.5) | 0.99 (35.99) | All five |
| LN Course | 0.50 (16.5) | 0.99 (16.99) | All five |
| Reform | 0.99 | 0.99 | All five |
| Signicial | 0.99 | 0.99 | All five |
| Shoegazer | 0.99 | 0.99 | All five |

---

## 3. Map Detection Fix ("1st Dan Low")

### Root Cause

The overlay uses two separate .osu parsers: one for structural analysis (feature extraction, LN detection) and one for the Sunny star rating engine. The Sunny engine's parser reads hit objects by calling `next()` on the file iterator in a loop. When a .osu file contains blank lines inside the `[HitObjects]` section — common in files exported or edited by third-party tools — the parser receives `"\n"` (a blank line) and attempts to parse it as a hit object. Splitting `"\n"` by commas gives `["\n"]`, and `float("\n")` raises a `ValueError`.

**The crash chain:**
1. `float("\n")` → `ValueError`
2. The Sunny wrapper catches the exception → returns `sr=0.0`, `success=False`
3. The pipeline passes `sr=0.0` to the rank engine without checking the `success` flag
4. The rank engine's `sr_to_dp(0.0)` produces DP=1.0 → overlay displays "1st Dan Low"

### Fix

Two corrections, applied together:

**Parser fix** — blank lines in `[HitObjects]` are now skipped rather than parsed:

```python
# Before:
    while line is not None:
        parse_hit_object(line)  ← crashes on "\n"

# After:
    while line is not None:
        line = line.strip()
        if not line:            ← skip blank lines
            line = next(f)
            continue
        parse_hit_object(line)
```

**Pipeline guard** — when the SR engine reports failure, the pipeline returns an error payload instead of forwarding `sr=0.0`:

```python
sr_result = run_sr_engine(path, mod)
if not sr_result["success"]:
    return {"error": sr_result["error"], "dp": None, ...}
```

This also covers any other scenario that causes the SR engine to fail: file lock by osu!, corrupted timing points, encoding issues, incomplete downloads — anything that would previously produce a silent "1st Dan Low".

<div align="center">
<img width="7166" height="1525" alt="Cafe Product and Complement-2026-07-02-215949" src="https://github.com/user-attachments/assets/d71e33b3-40c3-4f09-b3a1-216c627263e9" />
</div>

---

## 4. BPM Rate Adjustment

### Problem

When Half Time or Double Time was enabled, the overlay correctly recalculated star rating, MSD skillsets, and play duration — but the displayed BPM always showed the original value from the .osu file, ignoring the speed mod.

### Fix

The pipeline now multiplies the parsed BPM (min, max, common) by the effective rate factor before forwarding to the overlay:

| Mod | Rate | Original BPM | Displayed BPM (2.2) |
|-----|------|-------------|-------------------|
| None | 1.0× | 180 | 180 |
| DT (stable) | 1.5× | 180 | 270 |
| HT (stable) | 0.75× | 180 | 135 |
| DT (lazer custom) | 1.25× | 180 | 225 |
| HT (lazer custom) | 0.55× | 180 | 99 |

This applies to both the primary SR path and the MinaCalc fallback path, and works for osu!stable bitmask mods as well as osu!lazer custom clock rates.

**Before (no rate adjustment):**

```python
merged["bpm"]        = round(float(features.get("bpm", 0.0) or 0.0), 1)
merged["bpm_min"]    = int(parsed.get("bpm_min",  round(merged["bpm"])) or round(merged["bpm"]))
merged["bpm_max"]    = int(parsed.get("bpm_max",  round(merged["bpm"])) or round(merged["bpm"]))
merged["bpm_common"] = int(parsed.get("bpm_common", round(merged["bpm"])) or round(merged["bpm"]))
```

**After (rate applied to all four BPM fields):**

```python
raw_bpm    = float(features.get("bpm", 0.0) or 0.0)
raw_min    = float(parsed.get("bpm_min", raw_bpm) or raw_bpm)
raw_max    = float(parsed.get("bpm_max", raw_bpm) or raw_bpm)
raw_common = float(parsed.get("bpm_common", raw_bpm) or raw_bpm)

merged["bpm"]        = round(raw_bpm    * effective_rate, 1)
merged["bpm_min"]    = int(round(raw_min    * effective_rate))
merged["bpm_max"]    = int(round(raw_max    * effective_rate))
merged["bpm_common"] = int(round(raw_common * effective_rate))
```

The same pattern is applied in the MinaCalc fallback path (the if/else branch where the primary SR engine is unavailable), using the same `effective_rate` derived from the mod parameter or the osu!lazer custom clock rate.

---

## Files Changed

These descriptions correspond to the changes in the source tree.

- **Parser** — added blank-line skip in hit-object reading loop
- **Pipeline** — SR→DP boundary interpolation for 7K; SR failure early-return guard; BPM rate multiplication in both result paths
- **Celestial estimator** — DP cap constant corrected
- **LN Course estimator** — DP cap constant corrected
- **Version metadata** — build ID and window title updated

---

*Release: 2.2.0*
*Date: 2026-06*
