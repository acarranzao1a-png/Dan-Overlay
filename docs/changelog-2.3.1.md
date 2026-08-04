# DanOverlay 2.3.1 — Custom-Rate Fixes & Hero-Dan Lazer Polish

## Summary

Version 2.3.1 fixes three calculation/display bugs — two reported by users
(custom clock rates in osu!lazer) and one found while developing the live timer
for the Hero-Dan Lazer skin — and brings a full visual polish pass to the Sunny
Rebirth (skin 7) and Hero-Dan Lazer (skin 8) skins.

---

## Technical Fixes

### 1. Custom-Rate Interpolation: Alternative-Mode Stages Reverted to the NM Value

#### Problem

With a native rate (DT 1.5× / HT 0.75× / NM 1.0×) the overlay estimated the
correct stage, but with any osu!lazer **custom** rate the Signicial / Shoegazer
(and also Celestial / LN Course) stages reverted to the no-mod value.

Reported example: a map estimated **Alpha** at NM — enabling DT (1.5×) correctly
jumped to **Eta**, but increasing the rate by a tenth in lazer (1.6×) snapped
back to **Alpha** even though the displayed DP kept rising.

#### Root Cause

`analyze_map()` computes the full result at the two nearest native rates and
interpolates the final fields for custom rates. The alternative-mode dicts were
copied from the NM result and only the numeric `dp_*` / `confidence` fields were
interpolated — the display fields (`label`, `stage_key`, `short`, `subtitle`,
`tier`, `category`, `beyond`) kept the NM values. Reform re-derived its label
from the interpolated DP; the alternative modes did not.

#### Fix

New public `fields_from_dp(dp)` helper in each estimator that re-derives every
DP-dependent display field from a `dp_*` value:

- `src/07_model/signicial_estimator.py` — stage_key / label / short / subtitle / beyond
- `src/07_model/shoegazer_estimator.py` — stage_key / label / short / beyond
- `src/07_model/celestial_estimator.py` — tier / category / short / label / beyond (via `_dp_to_slot`)
- `src/07_model/ln_course_estimator.py` — stage_key / label / short / beyond

`src/pipeline.py` now calls the matching helper after interpolating each mode's
DP, so the displayed stage always matches the interpolated DP. Verified with the
reported scenario (Alpha → DT 1.6×): the stage now follows the DP monotonically
instead of reverting to Alpha.

### 2. Custom Rates Below HT (0.75×): Calculation Frozen

#### Problem

Raising the clock rate above HT 0.75× updated the estimate normally, but rates
**below** 0.75× produced the exact same result as 0.75× — as if the overlay
stopped receiving data (confirmed general, not skin-specific).

#### Root Cause

In `analyze_map()` the `< 0.75` branch hard-coded `_t = 0.0`, so the interpolated
result was always the full 0.75× analysis.

#### Fix

`src/pipeline.py` — rates below 0.75× now **extrapolate** against the 0.75–1.0
segment (`t = (rate − 0.75) / 0.25`, negative below 0.75) instead of clamping.
Verified monotonic across the full lazer range (0.5× → 2.0×) for SR, DP, BPM and
every alternative mode; low extrapolations are floored safely (Reform clamps to
1st Dan via `dp_to_label`, alternative modes clamp to their minimum stage).

### 3. Skin 8 (Hero-Dan Lazer) Live Timer Frozen

#### Problem

The live timer added to the LENGTH pill of the Hero-Dan Lazer skin stayed frozen
at `0:00 / --:--` during gameplay.

#### Root Cause

