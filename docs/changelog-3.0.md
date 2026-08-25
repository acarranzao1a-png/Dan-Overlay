# DanOverlay 3.0 — ISOR Engine (Isotonic Strain Organic Residual)

## Summary

Version 3.0 introduces **ISOR**, a new dan-estimation engine for 4K rice maps,
available as an **alternate engine** that the user can switch to from the
overlay settings — the legacy engine remains intact and selectable. ISOR ships
with two estimation modes (**Reform** and **Celestial**), a recalibrated
Celestial ruler based on 160 official packs, full mod/rate support with
guaranteed rate monotonicity, and a continuous top-scale gate that restores the
official dan ladder (Zeta–Kappa) without touching the benchmark calibration.

---

## 1. New Engine — ISOR

ISOR (**I**sotonic **S**train **O**rganic **R**esidual) is a new calculation
engine built from the ground up for osu!mania 4K rice maps. It is **not** a
replacement: the user picks `legacy` or `isor` in the settings, and the overlay
re-analyzes the active map on switch.

**Design principles:**

- **Continuous functions only** — every correction is a sigmoid, cosine ramp,
  interpolation or clamp; no rigid `if feature > X: +Y` patches.
- **Human labels are the ground truth** — calibrated against the Leo_Black VSRG
  benchmark (746 maps), the official DDMythical packs (151) and the official
  Celestial packs (160).
- **Generalization measured, not assumed** — every change is validated with
  K-fold plus two external corpora (official packs and practice packs) before
  shipping.
- **Monotonic in rate** — a higher speed never shows a lower Dan (3-layer
  guarantee, see §5).

**Files:**

```
src/08_isor_engine/
├── __init__.py          # package + documentation
├── isor_engine.py       # engine: triangulation, ridge meta-layer, gates
├── strain.py            # biomechanical strain layer (7 streams, entropy)
├── ISOR.md              # complete technical documentation (this release)
├── ISOR.csv             # benchmark predictions (746 maps, official format)
└── assets/              # benchmark charts and diagrams (PNG, 300 DPI)

config/
├── vsrg_ridge_model.json   # dual-band ridge model (high λ=8, low λ=32, 98 features)
└── celestial_ruler.json    # celestial ruler (35 slots, from 160 official packs)
```

**Scope:** strictly 4K rice. LN-dominant maps and 7K are outside ISOR's
calibrated domain (the ridge is gated by LN ratio; the UI disables the LN
Course mode under ISOR). The parser and domain validator are **the same
modules the legacy engine uses** (`src/02_runtime_bridge/parser.py`,
`validator.py`) — parse errors are handled identically and never produce a
silent fallback estimate.

---

## 2. Estimation Modes under ISOR

ISOR supports **Reform** and **Celestial**. The other scales (Signicial,
Shoegazer, LN Course) are **disabled while the ISOR engine is active**:

- Keyboard shortcuts for those modes (`Ctrl+3`, `Ctrl+4`, `Ctrl+5`) show an
  informational toast ("mode is not supported by ISOR") and the overlay stays
  on the current valid mode.
- Switching to ISOR while on an unsupported mode auto-switches to **Reform**.
- The engine returns `None` for signicial/shoegazer/ln_course estimates.

---

## 3. Celestial Recalibration

The Celestial mode is now driven by the **ISOR continuous DP** projected
through a freshly calibrated 35-slot ruler (`config/celestial_ruler.json`):

- Calibrated from the **160 official Celestial pack maps** (7 tiers × 5
  categories I–V: Beginner → Singularity).
- Slot medians enforced **monotonic** (PAVA), boundary interpolation
  (midpoints between adjacent means), DP clamped to [0.5, 35.99].
- Validated with K-fold **by slots** (7 held-out slots per fold — never maps
  from the same slot in training): 76.9% tier accuracy, 25.6% exact slot
  (chance = 2.9%).
- The legacy engine keeps its own SR-based celestial estimator; both engines
  produce independent results (no cross-contamination).

---

## 4. Continuous Top-Scale Gate (Zeta–Kappa)

The VSRG benchmark never grades above ~18.6 DP, so a benchmark-calibrated base
compresses the top of the official ladder (official packs reach 20.5). ISOR
restores the official scale with a continuous gate that only activates above
the benchmark's reachable range:

- Cosine ramp on `[18.8, 19.2]`, returning to the canonical SR ruler
  projection with an adaptive lift (`min(0.6, max(0, 20.2 − dp_sr))`).
- Final cap at **20.5 DP** (official Kappa center) — no overshoot.
- **Zero impact on the benchmark**: the maximum benchmark base DP is 18.255,
  below the gate threshold (verified bit-identical CSV).

Result: official Zeta–Kappa packs — 84% exact tier accuracy, Kappa maps rated
within the Kappa band (MAE 0.00).

---

## 5. Mods & Rates — Three-Layer Monotonicity

ISOR accepts `mod` (NM/DT/HT/NC) and lazer custom clock rates (HT 0.5–0.99×,
DT/NC 1.01–2.0×) and guarantees the Dan never decreases when the rate
increases:

1. **SR layer** — isotonic per-map clamp in `primary_sr_bridge` (rate → SR
   registry, floor/ceiling).
2. **MSD layer** — native-anchor interpolation in `minacalc_bridge`.
3. **DP layer** — custom rates are floored against the nearest lower native
   anchor (0.75 / 1.0 / 1.5), ported from the legacy pipeline.

