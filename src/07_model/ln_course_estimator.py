"""ln_course_estimator.py — LN Dan Course stage estimator.

Architecture (mirrors shoegazer_estimator.py / signicial_estimator.py):
    SR (primary engine) + LN Course SR means per stage × family
    → boundary interpolation → dp_ln (1.0–16.0) → stage

Stage order (weakest → strongest):
    1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th,
    Yoake, Yuugure, Yoru, Yami, Yume, Yokaze

LN families (4 subfamilies, Stage 1–4 of LN Dan Courses v2):
    allround        — All-round / Hybrid LN
    jack_technical  — Jack / Technical LN
    inverse         — Inverse / Jumpstream / Wall LN
    speed_density   — Speed / Density LN

dp_ln: 1.0 (1st) → 16.0 (Yokaze)

Profile JSON shape (produced by calibrate_ln_course.py):
{
  "global": {              # family-agnostic monotonic ruler (PAVA-enforced)
    "1st":  {"sr_mean": float, ...},
    ...
    "Yokaze": {"sr_mean": float, ...}
  },
  "allround":       { ... },
  "jack_technical": { ... },
  "inverse":        { ... },
  "speed_density":  { ... },
  "regression": {           # OLS model: dp ~ dp_sr + LN_features + bias
    "feature_order": ["dp_sr", "hold_occupancy", ...],
    "coefs": [float, ...],
    "training_n": int,
    "r2": float,
    "mae": float
  },
  "family_feature_means": { ... }
}
"""

import json
import math
import os
import sys
from dataclasses import dataclass

if getattr(sys, "frozen", False):
    _PROFILES_PATH = os.path.join(sys._MEIPASS, "config", "ln_course_profiles.json")
else:
    _ROOT = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    _PROFILES_PATH = os.path.join(_ROOT, "config", "ln_course_profiles.json")

# Ordered stage keys (index 0 → dp 1.0, index 15 → dp 16.0)
STAGE_KEYS: list[str] = [
    "1st", "2nd", "3rd", "4th", "5th", "6th",
    "7th", "8th", "9th", "10th",
    "Yoake", "Yuugure", "Yoru", "Yami", "Yume", "Yokaze",
]

LN_FAMILIES: list[str] = [
    "allround", "jack_technical", "inverse", "speed_density",
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
    "Yoake":   "夜明け Yoake",
    "Yuugure": "夕暮れ Yuugure",
    "Yoru":    "夜 Yoru",
    "Yami":    "闇 Yami",
    "Yume":    "夢 Yume",
    "Yokaze":  "夜風 Yokaze",
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
    "Yoake":   "夜明",
    "Yuugure": "夕暮",
    "Yoru":    "夜",
    "Yami":    "闇",
    "Yume":    "夢",
    "Yokaze":  "風",
}

_LN_FAMILY_DISPLAY: dict[str, str] = {
    "allround":       "All-round LN",
    "jack_technical":  "Jack/Technical LN",
    "inverse":         "Inverse/Wall LN",
    "speed_density":   "Speed/Density LN",
}

SKILLSET_KEYS = [
    "stream", "jumpstream", "handstream",
    "stamina", "jackspeed", "chordjack", "technical",
]

_STAGE_DP: dict[str, int] = {key: i + 1 for i, key in enumerate(STAGE_KEYS)}

_profiles: dict | None = None
_ruler_caches: dict[str, list] = {}
_boundary_caches: dict[str, list] = {}


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

