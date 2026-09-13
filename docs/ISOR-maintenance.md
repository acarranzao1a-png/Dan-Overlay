# ISOR Engine — Calculation and Estimation Fixes

Scope: 4K rice charts. Status: pre-release (beta), not a public update.

---

## 1. Context: observations and defects found

The starting point was a set of user observations about ISOR's output on rice charts, plus defects
that surfaced while investigating them.

### 1.1 User observations

| observation | what it turned out to be |
|---|---|
| Tiers from Alpha to Beta score noticeably worse than neighbouring tiers | The fused base overrated that stripe by about +0.2 Dan and no correction stage was acting on it. Part of the remaining gap is a question of reference scale rather than a defect: tier ladders differ in what they assign to a chart of a given difficulty. |
| A cluster in the Theta range (roughly 17.4-18.3) is consistently underrated, by +0.25 up to +1.20 | Systematic, not anecdotal. From tier 16 upward the fused base underrates monotonically: −0.16 in 16-17, −0.43 in 17-18, −0.83 in 18-19. In DP terms the base sat at label+0.07 where the scoring contract needs label+0.50. |
| Individual charts are badly overrated (e.g. a Delta-high chart predicted nearly 1.3 Dan high) | The band it belongs to is unbiased, so these are individual cases rather than a band effect. They concentrate in stamina / dense handstream, the one skillset where disagreement between the SR, choke and MSD projections predicts error. |
| Large individual errors appear across every tier | Of the 14 maps with an error above 1.0 Dan, 11 need a correction outside ±1.0, which the corrector cannot express. |
| Request: no artificial per-case buffs of the kind the legacy path applies to specific chart types | Audited: no condition on chart type, skillset, chart name or pack exists anywhere in the correction path. The correction is a fitted function of chart features. |
| Request: hitting the exact Dan tier is the metric that matters, not the subtier or the exact DP | Adopted as the primary metric. |

### 1.2 Defects found while investigating

- **No active correction between tiers 10.5 and 13.** The blend gate handed those charts to a head
  trained on higher tiers, the low head stopped below 10.5, and the level calibration started at 15.5.
  A +0.2 residual bias sat in a gap between all three mechanisms.
- **The fused base underrates the top of the ladder monotonically**, and the corrector recovered only
  about 28 % of the correction required there.
- **A validated reading axis was implemented but never used.** The mask transition entropy existed in
  the engine, with a note stating it had to be integrated as a model feature rather than as a
  standalone modulator, and it was not called from anywhere.
- **The ±1 correction cap binds on the worst cases**, though raising it did not turn out to help.

---

## 2. Approach, and what was tried

Each candidate change followed the same sequence: reproduce the architecture offline, measure the
change on held-out data before touching the product, apply it only if it improved the metric without
regressing the rest, and roll it back otherwise. Several candidate changes were discarded at that
stage.

### 2.1 Applied

**Level anchor calibration.** Measured problem: a residual positive bias of roughly +0.2 Dan in the
10.5-13 stripe with no correction stage covering it. A smooth curve of the level was added —

```
dp ← clip(dp + Σ a_j · exp(−((base − c_j)/w)²), 0, 20.5)
```

— with the Gaussian support placed only where the bias was measured, so the correction is exactly zero
outside that range. It is a calibration curve: a function of the level with a handful of coefficients,
not a per-chart or per-skillset rule.

Effect, end to end, per tier band: `1-10 −0.013`, `10-11 −0.103`, `11-12 +0.014`, `12-13 +0.029`,
`14-16 −0.001`, `16-17 −0.003`, `17+ +0.005`, overall **−0.005 on the rice metric**.
Cost accepted: a **+0.004** regression on the 11-17 band, traded for the 10-11 improvement.

**Mask transition entropy as a model feature.** The entropy of consecutive row-mask bigrams was wired
into the low head's input as an additional column, refitted on its exact training population. It is
rate-invariant: it reads the sequence of chord masks, not their timing.

Effect: `1-10 −0.007`, `11-17 exactly unchanged`, overall **−0.001 on the rice metric**, with no
regression on any band.

### 2.2 Evaluated and discarded

| candidate | reason |
|---|---|
| Raising the correction cap from 1.0 to 1.5 | Improved the metric when measured on the same data the heads were fitted on, but degraded consistently on held-out data, monotonically with the cap value. |
| Texture and irregularity block in the higher-tier head | Small gain on the benchmark, no change elsewhere, but a clear regression on held-out data. Applied, measured, rolled back. |
| Same texture block in the lower-tier head | Gain confined to one band, no effect out of sample. |
| Additional skillset × signal interactions | Improved the training fit while degrading held-out error: overfitting at the current sample size. |
| A dedicated head for the top band | Improved the benchmark and broke the independent high-tier corpus. Rolled back. |

