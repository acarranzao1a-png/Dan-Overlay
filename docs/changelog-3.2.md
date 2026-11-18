# DanOverlay 3.2 — The Rice Model

## Summary

Version **3.2** replaces the correction stack that had carried ISOR since 3.0 with a gradient-boosted
model trained on the engine's own projections, and documents what that model cannot do as carefully
as what it can.

**This is not the release where ISOR became the best estimator on the benchmark.** Koishi still
leads on mean absolute error in every scope measured, and on the official dan packs it leads by a
wide margin. **It is the release where ISOR stopped being a middle-of-the-field engine and became
the most precise one on the metric the scene actually argues about**: the share of charts landed
within ±0.20 dan, where it is now first of all nine estimators, with full coverage.

The full breakdown — every table, the head-to-head matrix, the in-sample caveat and the per-skillset
split — lives in the engine document:
**[src/08_isor_engine/README.md](../src/08_isor_engine/README.md)**.

---

## 1. What changed in ISOR

The 3.0/3.1 pipeline fused three physics projections and applied a multi-head Ridge/RBF correction on
top. 3.2 keeps the physics and replaces the correction with a model that reads the engine's own
output.

- **Input**: 124 columns — the 4 canonical projections, 109 structural features and 11 curve
  statistics.
- **Model**: gradient-boosted trees, 500 of them at depth 3, learning rate 0.03, subsample 0.8,
  **Huber loss (α = 0.7)**. Exported to JSON and walked in pure Python, so the build carries no
  machine-learning dependency.
- **Gate**: the model answers only when the engine's own `DP` falls inside `[12.0, 15.0)`. Outside it
  the calibrated physics projection stands, because trees cannot extrapolate and measured worse
  there — roughly eight points of exact rate lost in the 9–12 bands.
- **Fallback**: delete `config/rice_model.json` and the engine reverts to the physics path with no
  other change.

### The metrics

| scope | exact rate | MAE | note |
|---|---|---|---|
| 3.1 correction stack | 57.0 % | 0.2449 | 644-map scope |
| **3.2, out-of-fold** | **67.83 %** | **0.1962** | 1262 rice maps |
| **3.2, shared with Koishi** | **71.79 %** | **0.1741** | 1106 maps |
| 3.2, in-sample | 83.82 % | 0.1239 | never published |
| **3.2, high band 11–17** | **71.89 %** | 0.1722 | **best exact of any estimator** |

**The last row is the headline.** On the competitive band ISOR has the highest exact-tier rate of any
of the nine estimators measured — ahead of Koishi, Mixed, XDC1, ROXY and the rest — while covering
all 1103 charts.

**The in-sample row is the reason the out-of-fold one is quoted.** A model scored on its own training
data reports twelve points more than it deserves.

### Where it still loses

- **Mean absolute error.** Koishi scores 0.1510 on the high band against ISOR's 0.1722, and 0.1540
  against 0.1962 on the full ladder. The gap is a heavier tail, not a worse average fit: ISOR has
  four times as many charts beyond 0.50 error.
- **The official dan packs.** These sit mostly in the high tiers, outside the model's gate, so the
  physics projection answers alone. Koishi scores 0.2253 MAE there against ISOR's 0.2844 on the same
  48 charts it answers.

---

## 2. What was tried

The 3.2 numbers did not come from one idea. They came from a long list of things that were measured
and thrown away.

### What worked

| lever | effect |
|---|---|
| **Model over the engine's projections** | the base of the gain — the four projections alone already reach 65 % |
| **Huber loss, α = 0.7** | +0.9 pp exact over squared error, and a lower MAE |
| **The gate** | without it the model drags the low tiers down; with it the band improves and the rest is untouched |
| **Full 1364-map corpus** | the previous 644-map scope hid the tails; measuring all of it is what made the tail problem visible |

### What did not

Every item below was measured out-of-fold and lost to the configuration that shipped.

| lever | result |
|---|---|
| Sub-band models (one per dan band) | 66.6 % exact — worse than the global model |
| Wider gate | 68.5 % — the model degrades outside the band it was validated on |
| Out-of-gate model plus clipping | worse than the physics projection |
| Tail specialist model | no gain over the gated model |
| One model per skillset | 71.3 % — `speed` and `tech` lack the rows to fit 124 columns |
| Direct MAE loss (`absolute_error`) | 71.2 % — optimising the metric directly made it worse |
| Seed ensembles, sample weighting, ET/RF blends | no gain |
| SVR | 58.0 % |
| Feature selection (top-K) | worse at every K |
| Ordinal labels | no gain |
| Grid snapping to tier boundaries | **rejected as benchmark gaming** — it raised the reported score without improving the estimate |

**The last one matters.** It was the only lever that produced a double-digit jump, and it was
discarded because the jump came from snapping predictions onto the boundaries of the metric, not from
predicting the charts better. A number obtained that way is not a measurement.

---

## 3. Three new skins

| ID | Name | Default layout |
|---|---|---|
| **10** | Dynamic Orbital Island | collapsed, 661 × 122 |
| **11** | Chrono-Tachometer Blade | collapsed, 784 × 197 |
| **12** | Swiss Brutalist Ticker | collapsed, 630 × 132 |

## 4. One size specification for twelve skins

Window sizes used to be duplicated between a code table and per-skin numbers, and the copies drifted.
3.2 replaces them with a single machine-readable reference — `config/skin_dimensions.json` — and a
generated document, `docs/skin-dimensions.md`.

