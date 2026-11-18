# DanOverlay — Skin Dimensions Reference

This document is the specification for the window size of every DanOverlay skin
(skins 1 to 12). Each layout of each skin has two numbers:

* **Viewport** — the inner size the UI is laid out at. This is what the HTML and
  CSS are designed for, and the size the window is set to; the host adds the OS
  frame on top so the viewport ends up exactly this size.
* **Window outer** — the same view plus the Windows frame: **+16 px** of width and
  **+39 px** of height (border and title bar).

`zoom` is the CSS zoom the skin runs at, so the layout inside the viewport keeps
the proportions it was drawn for.

The machine-readable version of this table lives in
`config/skin_dimensions.json` and is what the overlay actually reads.

---

## Summary

| ID | Skin | Layout | Viewport (W × H) | Window Outer (W × H) | Zoom |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **1** | Modern | complete | 684 × 281 | 700 × 320 | 100% |
| **1** | Modern | simplified | 684 × 181 | 700 × 220 | 100% |
| **1** | Modern | compact | 684 × 37 | 700 × 76 | 100% |
| **2** | Classic | complete | 684 × 281 | 700 × 320 | 100% |
| **2** | Classic | simplified | 684 × 181 | 700 × 220 | 100% |
| **2** | Classic | compact | 684 × 37 | 700 × 76 | 100% |
| **3** | Graph | complete | 684 × 281 | 700 × 320 | 100% |
| **3** | Graph | simplified | 684 × 181 | 700 × 220 | 100% |
| **3** | Graph | compact | 684 × 37 | 700 × 76 | 100% |
| **4** | Vertical Monolith | collapsed | 268 × 296 | 284 × 335 | 61% |
| **4** | Vertical Monolith | expanded | 268 × 427 | 284 × 466 | 61% |
| **5** | Broadcast Bar | collapsed | 573 × 131 | 589 × 170 | 75% |
| **5** | Broadcast Bar | expanded | 573 × 233 | 589 × 272 | 75% |
| **6** | Dark Vignette | collapsed | 629 × 172 | 645 × 211 | 73% |
| **6** | Dark Vignette | expanded | 629 × 258 | 645 × 297 | 73% |
| **7** | Sunny Rebirth | default | 784 × 301 | 800 × 340 | 100% |
| **8** | Hero-Dan Lazer | collapsed | 578 × 99 | 594 × 138 | 94% |
| **8** | Hero-Dan Lazer | expanded | 578 × 195 | 594 × 234 | 94% |
| **9** | Josh type shit | complete | 524 × 146 | 540 × 185 | 100% |
| **9** | Josh type shit | simplified | 409 × 129 | 425 × 168 | 100% |
| **9** | Josh type shit | compact | 323 × 93 | 339 × 132 | 100% |
| **10** | Dynamic Orbital Island | collapsed | 661 × 122 | 677 × 161 | 100% |
| **10** | Dynamic Orbital Island | expanded | 661 × 252 | 677 × 291 | 100% |
| **11** | Chrono-Tachometer Blade | collapsed | 784 × 197 | 800 × 236 | 100% |
| **11** | Chrono-Tachometer Blade | expanded | 784 × 213 | 800 × 252 | 100% |
| **12** | Swiss Brutalist Ticker | collapsed | 630 × 132 | 646 × 171 | 77% |
| **12** | Swiss Brutalist Ticker | expanded | 630 × 163 | 646 × 202 | 77% |

---

## Per skin

### Skin 1: Modern

* **Zoom**: 100% (1.00)
* **Layouts**:
  * complete — viewport **684 × 281**, window outer 700 × 320
  * simplified — viewport **684 × 181**, window outer 700 × 220
  * compact — viewport **684 × 37**, window outer 700 × 76

### Skin 2: Classic

* **Zoom**: 100% (1.00)
* **Layouts**:
  * complete — viewport **684 × 281**, window outer 700 × 320
  * simplified — viewport **684 × 181**, window outer 700 × 220
  * compact — viewport **684 × 37**, window outer 700 × 76

### Skin 3: Graph

* **Zoom**: 100% (1.00)
* **Layouts**:
  * complete — viewport **684 × 281**, window outer 700 × 320
  * simplified — viewport **684 × 181**, window outer 700 × 220
  * compact — viewport **684 × 37**, window outer 700 × 76

### Skin 4: Vertical Monolith

* **Zoom**: 61% (0.61)
* **Layouts**:
  * collapsed — viewport **268 × 296**, window outer 284 × 335
  * expanded — viewport **268 × 427**, window outer 284 × 466

### Skin 5: Broadcast Bar

* **Zoom**: 75% (0.75)
* **Layouts**:
  * collapsed — viewport **573 × 131**, window outer 589 × 170
  * expanded — viewport **573 × 233**, window outer 589 × 272

### Skin 6: Dark Vignette

* **Zoom**: 73% (0.73)
* **Layouts**:
  * collapsed — viewport **629 × 172**, window outer 645 × 211
  * expanded — viewport **629 × 258**, window outer 645 × 297

### Skin 7: Sunny Rebirth

* **Zoom**: 100% (1.00)
* **Layouts**:
  * default — viewport **784 × 301**, window outer 800 × 340

### Skin 8: Hero-Dan Lazer

* **Zoom**: 94% (0.94)
* **Layouts**:
  * collapsed — viewport **578 × 99**, window outer 594 × 138
  * expanded — viewport **578 × 195**, window outer 594 × 234

### Skin 9: Josh type shit

* **Zoom**: 100% (1.00)
* **Layouts**:
  * complete — viewport **524 × 146**, window outer 540 × 185
  * simplified — viewport **409 × 129**, window outer 425 × 168
  * compact — viewport **323 × 93**, window outer 339 × 132

### Skin 10: Dynamic Orbital Island

* **Zoom**: 100% (1.00)
* **Layouts**:
  * collapsed — viewport **661 × 122**, window outer 677 × 161
  * expanded — viewport **661 × 252**, window outer 677 × 291

### Skin 11: Chrono-Tachometer Blade

* **Zoom**: 100% (1.00)
* **Layouts**:
  * collapsed — viewport **784 × 197**, window outer 800 × 236
  * expanded — viewport **784 × 213**, window outer 800 × 252

### Skin 12: Swiss Brutalist Ticker

* **Zoom**: 77% (0.77)
* **Layouts**:
  * collapsed — viewport **630 × 132**, window outer 646 × 171
  * expanded — viewport **630 × 163**, window outer 646 × 202