`renderMapDuration()` — which mirrors the timer into the pill and advances the
playback globals (`currentPlaybackMs` / `currentTotalMs`) — started with
`if (!ui.mapDuration) return;`. Skin 8 has no `#mapDuration` element (it exists
only in the other skins' markup), so the function bailed on every MUSIC_TIME
event before reaching the `#ui-len` mirror.

#### Fix

`src/01_overlay_ui/web/overlay.js` — the guard now bails only when **both**
`#mapDuration` and `#ui-len` are missing. Other skins are unaffected; skin 8's
LENGTH pill now counts live during gameplay.

---

## Visual Changes

### Skin 7 — Sunny Rebirth (`ui-7`)

#### Animated Map Title Marquee

Integrated the sliding track with ghost copy (`skinMapTitleWrap`,
`skinMapTitleTrack` and `skinMapTitleGhost`). When the map name is long, the
title scrolls smoothly and continuously; short titles stay static.

#### Dynamic Transparent Gradient Mask (`.has-marquee`)

A fade is applied on the left/right edges via
`-webkit-mask-image: linear-gradient(...)`.

**Smart behaviour:** the mask **only activates while the title is actually
scrolling**. If the map name is short and fits on screen, it stays **100% solid
and sharp**, with no unwanted transparency at the corners.

### Skin 8 — Hero-Dan Lazer (`ui-8`)

#### Full Support for Alternative Modes (Celestial, Signicial, Shoegazer, LN Course, 7K)

- **Category label (`#ui-category`):** switches dynamically between
  `CELESTIAL 4K`, `SIGNICIAL 4K`, `SHOEGAZER 4K`, `LN COURSE`, `7K` and
  `REFORM 4K`.
- **Dan Points (`#ui-dp-int` / `#ui-dp-dec`):** shows the real, exact DP of the
  active mode (`dp_celestial`, `dp_signicial`, `dp_shoegazer`, `dp_ln`, `dp_7k`).
- **Mode-specific palette:** automatically assigns the official palette of each
  mode/stage to the HUD CSS variables.

#### Full Multi-Colour Palette Visualisation

- **Neon background triangles (`#bg-canvas`):** floating particles now pick
  randomly among **all 3–4 colours** of the active Dan's palette (leveraging
  full palettes such as 8th Dan, 10th Dan, Gamma, Signicial VII, etc.).
- **Side neon pillars (`--c-pillar-grad`):** the vertical pillars now cycle
  smoothly through the Dan's complete colour range.

#### DP Sublevel Pills with Intensity Gradient (`#ui-pills`)

When the sublevel pills light up (`LOW` → `HIGH`), a **progressive intensity
gradient** is generated left-to-right: the leftmost pills start soft and
increase opacity and neon glow towards the right.

#### Higher Contrast & Visibility on the Stat Cards (`stat-pill`)

MSD, Star Rate, BPM and Length containers were redesigned with a dark frosted
glass background (`rgba(10, 12, 18, 0.84)` + `backdrop-filter: blur(12px)`),
a high-contrast thin border (`rgba(255, 255, 255, 0.16)`), drop shadow and
bright typography — they now stand out cleanly above the background triangles.

#### Live Timer in the LENGTH Pill (`#ui-len`)

The timer is synchronised in real time during gameplay in
`elapsed / total` format (e.g. `0:00 / 2:13` → `1:15 / 2:13`).

#### Animated Map Title Marquee

Same horizontal scroll structure and conditional transparent mask as Skin 7.

---

## Files Modified

- `docs/changelog-2.3.1.md`
- `src/01_overlay_ui/web/overlay.js` — timer mirror fix, per-mode display logic,
  marquee ghost sync, palette plumbing (`window.__currentPalette`)
- `src/01_overlay_ui/web/ui-7/skin.css` — marquee wrap + conditional fade mask
- `src/01_overlay_ui/web/ui-8/index.html` — marquee structure, particle palette
- `src/01_overlay_ui/web/ui-8/skin.css` — marquee, pillar gradient, pill glow,
  glassmorphism stat cards
- `src/07_model/celestial_estimator.py` — `fields_from_dp()`
- `src/07_model/ln_course_estimator.py` — `fields_from_dp()`
- `src/07_model/shoegazer_estimator.py` — `fields_from_dp()`
- `src/07_model/signicial_estimator.py` — `fields_from_dp()`
- `src/pipeline.py` — HT extrapolation, alternative-mode label re-derivation

---

*Release: 2.3.1 — 2026-08*
