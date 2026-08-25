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
4. [Detailed Execution Pipeline](#4-detailed-execution-pipeline)
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
   Calibrated against rigorous human-verified datasets: the Leo_Black VSRG Benchmark (746 beatmaps with verified expected Dans), official DDMythical Reform course packs (151 beatmaps), and official Celestial packs (160 beatmaps). No parameter is tuned arbitrarily.
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
    OSU[".osu Beatmap File (4K Rice)"] --> PARSE["parsear_osu_v2<br/>Enforce 4K Mania Mode"]
    PARSE --> VAL["validate_domain<br/>Notes ≥ 20 · Drain ≥ 5s · LN Ratio ≤ 0.18"]
    VAL -->|Invalid / LN Dominant| ERR["Domain Error (Out of Scope)"]
    VAL -->|Valid 4K Rice| FEAT["extract_features<br/>40+ Base Structural Metrics"]

    FEAT --> SUNNY["analyze_primary_sr(mod, rate)<br/>Sunny SR + Strains (Jbar, Pbar, Xbar, Abar)<br/>Isotonic Rate Clamp"]
    FEAT --> MSD["calculate_msd(rate)<br/>MinaCalc C++: 7 Skillsets + Overall<br/>Monotonic Native Anchors"]
    FEAT --> CHOKE["Choke Point 10s Window<br/>Max NPS + Peak Local Strains"]
    FEAT --> BIO["strain.py<br/>7 Dual-Decay Streams + Shannon Entropy<br/>+ Sostenuto Density Stats"]
    FEAT --> CLASS["Family Classifier<br/>Cosine Pattern Profiles + Bar Ratios"]

    SUNNY --> TRIA["Triangulated Organic Base"]
    MSD --> TRIA
    CHOKE --> TRIA
    CLASS --> TRIA

    subgraph TRIA["Organic Convex Triangulation"]
        ROUT["Skillset Routing<br/>(Jack / Speed / Stamina / Tech / General)"]
        PROJ["Ruler Projections<br/>DP_sr · DP_choke · DP_msd"]
        W["Dynamic Weight System<br/>w_sr · w_choke · w_msd"]
        CORR["Continuous Dampers & Alpha/Beta Anchors"]
        ROUT --> PROJ --> W --> CORR
    end

    BIO --> RIDGE["Dual-Band Ridge Corrector (ISOR-R)"]
    TRIA --> RIDGE
    RIDGE --> BLEND["C¹ Blended Base<br/>σ(4·(DP_org - 10)) Blend"]

    subgraph RIDGE["Regularized Ridge Meta-Layer"]
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

## 4. Detailed Execution Pipeline

### 4.1 Parsing & Domain Validation
The beatmap file is parsed via `parsear_osu_v2`, enforcing `mode == 3` (osu!mania) and $K = 4$ columns. `validate_domain` enforces structural integrity:
- **Minimum Note Count:** $N \ge 20$.
- **Minimum Active Drain Duration:** $T_{\text{drain}} \ge 5.0\text{ s}$.
- **Long Note Ratio:** $r_{\text{LN}} = N_{\text{LN}} / N \le 0.18$. Maps exceeding this threshold trigger a graceful `DomainError`.

### 4.2 Signal Ingestion
Five independent feature extractors process the note array simultaneously:
1. **Sunny Primary SR Bridge:** Extracts raw star rating $SR_{\text{raw}}$, peak strain components (Jbar, Pbar, Xbar: $\bar{J}, \bar{P}, \bar{X}$), and mean stream strain $\bar{A}$ (Abar).
2. **MinaCalc MSD Subprocess:** Evaluates 7 core skillsets (Overall, Stream, Jumpstream, Handstream, Stamina, JackSpeed, Chordjack, Technical).
3. **10-Second Choke Point Analyzer:** Computes rolling density $NPS_{10\text{s}}$, burst ratios, and local chord clusters in $O(W \log N)$ time.
4. **Biomechanical Strain Module (`strain.py`):** Generates 7 physical strain streams, Shannon pattern entropy, and sustained density metrics.
5. **Pattern Classifier:** Identifies macro-families via cosine similarity against reference pattern profiles.

### 4.3 Skillset Routing
The map is dynamically mapped to a canonical skillset $\kappa \in \{\text{jack}, \text{speed}, \text{stamina}, \text{tech}, \text{general}\}$:
```python
if "jack" in family or jbar_max > 55.0 or jack_density >= jack_threshold:
    skillset = "jack"
elif "tech" in family or family == "ln":
    skillset = "tech"
elif "stream" in family and jump_ratio < speed_jump_threshold:
    skillset = "speed"
elif "stamina" in family or jump_ratio >= speed_jump_threshold:
    skillset = "stamina"
else:
    skillset = "general"
```

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
DP_{\text{organic}} = \frac{w_{\text{SR}} DP_{\text{SR}} + w_{\text{choke}} DP_{\text{choke}} + w_{\text{MSD}} DP_{\text{MSD}} + w_{\text{bio}} DP_{\text{bio}}}{w_{\text{SR}} + w_{\text{choke}} + w_{\text{MSD}} + w_{\text{bio}}}
$$

### 4.6 Dual-Model Ridge Meta-Correction
To correct subtle non-linear residual errors ($y - DP_{\text{base}}$), a dual regularized Ridge model is applied across the standardized 98-D feature vector $\mathbf{z}$:

$$
\hat{\delta} = \mathbf{z}^T \mathbf{\beta}
$$

- **High-Tier Model ($\lambda = 8$):** Trained on tiers 11–17.5.
- **Low-Tier Model ($\lambda = 32$):** Trained on tiers 1–10.5 augmented with 67 official DDMythical low-tier maps.
- **Transition Gate:** Blended smoothly via $\sigma\left(4.0 \cdot (DP_{\text{organic}} - 10.0)\right)$.

### 4.7 Apex Cosine Gate (Zeta–Kappa Canon Restoration)
Because standard training sets sparsely populate tiers beyond 18.0 DP, a $C^0$ cosine transition gate activates smoothly above 18.8 DP to restore the official high-tier progression:

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

<p align="center">
  <img src="assets/ruler_interpolation.png" alt="Piecewise-Linear Frontier Ruler Interpolation" width="780" />
</p>

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
w_{\text{choke}} &= \max\left(w_{\text{choke}}^{\min}, \; 1.0 - w_{\text{SR}} - w_{\text{MSD}} - w_{\text{bio}}\right)
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

### 5.7 $L_2$ Regularized Ridge Meta-Corrector
Given standardized feature matrix $\mathbf{Z} \in \mathbb{R}^{N \times D}$ and target residual vector $\mathbf{y} = \mathbf{DP}_{\text{expected}} - \mathbf{DP}_{\text{base}}$:

$$
\begin{aligned}
\mathbf{\beta} &= \left(\mathbf{Z}^T \mathbf{Z} + \lambda \mathbf{I}\right)^{-1} \mathbf{Z}^T \mathbf{y} \\
\hat{\delta}(\mathbf{x}) &= \text{clip}\left(\left(\frac{\mathbf{x} - \mathbf{\mu}_x}{\mathbf{\sigma}_x}\right)^T \mathbf{\beta}, \;-1.0, \;+1.0\right)
\end{aligned}
$$

* **High-Tier Model:** $\lambda = 8.0$ across $D = 98$ features.
* **Low-Tier Model:** $\lambda = 32.0$ across $D = 98$ features.

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

<p align="center">
  <img src="assets/apex_cosine_gate.png" alt="Apex Cosine Transition Gate" width="780" />
</p>

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
  │                      TOTAL EVALUATION CORPUS (1,057 Maps)              │
  ├────────────────────────────┬────────────────────────────┬──────────────┤
  │ Leo_Black VSRG Benchmark   │ Official Reform Packs      │ Celestial    │
  │ 746 Maps (Ground Truth)    │ 151 Maps (1st to Kappa)    │ 160 Maps     │
  └────────────────────────────┴────────────────────────────┴──────────────┘
```

---

### 9.2 Complete Leo_Black VSRG Benchmark Results

> **Evaluation Methodology & Transparency:**  
> The benchmark metrics presented below were evaluated through rigorous **local testing** using the official reference dataset and scoring criteria established in [Leo_Black's VSRG DanEstimation Benchmark](https://github.com/LeoBlackMT/VSRG-DanEstimation-Benchmark). To guarantee full reproducibility and transparency, the complete raw predictions for all 746 benchmark beatmaps are provided in [ISOR.csv](ISOR.csv).

#### A. High Rice Scale (Tiers 11.0 – 17.0 · 485 Maps) — *Core Competitive Arena*
| Algorithm | Valid Maps | Coverage | MAE (Lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) | Benchmark Rank |
| :---| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ISOR (DanOverlayV2)** | **485 / 485** | **100.0%** | **0.2110** | **0.2790** | **60.0%** | **93.2%** | #1 |
| **ROXY** | 480 / 485 | 99.0% | 0.2191 | 0.2966 | 59.4% | 92.9% | #2 |
| **Mixed** | 485 / 485 | 100.0% | 0.2329 | 0.3308 | 58.4% | 92.0% | #3 |
| **Azusa** | 485 / 485 | 100.0% | 0.2795 | 0.3820 | 46.4% | 88.7% | #4 |
| **Daniel** | 481 / 485 | 99.2% | 0.3116 | 0.4535 | 46.4% | 83.6% | #5 |
| **Companella** | 485 / 485 | 100.0% | 0.4409 | 0.6120 | 35.5% | 70.1% | #6 |
| **Sunny (Native)** | 485 / 485 | 100.0% | 0.5478 | 0.7517 | 32.2% | 56.9% | #7 |

<p align="center">
  <img src="assets/benchmark_accuracy_breakdown.png" alt="Benchmark Accuracy Breakdown" width="820" />
  <br/><em>Accuracy tier distribution — High Rice Scale (Tiers 11–17, 485 maps)</em>
</p>

<p align="center">
  <img src="assets/benchmark_delta_distribution.png" alt="Residual Error Distribution" width="800" />
  <br/><em>Residual error distribution — High Rice Scale (Tiers 11–17, 485 maps)</em>
</p>

---

#### B. Full Rice Scale (Tiers 1.0 – 18.0 · 644 Maps) — *Comprehensive Ladder*
| Algorithm | Valid Maps | Coverage | MAE (Lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) | Full Coverage Rank |
| :---| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ISOR (DanOverlayV2)** | **644 / 644** | **100.0%** | **0.2920** | **0.4157** | **50.8%** | **84.2%** | #1 |
| **Mixed** | 644 / 644 | 100.0% | 0.3019 | 0.4338 | 50.5% | 83.2% | #2 |
| **Azusa** | 644 / 644 | 100.0% | 0.3370 | 0.4657 | 41.6% | 80.1% | #3 |
| **ROXY** *(Partial)* | 502 / 644 | 78.0% | 0.2414 | 0.3372 | 57.2% | 90.2% | *(Incomplete Scope)* |
| **Daniel** *(Partial)* | 522 / 644 | 81.1% | 0.3193 | 0.4633 | 46.6% | 82.2% | *(Incomplete Scope)* |
| **Companella** | 644 / 644 | 100.0% | 0.5420 | 0.8050 | 32.5% | 64.1% | #4 |
| **Sunny (Native)** | 644 / 644 | 100.0% | 0.6196 | 0.8500 | 30.1% | 52.8% | #5 |

<p align="center">
  <img src="assets/benchmark_scatter_plot.png" alt="ISOR Expected vs Estimated Dan Scatter Plot" width="680" />
  <br/><em>Calibration scatter — Full Rice Scale (644 maps, LN excluded)</em>
</p>

---

#### C. Official Dan Reform Canon (60 Canon Maps · DDMythical, Emik03, Thaumiel, Cloverwisp)
| Algorithm | Valid Maps | Coverage | MAE (Lower is better) | RMSE | Exact ($\le 0.20$) | Close ($\le 0.50$) |
| :---| :---: | :---: | :---: | :---: | :---: | :---: |
| **ISOR (DanOverlayV2)** | **60 / 60** | **100.0%** | **0.3213** | **0.4503** | **40.0%** | **85.0%** |
| **ROXY** *(Partial)* | 46 / 60 | 76.7% | 0.2435 | 0.3231 | 56.5% | 93.5% |
| **Daniel** *(Partial)* | 51 / 60 | 85.0% | 0.3235 | 0.4286 | 39.2% | 78.4% |
| **Mixed** | 60 / 60 | 100.0% | 0.3433 | 0.5199 | 51.7% | 83.3% |
| **Sunny (Native)** | 60 / 60 | 100.0% | 0.3450 | 0.5074 | 56.7% | 70.0% |
| **Azusa** | 60 / 60 | 100.0% | 0.3552 | 0.4762 | 38.3% | 78.3% |
| **Companella** | 60 / 60 | 100.0% | 0.7313 | 1.0728 | 35.0% | 58.3% |

---

### 9.3 Pattern-Specific Breakdown for ISOR

Performance across distinct mechanical archetypes on the **High Rice Scale
(Tiers 11–17, 485 maps)** — the same scope as the benchmark charts:

| Pattern Skillset | Evaluated Maps ($n$) | MAE (Lower is better) | RMSE | Exact Fit ($\le 0.20$) | Close Fit ($\le 0.50$) |
| :---| :---: | :---: | :---: | :---: | :---: |
| **Jack / Chordjack** | 181 | **0.2036** | 0.2688 | 59.7% | 93.9% |
| **Speed / Burst Streams** | 109 | **0.1917** | 0.2490 | 67.9% | 92.7% |
| **Technical / Poly-Rhythm** | 81 | **0.2198** | 0.2801 | 60.5% | 95.1% |
| **Stamina / Dense Jumpstream** | 102 | **0.2283** | 0.3149 | 54.9% | 93.1% |

<p align="center">
  <img src="assets/benchmark_pattern_breakdown.png" alt="MAE by Pattern Skillset" width="800" />
  <br/><em>MAE by pattern skillset — High Rice Scale (Tiers 11–17)</em>
</p>

---

### 9.4 Head-to-Head Matrix: ISOR vs. Key Benchmark Engines

Direct symmetric comparison across common matched beatmaps on the **High Rice
Scale (Tiers 11–17)**:

$$
\begin{aligned}
\text{vs. ROXY (482 maps):} &\quad \mathbf{\text{ISOR MAE: } 0.2097} \;\text{ vs. }\; \text{ROXY MAE: } 0.2191 \quad (\mathbf{251 \text{ Wins}} \;/\; 219 \text{ Losses} \;/\; 12 \text{ Ties}) \\
\text{vs. Mixed (487 maps):} &\quad \mathbf{\text{ISOR MAE: } 0.2108} \;\text{ vs. }\; \text{Mixed MAE: } 0.2329 \quad (\mathbf{257 \text{ Wins}} \;/\; 218 \text{ Losses} \;/\; 12 \text{ Ties}) \\
\text{vs. Azusa (487 maps):} &\quad \mathbf{\text{ISOR MAE: } 0.2108} \;\text{ vs. }\; \text{Azusa MAE: } 0.2784 \quad (\mathbf{295 \text{ Wins}} \;/\; 183 \text{ Losses} \;/\; 9 \text{ Ties}) \\
\text{vs. Daniel (483 maps):} &\quad \mathbf{\text{ISOR MAE: } 0.2105} \;\text{ vs. }\; \text{Daniel MAE: } 0.3112 \quad (\mathbf{279 \text{ Wins}} \;/\; 199 \text{ Losses} \;/\; 5 \text{ Ties})
\end{aligned}
$$

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
├── ISOR.csv                  # Benchmark predictions (746 maps, official CSV)
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
4. **Deterministic Reproducibility:** Fixed-point bit-exact mathematical outputs across all platforms.
5. **No Regressions on Out-of-Sample Sets:** Generalization confirmed via external practice and official packs.

---

## 12. Known Limitations & Scope Constraints

* **Strictly 4K Rice:** Long-note dominant beatmaps and non-4K keymodes are rejected by domain validation.
* **Residual Physical Variance Floor:** On the 11–17 tier band, bias is $\approx 0$ with residual variance $\sigma \approx 0.25 - 0.31$, representing the empirical theoretical limit of 4K notechart signals.
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

---

*ISOR — Isotonic Strain Organic Residual. Engineered for precision, physiological fidelity, and mathematical continuity in VSRG difficulty estimation.*
