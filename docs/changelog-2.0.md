# DanOverlay 2.0 — Changelog

## 7K osu!mania Support (Major)

### SR Means Calibration
- Calibrated from 619 maps (7K Regular Dans) + 45 original regular dan course maps
- 15 tiers: 0th Dan to 10th Dan, Gamma, Azimuth, Zenith, Stellium
- config/sr_means_7k.json with general + per-skillset means (jack, tech, speed, stream, hybrid/stamina)
- Each tier has: median, mean, n, min, max
- Monotonicity enforced across all 15 tiers

### Detection Pipeline
- Nearest-neighbor tier classification by general median SR
- Sublevel determined by position within tier's min-max range: Low, Mid-Low, Mid, Mid-High, High
- DP mapping: 0th=0.0, 1st=1.0, ..., 10th=10.0, Gamma=11.0, Azimuth=12.0, Zenith=13.0, Stellium=14.0
- Beyond Stellium: DP > 14.0, displayed as "Beyond Stellium"
- SR below 0th min correctly maps to 0th Dan (no "Below Gamma" fallback needed)

### Integration
- analysis_coordinator.py: early return in pipeline for key_count=7 maps
- contracts.py: AnalysisResult dataclass with mode_7k, tier_7k, sublevel_7k, dp_7k fields + to_dict() serialization
- overlay.js: handler for payload.mode === "7k" in _renderAnalysisPayload()
- PALETTES_7K color array with distinct gradients for all 15 tiers
- Validator accepts keycount == 7 alongside keycount == 4
- minacalc_bridge gate relaxed from keycount != 4 to keycount not in (4, 7)

### Accuracy
- 72.4% tier classification accuracy (688 maps, general means)
- 0% fallo rate (no map misclassified by 2+ tiers with per-skillset means)

---

## 3 New Skins

All built from scratch with complete overlay.js integration:

### ui-4: Vertical Monolith
- Frosted glass card with circular SVG ring (stroke-dashoffset synced to DP)
- Gradient text for Dan name via --dan-gradient-anim
- 5 sub-bars with skewX(-20deg) and progressive lighting
- Expandable info drawer (L key) with MSD/SR/BPM/Length stats
- Ambient radial background that shifts color per Dan palette

### ui-5: Broadcast Bar
- Horizontal split bar: colored left panel (gradient from Dan palette) + dark right panel
- DP displayed as massive number on colored panel
- Dan name as gradient text with drop-shadow on dark panel
- 5 sub-bars (15x20px, skewX, progressive lighting)
- Expandable drawer with stats row
- Right panel has subtle fade rgba(0,0,0,0.5) to transparent

### ui-6: Floating Big-Type
- Massive typography (10rem DP.int, 7rem rank name)
- Rotated (-90deg) "DP" label on left
- DP shadow glow from --dan-primary-raw
- Oval sub-bars (border-radius: 20px)
- Glass stats panel with border-left colored from Dan palette

### All 3 share:
- L key toggle expanded info drawer with map stats
- Loading screen, splash screen, connect screen, settings panel
- All required element IDs for overlay.js (badgeLeft, badgeRight, etc.)
- Demo cycling mode (auto-advance every 3s)
- Registered in overlay_host.py with switch_skin() support
- Preflight validation in build.bat
- System font stack (Inter / Outfit / system-ui)

---

## Celestial Mode Refinements

- DP system unified with Reform: boundary interpolation on SR means to DP = integer + fraction
- DP range: 1.0 (Beginner I) to 35.0 (Singularity V)
- Label format: "Beginner I" instead of "Beginner Tier 1"
- Short label: "B-I" instead of "B-T1"
- Confidence calculation from fractional position within slot boundary
- Internal category encoding (I-V) unchanged

---

## Bridge Race Condition Fix

