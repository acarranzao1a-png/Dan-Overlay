# DanOverlay 2.1 — Performance Optimisation

## Overview

Release focused exclusively on responsiveness and eliminating freezes when navigating between beatmaps. No changes to calculation logic, accuracy, or visual design.

---

## Problem Statement

Users reported two symptoms:

1. **Freezing on rapid map switching** — while scrolling through song select, the overlay would freeze showing the hint screen or the previous map's result for several seconds.
2. **Slow initial load** — the overlay took up to 5 seconds to appear after launching the executable.

## Diagnosis

Each pipeline stage was profiled with real maps (stamina marathons, jack, tech):

| Component | Average time |
|---|---|
| .osu file parsing | ~0.01s |
| Feature extraction | ~0.01s |
| Sunny SR (main calculation) | ~0.15s |
| MinaCalc msd.exe (subprocess) | ~0.15s |
| 4 mode estimators | ~0.01s |
| **Full pipeline** | **0.15–0.34s** |

The calculation pipeline **was not the problem**. The bottleneck was in three areas completely unrelated to the mathematical logic:

### 1. Google Fonts blocked initial render

Every skin loaded Inter from `fonts.googleapis.com` synchronously. If Google's server was slow or the user was offline, the browser rendered NOTHING until the font downloaded — between 2 and 5 seconds of blank window.

<div align=center>
<img width="312" height="755" alt="image" src="https://github.com/user-attachments/assets/bc14dd14-aeff-42c2-a817-1269894baded" />
</div>

### 2. Bridge waited up to 15s to confirm JS was ready

The communication mechanism between Python and the WebView page polled every 250ms for up to 15s. During this time, already-computed analysis results (0.3s) accumulated in a queue without being displayed, creating the illusion of freezing.

<div align=center>
<img width="335" height="737" alt="image" src="https://github.com/user-attachments/assets/d47f0773-b0a8-4be3-91a5-060f31653d6e" />
</div>

### 3. Every map switch spawned a new thread

The analysis coordinator created a `threading.Thread` for each `MAP_CHANGED` event. If the user scrolled through 5 maps rapidly, 5 threads ran the pipeline concurrently, competing for CPU with the overlay's UI thread.

<div align=center>
<img width="1492" height="342" alt="image" src="https://github.com/user-attachments/assets/58ff439c-e5e1-452a-b39b-a1227fc7aa59" />
</div>

---

## Changes Applied

### Phase 1 — Remove blocking external dependencies

| Problem | Solution | Gain |
|---|---|---|
| Google Fonts blocked render | Removed all `<link>` tags to `fonts.googleapis.com` from all skins. Overlay uses `system-ui` (OS native font) as primary, with Inter as optional fallback. | **-2 to -5s on initial load** |

### Phase 2 — Optimise Python ↔ JS communication

| Problem | Solution | Gain |
|---|---|---|
| Bridge polling at 250ms | Reduced to 100ms | **-0.3s detection** |
| Forced-ready timeout at 15s | Reduced to 8s | **-7s in worst case** |
| Cold imports on first analysis | Expanded warmup: numpy + pandas + parser + features + classifier + rank_engine pre-imported in background at startup | **-0.2s on first map** |

### Phase 3 — Analysis thread management

| Problem | Solution |
|---|---|
| Each MAP_CHANGED created a new thread | **Single worker**: one analysis thread handles all requests |
| Old analyses ran to completion even though their results were discarded | **Early bailout**: worker checks the cancellation token at multiple checkpoints and aborts if the map changed |
| Rapid switches saturated CPU | **200ms debounce**: if the user switches maps within 200ms, the timer resets. Only the last map is analysed |

<div align=center>
<img width="2488" height="8192" alt="Overlay Rendering Workflow-2026-06-10-013141" src="https://github.com/user-attachments/assets/e6044c44-47bc-4b4b-adc5-e9303888389d" />
</div>

### Phase 4 — Sublevel threshold consistency

Low / Mid-Low / Mid / Mid-High / High thresholds were defined inconsistently across 4 files. Unified to symmetric 20% bands:

| Sublevel | Range (DP fraction) |
|---|---|
| Low | 0.00 – 0.20 |
| Mid-Low | 0.20 – 0.40 |
| Mid | 0.40 – 0.60 |
| Mid-High | 0.60 – 0.80 |
| High | 0.80 – 1.00 |

Applies to all modes: Reform, Celestial, Signicial, Shoegazer, LN Course, and 7K.

---

## What Did NOT Change

- **Calculation accuracy**: Zero modifications to the Sunny SR algorithm, rank_engine, classifiers, or calibration profiles.
- **Visual design**: Skins, colours, animations, and layout intact.
- **Numerical results**: Same DP values, same sublevels, same classifications.

---

## Performance Table

| Scenario | Before | After |
|---|---|---|
| Initial overlay load | 3-8s (depending on Google Fonts connectivity) | **< 1s** |
| Single map analysis | 0.3s | 0.3s **(unchanged — was not the bottleneck)** |
| Rapid scroll through 10 maps | 5-10 concurrent threads, overlay frozen | **1 analysis, no freezing** |
| Map switch during ongoing analysis | Previous thread kept consuming CPU | **Aborts early** |
| Sublevels (Low/High) | 15/35/65/85 (asymmetric) — bars and text could mismatch | **20/40/60/80 symmetric** — bars and text always match |