def _build_sr_ruler(family_key: str = "global") -> list[tuple[float, int]] | None:
    """Build the 16-slot SR ruler from profiles for a given family.

    Returns sorted list of (sr_mean, dp_int) where dp_int is 1-16,
    or None if profiles lack sr_mean data.
    """
    if family_key in _ruler_caches:
        return _ruler_caches[family_key]

    profiles = _load_profiles()
    if not profiles:
        return None

    family_data = profiles.get(family_key)
    if not family_data:
        # Fallback to global if specific family not found
        family_data = profiles.get("global")
        if not family_data:
            return None

    ruler: list[tuple[float, int]] = []
    for key in STAGE_KEYS:
        slot = family_data.get(key)
        if not slot:
            continue
        sr = slot.get("sr_mean")
        if sr is None or sr <= 0:
            continue
        dp_int = _STAGE_DP[key]
        ruler.append((float(sr), dp_int))

    if len(ruler) < 2:
        return None

    # Enforce strict monotonicity
    ruler.sort(key=lambda x: x[1])
    for i in range(1, len(ruler)):
        if ruler[i][0] <= ruler[i - 1][0]:
            ruler[i] = (ruler[i - 1][0] + 0.001, ruler[i][1])

    _ruler_caches[family_key] = ruler

    # Pre-compute midpoint boundaries
    means = [sr for sr, _ in ruler]
    n = len(means)
    boundaries: list[tuple[float, float, int]] = []
    for i in range(n):
        lower = (means[i - 1] + means[i]) / 2.0 if i > 0 else means[0] - ((means[1] - means[0]) / 2.0 if n > 1 else 1.0)
        upper = (means[i] + means[i + 1]) / 2.0 if i < n - 1 else means[-1] + ((means[-1] - means[-2]) / 2.0 if n > 1 else 1.0)
        boundaries.append((lower, upper, ruler[i][1]))
    _boundary_caches[family_key] = boundaries

    return ruler


# ── SR → dp_ln ────────────────────────────────────────────────────────────────

def _sr_to_dp(sr: float, family_key: str = "global") -> float | None:
    """Convert SR → dp_ln (1.0–16.0+) via boundary interpolation.

    Each stage occupies dp_int ∈ [1, 16].  The fractional part t ∈ [0, 1)
    indicates position within that stage:  t=0 at the lower boundary,
    t just below 1 at the upper boundary.
    """
    ruler = _build_sr_ruler(family_key)
    if not ruler:
        return None

    boundaries = _boundary_caches.get(family_key)
    if not boundaries:
        return None

    # Below first boundary
    if sr < boundaries[0][0]:
        return max(0.5, float(boundaries[0][2]))

    # Above last boundary
    if sr >= boundaries[-1][1]:
        return min(16.99, float(boundaries[-1][2]) + 0.99)

    # Within range — find containing boundary slot
    for low_sr, high_sr, dp_int in boundaries:
        if low_sr <= sr < high_sr:
            width = max(high_sr - low_sr, 1e-6)
            t = (sr - low_sr) / width
            return float(dp_int) + t

    return None


def _dp_to_stage_key(dp: float) -> str:
    """Map a dp float (1.0-16.0+) to the stage key.

    math.floor ensures the stage matches the integer part of dp:
      dp ∈ [1.0, 2.0) → stage index 0 (1st)
      dp ∈ [2.0, 3.0) → stage index 1 (2nd)
      ...
    """
    idx = min(int(dp) - 1, len(STAGE_KEYS) - 1)
    idx = max(0, idx)
    return STAGE_KEYS[idx]


# ── OLS regression estimator ───────────────────────────────────────────────────

def _dp_from_regression(dp_sr: float, features: dict) -> float | None:
    """Apply the OLS regression model stored in profiles.

    dp = w_sr*dp_sr + w_ho*hold_occupancy + w_sh*simultaneous_hold
       + w_rd*release_density + w_cv*ln_duration_cv + bias
    """
    profiles = _load_profiles()
    if not profiles:
        return None
    reg = profiles.get("regression")
    if not reg:
        return None

    coefs   = reg.get("coefs", [])
    forder  = reg.get("feature_order", [])
    if not coefs or not forder or len(coefs) != len(forder):
        return None

    hold_occ = float(features.get("hold_occupancy", 0) or 0)
    feat_vals: dict[str, float] = {
        "dp_sr":              float(dp_sr),
        "hold_occupancy":     hold_occ,
        "simultaneous_hold":  float(features.get("simultaneous_hold", 0) or 0),
        "release_density":    float(features.get("release_density",   0) or 0),
        "ln_duration_cv":     float(features.get("ln_duration_cv",    0) or 0),
        "dp_sr_x_hold_occ":   float(dp_sr) * hold_occ,
        "bias":               1.0,
    }
    result = sum(coefs[i] * feat_vals.get(forder[i], 0.0) for i in range(len(coefs)))
    return float(result)


