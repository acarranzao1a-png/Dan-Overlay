"""signicial_estimator.py — Dan Signicial stage estimator.

Architecture (mirrors rank_engine.py Reform + celestial_estimator.py):
    SR (primary engine) + Signicial SR means per stage
    → boundary interpolation → dp_signicial (1.0–16.0) → stage

Stage order (weakest → strongest):
    I, II, III, IV, V, VI, VII, VIII, IX, X,   ← Roman numeral stages (Prelude–Finale)
    XI (Alpha), XII (Beta), XIII (Gamma), XIV (Delta),
    LastStage (Epsilon), ExtraStageI (Zeta)

dp_signicial: 1.0 (Stage I) → 16.0 (Zeta)

Profile JSON shape (produced by _calibrate_signicial.py):
{
  "I": {
    "sr_mean":     float,   ← primary input for the ruler
    "sr_lower":    float,
    "sr_upper":    float,
    "sr_by_type": { "jack": float|null, ... },
    "overall_msd": float,
    "map_count":   int
  },
  ...
  "ExtraStageI": { ... }
}
"""

import json
import os
import sys
from dataclasses import dataclass

if getattr(sys, "frozen", False):
    _PROFILES_PATH = os.path.join(sys._MEIPASS, "config", "signicial_profiles.json")
else:
    _ROOT = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    _PROFILES_PATH = os.path.join(_ROOT, "config", "signicial_profiles.json")

# Ordered stage keys (index 0 → dp 1.0, index 15 → dp 16.0)
STAGE_KEYS: list[str] = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "LastStage", "ExtraStageI",
    "ExtraStageII", "ExtraStageIII",
]

# Human-readable labels for each stage key
_STAGE_DISPLAY: dict[str, str] = {
    "I":           "Stage I",
    "II":          "Stage II",
    "III":         "Stage III",
    "IV":          "Stage IV",
    "V":           "Stage V",
    "VI":          "Stage VI",
    "VII":         "Stage VII",
    "VIII":        "Stage VIII",
    "IX":          "Stage IX",
    "X":           "Stage X",
    "XI":          "Alpha",
    "XII":         "Beta",
    "XIII":        "Gamma",
    "XIV":         "Delta",
    "LastStage":   "Epsilon",
    "ExtraStageI": "Zeta",
    "ExtraStageII": "Eta",
    "ExtraStageIII": "Theta",
}

# Short tags used for display
_STAGE_SHORT: dict[str, str] = {
    "I":           "I",
    "II":          "II",
    "III":         "III",
    "IV":          "IV",
    "V":           "V",
    "VI":          "VI",
    "VII":         "VII",
    "VIII":        "VIII",
    "IX":          "IX",
    "X":           "X",
    "XI":          "α",
    "XII":         "β",
    "XIII":        "γ",
    "XIV":         "δ",
    "LastStage":   "ε",
    "ExtraStageI": "ζ",
    "ExtraStageII": "η",
    "ExtraStageIII": "θ",
}

# Stage subtitle (used as danSuffix in the overlay for stages I-X)
STAGE_SUBTITLE: dict[str, str] = {
    "I":    "Prelude",
    "II":   "Abnormality",
    "III":  "Termination",
    "IV":   "Resuscitation",
    "V":    "Disturbance",
    "VI":   "Revitalization",
    "VII":  "Motivation",
    "VIII": "Misfortune",
    "IX":   "Catastrophe",
    "X":    "Finale",
}

SKILLSET_KEYS = [
    "stream", "jumpstream", "handstream",
    "stamina", "jackspeed", "chordjack", "technical",
]

_STAGE_DP: dict[str, int] = {key: i + 1 for i, key in enumerate(STAGE_KEYS)}

_profiles: dict | None = None
_ruler_caches: dict[str | None, list | None] = {}       # chart_type → [(sr, dp_int), ...]
_boundaries_caches: dict[str | None, list | None] = {}   # chart_type → [(lo_sr, hi_sr, dp_int), ...]

# Family hint → type ruler key (None = general ruler)
_FAMILY_TO_TYPE: dict[str, str | None] = {
    "jack": "jack", "speed": "speed", "stamina": "stamina", "tech": "tech",
    "stream": None, "hybrid": None,
}