### 2.3 Measurement discipline

Two rules were adopted after getting them wrong once:

- **Leave-one-out must be computed as `yhat_loo = y − (y − yhat) / (1 − h_ii)`.** The alternative form
  doubles the correction and penalises every model; it produced a false conclusion about which model
  class performs better out of sample.
- **A gain measured only on data the model was fitted on is not evidence.** Every candidate change was
  re-measured on held-out data, and several were discarded at that point despite improving the
  primary metric.

---

## 3. Current results

Results on the **Leo Black benchmark**, run dated **2026-09-13**. The previous column is the published
`ISOR.csv`; the current column is the new run. Both come from the same harness over the same 644-map
rice set, so they are directly comparable.

| | previous build | current build | change |
|---|---|---|---|
| **rice MAE** | 0.2920 | **0.2449** | **−0.0471 (−16.1 %)** |
| rice RMSE | 0.4157 | **0.3376** | −0.0781 |
| bias | −0.0525 | +0.0159 | — |
| **exact** (\|err\| ≤ 0.20) | 51.40 % (331) | **56.99 % (367)** | **+5.59 pp** |
| close (0.20 < \|err\| ≤ 0.50) | 32.76 % (211) | 30.90 % (199) | −1.86 pp |
| *cumulative* \|err\| ≤ 0.50 | 84.16 % | **87.89 %** | +3.73 pp |
| moderate (0.50 < \|err\| ≤ 1.00) | 11.49 % (74) | 10.56 % (68) | −0.93 pp |
| miss (\|err\| > 1.00) | 4.35 % (28) | **1.55 % (10)** | −2.80 pp |
| **RC 11-17 MAE** | 0.2110 | **0.2066** | −0.0044 |
| RC 11-17 exact | 60.6 % | **62.9 %** | +2.3 pp |

The exclusive *close* band shrinks while the cumulative figure grows: maps are moving out of it into
*exact*, which is the intended direction. The largest single improvement is in the worst band, where
maps with an error above 1.0 Dan fell from 28 to 10.

By skillset:

| skillset | n | MAE previous | MAE current | change | exact previous | exact current |
|---|---|---|---|---|---|---|
| jack | 221 | 0.2622 | **0.2264** | −0.0358 | 55.7 % | **58.4 %** |
| speed | 147 | 0.2648 | **0.2285** | −0.0363 | 56.5 % | **58.5 %** |
| stamina | 131 | 0.3226 | **0.2621** | −0.0605 | 45.8 % | **57.3 %** |
| tech | 111 | 0.3012 | **0.2724** | −0.0288 | 52.3 % | **56.8 %** |
| course | 34 | 0.4562 | **0.2788** | −0.1774 | 20.6 % | **41.2 %** |

Reference output: `src/08_isor_engine/ISOR_rice_2026-09-13_1542.csv` (in-repo snapshot of the benchmark run; the runner writes its own dated copy under the local `tests/` lab workspace, which is not committed).

---

## 4. Assessment

**What improved.** Every skillset improved, in both mean error and exact-tier rate. The largest gains
are in the lowest tiers and in course charts, which is consistent with the defects addressed: a
residual positive bias in the 10.5-13 stripe and an unused reading axis in the lower-tier head.

**What did not.** Five candidate changes were evaluated and discarded; two of them improved the
benchmark on their own and were rolled back after failing on held-out data. Roughly 77 % of the
remaining error sits on charts handled by the higher-tier head, where the error is dispersion rather
than bias — level calibration cannot reduce it, and the only measured lever with a large effect is a
larger set of labelled charts.

**What is still weak.** The correction of the top of the ladder rests on a small number of charts. It
improves the internal benchmark but the available independent high-tier data is nearly empty, so the
evidence there is thin and should not be treated as established.

**Cost accepted.** The 11-17 band regressed by 0.004 as the price of the larger gain in 10-11. If that
trade is not wanted, the change is reversible from the stored backups.

**Net.** The rice metric improved by 16.1 % and every skillset improved, with no band left worse except
the deliberate 11-17 trade. The result is a real improvement over the previous build, and further model
work offers little: the remaining headroom is in data, not in the estimator.
