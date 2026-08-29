# DanOverlay 3.1 — Etterna Integration & Performance Optimization

## Summary

Version **3.1** introduces native, theme-independent **Etterna** integration to DanOverlay, turning it into a unified difficulty and skillset estimation platform across both **osu!mania** and **Etterna**. This release adds real-time song data extraction, live gameplay tracking, post-song evaluation screens with Wife% calculation, official Etterna grade badges (`F` through `AAAAA`), custom banner and pack metadata in the density graph generator, alongside extensive $O(N)$ engine-level performance optimizations and vectorization.

---

## 1. New Feature: Etterna Integration

DanOverlay connects non-invasively to **Etterna** via lightweight background Lua actors. Just as DanOverlay reads osu!mania live game states through `tosu.app`, it communicates with Etterna through atomic state updates written to the game's `Save/` directory.

> **Full Lua Actor & Theme Installation Guide**: [src/02_runtime_bridge/etterna/bridges/README.md](../src/02_runtime_bridge/etterna/bridges/README.md)

### How the Etterna Communication Operates
- **Non-Invasive File IPC**: The runtime bridge (`etterna_source.py`) monitors the Etterna `Save/` folder at ~16 Hz, detecting active song changes, rate modifications, live gameplay timestamps, and score evaluation results.
- **Three Core Theme Actors (`src/02_runtime_bridge/etterna/bridges/`)**:
  - `dan_overlay_bridge.lua` (`ScreenSelectMusic`): Emits active song metadata (Title, Artist, Song Directory, Stepfile Path, Difficulty, Meter, Rate Multiplier, Background Image, and native MSD ratings).
  - `dan_overlay_menu.lua` (`ScreenSelectMusic`): Maintains smooth rate synchronization and wheel settlement during rapid song-wheel scrolling.
  - `dan_overlay_gameplay.lua` (`ScreenGameplay` & `ScreenEvaluation`): Emits play session starts/stops and evaluation screen statistics (Wife% accuracy, clear/fail status, and official Etterna grade) with **zero CPU overhead** during active gameplay.
- **Universal Theme Support**: Works out of the box with **Rebirth**, **Til Death**, **Simply Love**, **Cyberia**, **Default**, and custom Etterna themes.
- **Process Detection**: Verifies when `Etterna.exe` is actively running to prevent reading stale cached state when starting the overlay first.

### Real-Time Etterna Overlay Behavior & Adaptations
When DanOverlay is linked to Etterna, the interface adapts specifically to match the game's mechanics:
- **Omission of osu!-Specific Metrics**: Fields like Star Rating ($SR$) and Overall Difficulty ($OD$) are automatically omitted in Etterna mode.
- **Wife% Accuracy & Official Grade Badges**: Evaluates performance on the end-of-song score screen and displays the exact Wife% accuracy along with official Etterna grade colors:
  | Grade | Wife% Threshold | Theme Accent Color | Status / Tier |
  | :--- | :--- | :--- | :--- |
  | **AAAAA** | $\ge 99.996\%$ | Pure White (`#FFFFFF`) | Theoretical Perfection |
  | **AAAA** | $\ge 99.955\%$ | Cyan (`#00FFFF`) | Master Tier |
  | **AAA** | $\ge 99.700\%$ | Gold / Yellow (`#FFD700`) | Elite Tier |
  | **AA** | $\ge 93.000\%$ | Neon Green (`#20D070`) | Official Clear Threshold |
  | **A** | $\ge 80.000\%$ | Bright Red (`#E53935`) | Standard Pass |
  | **B** | $\ge 70.000\%$ | Soft Purple | Passing Range |
  | **C** | $\ge 60.000\%$ | Muted Violet | Intermediate |
  | **D** | $< 60.000\%$ | Dark Slate | Sub-Clear |
  | **F** | Fail / Very Low | Deep Red | Failed Run |
