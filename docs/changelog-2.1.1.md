# DanOverlay 2.1.1 — Accuracy Display Fix

## Problem

After finishing a play, the result text always displayed "Perfect!" regardless of the player's actual accuracy. This happened in all game modes (Reform, Celestial, Signicial, etc.).

## Root Cause

A real-time data source initialises the accuracy field to 1.0 (100 %) as a placeholder value before the first note is hit. The overlay was accepting this placeholder and treating it as a real reading, causing every play to show "Perfect!" even when the actual accuracy was far lower.

```mermaid
flowchart LR
  subgraph Before["Before"]
    A["tosu sends accuracy = 1.0<br>(placeholder, no notes hit yet)"] --> B["Overlay accepts it as real"]
    B --> C["result = Perfect!<br>(always, regardless of actual play)"]
    D["tosu sends accuracy = 0.92<br>(actual play result)"] --> E["Overlay ignores it<br>(placeholder already overwrote it)"]
    E --> F["result still shows Perfect!"]
  end
```

```mermaid
flowchart LR
  subgraph After["After"]
    A2["tosu sends accuracy = 1.0<br>(placeholder)"] --> B2["Overlay detects it's a placeholder<br>accuracy ≠ 1.0 required"]
    B2 --> C2["Overlay waits for real data"]
    D2["tosu sends accuracy = 0.92<br>(actual play result)"] --> E2["Overlay accepts genuine reading"]
    E2 --> F2["result = Clear!<br>(correct for 92 % accuracy)"]
  end
```

## Fix Applied

1. **During gameplay**: placeholder accuracy values of exactly 1.0 are now ignored, so the overlay waits for genuine accuracy updates.
2. **On the results screen**: the final accuracy is only read from the definitive results source when no real gameplay value was recorded.
