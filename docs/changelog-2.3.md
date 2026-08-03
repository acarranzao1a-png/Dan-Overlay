# DanOverlay 2.3 — Sunny Rebirth & Hero-Dan Lazer Skins

## Summary

Version 2.3 adds two brand-new skins (Sunny Rebirth and Hero-Dan Lazer), exposes
the Sunny SR strain components to the frontend, and fixes several UI bugs
discovered while integrating the new skins. It also formally documents two
calculation fixes that were implemented **before** the project went open source
(7K difficulty detection and custom-rate monotonicity) so the history is complete.

---

## Pre-Open-Source Fixes (documented for completeness)

These changes were implemented and shipped with the initial open-source release.
They are documented here so the timeline is clear.

### 1. 7K Difficulty Detection Under Speed Mods

**Problem.** The 7K path computed the raw star rating with `algorithm.calculate()`
directly, which ignores the mod clock rate. Under DT/HT — and especially under
osu!lazer custom rates — the SR used for tier estimation did not reflect the
actual playback speed, so 7K maps could display the wrong tier and sublevel.

**Files modified:** `src/pipeline.py` (7K branch), `config/sr_means_7k.json`
(calibration data used by the tier ruler).

**Solution.** The 7K path now goes through the same rate-aware helper as 4K —
`analyze_primary_sr(path, mod, rate)` — and tier estimation uses boundary
interpolation (midpoints between adjacent tier medians), consistent with the 4K
Reform system. The displayed BPM is also rate-adjusted (DT ×1.5, HT ×0.75,
custom rates as-is). The vendored Sunny engine itself was **not** modified.

### 2. Custom-Rate SR Monotonicity (osu!lazer)

**Problem.** With osu!lazer custom clock rates, the SR — and therefore the Dan
estimate — was not monotonic in the rate: lowering DT from 1.5× to 1.49× could
produce a *higher* Dan. Measured on Mario Paint (Epsilon speed): SR 11.45 at
1.45×, 11.35 at 1.50×, 11.25 at 1.53× — a "W" shape instead of a rising curve.

**Root cause (chain of issues):**
1. `is_custom` in `primary_sr_bridge.py` compared the rate against a fixed list
   (1.0 / 0.75 / 1.5), so a rate of 1.5 with mod NM was silently discarded.
2. Two different scaling routes (the mod's internal floor vs. the integer-rounded
   temp file) produced different SR values for the same rate.
3. The MSD family override could flip the family (tech ↔ stream) between
   adjacent rates, re-routing the DP through a different per-skillset ruler.
4. Final root: the Sunny star-rating formula itself is intrinsically
   non-monotonic under timing scaling (verified by comparing float vs. integer
   timings — not a quantization artifact). Since the engine is vendored and
   intentionally left unmodified, the formula could not be changed.

**Files modified:** `src/pipeline.py` (`analyze_map` custom-rate interpolation),
`src/primary_sr_bridge.py` (`is_custom = rate != 1.0`, `round()` on the temp
file, gated MSD family override).

**Solution.** `analyze_map` now computes the **full result at the two nearest
native rates** (HT 0.75× / NM 1.0× / DT 1.5×) and linearly interpolates the
final fields (DP, SR, Dan label, sublevel, and every alternative-mode estimate)
at the custom rate. The final result is monotonic **by construction** and the
fix is universal — it applies to 4K, 7K, LN, and all scoring modes. Temporary
DIAG logging added during this debugging was removed in this release.

---

## 2.3 Changes

### 3. New Skin — Sunny Rebirth (skin 7)

A live **Sunny SR HUD**: shows only the map's Sunny Star Rating and the four
strain components — **Jbar, Pbar, Xbar, Abar** — as animated bars, plus map
context (title with marquee scroll, MANIA 4K/7K badge, skillset, MSD, status).

- SR-only by design: mode result screens (Celestial, Signicial, Shoegazer,
  LN Course) are intentionally suppressed in this skin.
- Strain bars now receive real values: the pipeline injects the Sunny component
  strains into the analysis payload for **both 4K and 7K** maps.
- Brighter background triangles, rounded HUD corners, brighter top gradient.
- Layout uses percentage sizing instead of `vh` units so the locked resize mode
  (R key) no longer clips the bottom/right edges.

### 4. New Skin — Hero-Dan Lazer (skin 8)

A dan-focused HUD: giant Dan rank title, animated DP with sublevel pills,
mode category badge (Reform / Celestial / Signicial / Shoegazer / LN Course /
7K), and an **expandable map-info bar** (MSD, SR, BPM, length) that toggles with
**L** — the same expand/collapse behaviour as skins 4/5/6.

- Mode screens are fully visible in this skin (it is a Dan calculator skin,
  unlike Sunny Rebirth).
- Default window size calibrated with the dev measurement tool:
  594×234 expanded / 594×138 collapsed at 94% zoom; Ctrl+R restores it.
- Includes the settings panel with all 8 skins selectable.

### 5. Sunny Components in the Analysis Payload

`AnalysisResult.to_dict()` now exposes `jbar_max`, `pbar_max`, `xbar_max` and
`abar_mean` (read from `debug["sr_result"]`). `pipeline.py` injects them into
both the 4K primary path and the 7K branch via a new `_inject_sunny_components`
helper — this is what feeds the Sunny Rebirth strain bars.

### 6. Bug Fixes

| Fix | Details |
|-----|---------|
| Skin-switch crash | Switching skins could throw `Cannot read properties of null (reading 'classList')` because `ui.panel` was null on skins without `#danPanel`. `ui.panel` now falls back to `#overlay`. |
| L-key toggle never collapsing | `_cycleLayout` toggled the `expanded`/`is-expanded` classes independently; on Hero-Dan Lazer (which starts with only `expanded`) the OR check always reported expanded. Both classes now toggle in sync from a single source of truth. |
| Locked-mode clipping (skins 7/8) | `vh` units resolve against the unzoomed viewport under CSS root zoom, clipping the bottom/right edges in locked resize mode. Both skins now use percentage height chains like skins 4/5/6. |
| Map title truncation (skin 7) | Long titles now scroll horizontally (marquee) instead of being cut with an ellipsis. |
| Window reset for skin 8 | Ctrl+R and the settings "Reset to Default" button now restore 594×234/138 @ 94% zoom instead of the generic 700×320. |

### 7. Integration

- All skins' settings panels list the new options (Sunny Rebirth, Hero-Dan Lazer).
- `overlay_host.py` registers both skins (loading + runtime skin switching) and
  applies per-skin startup window defaults (800×340 for Sunny Rebirth,
  594×234 for Hero-Dan Lazer).
- Removed the temporary `pipeline DIAG` / `pipeline MERGE-DIAG` logging that was
  added during the custom-rate monotonicity investigation.

---

*Release: 2.3.0 — 2026-08*
