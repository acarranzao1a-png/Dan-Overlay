# DanOverlay 2.2 — Calculation Pipeline & Detection Fixes

## Summary

Version 2.2 focuses on calculation accuracy and map detection robustness, addressing three user-reported issues and one internal improvement.

### 1. 7K Dan Estimation Rewrite

The 7K system now uses the same boundary interpolation method as Reform and all other scoring modes. Previously the overlay picked the nearest tier by median distance, which caused ambiguous maps near tier boundaries to display the wrong rank. The new method uses midpoints between adjacent tier medians, eliminating the ambiguity.

### 2. Celestial & LN Course Sublevel Fix

The maximum DP fraction for Celestial and LN Course modes was capped at 0.50, preventing the overlay from ever showing a "High" sublevel. Both caps have been corrected to allow the full 0.00–0.99 range, consistent with Reform, Signicial, and Shoegazer.

### 3. Map Detection Fix

Certain .osu files from external editors contain blank lines inside the hit objects section. The overlay's parser did not skip these blank lines and crashed on `float()` conversion, returning star rating 0.0. This caused maps to display as "1st Dan Low" regardless of actual difficulty. The fix skips empty lines during parsing, restoring correct detection on all maps.

### 4. SR Engine Failure Guard

When the star rating engine fails for any reason (file locked by the game, corrupted timing data, encoding issues), the overlay now returns an explicit error payload instead of passing SR=0.0 through the ranking pipeline. This prevents the misleading "1st Dan Low" display on genuinely undetectable maps.

### 5. BPM Rate Adjustment

BPM values are now multiplied by the active speed mod rate (DT ×1.5, HT ×0.75, osu!lazer custom rates). Previously the overlay always displayed the original BPM regardless of mod selection.

---

*Release: 2.2.0 — 2026-06*