- Queue mechanism in bridge.py: all _send() calls buffer when JS is not ready
- mark_ready() flushes the queue once the page confirms it can receive events
- Polling thread in overlay_host.py checks typeof window.__overlayFromPython === 'function' every 250ms
- 15-second timeout with forced ready fallback
- Background threads (audio, tosu) queue events silently without raising errors
- Fixed background_color alpha channel (#00000000 to #000000) in create_window()

---

## Build and Distribution

- build.bat fully translated to English
- Removed dead changelog.txt copy from dist packaging
- Preflight checks for ui-4, ui-5, ui-6
- Config files verified UTF-8 (no BOM issues found)

---

## Housekeeping

- scripts/ folder created for analysis/calibration scripts
- 7K calibration scripts: compute_7k_sr.py, extract_7k_srmeans.py, extract_original_7k.py
- Benchmark scripts: bmk_7k_accuracy.py, bmk_7k_pipeline.py, benchmark_7k_general.py
- README.md updated with Mermaid flow diagrams (complete system, pipeline, rank engine, overlay JS)
- Monotonicity fixes for 7K SR means (9th-10th boundary corrected)
- Per-skillset tiebreak experiment for 7K classifier (abandoned — data too sparse)

---

## Data Summary

| Tier | DP Base | Median SR | Min SR | Max SR | N maps |
|---|---|---|---|---|---|
| 0th Dan | 0.0 | 3.74 | 3.31 | 4.07 | 3 |
| 1st Dan | 1.0 | 4.71 | 4.23 | 5.03 | 3 |
| 2nd Dan | 2.0 | 4.91 | 4.75 | 5.68 | 3 |
| 3rd Dan | 3.0 | 5.45 | 5.13 | 5.88 | 3 |
| 4th Dan | 4.0 | 5.86 | 5.57 | 6.15 | 3 |
| 5th Dan | 5.0 | 6.08 | 5.97 | 6.26 | 3 |
| 6th Dan | 6.0 | 6.44 | 6.22 | 7.06 | 3 |
| 7th Dan | 7.0 | 6.99 | 6.73 | 7.22 | 3 |
| 8th Dan | 8.0 | 7.63 | 7.15 | 7.78 | 3 |
| 9th Dan | 9.0 | 7.64 | 7.46 | 8.09 | 3 |
| 10th Dan | 10.0 | 8.26 | 7.91 | 8.63 | 3 |
| Gamma | 11.0 | 8.79 | 8.34 | 8.94 | 3 |
| Azimuth | 12.0 | 9.25 | 9.11 | 9.39 | 3 |
| Zenith | 13.0 | 9.99 | 9.87 | 9.99 | 3 |
| Stellium | 14.0 | 10.57 | 10.27 | 10.61 | 3 |

All 15 tiers calibrated from original DDMythical 7K regular dan course packs (1 map per skillset per tier). Median SR values follow a strictly monotonic progression.

---

## Celestial DP Table

DP range: 1.0 (Beginner Tier 1) to 35.0 (Singularity Tier 5). Calculated via boundary interpolation on SR means, identical to Reform mode.

| Tier | Display Name | DP | SR Mean |
|---|---|---|---|
| Beginner | Beginner Tier 1 | 1 | 0.35 |
| Beginner | Beginner Tier 2 | 2 | 0.48 |
| Beginner | Beginner Tier 3 | 3 | 1.14 |
| Beginner | Beginner Tier 4 | 4 | 1.86 |
| Beginner | Beginner Tier 5 | 5 | 2.19 |
| Intermediate | Intermediate Tier 1 | 6 | 2.37 |
| Intermediate | Intermediate Tier 2 | 7 | 2.71 |
| Intermediate | Intermediate Tier 3 | 8 | 2.91 |
| Intermediate | Intermediate Tier 4 | 9 | 3.24 |
| Intermediate | Intermediate Tier 5 | 10 | 3.62 |
| Expert | Expert Tier 1 | 11 | 3.77 |
| Expert | Expert Tier 2 | 12 | 4.33 |
| Expert | Expert Tier 3 | 13 | 4.56 |
| Expert | Expert Tier 4 | 14 | 4.54 |
| Expert | Expert Tier 5 | 15 | 4.68 |
| Mastery | Mastery Tier 1 | 16 | 5.10 |
| Mastery | Mastery Tier 2 | 17 | 5.36 |
| Mastery | Mastery Tier 3 | 18 | 5.75 |
| Mastery | Mastery Tier 4 | 19 | 5.72 |
| Mastery | Mastery Tier 5 | 20 | 6.00 |
| Ascension | Ascension Tier 1 | 21 | 6.08 |
| Ascension | Ascension Tier 2 | 22 | 6.58 |
| Ascension | Ascension Tier 3 | 23 | 6.84 |
| Ascension | Ascension Tier 4 | 24 | 6.97 |
| Ascension | Ascension Tier 5 | 25 | 7.34 |
| Transcendence | Transcendence Tier 1 | 26 | 7.50 |
| Transcendence | Transcendence Tier 2 | 27 | 7.81 |
| Transcendence | Transcendence Tier 3 | 28 | 8.03 |
| Transcendence | Transcendence Tier 4 | 29 | 8.32 |
| Transcendence | Transcendence Tier 5 | 30 | 8.56 |
| Singularity | Singularity Tier 1 | 31 | 8.81 |
| Singularity | Singularity Tier 2 | 32 | 8.91 |
| Singularity | Singularity Tier 3 | 33 | 9.45 |
| Singularity | Singularity Tier 4 | 34 | 9.84 |
| Singularity | Singularity Tier 5 | 35 | 10.09 |

---

## Next Goal: Calculation Speed Optimization
- Analyze current pipeline hot spots (parser, algorithm.py, MSD subprocess)
- Profile SR computation thread to identify bottlenecks
- Evaluate caching opportunities at parser and feature_extractor level
- Consider lazy extraction of features that are only needed by specific estimators