# Shrinkage: blend type-specific SR toward general mean to avoid inversions
# from single-map stage-type cells.  1.0 = pure type, 0.0 = pure general.
_SHRINKAGE: float = 0.6


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

def _build_ruler(chart_type: str | None = None) -> list[tuple[float, int]] | None:
    """Build SR ruler from profiles.

    When chart_type is provided (e.g. "jack"), uses sr_by_type for that type,
    falling back to sr_mean for stages where the type value is missing.
    When chart_type is None, uses the general sr_mean.

    Returns sorted list of (sr_mean, dp_int) where dp_int is 1-16, or None.
    """
    if chart_type in _ruler_caches:
        return _ruler_caches[chart_type]

    profiles = _load_profiles()
    if not profiles:
        return None

    # For type rulers, need the general ruler as fallback per stage
    general = _build_ruler(None) if chart_type is not None else None
    general_map = {dp: sr for sr, dp in (general or [])}

    ruler: list[tuple[float, int]] = []
    for key in STAGE_KEYS:
        slot = profiles.get(key)
        if not slot:
            continue
        dp_int = _STAGE_DP[key]

        if chart_type is None:
            sr = slot.get("sr_mean")
        else:
            type_sr = (slot.get("sr_by_type") or {}).get(chart_type)
            gen_sr = general_map.get(dp_int)
            if type_sr is not None and gen_sr is not None:
                sr = _SHRINKAGE * float(type_sr) + (1.0 - _SHRINKAGE) * gen_sr
            elif type_sr is not None:
                sr = type_sr
            else:
                sr = gen_sr

        if sr is None or float(sr) <= 0:
            continue
        ruler.append((float(sr), dp_int))

    if len(ruler) < 2:
        _ruler_caches[chart_type] = None
        _boundaries_caches[chart_type] = None
        return None

    # Enforce strict monotonicity (fix calibration rounding artifacts)
    ruler.sort(key=lambda x: x[1])
    for i in range(1, len(ruler)):
        if ruler[i][0] <= ruler[i - 1][0]:
            ruler[i] = (ruler[i - 1][0] + 0.001, ruler[i][1])

    # Pre-compute midpoint boundaries (identical to celestial_estimator)
    means = [sr for sr, _ in ruler]
    n = len(means)
    boundaries: list[tuple[float, float, int]] = []
    for i in range(n):
        lower = (means[i - 1] + means[i]) / 2.0 if i > 0 else means[0] - ((means[1] - means[0]) / 2.0 if n > 1 else 1.0)
        upper = (means[i] + means[i + 1]) / 2.0 if i < n - 1 else means[-1] + ((means[-1] - means[-2]) / 2.0 if n > 1 else 1.0)
        boundaries.append((lower, upper, ruler[i][1]))

    _ruler_caches[chart_type] = ruler
    _boundaries_caches[chart_type] = boundaries
    return ruler


# ── SR → dp_signicial ─────────────────────────────────────────────────────────

def _sr_to_dp_signicial(sr: float, chart_type: str | None = None) -> float | None:
    """Convert SR → dp_signicial (1.0–18.0+) via boundary interpolation.

    Uses chart_type-specific ruler when available, general otherwise.
    Identical logic to rank_engine.py's sr_to_dp.
    """
    resolved_type = chart_type
    ruler = _build_ruler(resolved_type)
    if ruler is None and resolved_type is not None:
        resolved_type = None
        ruler = _build_ruler(None)
    if ruler is None:
        return None

    boundaries = _boundaries_caches.get(resolved_type)
    if not boundaries:
        return None

    # Below first boundary
    if sr < boundaries[0][0]:
        return max(0.5, float(boundaries[0][2]))

    # Above last boundary — cap at max stage count
    if sr >= boundaries[-1][1]:
        return min(18.99, float(boundaries[-1][2]) + 0.99)

    # Within range — find containing boundary slot
    for low_sr, high_sr, dp_int in boundaries:
        if low_sr <= sr < high_sr:
            width = max(high_sr - low_sr, 1e-6)
            t = (sr - low_sr) / width
            return float(dp_int) + t

    return None


def _dp_to_stage_key(dp: float) -> str:
    """Map a dp_signicial float (1.0-18.0+) to the stage key."""
    import math
    idx = min(math.floor(dp) - 1, len(STAGE_KEYS) - 1)
    idx = max(0, idx)
    return STAGE_KEYS[idx]


