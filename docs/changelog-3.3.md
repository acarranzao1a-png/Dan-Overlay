# DanOverlay 3.3 — Two More Ratings, and a Chart Worth Keeping

## Summary

Version **3.3** does not change how ISOR estimates difficulty. The rice model from 3.2 is untouched,
the calibration is untouched and every number the engine computes is the same one it computed
before.

**What changes is what you are allowed to see.** The overlay can now show the MSD that Etterna
actually displays, the Quaver Skill Rating, or both, selectable from the settings panel. The chart
exporter was rebuilt around a single large dan mark instead of a row of generic boxes. Twelve skins
learned to rename their own labels when the metric changes, so no screen says "MSD" while showing a
Quaver number.

Alongside that, three user-facing bugs were fixed: Etterna was only found if it lived in one of eight
hardcoded paths, its note grades were promoted one step early, and osu!lazer could leave the overlay
showing the previous map's numbers under the new map's title for as long as the map lasted.

**One optimisation was attempted and reverted.** It is documented in section 5 with its measurements,
because a negative result that is not written down gets attempted again.

---

## 1. Two more difficulty numbers

### 1.1 MinaCalc v527

The binary the engine had been calling was a MinaCalc build of unknown provenance and no version
string. Comparing it against a fresh v527 build on the same charts showed why Etterna disagreed with
us: `jackspeed`, `technical` and `handstream` matched to the millisecond, while `stream` differed by
up to 1.7 and `stamina` by up to 3.3. That is the profile of the version that rewrote those two
skillsets — the old binary was simply older.

`tools/bin/msd527.exe` (432 KB, built from `tools/msd527` with `minacalc-rs` 527) replaces it **for
display only**. It answers the same stdin/stdout contract plus a `version` field, and runs in 10 ms
against the old binary's 22 ms.

Two modes are exposed, because they are not the same number:

| mode | meaning |
|---|---|
| `ssr` | score-relative, the score goal applies (default 0.93) |
| `msd` | raw, uncapped |

### 1.2 Quaver Skill Rating

