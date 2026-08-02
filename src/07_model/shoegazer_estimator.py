"""shoegazer_estimator.py — Dan Shoegazer stage estimator.

Architecture (mirrors signicial_estimator.py):
    SR (primary engine) + Shoegazer SR means per stage
    → boundary interpolation → dp_shoegazer (1.0–12.0) → stage

Stage order (weakest → strongest):
    1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th, Luminal, Tachyon

dp_shoegazer: 1.0 (1st Dan) → 12.0 (Tachyon)

Profile JSON shape (produced by _calibrate_shoegazer.py):
{
  "1st": {
    "sr_mean":     float,
    "sr_lower":    float,
    "sr_upper":    float,
    "sr_count":    int,
    "overall_msd": float,
    ...
  },
  ...
  "Tachyon": { ... }
}
"""

import json
import math
import os
import sys
from dataclasses import dataclass

if getattr(sys, "frozen", False):
    _PROFILES_PATH = os.path.join(sys._MEIPASS, "config", "shoegazer_profiles.json")
else:
    _ROOT = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    _PROFILES_PATH = os.path.join(_ROOT, "config", "shoegazer_profiles.json")

# Ordered stage keys (index 0 → dp 1.0, index 11 → dp 12.0)
STAGE_KEYS: list[str] = [
    "1st", "2nd", "3rd", "4th", "5th", "6th",
    "7th", "8th", "9th", "10th", "Luminal", "Tachyon",
]

# Human-readable labels
_STAGE_DISPLAY: dict[str, str] = {
    "1st":     "1st Dan",
    "2nd":     "2nd Dan",
    "3rd":     "3rd Dan",
    "4th":     "4th Dan",
    "5th":     "5th Dan",
    "6th":     "6th Dan",
    "7th":     "7th Dan",
    "8th":     "8th Dan",
    "9th":     "9th Dan",
    "10th":    "10th Dan",
    "Luminal": "Luminal",
    "Tachyon": "Tachyon",
}

# Short tags for compact display
_STAGE_SHORT: dict[str, str] = {
    "1st":     "1",
    "2nd":     "2",
    "3rd":     "3",
    "4th":     "4",
    "5th":     "5",
    "6th":     "6",
    "7th":     "7",
    "8th":     "8",
    "9th":     "9",
    "10th":    "10",
    "Luminal": "☆",
    "Tachyon": "ε",
}

SKILLSET_KEYS = [
    "stream", "jumpstream", "handstream",
    "stamina", "jackspeed", "chordjack", "technical",
]

_STAGE_DP: dict[str, int] = {key: i + 1 for i, key in enumerate(STAGE_KEYS)}

_profiles: dict | None = None
_ruler_cache: list | None = None
_boundaries_cache: list | None = None


# ── Profile loader ─────────────────────────────────────────────────────────────

def _load_profiles() -> dict | None:
    global _profiles
    if _profiles is not None:
        return _profiles
    if not os.path.isfile(_PROFILES_PATH):
        return None
    try:
        with open(_PROFILES_PATH, encoding="utf-8") as f:
            _profiles = json.load(f)
        return _profiles
    except (json.JSONDecodeError, OSError):
        return None


# ── SR ruler ──────────────────────────────────────────────────────────────────

def _build_sr_ruler() -> list[tuple[float, int]] | None:
    """Build the 12-slot SR ruler from profiles.

    Returns sorted list of (sr_mean, dp_int) where dp_int is 1-12,
    or None if profiles lack sr_mean data.
    Enforces strict monotonicity to handle calibration artifacts.
    """
    global _ruler_cache, _boundaries_cache
    if _ruler_cache is not None:
        return _ruler_cache

    profiles = _load_profiles()
    if not profiles:
        return None

    ruler: list[tuple[float, int]] = []
    for key in STAGE_KEYS:
        slot = profiles.get(key)
        if not slot:
            continue
        sr = slot.get("sr_mean")
        if sr is None or sr <= 0:
            continue
        dp_int = _STAGE_DP[key]
        ruler.append((float(sr), dp_int))

    if len(ruler) < 2:
        return None

    # Enforce strict monotonicity (fix calibration rounding artifacts like 8th > 9th)
    ruler.sort(key=lambda x: x[1])
    for i in range(1, len(ruler)):
        if ruler[i][0] <= ruler[i - 1][0]:
            ruler[i] = (ruler[i - 1][0] + 0.001, ruler[i][1])

    _ruler_cache = ruler

    # Pre-compute midpoint boundaries (matching celestial/signicial)
    means = [sr for sr, _ in ruler]
    n = len(means)
    boundaries: list[tuple[float, float, int]] = []
    for i in range(n):
        lower = (means[i - 1] + means[i]) / 2.0 if i > 0 else means[0] - ((means[1] - means[0]) / 2.0 if n > 1 else 1.0)
        upper = (means[i] + means[i + 1]) / 2.0 if i < n - 1 else means[-1] + ((means[-1] - means[-2]) / 2.0 if n > 1 else 1.0)
        boundaries.append((lower, upper, ruler[i][1]))
    _boundaries_cache = boundaries

    return _ruler_cache


# ── SR → dp_shoegazer ─────────────────────────────────────────────────────────

