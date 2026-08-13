# DanOverlay 2.3.5 — Skin 9, Custom-Rate SR Directo y Rendimiento

## Summary

Version 2.3.5 rewrites the custom clock-rate calculation to produce the
**true engine SR** at every rate (matching ManiaMapAnalyser), adds a full-result
analysis cache (~60 % faster custom-rate switching), eliminates the last
"Blocked external WebSocket request" message from tosu, ships a brand-new
streamer skin (Skin 9 — "Josh type shit") with three calibrated layouts, and
fixes green-screen behaviour on skins without `#danPanel`.

---

## 1. Custom Clock Rates: True Engine SR (was: Linear Interpolation)

### Problem

Custom lazer rates (e.g. DT 1.25×) were estimated by linearly interpolating
the final result between the native anchors (0.75× / 1.0× / 1.5×). That
**systematically underrated mid rates** — the engine's SR-vs-rate curve is not
linear (e.g. 8.73 SR at 1.25× but 10.10 at 1.5×), so a linear interpolation
between the anchors produced values below the true engine SR. On maps inside
the engine's intrinsic "W" response the interpolated SR/DP could even
**decrease** when the rate increased.

### Solution

- `src/02_runtime_bridge/primary_sr_bridge.py` — new `_scale_osu_timings()`:
  writes a temp `.osu` with hit times **divided by the rate** (the engine's
  own DT mod applies `h / 1.5`, so `1/rate` is the correct scaling) and runs
  the engine with `mod="NM"` → the **true SR at the custom rate**.
- `src/pipeline.py` — custom rates now run the pipeline **directly** at that
  rate (single pass: SR, DP, classifier, alternative modes and MSD all true),
  instead of interpolating two anchor analyses.
- `_monotonic_floor()` — the result is floored against the nearest lower
  native anchor (DP, SR and every alternative-mode DP, with labels re-derived)
  so the dan can never decrease with the rate, even on maps where the raw
  engine SR dips.

Verified against rate-scaled test files (0.9×–1.25×): SR matches the true
engine value within ±0.01 across the board and the DP/dan is identical to a
native-rate run.

## 2. Performance: Full-Result Analysis Cache

`_analyze_map_impl` now caches its complete result keyed by
`(path, mtime, mod, strict_domain, rate)` with a 96-entry LRU and deep copies
on read/write. The Sunny engine (~300 ms on dense maps, ~70 % of the cost)
is the bottleneck; the cache removes duplicate work:

| Scenario | Before | After |
|----------|--------|-------|
| New custom rate (with anchor) | ~600 ms (2× Sunny) | ~240 ms (1× Sunny) |
| Rate already computed | — | 1.5 ms |
| Internal floor anchor | recomputed every time | once per session |

## 3. tosu Connection: "Blocked external WebSocket request" Fully Eliminated

The legacy JS WebSocket (origin `file://`, rejected by modern tosu) was being
opened unconditionally after a rewrite dropped the guards — producing the
blocked-request log again. Both guards are restored and hardened:

- `connect()` refuses to open the socket while the pywebview bridge exists
  (kills any reconnect loop instantly).
- `boot()` waits for the `pywebviewready` event before deciding — the bridge
  is injected a moment after boot, so the old one-shot race that logged a
  single blocked request at startup is gone too. A 3 s fallback timer covers
  plain-browser dev mode, where that event never fires.

Result: **zero** "Blocked external WebSocket request" messages in tosu.

## 4. New Skin: Skin 9 — "Josh type shit"

A streamer-focused HUD with three layout densities toggled with **L**:

| Layout | Window |
|--------|--------|
| Complete | 485 × 169 |
| Simplified | 485 × 158 |
| Compact | 370 × 120 |

- Dimensions calibrated with the built-in resolution meter (no zoom).
- The active layout is **persisted** in settings and restored on launch with
  its own window size (previously the layout was restored only as CSS classes,
  so the window kept the default size).
- **Ctrl+R** now resets to the active layout's default size instead of the
  generic 700×320, and no longer forces the layout back to "complete".
- Registered in every skin's settings dropdown, `overlay_host.py` and the
  startup defaults.

## 5. Green Screen Fixed (Skins Without `#danPanel`)

### Problem

The green-screen toggle looked up `#danPanel`, which skins 7/8/9 don't have
(they use `main#overlay`). The class was never applied, so only the map
background was hidden (`opacity: 0`) while the dark scrim stayed visible —
"the background goes fully dark". On disable the inline opacity was never
restored — "it stays black".

### Solution

- The panel lookup falls back to `#overlay`, so the `green-screen` class is
  applied to the right element and the chroma-green CSS engages properly.
- The background's previous opacity is saved on enable and **restored on
  disable**, so the map returns immediately.
- Skin 9 keeps its text outlines over the chroma background (the green-screen
  rule that stripped `text-shadow` was removed) and the map title + difficulty
  now have an explicit black outline (`ui-9/skin.css`).

## 6. Build & Packaging

- **`build.bat`** — `--specpath build\spec` previously made PyInstaller
  resolve relative paths against the spec directory (`Unable to find
  build\spec\src\01_overlay_ui\web`). All paths (`ENTRY`, `--add-data`,
  `--add-binary`, `--paths`, `--icon`, `--workpath`, `--distpath`) are now
  absolute (`%CD%`); the spec is generated inside `build\spec\` and cleaned
  automatically.
- **Spec files** — `*.spec` added to `.gitignore` and the tracked specs
  (2.2.0/2.3.0/2.3.1) removed from the repository; they are regenerable build
  artifacts.
- **Version bump to 2.3.5** in `build.bat`, the window title
  (`overlay_host.py`) and every skin's "What's New" screen.

---

## Files Modified

- `src/02_runtime_bridge/primary_sr_bridge.py` — `_scale_osu_timings`, direct
  custom-rate calculation
- `src/pipeline.py` — direct custom-rate path, `_monotonic_floor`, full-result
  LRU cache
- `src/01_overlay_ui/web/overlay.js` — WS guards + `pywebviewready`, skin 9
  layouts (L, persistence, Ctrl+R), green-screen fix
- `src/01_overlay_ui/web/ui-9/` — **new** Skin 9 (index.html, skin.css)
- `src/01_overlay_ui/web/ui-9` integration in all skins' dropdowns + What's New
  version
- `src/01_overlay_ui/overlay_host.py` — version 2.3.5, skin 9 registration
- `build.bat` — version 2.3.5, specpath fix (absolute paths)
- `.gitignore` — `*.spec`; tracked specs removed

---

*Release: 2.3.5 — 2026-08*