- Every layout of every skin records its **viewport** size and its **window outer** size (the viewport
  plus the 16 × 39 px Windows frame).
- `set_window_size` now receives the **client** size and converts it with `AdjustWindowRectEx`, so a
  skin declared at 661 × 122 renders at 661 × 122 instead of 647 × 108.
- Every skin opens in its own natural format instead of inheriting the previous skin's window.

## 5. Half the executable

| | 3.2.0-beta | 3.2 |
|---|---|---|
| single-file executable | 147 MB | **71.4 MB** |

- `pandas` and `tzdata` were imported during warm-up and **never used**; they are gone from the code,
  the module list and the bundle.
- `scipy`, `sklearn`, `matplotlib`, `IPython`, `pytest` and `tkinter` are excluded explicitly, so a
  development environment that happens to have them installed cannot leak them into a release.
- The Qt runtime the previous build carried as a fallback backend is no longer collected; the overlay
  runs on WebView2 through WinForms, which is what it always used.
- Bytecode is compiled with `--optimize 1`.

## 6. Benchmarking that can be audited

- **Full corpus.** All 1364 benchmark maps are answered and published, not a 644-map subset.
  `src/08_isor_engine/ISOR.csv` now holds the complete 1364-row prediction file.
- **Out-of-fold.** The shipped CSV contains cross-validated predictions inside the model's gate; the
  in-sample result is documented and labelled as unfit to publish.
- **A standalone figure generator.** `tests/prototype/02_benchmarks/benchmark_charts.py` renders the
  eight benchmark figures with matplotlib alone. The previous generator drove headless Chromium and
  failed silently when the browser could not launch, leaving stale images in place.
- **The benchmark's own caveat is quoted** next to the tables, because its author states that the
  results are statistical references and not a conclusion that one algorithm is better.

## 7. Interface and housekeeping

- **Version labels.** `3.2.0-beta` and the "Open Beta Testing" wording are removed from the window
  title, the mode label and the build artefact.
- **Text pass.** Emoji removed from UI strings, mojibake fixed, third-party attribution reworded, and
  references to the benchmark engine removed from engine comments.

---

## 8. Where 3.2 stands

**Not the best estimator. The most precise one on the metric the scene argues about.**

Against the field, on the 1103 maps of the high band:

| | exact rate | MAE |
|---|---|---|
| **ISOR 3.2** | **71.89 % (#1)** | 0.1722 (#4) |
| Koishi | 71.53 % | **0.1510 (#1)** |
| Mixed | 69.72 % | 0.1699 |
| XDC1 | 67.97 % | 0.1717 |
| ROXY | 63.78 % | 0.1980 |

Seven of the eight pairwise head-to-heads go to ISOR on per-map error; the eighth, against Koishi,
does not.

**What that means in plain terms**: if the question is "which engine lands inside the accepted window
most often", 3.2 is the answer. If the question is "which engine is closest on average", it is not,
and the difference is concentrated in the charts the model was never allowed to touch.

---

## 9. Future work

### Interlude (YAVSRG) compatibility

**Planned for the next release.** DanOverlay today reads live state from two games: osu!mania through
`tosu`, and Etterna through the Lua actors in `src/02_runtime_bridge/etterna/bridges/`. **Interlude —
the rhythm game client of the [YAVSRG project](https://github.com/YAVSRG/YAVSRG) — is the obvious third**,
and adding it means a new source module next to the two existing ones, not a change to the engine.

What the work involves, based on how the project is structured:

1. **A `bridge`/`source` module in the shape of `tosu_source.py` and `etterna_source.py`**: detect the
   game process, resolve the active chart, and publish the same normalised chart dictionary the rest of
   the pipeline already consumes.
2. **Chart ingestion.** Interlude parses osu! and its own formats through **Prelude**, its core library.
   Anything it converts can be handed to the existing parser; anything native needs a reader.
3. **Post-play results.** Prelude owns score storage and score calculations, so the local score database
   is the cleanest source for a finished run — the equivalent of the Etterna evaluation screen.
4. **Live gameplay state.** This is the open question: the client publishes a protocol for talking to
   its *server* (`Interlude.Web.Shared`), not for third-party overlays. A live overlay needs either a
   documented hook or a small companion process, and that is a research step before it is a coding step.

**Honest framing**: items 1–3 are ordinary adapter work. **Item 4 has no public integration point that
I could find, so the first deliverable is a conversation in the YAVSRG Discord, not a pull request.**
This section says what would be built, not that it is scheduled.

### The tail

The gap to Koishi is structural, not statistical: it lives in the ~160 charts outside the model's
gate. Five approaches have been measured and rejected (§2). **The next one worth trying is not a
better model but a better bracket**: a second gated model trained only on the 9–12 band, where the
physics projection is demonstrably weakest, with its own out-of-fold validation.

---

## Upgrade notes

- `config/rice_model.json`, `config/classifier_model.json` and `config/skin_dimensions.json` are new
  required files. The build refuses to start without them.
- `src/08_isor_engine/ISOR.md` is now `src/08_isor_engine/README.md`.
- `docs/skin-dimensions-frameless.md` is now `docs/skin-dimensions.md`; the JSON keys `frameless` and
  `framed_outer` are now `viewport` and `window_outer`.
- The benchmark prediction file `ISOR.csv` moved from 746 to 1364 rows. Consumers that assumed the
  old scope must filter by `pattern`.