# ── MSD fallback ───────────────────────────────────────────────────────────────

def _estimate_from_msd(skillsets: dict, family_key: str = "global") -> float | None:
    """Flat MSD distance fallback when SR is unavailable."""
    profiles = _load_profiles()
    if not profiles:
        return None

    family_data = profiles.get(family_key) or profiles.get("global")
    if not family_data:
        return None

    vals = [float(skillsets.get(k, 0.0) or 0.0) for k in SKILLSET_KEYS]
    if not vals or max(vals) < 1.0:
        return None
    overall = max(vals)

    msd_ruler: list[tuple[float, int]] = []
    for key in STAGE_KEYS:
        slot = family_data.get(key, {})
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
class LnCourseResult:
    stage_key:    str    # "1st", "2nd", ..., "Yokaze"
    label:        str    # "1st Dan", ..., "夜風 Yokaze"
    short:        str    # "1", ..., "風"
    confidence:   float
    dp_ln:        float
    ln_family:    str    # "allround", "jack_technical", "inverse", "speed_density"
    ln_family_label: str # "All-round LN", ...
    beyond:       bool = False  # True when SR exceeds Yokaze ceiling

    def to_dict(self) -> dict:
        return {
            "stage_key":       self.stage_key,
            "label":           self.label,
            "short":           self.short,
            "confidence":      round(self.confidence, 4),
            "dp_ln":           round(self.dp_ln, 3),
            "ln_family":       self.ln_family,
            "ln_family_label": self.ln_family_label,
            "beyond":          self.beyond,
        }


# ── Public API ─────────────────────────────────────────────────────────────────

def estimate(
    skillsets: dict,
    sr: float | None = None,
    ln_family: str = "allround",
    features: dict | None = None,
) -> LnCourseResult | None:
    """Estimate LN Course stage from MSD skillsets and optional SR.

    Parameters
    ----------
    skillsets : dict
        MinaCalc skillset values.
    sr : float | None
        Primary SR from the Sunny engine.
    ln_family : str
        Detected LN subfamily key.
    features : dict | None
        Structural features (reserved for future family-aware adjustments).

    Returns
    -------
    LnCourseResult | None
    """
    family_key = ln_family if ln_family in LN_FAMILIES else "allround"
    dp: float | None = None

    # Primary path: SR ruler → dp_sr, then OLS regression correction
    if sr is not None and sr > 0.0:
        dp_sr_raw = _sr_to_dp(sr, "global")
        if dp_sr_raw is not None and features is not None:
            dp = _dp_from_regression(dp_sr_raw, features)
            if dp is not None:
                dp = max(1.0, min(16.99, dp))
        if dp is None:
            dp = dp_sr_raw

    # Fallback: MSD distance
    if dp is None and skillsets:
        dp = _estimate_from_msd(skillsets, "global")

    if dp is None:
        return None

    beyond = dp > 16.99
    dp = max(1.0, dp)

    stage_key  = _dp_to_stage_key(dp)
    label      = _STAGE_DISPLAY[stage_key]
    short      = _STAGE_SHORT[stage_key]
    confidence = _confidence_from_dp_frac(dp)
    family_label = _LN_FAMILY_DISPLAY.get(family_key, "LN")

    return LnCourseResult(
        stage_key=stage_key,
        label=label,
        short=short,
        confidence=confidence,
        dp_ln=round(dp, 3),
        ln_family=family_key,
        ln_family_label=family_label,
        beyond=beyond,
    )