# ── MSD fallback ───────────────────────────────────────────────────────────────

def _estimate_from_msd(skillsets: dict) -> float | None:
    """Flat MSD distance fallback when SR is unavailable.

    Computes overall MSD from skillsets and maps through stage means stored
    in the profiles.
    """
    profiles = _load_profiles()
    if not profiles:
        return None

    vals = [float(skillsets.get(k, 0.0) or 0.0) for k in SKILLSET_KEYS]
    if not vals or max(vals) < 1.0:
        return None
    overall = max(vals)

    # Build per-stage overall_msd list
    msd_ruler: list[tuple[float, int]] = []
    for key in STAGE_KEYS:
        slot = profiles.get(key, {})
        msd_val = slot.get("overall_msd")
        if msd_val:
            msd_ruler.append((float(msd_val), _STAGE_DP[key]))

    if len(msd_ruler) < 2:
        return None

    # Clamp to ruler range
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
    """Confidence 0-1 based on how centred dp is within its stage slot.

    1.0 = exactly at slot centre (e.g. dp=1.5)
    0.0 = at the boundary between two stages.
    """
    import math
    frac = dp - int(dp)  # 0.0 = lower boundary, 1.0 = upper boundary
    # Distance from nearest boundary: 0.5 = centre (max conf), 0.0/1.0 = boundary (min)
    dist = abs(frac - 0.5)
    # cosine-smoothed: 1 at centre, 0 at boundary
    conf = 0.5 * (1.0 + math.cos(math.pi * dist / 0.5))
    return max(0.0, min(1.0, conf))


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class SignicialResult:
    stage_key:    str    # "I", "II", ..., "ExtraStageI"
    label:        str    # "Stage I", ..., "Alpha", ..., "Zeta"
    short:        str    # "I", ..., "X", "α", ..., "ζ"
    subtitle:     str    # "Prelude" etc. for I-X, "" for Alpha-Zeta
    confidence:   float
    dp_signicial: float
    beyond:       bool = False  # True when SR exceeds Zeta ceiling

    def to_dict(self) -> dict:
        return {
            "stage_key":    self.stage_key,
            "label":        self.label,
            "short":        self.short,
            "subtitle":     self.subtitle,
            "confidence":   round(self.confidence, 4),
            "dp_signicial": round(self.dp_signicial, 3),
            "beyond":       self.beyond,
        }


# ── Public API ─────────────────────────────────────────────────────────────────

def estimate(skillsets: dict, sr: float | None = None,
             family_hint: str | None = None) -> SignicialResult | None:
    """Estimate Signicial stage from MSD skillsets and optional SR.

    Parameters
    ----------
    skillsets : dict
        MinaCalc skillset values (stream, jumpstream, handstream,
        stamina, jackspeed, chordjack, technical).
    sr : float | None
        Primary SR from the Sunny engine.  When provided, the SR ruler is
        used as the primary estimation path.  Falls back to MSD distance
        when sr is None or the ruler is unavailable.
    family_hint : str | None
        Chart family from classifier ("jack", "speed", "stamina", "tech",
        "stream", "hybrid").  When a type-specific ruler exists, the hint
        selects it; otherwise falls back to the general ruler.

    Returns
    -------
    SignicialResult | None
    """
    dp: float | None = None
    chart_type = _FAMILY_TO_TYPE.get(family_hint) if family_hint else None

    # Primary path: SR ruler (type-specific when available)
    if sr is not None and sr > 0.0:
        dp = _sr_to_dp_signicial(sr, chart_type=chart_type)

    # Fallback: MSD distance
    if dp is None and skillsets:
        dp = _estimate_from_msd(skillsets)

    if dp is None:
        return None

    beyond = dp > 18.99
    dp = max(1.0, dp)

    stage_key   = _dp_to_stage_key(dp)
    label       = _STAGE_DISPLAY[stage_key]
    short       = _STAGE_SHORT[stage_key]
    subtitle    = STAGE_SUBTITLE.get(stage_key, "")
    confidence  = _confidence_from_dp_frac(dp)

    return SignicialResult(
        stage_key=stage_key,
        label=label,
        short=short,
        subtitle=subtitle,
        confidence=confidence,
        dp_signicial=round(dp, 3),
        beyond=beyond,
    )
