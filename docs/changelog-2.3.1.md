# DanOverlay 2.3.1 — Custom-Rate Fixes & Hero-Dan Lazer Polish

## Summary

Version 2.3.1 fixes three calculation/display bugs — two reported by users
(custom clock rates in osu!lazer) and one found while developing the timer for
the Hero-Dan Lazer skin — and includes visual polish on the Sunny Rebirth and
Hero-Dan Lazer skins.

---

## 1. Custom-Rate Interpolation: Alternative-Mode Stages Reverted to the NM Value

### Problem

With a native rate (DT 1.5× / HT 0.75× / NM 1.0×) the overlay estimated the
correct stage, but with any osu!lazer **custom** rate the Signicial / Shoegazer
(and also Celestial / LN Course) stages reverted to the no-mod value.

Reported example: a map estimated **Alpha** at NM — enabling DT (1.5×) correctly
jumped to **Eta**, but increasing the rate by a tenth in lazer (1.6×) snapped
back to **Alpha** even though the displayed DP kept rising.

### Root Cause

`analyze_map()` computes the full result at the two nearest native rates and
interpolates the final fields for custom rates. The alternative-mode dicts were
copied from the NM result and only the numeric `dp_*` / `confidence` fields were
interpolated — the display fields (`label`, `stage_key`, `short`, `subtitle`,
`tier`, `category`, `beyond`) kept the NM values. Reform re-derived its label
from the interpolated DP; the alternative modes did not.

### Fix

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

## 2. Custom Rates Below HT (0.75×): Calculation Frozen

### Problem

Raising the clock rate above HT 0.75× updated the estimate normally, but rates
**below** 0.75× produced the exact same result as 0.75× — as if the overlay
stopped receiving data (confirmed general, not skin-specific).

### Root Cause

In `analyze_map()` the `< 0.75` branch hard-coded `_t = 0.0`, so the interpolated
result was always the full 0.75× analysis.

### Fix

`src/pipeline.py` — rates below 0.75× now **extrapolate** against the 0.75–1.0
segment (`t = (rate − 0.75) / 0.25`, negative below 0.75) instead of clamping.
Verified monotonic across the full lazer range (0.5× → 2.0×) for SR, DP, BPM and
every alternative mode; low extrapolations are floored safely (Reform clamps to
1st Dan via `dp_to_label`, alternative modes clamp to their minimum stage).

## 3. Skin 8 (Hero-Dan Lazer) Live Timer Frozen

### Problem

The live timer added to the LENGTH pill of the Hero-Dan Lazer skin stayed frozen
at `0:00 / --:--` during gameplay.

### Root Cause

`renderMapDuration()` — which mirrors the timer into the pill and advances the
playback globals (`currentPlaybackMs` / `currentTotalMs`) — started with
`if (!ui.mapDuration) return;`. Skin 8 has no `#mapDuration` element (it exists
only in the other skins' markup), so the function bailed on every MUSIC_TIME
event before reaching the `#ui-len` mirror.

### Fix

`src/01_overlay_ui/web/overlay.js` — the guard now bails only when **both**
`#mapDuration` and `#ui-len` are missing. Other skins are unaffected; skin 8's
LENGTH pill now counts live during gameplay.

## 4. Skin Polish (Sunny Rebirth & Hero-Dan Lazer)

- **Marquee fade mask** — long map titles fade out at the edges instead of
  clipping hard (`has-marquee` mask on both `ui-7/skin.css` and `ui-8/skin.css`).
- **Hero-Dan Lazer palette-driven visuals** — particles now sample the full dan
  palette (via `window.__currentPalette`) instead of two colors; sublevel pills
  get a palette gradient with glow; the neon pillars use the complete palette
  gradient (`--c-pillar-grad`); stat pills got a glassmorphism restyle.
- **Per-mode display in Hero-Dan Lazer** — `_updateHeroDanLazerSkin()` now
  selects the correct category, DP source and palette per mode (Reform, 7K,
  LN Course, Celestial, Signicial, Shoegazer) instead of always using the Reform
  DP/label, and mirrors the map title into the marquee ghost.

---

*Release: 2.3.1 — 2026-08*