- **Audio Visualizer**: Temporarily disabled during Etterna playback.
- **Density Graph Skin (`skin-graph`) Notice**: The density graph skin is currently **not supported / unusable** in Etterna mode. Users should use other HUD skins (Modern, Classic, Monolith, Rebirth HUD, etc.) when playing Etterna.

---

## 2. Advanced Simfile Timing Engine (`sm_parser.py`)

A native, high-precision simfile parser was built into DanOverlay to process `.sm` and `.ssc` files directly:

- **Timing Vector Support**: Handles multiple BPM changes, `STOPS`, `DELAYS`, and split per-chart timing definitions.
- **$O(N)$ Sequential Timing Cursor**: Replaced repetitive $O(N \times M)$ beat scanning with a monotonic linear timing accumulator. Parse time for dense 50,000+ row simfiles dropped from ~70 ms to **$<15\text{ ms}$**.
- **Difficulty Selection**: Accurately extracts the target difficulty level (`Beginner`, `Easy`, `Medium`, `Hard`, `Challenge`, `Edit`) from multi-chart simfiles.

---

## 3. Core Engine Speed & Vectorization Optimizations

Both the **ISOR Engine** and **Legacy Engine** received performance optimizations with **zero mathematical drift** (100% bit-exact outputs):

### Vectorized Sunny SR Calculation (`algorithm.py`)
- Replaced per-note Python loops with batch NumPy array operations.
- Vectorized `get_key_usage_400`, `get_key_usage`, `compute_anchor`, `compute_Jbar`, `compute_Xbar`, and `compute_Pbar` using `np.searchsorted` and in-place `np.add.at` accumulation.

### Linear-Time Choke Point Analyzer (`isor_engine.py`)
- Refactored `extract_choke_and_local_strains` from $O(W \log N)$ repeated binary searches to an $O(W + N)$ two-pointer monotonic sliding window.
- Precomputed boundary lookup caching in `interpolate_ruler` to eliminate repetitive matrix reconstruction.
- Pre-cast Ridge Model weight matrices to contiguous float arrays on startup for sub-millisecond vector dot products (`xh @ beta`).

### Active State Tracking in Biomechanical Strain (`strain.py`)
- Replaced full 256-state transition loops in Shannon column entropy calculation with an `active_transitions` set, bypassing ~95% of inactive state evaluations.
- Vectorized summary quantiles in `_summarize` via NumPy array sorting and power-mean calculations.

---

## 4. Density Graph Generator Adaptations

- **Symmetric Banner Display**: Charts with bundled banner images render symmetrically below the density graph with dark backdrop scaling.
- **Pack Name & Active Rate Metadata**: Displays the parent pack name (e.g. `Tech Corps v2`) and active playback multiplier (e.g. `1.25x`) directly in the header row.

---

## 5. Auto-Installer, Troubleshooting & Bug Reporting

- **Automatic Theme Installation**: DanOverlay automatically scans your Etterna installation and injects the necessary bridge actors into standard themes (`Til Death`, `Rebirth`, `_fallback`, etc.) upon launch with automated backup creation (`.dan_backup`).
- **Manual Theme Fallback**: If you use a customized or non-standard theme, manual setup instructions and bridge files are available in [src/02_runtime_bridge/etterna/bridges/README.md](../src/02_runtime_bridge/etterna/bridges/README.md).

> [!IMPORTANT]
> **Reporting Etterna Issues & Feedback:**  
> If you encounter any theme compatibility issues, chart parsing quirks, or if the auto-installer did not inject lines into your custom theme, please report them directly via **Discord** (or open an issue on GitHub) with your theme name, simfile `.sm`/`.ssc`, and logs so we can fix them quickly.

---

## 6. Acknowledgements & Credits

- **[JoseMGS3/DanielEtterna](https://github.com/JoseMGS3/DanielEtterna) by JoseMGS3** — Sincere thanks and credit to JoseMGS3 for sharing his codebase, providing knowledge on Etterna Lua bridging, and inspiring the implementation of the Etterna theme integration in DanOverlay.