`tools/bin/qsr/` wraps [Quaver.API](https://github.com/Quaver/Quaver.API) (MPL-2.0), which already
ships an `.osu` parser and the key-mode difficulty calculator. The rating is the calculator's
`OverallDifficulty`; nothing was reimplemented.

Two things are worth recording:

- **The bundle was trimmed.** A plain build copies nineteen files (3.4 MB) because Quaver.API
  declares MonoGame, ImageSharp, SQLite, Newtonsoft and YamlDotNet. Removing them one at a time until
  the process failed left six files and 394 KB; only `DeepCloner` is loaded at runtime. Verified
  against 42 charts across every tier with no failures.
- **The converter truncates silently.** One chart carrying inherited timing points at −100 slider
  velocity converts three notes out of two thousand, which would render as a rating near 1.5. The tool
  therefore reports the converted note count, and the bridge withholds the number when it does not
  match the source file. No rating is better than a wrong one.

### 1.3 The selector

Every skin's settings panel gains a **Difficulty Metric** selector: `MinaCalc (Etterna)`,
`Quaver Skill Rating`, or `Both`. In `Both` the main slot keeps the MSD and the QSR appears in a small
pill in the corner.

### 1.4 What this does not touch

`dp_msd` carries **20 % of the physics triangulation** and is **one of the four projections** the rice
model reads. Swapping that source would silently invalidate the 3.2 calibration, so it was not
swapped. The engine keeps calling the old `msd.exe`; the new binaries feed presentation fields only.

If either binary is missing, blocked by antivirus or the .NET runtime is absent, the overlay falls
back to the engine's own MSD. Nothing breaks and nothing is shown that is not known to be right.

---

## 2. The chart exporter, rebuilt

The exported image is what people post, so it got the most work this release.

- **Proportions.** 1800 × 980, with a symmetric 416 px card body inside a 546 px graph frame, which
  removed the empty bands the old layout carried.
- **The dan mark.** The row of square boxes is gone. The estimated dan is now a 170 px glyph with a
  radial ambient glow behind it, captioned by a small mono `ESTIMATED TIER` line, in the official
  chromatic gradient for that dan.
- **Density curve.** A continuous vertical gradient fill following notes-per-second, replacing the
  separate vertical lines that read as a bar chart.
- **Sustained NPS.** A new KPI: the average density of the sustained hard sections, drawn as a dotted
  cyan reference line with a right-axis badge and a peak pill. This answers "what does this map demand
  on average during its hard parts", which a peak figure does not.
- **Etterna and osu! side by side.** Etterna exports its original banner at its real aspect ratio,
  labels the figure `OVERALL MSD`, shows the difficulty as `[Hard 21]` and lists rates and credits
  cleanly. osu! exports a focused mini-banner, drops the `.osu test files` path from the corner, and
  removes the redundant `1.00X NM` badges and `CLASS //` prefixes.
- **v527 in the export.** `chart_export.py` prefers `display_msd` over the engine value when it is
  available, so the exported skillsets match what the overlay showed.

---

## 3. Every skin learns to say the right name

Each skin now declares its own label pair and swaps between them when the metric changes, because a
screen that reads "MINACALC MSD" above a Quaver number is worse than no label at all.

| skins | MSD label | QSR label |
|---|---|---|
| 1, 2, 8, 9 | `MSD` | `QSR` |
| 4, 5, 6 | `Etterna MSD` | `Quaver QSR` |
| 7, 10, 11 | `MINACALC MSD` | `QUAVER QSR` |
| 12 | `MINACALC_MSD` | `QUAVER_QSR` |

`_updateMetricLabels()` drives the swap. The secondary pill has a ghost element and a fallback element
per skin so the two-number mode does not break any container.

---

## 4. Bug fixes

### 4.1 Etterna is found wherever it is installed

`_PROCESS_QUERY_LIMITED_INFORMATION` was referenced but never defined. The resulting `NameError` was
swallowed by a bare `except`, so process-path lookup always failed and only eight hardcoded
install paths could ever match — anyone who had moved or renamed the Etterna folder was invisible to
the bridge.

Defining the constant was not enough: `OpenProcess` without a declared `restype` returns a truncated
32-bit integer for a 64-bit handle, so `QueryFullProcessImageNameW` failed anyway. The Win32 calls now
declare `argtypes` and `restype`, `CloseHandle` runs in a `finally`, and the `except` was narrowed to
`OSError` so a `NameError` can never hide there again. `Program Files (x86)` was added to both
candidate lists, the theme is patched again when Etterna starts, and `%APPDATA%\Etterna\Save` is used
when the install root has no `Save` folder.

### 4.2 Etterna note grades were one step early

The thresholds used the `+` variants of each grade instead of the base grade, which promoted a score
to the next rank a fraction early. Corrected to `99.9935 / 99.970 / 99.80 / 96.50 / 85.00` for
AAAAA / AAAA / AAA / AA / A; B and C unchanged.

### 4.3 DevTools could ship again

The released 3.2 binary opened Edge DevTools on launch while the source, HEAD and working tree all
said `debug=False`. The bundled bytecode was disassembled to confirm it, rebuilt, and the call is now
pinned with a comment explaining why it must stay `False`.

### 4.4 osu!lazer: the analysis that was thrown away

This one looked like an engine bug and was not.

The coordinator identified each request with `md5 | version | sequence`, where the sequence
incremented on every map-change notification. Any second notification arriving while the pipeline was
running therefore invalidated the analysis in flight: the result was discarded **silently**, no event
was emitted, and the overlay kept showing the previous map's numbers under the new map's title.

lazer produced those notifications continuously. The change detector compared
`tuple(active_mods)`, and in lazer that array is read from three different contexts
(`menu` / `play` / `resultsScreen`) whose order is not stable. In stable the same information arrives
as a numeric bitmask that does not move. So the storm, and the discarded results, were lazer-only.

Four changes:

- The token now identifies the request by what it depends on — md5, path, version, mod, rate, engine —
  so a duplicate for the same map no longer invalidates anything.
- An in-flight guard stops a duplicate from starting a second pipeline run.
- A dispatch whose result is already cached serves the cache instead of recomputing.
- A `finally` always releases the in-flight slot, including when a result is legitimately dropped.

On the detector side, `MAP_CHANGED` now fires only when the md5, the rate, the rate label or **the
path** changes. `active_mods` is still tracked and passed through, but it no longer triggers
reanalysis.

### 4.5 Why it looked like an LN overestimation

The report was that LN maps are overestimated in lazer but not in stable. Analysing the chart in
question — Kyutatsuki, *Sea of Stars [Constellations]* — with the shipped engine gives **15.24 DP,
Epsilon**, on both clients; it carries 2364 long notes out of 8737 (37 %), so it routes to the legacy
LN engine and returns MSD 35.61 at every rate tested, from 1.00 to 1.60.

The 20.99 Kappa seen in the report came with `MSD --.--`, and no rate of that chart removes the MSD.
It was the previous map's result, still on screen because of 4.4. **The engine was never wrong about
the LN map; the result for it never arrived.**

### 4.6 Regression test

`tests/prototype/02_benchmarks/test_lazer_mapchange.py` asserts both halves: a duplicate notification
still delivers exactly one result, and reordering the mod array emits nothing.

---

## 5. An optimisation attempt that did not survive measurement

The engine has one aggregate stamina feature. A dynamic tank was built instead: density above a
baseline drains it, rests refill it, and five shapes are measured from the resulting curve — minimum
level, time below half, longest sustained drain, recovery ratio, depletion rate. The constants are
physical rather than fitted: a sustained load at the map's p90 empties the tank in about 45 seconds.

**It helped exactly where the model is not allowed to look.** Measured against the same five-fold
split:

| configuration | all charts | inside the gate |
|---|---|---|
| 3.2 (124 inputs) | 0.1962 MAE / 67.35 % | 0.1564 / 73.83 % |
| + stamina (129 inputs) | **0.1956** / 66.64 % | **0.1556** / 72.87 % |

Mean absolute error improved by 0.0006 and exact rate fell by 0.71 points, 0.96 inside the gate. The
large gain the first experiment showed — 31.6 % to 52.6 % exact in the 17+ band — was real but
irrelevant: the gate stops at 15, so the model never touches those charts.

**Reverted.** The feature code, the model and the CSV were all restored; the ship state is byte for
byte the 3.2 estimator.

A second thing came out of the same session and is worth recording. On 1461 community practice-pack
charts, the model scores 32.5 % exact tier against 48.9 % for the raw physics. The folder labels in
those packs are community-made and not all correct, so this is not proof of anything — but it is the
first sign that the model may be fitted to the benchmark's labelling style rather than only to
difficulty. It is logged as an open question, not as a change.

---

## 6. Benchmark data

`src/08_isor_engine/ISOR.csv` now covers the benchmark's current 1382 charts instead of the 1280 rows
the previous submission answered, adding the 18 charts the benchmark gained after that submission.
The 18 were never in the model's training set, so their predictions are genuinely out of fold.

| | published in the benchmark | 3.3 |
|---|---|---|
| rows with a value | 1280 | **1280** |
| rice MAE | 0.2672 | **0.2047** |
| rice exact rate | 52.81 % | **67.27 %** |

The 102 long-note rows keep the previous submission's explicit scope declaration rather than
publishing estimates the engine cannot stand behind.

---

## 7. Requirements and build

- **.NET 8 desktop runtime is required for QSR.** Without it the process does not start and the
  overlay simply shows the MSD. This is a soft dependency by design, and it is the reason QSR is a
  separately built folder rather than a second binary.
- **`build.bat` bundles both additions behind `if exist` guards**, so a checkout without them still
  builds; it warns instead of failing.
- **Size.** `msd527.exe` adds 432 KB and the QSR folder 394 KB, against a ~71 MB executable.
- **Nothing machine-learning related was added.** The rice model is still walked in pure Python.

---

## 8. Where 3.3 stands

**The estimator is the 3.2 estimator.** Out-of-fold: 67.83 % exact, 0.1962 MAE on 1262 rice charts;
71.79 % / 0.1741 on the 1106 shared with Koishi. Those figures did not move, and section 5 explains
one attempt to move them that did not work.

What 3.3 changes is trust in the display: the MSD on screen is now the one Etterna shows, a second
rating is available for people who want it, the exported chart is worth posting, and a lazer session
no longer leaves stale numbers on screen.