Verified on the full rate grid [0.5 → 2.0] across all patterns: monotonic in
every case. Default (NM, 1.0×) is bit-identical to the benchmark-validated
model.

---

## 6. Benchmark Results (local evaluation)

All metrics below were computed from the official Leo_Black VSRG dataset with
the published CSV (`ISOR.csv` in the engine folder). These are **local
evaluation results**; the overlay has not been submitted to the public
leaderboard.

| Scope | n | MAE | RMSE | Exact (≤0.20) | Close (≤0.50) |
|---|---|---|---|---|---|
| RC 11–17 | 485 | 0.2110 | 0.2790 | 60.0% | 93.2% |
| RC full (rice) | 644 | 0.2920 | 0.4157 | 50.8% | 84.2% |
| Official Dan Reform canon | 60 | 0.3213 | 0.4503 | 40.0% | 85.0% |

Head-to-head on common maps (RC 11–17): vs Roxy 0.2097 vs 0.2191 (251W/219L/12T),
vs Mixed 0.2108 vs 0.2329 (257W/218L/12T), vs Azusa 0.2108 vs 0.2784
(295W/183L/9T), vs Daniel 0.2105 vs 0.3112 (279W/199L/5T).

Generalization (separate corpora): official DDMythical packs 92.7% within
±1.0 Dan (MAE 0.429); practice packs 81.7% within ±1.0 Dan.

---

## 7. Bug Fixes & Robustness

| Fix | Details |
|-----|---------|
| Model lookup in frozen builds | `isor_engine` now resolves `vsrg_ridge_model.json` from `sys._MEIPASS/config/` when frozen (PyInstaller). |
| `rhythm_profile` hidden import | The engine imports `rhythm_profile` dynamically; it is now declared in `build.bat` so the exe bundles it. |
| `strain` hidden import | The biomechanical layer is imported lazily inside the analysis function; declared in `build.bat`. |
| Silent parse failures | ISOR shares the production `parser`/`validator`; missing/broken files return a structured error with `dp=None` — never a fake `1.00 / 1st dan low`. |
| Chart data accuracy | Benchmark charts (assets/) were re-rendered with dynamically computed values; hardcoded percentages and pattern counts were replaced by real computations. |

---

## 8. Build & Packaging (3.0.0)

`build.bat` now produces **DanOverlay 3.0.0**:

- Preflight validates the new files: `config/vsrg_ridge_model.json`,
  `config/celestial_ruler.json`, `src/08_isor_engine/isor_engine.py`,
  `src/08_isor_engine/strain.py`.
- Module path `src/08_isor_engine` added to PyInstaller `--paths`.
- Hidden imports added: `isor_engine`, `strain`, `rhythm_profile`.
- The `config/` folder is bundled as a whole, so both new JSON models ship
  with the exe.
- Window title version updated to 3.0.0 (`overlay_host.py`).

---

## 9. Integration

- **Engine selector** in the overlay settings: `legacy` | `isor` (persisted in
  `settings.json`; default is ISOR).
- `analysis_coordinator` reads the engine from settings, passes it to
  `analyze_map(engine=...)`, and includes the engine in the result cache key
  (switching engines re-analyzes the active map).
- Mode restrictions handled in the frontend (toasts + auto-switch to Reform).
- The Celestial mode renders from `payload.celestial` returned by the active
  engine — ISOR's ruler-based result and the legacy's SR-based result are
  kept separate.

---

## 10. Documentation & Artifacts — Locations

**Complete ISOR documentation**

- `src/08_isor_engine/ISOR.md` — the full technical reference: acronym
  breakdown, architecture diagrams (mermaid), pipeline detail, all
  mathematical formulas (ruler interpolation, SR modulation, dynamic weights,
  dual-decay strain streams, Shannon entropy, ridge, blend C¹, top gate,
  3-layer monotonicity), the 98-feature vector, both estimation modes,
  mod/rate support, calibration, validation results, limitations and overlay
  integration. Charts are embedded from `src/08_isor_engine/assets/`.

**Benchmark predictions CSV**

- `src/08_isor_engine/ISOR.csv` — raw predictions for all 746 VSRG benchmark
  maps in the official 8-column format (`bid,name,pattern,subPattern,
  expected,got,delta,deltaAbs`). This is the same data published in the local
  benchmark copy (`archive/VSRG-DanEstimation-Benchmark-DanOverlayV2/results/
  DanOverlayV2.csv`) and is the source for every number in section 6.

**Benchmark charts & diagrams** (generated PNGs, 300 DPI, dark mode)

- `src/08_isor_engine/assets/benchmark_accuracy_breakdown.png` — band accuracy
  distribution (Exact/Close/Moderate/Miss)
- `src/08_isor_engine/assets/benchmark_scatter_plot.png` — expected vs
  estimated calibration (4K rice, 644 maps)
- `src/08_isor_engine/assets/benchmark_delta_distribution.png` — residual error
  distribution (band 11–17)
- `src/08_isor_engine/assets/benchmark_pattern_breakdown.png` — MAE by pattern
  skillset (band 11–17)
- `src/08_isor_engine/assets/benchmark_head_to_head.png` — head-to-head win
  rates (band 11–17)
- `src/08_isor_engine/assets/apex_cosine_gate.png` / `ruler_interpolation.png`
  — conceptual diagrams of the top gate and the ruler interpolation

**Models**

- `config/vsrg_ridge_model.json` — deployed dual-band ridge model
- `config/celestial_ruler.json` — deployed celestial 35-slot ruler

---

*Release: 3.0.0 — 2026-08*