def _sr_to_dp(sr: float) -> float | None:
    """Convert SR → dp_shoegazer (1.0–12.0+) via boundary interpolation.

    Each stage occupies dp_int ∈ [1, 12].  The fractional part t ∈ [0, 1)
    indicates position within that stage:  t=0 at the lower boundary,
    t just below 1 at the upper boundary.
    """
    ruler = _build_sr_ruler()
    if not ruler:
        return None

    boundaries = _boundaries_cache
    if not boundaries:
        return None

    # Below first boundary
    if sr < boundaries[0][0]:
        return max(0.5, float(boundaries[0][2]))

    # Above last boundary
    if sr >= boundaries[-1][1]:
        return min(12.99, float(boundaries[-1][2]) + 0.99)

    # Within range — find containing boundary slot
    for low_sr, high_sr, dp_int in boundaries:
        if low_sr <= sr < high_sr:
            width = max(high_sr - low_sr, 1e-6)
            t = (sr - low_sr) / width
            return float(dp_int) + t

    return None


def _dp_to_stage_key(dp: float) -> str:
    """Map a dp float (1.0-12.0+) to the stage key.

    math.floor ensures the stage matches the integer part of dp:
      dp ∈ [1.0, 2.0) → stage index 0 (1st)
      dp ∈ [2.0, 3.0) → stage index 1 (2nd)
      ...
    """
    idx = min(int(dp) - 1, len(STAGE_KEYS) - 1)
    idx = max(0, idx)
    return STAGE_KEYS[idx]


# ── MSD fallback ───────────────────────────────────────────────────────────────

def _estimate_from_msd(skillsets: dict) -> float | None:
    """Flat MSD distance fallback when SR is unavailable."""
    profiles = _load_profiles()
    if not profiles:
        return None

    vals = [float(skillsets.get(k, 0.0) or 0.0) for k in SKILLSET_KEYS]
    if not vals or max(vals) < 1.0:
        return None
    overall = max(vals)

    msd_ruler: list[tuple[float, int]] = []
    for key in STAGE_KEYS:
        slot = profiles.get(key, {})
        msd_val = slot.get("overall_msd")
        if msd_val and msd_val > 0:
            msd_ruler.append((float(msd_val), _STAGE_DP[key]))

    if len(msd_ruler) < 2:
        return None

    if overall <= msd_ruler[0][0]:
        return float(msd_ruler[0][1])
    if overall >= msd_ruler[-1][0]:
        sr_last, dp_last = msd_ruler[-1]
        sr_prev, dp_prev = msd_ruler[-2]
        step = sr_last - sr_prev
        if step > 0:
            return float(dp_last) + (overall - sr_last) / step
        return float(dp_last)

    for i in range(len(msd_ruler) - 1):
        m_lo, dp_lo = msd_ruler[i]
        m_hi, dp_hi = msd_ruler[i + 1]
        if m_lo <= overall <= m_hi:
            frac = (overall - m_lo) / (m_hi - m_lo)
            return dp_lo + frac * (dp_hi - dp_lo)

    return None


# ── Confidence ─────────────────────────────────────────────────────────────────

def _confidence_from_dp_frac(dp: float) -> float:
    frac = dp - int(dp)
    dist = abs(frac - 0.5)
    conf = 0.5 * (1.0 + math.cos(math.pi * dist / 0.5))
    return max(0.0, min(1.0, conf))


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class ShoegazerResult:
    stage_key:     str    # "1st", "2nd", ..., "Tachyon"
    label:         str    # "1st Dan", ..., "Luminal", "Tachyon"
    short:         str    # "1", ..., "10", "☆", "ε"
    confidence:    float
    dp_shoegazer:  float
    beyond:        bool = False  # True when SR exceeds Tachyon ceiling

    def to_dict(self) -> dict:
        return {
            "stage_key":     self.stage_key,
            "label":         self.label,
            "short":         self.short,
            "confidence":    round(self.confidence, 4),
            "dp_shoegazer":  round(self.dp_shoegazer, 3),
            "beyond":        self.beyond,
        }


# ── Public API ─────────────────────────────────────────────────────────────────

def estimate(skillsets: dict, sr: float | None = None) -> ShoegazerResult | None:
    """Estimate Shoegazer stage from MSD skillsets and optional SR.

    Parameters
    ----------
    skillsets : dict
        MinaCalc skillset values.
    sr : float | None
        Primary SR from the Sunny engine.

    Returns
    -------
    ShoegazerResult | None
    """
    dp: float | None = None

    # Primary path: SR ruler
    if sr is not None and sr > 0.0:
        dp = _sr_to_dp(sr)

    # Fallback: MSD distance
    if dp is None and skillsets:
        dp = _estimate_from_msd(skillsets)

    if dp is None:
        return None

    beyond = dp > 12.99
    dp = max(1.0, dp)

    stage_key  = _dp_to_stage_key(dp)
    label      = _STAGE_DISPLAY[stage_key]
    short      = _STAGE_SHORT[stage_key]
    confidence = _confidence_from_dp_frac(dp)

    return ShoegazerResult(
        stage_key=stage_key,
        label=label,
        short=short,
        confidence=confidence,
        dp_shoegazer=round(dp, 3),
        beyond=beyond,
    )
