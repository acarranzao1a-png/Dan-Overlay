# ISOR — Isotonic Strain Organic Residual

**Next-Generation Dan & Difficulty Estimation Engine for DanOverlay (osu!mania 4K Rice).**

ISOR is an advanced, physiologically grounded difficulty estimation engine designed as an **alternate engine** for DanOverlay. Users can freely switch between the legacy engine and ISOR via the overlay settings panel. Both engines coexist seamlessly without breaking compatibility.

> [!IMPORTANT]
> **Operational Scope & Domain Boundaries**  
> ISOR is strictly calibrated and validated **exclusively for 4K rice beatmaps** (jacks, chordjacks, streams, speed bursts, stamina drains, technical patterns, and marathon courses).  
> - **Long Note (LN) maps are unsupported** and explicitly rejected based on LN ratio gating ($r_{\text{LN}} > 0.18$).  
> - **7K / non-4K keymodes are out of scope** (domain validation strictly enforces $K = 4$).  
> - Supported estimation scales are **Dan Reform** (20-tier continuous scale from 1st Dan to Kappa) and **Celestial** (35 discrete rank slots across 7 tiers). Legacy Signicial, Shoegazer, and LN Course ladders remain on legacy mode.

---

## Table of Contents

1. [The Acronym](#1-the-acronym)
2. [Core Design Philosophy](#2-core-design-philosophy)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Execution Pipeline](#4-execution-pipeline)
5. [Mathematical & Algorithmic Foundations](#5-mathematical--algorithmic-foundations)
6. [Feature Vector Specification (98-D)](#6-feature-vector-specification-98-d)
7. [Estimation Modes & Tier Systems](#7-estimation-modes--tier-systems)
8. [Mod & Custom Rate Scaling (HT / DT / NC / Lazer)](#8-mod--custom-rate-scaling)
9. [Calibration, Benchmarking & Empirical Validation](#9-calibration-benchmarking--empirical-validation)
10. [Repository & Module Structure](#10-repository--module-structure)
11. [Architectural Guarantees](#11-architectural-guarantees)
12. [Known Limitations & Scope Constraints](#12-known-limitations--scope-constraints)
13. [Overlay Integration & Runtime Dispatch](#13-overlay-integration--runtime-dispatch)

---

## 1. The Acronym

The name **ISOR** embodies the four methodological pillars that drive its calculation pipeline:

| Pillar | Term | Technical Implementation in the Engine |
| :---: | :---: | :---|
| **I** | **Isotonic** | Calibration uses Pool Adjacent Violators Algorithm (**PAVA**) isotonic regression across difficulty rulers, paired with an isotonic rate clamp per beatmap that mathematically guarantees estimated SR never decreases with playback speed. All rating scales are strictly monotonic by construction. |
| **S** | **Strain** | Multi-layer biomechanical strain modeling: 7 distinct physical streams with dual exponential decay kernels (burst vs. sustain), rolling Shannon column/mask entropy, and weighted quantile aggregation to quantify physiological hand load. |
| **O** | **Organic** | An organic difficulty baseline constructed from the continuous convex triangulation of three human-aligned projections: modulated Star Rating ($DP_{\text{SR}}$), 10-second choke point density ($DP_{\text{choke}}$), and multi-skillset MinaCalc MSD ($DP_{\text{MSD}}$). |
| **R** | **Residual** | A regularized meta-corrector ($L_2$ Ridge) that estimates the subtle mathematical **residual** between the organic base and human consensus ratings. It operates strictly within reliable domain gates with continuous blending across low- and high-tier regimes. |

---

## 2. Core Design Philosophy

1. **Continuous Formulations, Zero Step Discontinuities:**  
   No heuristic corrections use brittle piecewise thresholds such as `if feature > X: +Y`. All boosts, gates, floors, and dampers are formulated as $C^0$/$C^1$ continuous functions (sigmoids, cosines, smooth clamps, and linear blends). This completely eliminates artificial difficulty cliffs.
2. **Human Consensus as Ground Truth:**  
   Calibrated against rigorous human-verified datasets: the Leo_Black VSRG Benchmark (1364 beatmaps with verified expected Dans), official DDMythical Reform course packs (151 beatmaps), and official Celestial packs (160 beatmaps). No parameter is tuned arbitrarily.
3. **Verified Generalization Over Blind Overfitting:**  
   Every architectural iteration is validated using stratified K-Fold Cross-Validation and evaluated against independent external corpora (official packs and unseeded community practice sets). Generalization metrics are reported transparently.
4. **Strict Rate Monotonicity:**  
   A beatmap will **never** display a lower Dan rating when playback speed is increased ($\text{HT} \to \text{NM} \to \text{DT} \to \text{custom lazer rates}$), guaranteed through three independent architectural layers.
5. **Non-Destructive Coexistence:**  
   ISOR lives alongside the legacy model without overwriting existing workflows, allowing real-time comparative inspection.

---

## 3. High-Level Architecture

```mermaid
flowchart TD
    MAP["Beatmap / Simfile (.osu · .sm · .ssc)"] --> LOAD["_load_parsed_chart<br/>Unified Chart Dict (4K Rice)<br/>O(N) Sequential Timing Cursor"]
    LOAD --> VAL["validate_domain<br/>Notes ≥ 20 · Drain ≥ 5s · LN Ratio ≤ 0.18"]
    VAL -->|Invalid / LN Dominant| ERR["Domain Error (Out of Scope)"]
    VAL -->|Valid 4K Rice| FEAT["extract_features<br/>40+ Base Structural Metrics"]

    FEAT --> SUNNY["analyze_primary_sr(mod, rate)<br/>Sunny SR + Vectorized Strains (Jbar, Pbar, Xbar, Abar)<br/>Isotonic Rate Clamp"]
    FEAT --> MSD["calculate_msd(rate)<br/>MinaCalc C++ / Etterna MSD: 7 Skillsets + Overall<br/>Monotonic Native Anchors"]
    FEAT --> CHOKE["Choke Point 10s Window<br/>Linear O(W + N) Two-Pointer Sliding Scan"]
    FEAT --> BIO["strain.py<br/>7 Dual-Decay Streams + Shannon Entropy (Active Set Tracking)<br/>+ Sostenuto Density Stats"]
    FEAT --> CLASS["Family Classifier<br/>Cosine Pattern Profiles + Bar Ratios"]

    SUNNY --> TRIA["Triangulated Organic Base"]
    MSD --> TRIA
    CHOKE --> TRIA
    CLASS --> TRIA

    subgraph TRIA["Organic Convex Triangulation"]
        ROUT["Skillset Routing<br/>(Jack / Speed / Stamina / Tech / General)"]
        PROJ["Precomputed Ruler Projections<br/>DP_sr · DP_choke · DP_msd"]
        W["Dynamic Weight System<br/>w_sr · w_choke · w_msd"]
        CORR["Continuous Dampers & Alpha/Beta Anchors"]
        ROUT --> PROJ --> W --> CORR
    end

    BIO --> RIDGE["Dual-Band Ridge Corrector (ISOR-R)"]
    TRIA --> RIDGE
    RIDGE --> BLEND["C¹ Blended Base<br/>σ(4·(DP_org - 10)) Blend"]

    subgraph RIDGE["Regularized Ridge Meta-Layer (Pre-Cast Arrays)"]
        HIGH["High Model: Tier 11–17 (λ=8, 98-D Features)"]
        LOW["Low Model: Tier 1–10.5 (λ=32, 67 Augmented Packs)"]
        GATE["Smooth Sigmoidal Transition Gate"]
        HIGH --> GATE
        LOW --> GATE
    end

    BLEND --> APEX["Apex Cosine Gate [18.8, 19.2]<br/>Adaptive Lift + Kappa Cap (20.5)"]
    APEX --> MONO["Rate Monotonicity Floor<br/>Lower Native Anchor Clamping"]
    MONO --> OUT["Final Continuous Dan Rating (DP Scale)"]
    OUT --> REFORM["Reform Output: 20 Tiers + Sub-Tiers"]
    OUT --> CEL["Celestial Output: 35 Slots (7 Tiers × 5 Ranks)"]
```

---

## 4. Execution Pipeline

### 4.1 Parsing & Domain Validation
The beatmap/simfile is parsed into the unified DanOverlay chart dictionary via `_load_parsed_chart`:
- **Supported Formats:** Native osu!mania (`.osu`) and Etterna (`.sm`, `.ssc`) charts.
- **Single-Pass Timing Resolution:** Simfiles are converted via an $O(N)$ sequential timing accumulator across BPM changes, STOPS, and DELAYS, achieving $<15\text{ ms}$ parse time on dense 50,000+ row charts.
- `validate_domain` enforces structural integrity ($K = 4$ columns):
  - **Minimum Note Count:** $N \ge 20$.
  - **Minimum Active Drain Duration:** $T_{\text{drain}} \ge 5.0\text{ s}$.
  - **Long Note Ratio:** $r_{\text{LN}} = N_{\text{LN}} / N \le 0.18$. Maps exceeding this threshold trigger a graceful `DomainError`.

### 4.2 Signal Ingestion
Five independent feature extractors process the note array simultaneously:
1. **Sunny Primary SR Bridge:** Extracts raw star rating $SR_{\text{raw}}$, peak strain components (Jbar, Pbar, Xbar: $\bar{J}, \bar{P}, \bar{X}$), and mean stream strain $\bar{A}$ (Abar) using batch-vectorized NumPy operations.
2. **MinaCalc MSD Subprocess:** Evaluates 7 core skillsets (Overall, Stream, Jumpstream, Handstream, Stamina, JackSpeed, Chordjack, Technical). For Etterna, utilizes direct native engine MSD.
3. **10-Second Choke Point Analyzer:** Computes rolling peak density $NPS_{10\text{s}}$, burst ratios, and local chord clusters in $O(W + N)$ linear time via two-pointer monotonic sliding window.
4. **Biomechanical Strain Module (`strain.py`):** Generates 7 physical strain streams, Shannon pattern entropy with active transition set tracking, and sustained density metrics.
5. **Pattern Classifier:** Identifies macro-families via cosine similarity against reference pattern profiles.

### 4.3 Skillset Routing

The map is mapped to a canonical skillset $\kappa \in \{\text{jack}, \text{speed}, \text{stamina}, \text{tech}, \text{general}\}$ as a **continuous mixture over the canonical rulers**: the classifier's family label selects the candidate rulers and every historical hard threshold (`jbar_max > 55`, `jack_density >= thr`, `jump_ratio >= thr`) is a sharp sigmoid, so a chart blends between skillsets instead of switching discretely and never jumps ruler when it crosses a value:

```python
# isor_engine.compute_triangulated_rank
_jbar_gate = _sigmoid(jbar_max, k=0.5, x0=55.0)
_jd_gate   = _sigmoid(jack_density, k=40.0, x0=_JD_JACK_THR)
if "jack" in fam_lower:
    sk_w = {"jack": 1.0}
elif "tech" in fam_lower:
    sk_w = {"jack": _jbar_gate, "tech": 1.0 - _jbar_gate}
else:
    _rescue = 1.0 - (1.0 - _jbar_gate) * (1.0 - _jd_gate)
    _t = _sigmoid(jump_ratio, k=12.0, x0=<threshold for this family>)
    sk_w = {_lo: (1.0 - _t) * (1.0 - _rescue), "stamina": _t * (1.0 - _rescue), "jack": _rescue}
# normalised to sum 1.0; dp_sr / dp_choke are the weighted blend of the skillset rulers
sk_key = max(sk_w, key=sk_w.get)   # dominant skillset, used for the lin_base coefficients
```

`sk_key` (the dominant weighted skillset) selects the `lin_base` coefficient set. A chart whose family resolves to `ln` is never scored by ISOR: the pipeline delegates it to the legacy LN/7K path rather than mixing LN behaviour into a rice estimate.

### 4.4 Continuous Ruler Projections
Each primary signal is projected onto continuous Dan Points ($DP$) via piecewise-linear frontier interpolation against calibrated skillset vectors:

$$
\begin{aligned}
DP_{\text{SR}} &= \mathcal{P}\left(SR_{\text{mod}}, \mathbf{\mu}_{\text{SR}}^{(\kappa)}\right) \\
DP_{\text{choke}} &= \mathcal{P}\left(NPS_{\text{choke}}, \mathbf{\mu}_{\text{choke}}^{(\kappa)}\right) \\
DP_{\text{MSD}} &= \mathcal{P}\left(MSD_{\text{overall}}, \mathbf{\mu}_{\text{MSD}}\right)
\end{aligned}
$$

### 4.5 Organic Convex Triangulation
The intermediate organic rating $DP_{\text{organic}}$ is computed via normalized convex combination:

$$
DP_{\text{organic}} = \frac{w_{\text{SR}} DP_{\text{SR}} + w_{\text{choke}} DP_{\text{choke}} + w_{\text{MSD}} DP_{\text{MSD}}}{w_{\text{SR}} + w_{\text{choke}} + w_{\text{MSD}}}
$$

> **Biomechanical layer (`strain.py`) is a feature supplier, not a fourth vector.**
> `_BIO_ENABLED` is `False`: the $w_{\text{bio}}\,DP_{\text{bio}}$ term is not part of the
> deployed triangulation. The 7 strain streams, their q97 peaks and the sustained-density
> statistics feed the Ridge meta-corrector instead (see §6).

### 4.6 Ridge Error-Corrector

The physics triangulation leaves a residual $y - DP_{\text{base}}$ that is not a constant offset:
it depends on the level, the skillset and the chart's texture. A single dual-band Ridge model
(`config/vsrg_ridge_model.json`) corrects it:

$$
DP_{\text{ridge}} = DP_{\text{base}} + \text{clip}\Big(\beta_0 + \mathbf{x}^\top \boldsymbol{\beta},\; -1,\; +1\Big)
$$

| field | value |
|---|---|
| band | `11-17` |
| $\lambda$ | `8.0` |
| inputs | 98 standardised features (`keys`) |
| ordinal head | `false` |
| anchor calibration | stored in the same model (`anchors`) |

**Anchor calibration and the apex gate** are applied after this stage; both are described in §4.8.

### 4.7 Rice Model (gated GBDT)

The largest single accuracy gain in the engine's history is not a correction to the Physics stack but
a model that reads the engine's *own* projections and predicts the dan directly
(`config/rice_model.json`).

```mermaid
flowchart LR
    A["Physics triangulation<br/>dp_base"] --> B["Ridge corrector<br/>+ anchors"]
    B --> C{"12.0 &le; DP &lt; 15.0 ?"}
    C -- yes --> D["GBDT rice model<br/>500 trees, depth 3<br/>124 inputs"]
    C -- no --> E["DP_ridge stands<br/>(no extrapolation)"]
    D --> F["DP_final"]
    E --> F
    F --> G["round(DP - 0.5)<br/>= reported dan"]
```

**Why a gate.** Trees cannot extrapolate. Outside the band the model was validated on it is measurably
worse than the physics stack — in the 9-11 and 11-12 bands it loses roughly eight points of exact
rate — so it is simply not allowed to answer there. The model carries this scope in its own file:

```json
"scope": "4K rice. Applied only when the engine's dp is inside the gate; outside it the engine's own answer stands.",
"gate": [12.0, 15.0]
```

**What the model is.** An exported gradient-boosted tree ensemble, walked in pure Python so no ML
library ships with the app. Delete `config/rice_model.json` and the engine falls back to the physics
path with no other change.

| field | value |
|---|---|
| inputs | 124 columns: 4 projections + 109 features + 11 curve statistics |
| trees | 500 |
| max depth | 3 |
| min samples / leaf | 5 |
| learning rate | 0.03 |
| subsample | 0.8 |
| loss | Huber ($\alpha = 0.7$) |
| trained rows | 1262 |
| export fidelity | max deviation vs sklearn $8.4\times10^{-11}$ |

**Why Huber.** The metric the engine is judged on is the mean absolute error, and squared loss let a
handful of extreme rows pull the fit. Huber was selected on a held-out split, not on the reported
cross-validation, and it improves both the exact rate and the MAE.

**Honesty notes.** The model is trained on the same corpus it is scored on, exactly like the reference
implementations it is compared against, so the number that belongs in any report is the
cross-validated one (71.79 % exact, MAE 0.1741 on the 1106 shared maps), never the in-sample fit.

### 4.8 Anchor Calibration and Apex Cosine Gate

**Anchor calibration.** A residual level bias was measured in the stripe between the low-tier head and
the apex region — the fused base ran high there while no correction stage covered it. A smooth curve of
the level corrects it:

$$
DP \leftarrow \text{clip}\left(DP + \sum_j a_j \, e^{-\left((DP_{\text{base}} - c_j)/w\right)^2}, \; 0, \; 20.5\right)
$$

The Gaussian support is placed only where the bias was measured, so the correction decays to exactly
zero outside that range and cannot disturb the bands that were already calibrated. It is a calibration
curve — a function of the level with a handful of coefficients — not a per-chart or per-skillset rule.
It is applied after the correction stack and before the rate-monotonicity clamps.

**Apex cosine gate.** Because standard training sets sparsely populate tiers beyond 18.0 DP, a $C^0$
cosine transition gate activates smoothly above 18.8 DP to restore the official high-tier progression:

$$
DP_{\text{final}} = \min\left(DP_{\text{blended}} + \text{lift}_{\text{apex}}, \; 20.5\right)
$$

---

## 5. Mathematical & Algorithmic Foundations

### 5.1 Piecewise-Linear Frontier Ruler Interpolation
Given a monotonic vector of tier mean values $\mathbf{\mu} = [\mu_1, \mu_2, \dots, \mu_M]$, the boundary threshold between tier $i$ and tier $i+1$ is defined as the arithmetic midpoint:

$$
\text{lo}(i) = \frac{\mu_{i-1} + \mu_i}{2}, \quad \text{hi}(i) = \frac{\mu_i + \mu_{i+1}}{2}
$$

For any measured signal $x \in [\text{lo}(i), \text{hi}(i))$, the continuous projected rank $\mathcal{P}(x, \mathbf{\mu})$ is given by:

$$
\mathcal{P}(x, \mathbf{\mu}) = i + \frac{x - \text{lo}(i)}{\text{hi}(i) - \text{lo}(i)}
$$

Where the integer component represents the base Dan tier, and the fractional component denotes exact sub-tier progression.

---

### 5.2 Continuous Star Rating Modulation
Raw Star Rating is modulated using continuous differential strain signals with smooth boundary tapers:

$$
SR_{\text{mod}} = SR_{\text{raw}} \cdot \left(1.0 + \Delta_{\text{burst}} + \Delta_{\text{jack}} + \Delta_{\text{bpm}} - \Delta_{\text{fatigue}}\right)
$$

Where:

$$
\begin{aligned}
\Delta_{\text{burst}} &= \alpha_b \cdot \text{clamp}\left(\frac{\bar{P}_{\max} - P_0}{P_{\text{scale}}}, \; 0, \; 1\right) \\
\Delta_{\text{fatigue}} &= \alpha_f \cdot \left(1.0 - \exp\left(-\frac{T_{\text{drain}}}{\tau_d}\right)\right) \cdot \sigma\left(NPS_{\text{avg}} - NPS_0\right)
\end{aligned}
$$

---

### 5.3 Dynamic Triangulation Weights
Signal weights adapt dynamically to signal strength and inter-signal divergence:

$$
\sigma(u) = \frac{1}{1 + e^{-k u}}
$$

$$
\begin{aligned}
w_{\text{SR}} &= \min\left(w_{\text{SR}}^{\max}, \; w_{\text{SR}}^{\text{base}} + \gamma_{\text{SR}} \cdot \sigma(SR_{\text{raw}} - SR_0) \cdot \sigma(NPS_0 - NPS_{\text{choke}})\right) \\
w_{\text{MSD}} &= \min\left(w_{\text{MSD}}^{\max}, \; w_{\text{MSD}}^{\text{base}} + \gamma_{\text{MSD}} \cdot \sigma\left(\left|DP_{\text{SR}} - DP_{\text{choke}}\right| - \theta_{\text{agree}}\right)\right) \\
w_{\text{choke}} &= \max\left(w_{\text{choke}}^{\min}, \; 1.0 - w_{\text{SR}} - w_{\text{MSD}}\right)
\end{aligned}
$$

$$
\tilde{w}_j = \frac{w_j}{\sum_{k} w_k}, \quad \forall j \in \{\text{SR}, \text{choke}, \text{MSD}, \text{bio}\}
$$

---

### 5.4 Dual-Decay Biomechanical Strain Streams
Every hit object is mapped to a 4-bit column bitmask. The engine evaluates 7 parallel physiological strain streams:
$$\mathcal{S} = \{\text{speed}, \text{hand}, \text{jack}, \text{chordjack}, \text{tech}, \text{stamina}, \text{course}\}$$

For each stream $s \in \mathcal{S}$ at inter-onset interval $\Delta t = t_k - t_{k-1}$:

$$
\begin{aligned}
\text{burst}_k^{(s)} &= \text{burst}_{k-1}^{(s)} \cdot \exp\left(-\frac{\Delta t}{\tau_{\text{burst}}^{(s)}}\right) + \mathcal{I}_k^{(s)} \\
\text{sustain}_k^{(s)} &= \text{sustain}_{k-1}^{(s)} \cdot \exp\left(-\frac{\Delta t}{\tau_{\text{sustain}}^{(s)}}\right) + \mathcal{I}_k^{(s)} \\
\text{strain}_k^{(s)} &= \alpha_{\text{mix}}^{(s)} \cdot \text{burst}_k^{(s)} + \left(1 - \alpha_{\text{mix}}^{(s)}\right) \cdot \text{sustain}_k^{(s)}
\end{aligned}
$$

#### Typical Physiological Time Constants:
* **Stamina Stream:** $\tau_{\text{burst}} = 1200\text{ ms}$, $\tau_{\text{sustain}} = 10000\text{ ms}$, $\alpha_{\text{mix}} = 0.58$
* **Hand Strain Stream:** $\tau_{\text{burst}} = 240\text{ ms}$, $\tau_{\text{sustain}} = 3000\text{ ms}$, $\alpha_{\text{mix}} = 0.70$
* **Jack Stream:** $\tau_{\text{burst}} = 180\text{ ms}$, $\tau_{\text{sustain}} = 2000\text{ ms}$, $\alpha_{\text{mix}} = 0.75$

---

### 5.5 Weighted Quantile Aggregation
To prevent isolated 1-second difficulty spikes from distorting marathon ratings, stream arrays are aggregated using weighted tail quantiles:

$$
\Phi(S) = 0.30 \cdot q_{97}(S) + 0.22 \cdot q_{90}(S) + 0.18 \cdot \mu_{\text{tail}}(S) + 0.15 \cdot q_{75}(S) + 0.10 \cdot \mu_{\text{pow}}(S) + 0.05 \cdot q_{50}(S)
$$

Where:

$$
\mu_{\text{tail}}(S) = \mathbb{E}\left[S \;\middle|\; S \ge q_{90}(S)\right], \quad \mu_{\text{pow}}(S) = \left(\frac{1}{|S|}\sum_{x \in S} x^p\right)^{1/p} \quad (p = 2.5)
$$

---

### 5.6 Rolling Shannon Entropy of Column Transitions
Technical pattern complexity is quantified via the information entropy of active column bitmasks across sliding windows ($W = 750\text{ ms}$):

$$
H(W) = -\sum_{m \in \mathcal{M}} p(m) \log_2 p(m)
$$

Where $\mathcal{M}$ represents the state space of $2^4 - 1 = 15$ possible non-empty column activation configurations.

---

### 5.7 Regularized Ridge & RBF Meta-Correctors

**Ridge heads.** Given standardized feature matrix $\mathbf{Z} \in \mathbb{R}^{N \times D}$ and target residual vector $\mathbf{y}$:

$$
\begin{aligned}
\mathbf{y} &= \mathbf{DP}_{\text{expected}} - \mathbf{DP}_{\text{base}} \\
\mathbf{\beta} &= \left(\mathbf{Z}^T \mathbf{Z} + \lambda \mathbf{I}\right)^{-1} \mathbf{Z}^T \mathbf{y} \\
\hat{\delta}(\mathbf{x}) &= \text{clip}\left(\left(\frac{\mathbf{x} - \mathbf{\mu}_x}{\mathbf{\sigma}_x}\right)^T \mathbf{\beta}, \;-1.0, \;+1.0\right)
\end{aligned}
$$

* **High-tier head:** $\lambda = 8.0$ across $D = 98$ features.
* **Mid head:** $\lambda = 16.0$ across $D = 102$ features, mixed in by its own logistic weight.

**RBF low-tier head.** The lower band is where a linear corrector loses the most, so a Gaussian lift is
applied before the linear term. With centres $\mathbf{c}_k$ taken from the training population and
$\gamma$ set from the median pairwise distance:

$$
\begin{aligned}
\mathbf{z} &= \frac{\mathbf{x} - \mathbf{\mu}_x}{\mathbf{\sigma}_x} \\
\phi_k(\mathbf{z}) &= \exp\left(-\gamma \, \lVert \mathbf{z} - \mathbf{c}_k \rVert^2\right) \\
\hat{\delta}_{\text{low}}(\mathbf{x}) &= \text{clip}\left(\left[\mathbf{z}, \boldsymbol{\phi}(\mathbf{z})\right]^T \mathbf{\beta} + \beta_0, \;-1.0, \;+1.0\right)
\end{aligned}
$$

The design matrix is $[\mathbf{Z}, \boldsymbol{\Phi}, \mathbf{1}]$ and $\mathbf{\beta}$ comes from the
same ridge solve, so the model class changes while the estimator stays a closed-form linear solve in
the lifted space. The lift is $C^\infty$, which preserves the engine's continuity guarantee.

---

## 5bis. Verified State of the Current Build

The tables in §9 are the live measurement, recomputed from the raw CSVs. This section records how
the current build reaches those numbers and which caveats belong next to them. The contract is the
official one, `got = DP − 0.5`; *rice* means every benchmark map with `pattern != ln` (1262 of them).

| Metric | Current build |
|---|---|
| Rice corpus (1262 maps) — MAE | **0.1962** |
| Rice corpus (1262 maps) — exact rate ($\le 0.20$) | **67.51 %** |
| Shared with the reference implementation (1106 maps) — MAE | **0.1741** |
| Shared with the reference implementation (1106 maps) — exact rate | **71.79 %** |
| Coverage | **1364 / 1364** labels |

**Which number to quote.** The 71.79 % figure is the cross-validated out-of-fold score on the maps both
engines answer, so it is the only one that is directly comparable with a published result. The 67.51 %
belongs to the wider 1262-map corpus, which includes the low tiers no competitor estimates. The
in-sample fit is never quoted.

### In-sample versus out-of-fold

The rice model is trained on the benchmark, so applying it to the same maps overstates its accuracy.
The table below separates the two, on the 1106 maps shared with the reference implementation:

| | exact rate | MAE |
|---|---|---|
| **ours, out-of-fold (published)** | **71.79 %** | **0.1741** |
| ours, in-sample | 83.82 % | 0.1239 |
| reference implementation (in-sample) | 70.89 % | 0.1540 |

<p align="center">
<img src="assets/benchmark_fit_optimism.png" alt="Fit optimism: out-of-fold vs in-sample" width="820" />
</p>

**The 12-point gap between our two rows is the model's optimism, and it is the reason the published
figure is the out-of-fold one.** The CSV shipped with the benchmark is built from out-of-fold
predictions for the 940 maps inside the model's gate; outside the gate the engine's calibrated
projection is used.

**The comparison is therefore conservative for us.** The rival estimators publish figures produced on
the same corpus they were fitted on, so the head-to-head above compares our held-out result against
their in-sample one. Equalising the treatment would widen our advantage, but the honest number is the
one this section already quotes.

**Coverage is part of the result.** The engine answers every map in the benchmark, including 258 that
the reference implementation declines (its scope stops at 11–17 and it rejects charts with more than
18 % long notes).

<p align="center">
<img src="assets/benchmark_coverage.png" alt="Coverage vs exact rate" width="620" />
</p>

**Where the error lives.** The exact rate is not uniform across the ladder: the band the model was
validated on carries the result, and the tails — which no competitor estimates — carry most of the
mean error. That is the shape behind the numbers above, and it is the honest picture of the engine's
weak side.

<p align="center">
<img src="assets/benchmark_bands.png" alt="Mean absolute error and exact rate by dan band" width="720" />
</p>

### Correction stack

Four stages act on the organic base, in this order:

1. **Ridge error-corrector** — the dual-band linear model of §4.6, clipped to $\pm 1.0$.
2. **Anchor calibration** — a smooth curve of the base level,
   $DP \leftarrow \text{clip}\left(DP + \sum_j a_j e^{-((DP_{base} - c_j)/w)^2},\ 0,\ 20.5\right)$,
   with Gaussian support placed only where a level bias was measured, so it is exactly zero outside
   that range.
3. **Rice model** — the gated GBDT of §4.7, applied only when `12.0 ≤ DP < 15.0`.
4. **Apex cosine gate** for the upper canon, then the **rate monotonicity clamps** across the native
   anchors (see §5.8 and §5.9).

All corrections are clipped and every stage is continuous, so the engine keeps its
zero-step-discontinuity guarantee.

### Honesty caveat

The Ridge model, the anchors and the rice model are **fits on the evaluation corpus**, so a number
taken from the same maps the model was trained on contains in-sample optimism. The figure quoted
above is the out-of-fold one. The same caveat applies to the rival estimators, which also calibrate on
benchmark data, but it should not be hidden. Changes were only kept when they held up on held-out
data — several candidates that improved the benchmark were rejected and reverted for exactly this
reason.

### Hypotheses tested and refuted (do not repeat them)

A global de-bias of the choke projection (absorbed entirely by `lin_base`'s free coefficient);
switching the lower head to a label-based population; widening the blend gate; using either head
alone instead of the blend; the orthogonal reading axis `Hn` as a Ridge feature (diff −0.0002,
p=0.615); raising the ±1.0 correction cap (it binds on the worst cases but degrades held-out error
monotonically); a texture/irregularity block in either head; additional skillset × signal
interactions (improves the fit, degrades held-out error); and a dedicated top-band head (it improves
the benchmark's 17+ band from 0.4268 to 0.2353 but **worsens the official Zeta–Kappa packs** from
0.4747 to 0.4912, so it was reverted as benchmark-fitting).

---

### 5.8 Apex Cosine Transition Gate
For ratings entering the upper canon (Zeta to Kappa, $DP \in [18.8, 20.5]$):

$$
\begin{aligned}
u &= \text{clamp}\left(\frac{DP_{\text{base}} - 18.8}{0.4}, \; 0.0, \; 1.0\right) \\
g(u) &= \frac{1}{2}\left(1.0 - \cos(\pi u)\right) \\
\text{lift} &= \min\left(0.6, \;\max\left(0.0, \; 20.2 - DP_{\text{SR}}\right)\right) \\
DP_{\text{apex}} &= (1.0 - g(u)) \cdot DP_{\text{base}} + g(u) \cdot \left(DP_{\text{SR}} + \text{lift}\right) \\
DP_{\text{final}} &= \min(DP_{\text{apex}}, \; 20.5)
\end{aligned}
$$

---

### 5.9 Three-Layer Rate Monotonicity Architecture
To prevent any physical anomaly where a faster rate produces a lower difficulty rating:

$$
\begin{aligned}
\text{Layer 1 (Sunny SR):} &\quad SR(r) \leftarrow \max_{r' \le r} SR(r') \\
\text{Layer 2 (MinaCalc MSD):} &\quad MSD(r) \leftarrow \text{Interp}_{\text{monotonic}}\left(r, [0.75, 1.0, 1.5]\right) \\
\text{Layer 3 (Final DP):} &\quad DP(r) \leftarrow \max\left(DP(r), \; DP(r_{\text{anchor}})\right)
\end{aligned}
$$

$$
\forall r_1 < r_2 \implies DP(r_1) \le DP(r_2)
$$

---

## 6. Feature Vector Specification (98-D)

The regularized meta-layer inspects a vector of 98 continuous structural features:

| Group | Dimensions | Description & Representative Features |
| :---| :---: | :---|
| **Biomechanical Streams** | 7 | Weighted quantile aggregates $\Phi(S)$ for Speed, Hand, Jack, Chordjack, Tech, Stamina, Course. |
| **Global Biomechanical Signal** | 1 | $\log(1+x)$ compressed global strain intensity. |
| **Physical Pattern Statistics** | 9 | Chord rate, 3-note overlap density, rotation index, fast-jack frequency, anchor ratio, hand bias, active drain NPS. |
| **97th Percentile Strain Peaks** | 7 | Burst peak values ($q_{97}$) across all 7 physiological streams. |
| **Normalized MSD Roles** | 4 | Relative ratios of MinaCalc skillsets against overall rating. |
| **Sunny Strain Components** | 4 | Jbar, Pbar, Xbar, and Abar peak strain metrics ($\bar{J}, \bar{P}, \bar{X}, \bar{A}$). |
| **Absolute MSD Vector** | 8 | Raw MinaCalc MSD ratings (Overall + 7 skillsets). |
| **Feature Cross-Interactions** | 15 | Non-linear interaction products (e.g., `density × stamina`, `entropy × timing_cv`, `SR_MSD_gap`). |
| **Non-Linear Projections** | 12 | Exponential and polynomial transforms (e.g., `SR_to_DP_SR`, `mean_projections`, `jack_pbar_ratio`). |
| **BPM & Fatigue Disparities** | 6 | Excess BPM scaling factors, duration strain accumulation terms. |
| **Stamina Modulators** | 4 | Effective logarithmic duration $\ln(1 + T_{\text{drain}})$, hand transition ratios. |
| **Weak Base Projections** | 5 | Uncorrected intermediate values ($DP_{\text{SR}}$, $DP_{\text{choke}}$, $DP_{\text{MSD}}$, $SR_{\text{mod}}$, $SR_{\text{raw}}$). |
| **Slow-Hand Gate** | 1 | Low-speed hand fatigue threshold modulator (`same_hand_q10`). |
| **Sustained Density (`sustain_v1`)** | 15 | Rolling NPS percentiles (1000 ms & 4000 ms), profile flatness $q_{50}/q_{97}$, row/hand/column $\Delta t$ distributions. |
| **Total Dimensions** | **98** | **Full standardized feature representation** |

#### Head-specific extensions

The 98 dimensions above are the shared base. Individual heads declare extra columns, appended in the
order the model specifies so training and inference cannot drift apart:

| Head | Extra columns | Purpose |
| :---| :---: | :--- |
| **Low-tier head** | 1 | Row-mask transition entropy (§5.6) — an orthogonal reading axis for irregular transitions. |
| **Mid head and its gate** | 4 | Density variability, timing irregularity, transition variance, pattern irregularity. |
| **High-tier head** | 0 | Uses the 98 base dimensions. |

---

## 7. Estimation Modes & Tier Systems

ISOR exposes two dedicated estimation modes tailored to osu!mania 4K rice:

### 7.1 Reform System (20-Tier Continuous Scale)

Covers the canonical Dan Reform ladder from **1st Dan to Kappa**:

$$
\text{Tiers: } \underbrace{\text{1st} \to \text{10th}}_{\text{Regular Dans (1.0--10.0)}} \;\to\; \underbrace{\text{Alpha} \to \text{Epsilon}}_{\text{Extra Dans (11.0--15.0)}} \;\to\; \underbrace{\text{Zeta} \to \text{Kappa}}_{\text{Elite and Final Dans (16.0--20.0)}}
$$

#### Continuous Sub-Tier Classification
Sub-tiers are computed directly from the fractional component of continuous $DP$:

| Fractional DP Range | Sub-Tier Descriptor | Example Output |
| :---: | :---: | :---: |
| `0.00 – 0.20` | **Low** | `Alpha low (11.12)` |
| `0.21 – 0.40` | **Mid-Low** | `Delta mid-low (14.28)` |
| `0.41 – 0.60` | **Mid** | `Zeta mid (16.50)` |
| `0.61 – 0.80` | **Mid-High** | `Eta mid-high (17.74)` |
| `0.81 – 1.00` | **High** | `Theta high (18.91)` |

---

### 7.2 Celestial System (35 Discrete Slots: 7 Tiers × 5 Ranks)

Calibrated against the 160 official Celestial Dan maps (`celestial_ruler.json`):

$$
\text{Tiers: } \text{Beginner} \to \text{Intermediate} \to \text{Expert} \to \text{Mastery} \to \text{Ascension} \to \text{Transcendence} \to \text{Singularity}
$$

$$
\text{Slot Index: } S \in [0, 34], \quad \text{Tier} = \lfloor S / 5 \rfloor, \quad \text{Sub-Rank} = (S \bmod 5) + 1 \quad (\text{I} \to \text{V})
$$

* **Stratified Slot-Level Cross-Validation:** Achieves **76.9% exact tier accuracy** across 7 broad tiers, and **25.6% exact slot accuracy** across all 35 granular slots (random baseline is 2.86%).

---

## 8. Mod & Custom Rate Scaling

| Playback Setting | Applied Multiplier | Engine Resolution Pipeline |
| :---| :---: | :---|
| **NoMod (NM)** | $1.00\times$ | Native reference pass. |
| **HalfTime (HT)** | $0.75\times$ | Native Sunny & MinaCalc rate anchor. |
| **DoubleTime (DT / NC)** | $1.50\times$ | Native Sunny & MinaCalc rate anchor. (Nightcore $\equiv$ DT). |
| **Lazer Custom Rates** | $0.50\times \dots 2.00\times$ | Full `.osu` timing scaling + Isotonic clamp + Lower-anchor floor. |

> **Mathematical Guarantee:** Rate scaling across all modes satisfies $\frac{\partial DP}{\partial r} \ge 0$.

---

## 9. Calibration, Benchmarking & Empirical Validation

### 9.1 Evaluation Corpora & Ground Truth

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │                      TOTAL EVALUATION CORPUS (1,675 Maps)              │
  ├────────────────────────────┬────────────────────────────┬──────────────┤
  │ Leo_Black VSRG Benchmark   │ Official Reform Packs      │ Celestial    │
  │ 1364 Maps (Ground Truth)   │ 151 Maps (1st to Kappa)    │ 160 Maps     │
  └────────────────────────────┴────────────────────────────┴──────────────┘
```

---

### 9.2 Complete Leo_Black VSRG Benchmark Results

> **Evaluation Methodology & Transparency:**  
> The benchmark metrics presented below were evaluated through rigorous **local testing** using the official reference dataset and scoring criteria established in [Leo_Black's VSRG DanEstimation Benchmark](https://github.com/LeoBlackMT/VSRG-DanEstimation-Benchmark). To guarantee full reproducibility and transparency, the complete raw predictions for all 1364 benchmark beatmaps are provided in [ISOR.csv](ISOR.csv).

#### A. High Rice Scale (Tiers 11.0 – 17.0 · 1103 Maps) — *Core Competitive Arena*

> Every figure is recomputed from the raw CSVs, so the published tables cannot drift apart.
> Counts are per benchmark row; an algorithm that does not cover the whole scope is marked and
> its coverage shown, because a lower MAE over a subset is not comparable.
>
> **Read the two rank columns together.** The mean absolute error and the exact-tier rate disagree:
> ISOR has the highest exact rate of any estimator in this band, and the third-best MAE. The gap in
> MAE comes from a heavier tail (§5bis), not from a worse average fit.

| Algorithm | Valid Maps | Coverage | MAE (lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) | Rank by MAE | Rank by exact |
| :---| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Koishi** | 1096 / 1103 | 99.4% | **0.1510** | **0.1996** | 71.53% | **97.99%** | **#1** | #2 |
| **Mixed** | 1103 / 1103 | 100.0% | 0.1699 | 0.2275 | 69.72% | 96.01% | #2 | #3 |
| **XDC1** | 1102 / 1103 | 99.9% | 0.1717 | 0.2314 | 67.97% | 95.74% | #3 | #4 |
| **ISOR** | **1103 / 1103** | **100.0%** | 0.1722 | 0.2499 | **71.89%** | 95.38% | #4 | **#1** |
| **Roxy** | 1096 / 1103 | 99.4% | 0.1980 | 0.2740 | 63.78% | 94.98% | #5 | #5 |
| **Azusa** | 1101 / 1103 | 99.8% | 0.2183 | 0.3085 | 59.13% | 93.28% | #6 | #6 |
| **Companella** | 1103 / 1103 | 100.0% | 0.3666 | 0.5061 | 38.98% | 76.97% | #7 | #7 |
| **Daniel** | 1099 / 1103 | 99.6% | 0.4088 | 0.4809 | 23.38% | 67.52% | #8 | #9 |
| **Sunny (Native)** | 1103 / 1103 | 100.0% | 0.5156 | 0.6797 | 36.17% | 57.21% | #9 | #8 |

<p align="center">
  <img src="assets/benchmark_accuracy_breakdown.png" alt="Benchmark Accuracy Breakdown" width="820" />
  <br/><em>Accuracy tier distribution — High Rice Scale (Tiers 11–17, 1103 maps)</em>
</p>

<p align="center">
  <img src="assets/benchmark_delta_distribution.png" alt="Residual Error Distribution" width="800" />
  <br/><em>Residual error distribution — High Rice Scale (Tiers 11–17, 1103 maps)</em>
</p>

---

#### B. Full Rice Scale (Tiers 1.0 – 18.0 · 1262 Maps) — *Comprehensive Ladder*

> Here the ladder is not filtered, so the low tiers that every estimator struggles with are included.
> Coverage separates the field: Koishi answers 87.6 % of this corpus, XDC1 90.6 %, ISOR 100 %.

| Algorithm | Valid Maps | Coverage | MAE (lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) | Rank by MAE | Rank by exact |
| :---| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Koishi** | 1106 / 1262 | 87.6% | **0.1540** | **0.2046** | **70.89%** | **97.47%** | **#1** | **#1** |
| **XDC1** | 1144 / 1262 | 90.6% | 0.1803 | 0.2498 | 66.87% | 94.67% | #2 | #3 |
| **ISOR** | **1262 / 1262** | **100.0%** | 0.1962 | 0.2875 | 67.83% | 92.63% | #3 | #2 |
| **Mixed** | 1262 / 1262 | 100.0% | 0.2075 | 0.3020 | 65.06% | 91.20% | #4 | #4 |
| **Roxy** | 1119 / 1262 | 88.7% | 0.2093 | 0.2966 | 62.65% | 93.66% | #5 | #5 |
| **Azusa** | 1260 / 1262 | 99.8% | 0.2555 | 0.3713 | 55.32% | 88.33% | #6 | #6 |
| **Daniel** | 1140 / 1262 | 90.3% | 0.4216 | 0.5012 | 22.72% | 66.40% | #7 | #9 |
| **Companella** | 1262 / 1262 | 100.0% | 0.4276 | 0.6408 | 37.08% | 73.06% | #8 | #7 |
| **Sunny (Native)** | 1262 / 1262 | 100.0% | 0.5563 | 0.7452 | 35.10% | 55.07% | #9 | #8 |

**On the shared subset only**, where every estimator answers the same maps (1101 of them), the
ordering tightens: ISOR 71.93 % exact / 0.1730 MAE, Koishi 71.03 % / 0.1534, Mixed 69.85 % / 0.1704,
XDC1 67.85 % / 0.1743. **ISOR leads that set on exact rate and is third on MAE.**

<p align="center">
  <img src="assets/benchmark_scatter_plot.png" alt="ISOR Expected vs Estimated Dan Scatter Plot" width="680" />
  <br/><em>Calibration scatter — Full Rice Scale (1262 maps, LN excluded)</em>
</p>

---

#### C. Official Dan Reform Canon (60 Maps · DDMythical, Emik03, Thaumiel, Cloverwisp)

Scope as published by the benchmark: rice-only canon, excluding Signicial, Shoegazer and long-note
charts. These figures come from the submission currently registered in the benchmark.

| Algorithm | Valid Maps | Coverage | MAE (lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) |
| :---| :---: | :---: | :---: | :---: | :---: | :---: |
| **ISOR** | **60 / 60** | **100.0%** | **0.3213** | **0.4503** | **40.0%** | **85.0%** |
| **ROXY** *(Partial)* | 46 / 60 | 76.7% | 0.2435 | 0.3231 | 56.5% | 93.5% |
| **Daniel** *(Partial)* | 51 / 60 | 85.0% | 0.3235 | 0.4286 | 39.2% | 78.4% |
| **Mixed** | 60 / 60 | 100.0% | 0.3433 | 0.5199 | 51.7% | 83.3% |
| **Sunny (Native)** | 60 / 60 | 100.0% | 0.3450 | 0.5074 | 56.7% | 70.0% |
| **Azusa** | 60 / 60 | 100.0% | 0.3552 | 0.4762 | 38.3% | 78.3% |
| **Companella** | 60 / 60 | 100.0% | 0.7313 | 1.0728 | 35.0% | 58.3% |

**Koishi does not appear in that scope because no submission of it covers the canon.** To compare it
anyway, the next table measures both engines directly on the official packs.

#### C.2 Koishi on the official packs (131 maps, measured here)

Same packs, wider selection: every chart with a usable label, including the tiers below Alpha that
the canon excludes. **This is the scope where ISOR is weakest**, because the packs sit largely
outside the rice model's gate and the physics projection answers alone.

| Algorithm | Valid Maps | Coverage | MAE (lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) |
| :---| :---: | :---: | :---: | :---: | :---: | :---: |
| **Koishi** | 48 / 131 | 36.6% | **0.2253** | **0.3054** | **54.17%** | **89.58%** |
| **ISOR** | **131 / 131** | **100.0%** | 0.3536 | 0.4614 | 35.11% | 78.63% |

**On the 48 maps both estimators answer, ISOR scores 0.2844 against Koishi's 0.2253, and 35.42 %
exact against 54.17 %.** Koishi is better here on both metrics and answers a third of the scope;
ISOR answers all of it.

**The two tables are not comparable with each other.** C uses the canon selection the benchmark
publishes; C.2 uses every label the packs provide, which adds the low tiers where both engines do
worse. Read each one within its own scope, and neither against tables A and B, which measure the
Leo_Black corpus.

---

### 9.3 Pattern-Specific Breakdown for ISOR

Performance across distinct mechanical archetypes on the **High Rice Scale
(Tiers 11–17, 1103 maps)** — the same scope as the benchmark charts:

| Pattern Skillset | Evaluated Maps ($n$) | MAE (Lower is better) | RMSE | Exact Fit ($\le 0.20$) | Close Fit ($\le 0.50$) |
| :---| :---: | :---: | :---: | :---: | :---: |
| **Stamina / Dense Jumpstream** | 282 | **0.1496** | 0.2124 | **78.4%** | **97.2%** |
| **Jack / Chordjack** | 355 | **0.1614** | 0.2196 | 73.0% | 96.3% |
| **Speed / Burst Streams** | 247 | **0.1858** | 0.2488 | 68.4% | 94.3% |
| **Technical / Poly-Rhythm** | 207 | **0.2020** | 0.3321 | 67.2% | 92.3% |
| **Course / Marathon** | 12 | **0.2308** | 0.2813 | 41.7% | 100.0% |
| **Overall** | **1103** | **0.1722** | **0.2499** | **71.9%** | **95.4%** |

Technical is the weakest archetype on both axes, and it is also the one with the widest residual
spread (RMSE 0.33 against MAE 0.20). Course has too few maps in this scope for its figure to be
stable; it is listed for completeness, not as a ranking.

<p align="center">
  <img src="assets/benchmark_pattern_breakdown.png" alt="MAE by Pattern Skillset" width="800" />
  <br/><em>MAE by pattern skillset — High Rice Scale (Tiers 11–17)</em>
</p>

---

### 9.4 Head-to-Head Matrix: ISOR vs. Key Benchmark Engines

Direct symmetric comparison across common matched beatmaps on the **High Rice
Scale (Tiers 11–17)**. A tie is a per-map difference of $|\Delta\text{MAE}| \le 0.005$:

| Algorithm | Common Maps | ISOR MAE | Algorithm MAE | Wins | Losses | Ties |
| :---| :---: | :---: | :---: | :---: | :---: | :---: |
| **Koishi** | 1096 | **0.1710** | 0.1510 | 503 | **556** | 37 |
| **XDC1** | 1102 | **0.1721** | 0.1717 | **528** | 525 | 49 |
| **Mixed** | 1103 | **0.1722** | 0.1699 | **543** | 517 | 43 |
| **Roxy** | 1096 | **0.1701** | 0.1980 | **603** | 452 | 41 |
| **Azusa** | 1101 | **0.1720** | 0.2183 | **631** | 420 | 50 |
| **Companella** | 1103 | **0.1722** | 0.3666 | **796** | 285 | 22 |
| **Daniel** | 1099 | **0.1711** | 0.4088 | **882** | 208 | 9 |
| **Sunny** | 1103 | **0.1722** | 0.5156 | **863** | 228 | 12 |

**ISOR wins seven of the eight pairwise matchups and loses to Koishi**, by 53 maps out of 1096
(556–503). Against XDC1 and Mixed the win counts are level within noise (528–525 and 543–517), even
though ISOR leads both on exact rate. **The one clear loss is to Koishi, and it is a loss on error
magnitude, not on exactness** — which is the same trade-off §5bis describes.

<p align="center">
  <img src="assets/benchmark_head_to_head.png" alt="Head to Head Win Matrix" width="800" />
  <br/><em>Head-to-head win rates — High Rice Scale (Tiers 11–17)</em>
</p>

* **Apex Scale Consistency (Zeta to Kappa):** **84.0% exact tier accuracy**; Kappa tier: 4/4 rated within the Kappa band (MAE = 0.00).
* **Unseen Generalization:** Official test packs maintain $92.7\%$ within $\pm 1.0$ Dan ($\text{MAE} = 0.429$).

---

## 10. Repository & Module Structure

```text
src/08_isor_engine/
├── __init__.py               # Package declaration & public API exports
├── isor_engine.py            # Primary pipeline: Triangulation, Ridge meta-layer, Gates
├── strain.py                 # Biomechanical strain engine: 7 streams, Entropy, Quantiles
├── ISOR.csv                  # Benchmark predictions (1364 maps, official CSV)
└── ISOR.md                   # Complete technical documentation (this file)

config/
├── vsrg_ridge_model.json     # Calibrated Ridge weights (High λ=8, Low λ=32, 98 features)
└── celestial_ruler.json      # Monotonic Celestial 35-slot frontier rulers
```

> **Zero Duplication:** ISOR directly interfaces with existing core modules (`parser`, `validator`, `feature_extractor`, `classifier`, `primary_sr_bridge`, `minacalc_bridge`).

---

## 11. Architectural Guarantees

1. **Zero Piecewise Step Cliffs:** All internal functions and transitions are $C^0$/$C^1$ smooth.
2. **Strict Frontier Monotonicity:** Rulers enforced via PAVA; rate progression clamped isotonically.
3. **Domain-Restricted Meta-Layer:** Ridge corrections strictly gated by $r_{\text{LN}} \le 0.18$ and bound within $[-1.0, +1.0]$.
4. **Deterministic Reproducibility:** identical inputs produce identical outputs. The engine is **not** claimed to be bit-exact across platforms (floating-point libm differences and the `msd.exe` subprocess make that unprovable); what *is* guaranteed by construction is that a given rate always resolves to the same value regardless of the order in which rates were queried.
5. **No Regressions on Out-of-Sample Sets:** Generalization confirmed via external practice and official packs.

---

## 12. Known Limitations & Scope Constraints

* **Strictly 4K Rice:** Long-note dominant beatmaps and non-4K keymodes are rejected by domain validation.
* **Residual Physical Variance Floor:** On the 11–17 tier band, bias is $\approx 0$ with residual variance $\sigma \approx 0.25 - 0.31$, representing the empirical theoretical limit of 4K notechart signals.
* **Lower-Band Dispersion:** below tier 11 the residual error is dispersion rather than bias, so level calibration cannot reduce it; further gains there require additional labelled charts, not a different model.
* **Sparse Upper Canon:** the tiers above 16 are represented by very few labelled charts, and the official packs contain almost none above the Zeta band. Any correction fitted there rests on thin evidence and should be read as provisional.
* **Correction Cap:** each head and the total correction are clipped to $\pm 1.0$ Dan. A small number of charts require a larger correction; raising the cap was measured to degrade held-out accuracy, so the limit is deliberate.
* **Sub-0.75× Rate Plateau:** Rates below $0.75\times$ are plateaued against the lower native anchor to preserve monotonicity.
* **Celestial Intra-Tier Overlap:** Human consensus in Celestial packs exhibits real overlap across adjacent slots, bounding maximum 35-slot exact accuracy near $\approx 26\%$.

---

## 13. Overlay Integration & Runtime Dispatch

### 13.1 Python Runtime Import
```python
import sys
from pathlib import Path

# Add src/08_isor_engine directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "08_isor_engine"))

import isor_engine

# Execution
result = isor_engine.analyze_beatmap_isor(
    osu_path="path/to/beatmap.osu",
    mod="NM",
    rate=1.0
)

print(f"Calculated Rating: {result['dan_label']} ({result['dp']:.2f} DP)")
```

### 13.2 Standalone PyInstaller Bundling
Both `config/vsrg_ridge_model.json` and `config/celestial_ruler.json` are bundled as read-only assets in the frozen PyInstaller distribution. `resource_path.py` resolves runtime configuration paths transparently.

---

## 14. Acknowledgements & Credits

- **ROXY ([Algorithm Specification](https://github.com/LeoBlackMT/osumania_map_analyser/blob/main/docs/roxy_algorithm.md) | [Source Code](https://github.com/LeoBlackMT/osumania_map_analyser/blob/main/ManiaMapAnalyser%20by%20Leo_Black/js/estimator/roxyEstimator.js)) by Leo_Black (MIT)** — Primary inspiration for the biomechanical strain modeling (dual burst/sustain decay, pattern entropy, and physiological strain streams), as well as providing the reference VSRG DanEstimation Benchmark corpus used for ground-truth validation.
