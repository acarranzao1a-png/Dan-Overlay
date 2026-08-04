"""celestial_estimator.py — Dan Celestial tier+category estimator.

Architecture (mirrors rank_engine.py Reform):
    SR (primary engine) + celestial SR means per slot
    → boundary interpolation → dp_celestial (1.0–35.0) → (tier, category)

    MSD skillsets are retained as a fallback when SR is unavailable.

Profile JSON shape (produced by _calibrate_celestial.py):
{
  "Beginner": {
    "I": {
      "sr_mean":  float,   ← primary input for the ruler
      "sr_lower": float,
      "sr_upper": float,
      "overall_msd": float,
      "skillsets": {...},
      "map_count": int
    },
    ...
  },
  ...
}

Tier order (weakest → strongest):
    Beginner, Intermediate, Expert, Mastery, Ascension, Transcendence, Singularity

Categories per tier: I < II < III < IV < V
dp_celestial: 1.0 (Beginner I) → 35.0 (Singularity V)
"""

import json
import math
import os
import sys
from dataclasses import dataclass

if getattr(sys, "frozen", False):
    _PROFILES_PATH = os.path.join(sys._MEIPASS, "config", "celestial_profiles.json")
else:
    _ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    _PROFILES_PATH = os.path.join(_ROOT, "config", "celestial_profiles.json")

TIERS      = ["Beginner", "Intermediate", "Expert", "Mastery", "Ascension", "Transcendence", "Singularity"]
CATEGORIES = ["I", "II", "III", "IV", "V"]

_TIER_SHORT = {
    "Beginner":      "B",
    "Intermediate":  "Int",
    "Expert":        "E",
    "Mastery":       "M",
    "Ascension":     "A",
    "Transcendence": "T",
    "Singularity":   "S",
}

_CAT_TO_TIER = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}

# Ordered list of (tier, category) slots — index 0 = dp 1, index 34 = dp 35
_SLOTS: list[tuple[str, str]] = [(t, c) for t in TIERS for c in CATEGORIES]
_SLOT_INDEX: dict[tuple[str, str], int] = {slot: i + 1 for i, slot in enumerate(_SLOTS)}

SKILLSET_KEYS = ["stream", "jumpstream", "handstream",
                 "stamina", "jackspeed", "chordjack", "technical"]

_profiles: dict | None = None

# ── Ruler cache ────────────────────────────────────────────────────────────────

_ruler_caches: dict[str | None, list | None] = {}       # chart_type → [(sr, dp_int), ...]
_boundaries_caches: dict[str | None, list | None] = {}   # chart_type → [(lo_sr, hi_sr, dp_int), ...]

# Family hint → type ruler key (None = general ruler)
_FAMILY_TO_TYPE: dict[str, str | None] = {
    "jack": "jack", "speed": "speed", "stamina": "stamina", "tech": "tech",
    "stream": None, "hybrid": None,
}

# Shrinkage: blend type-specific SR toward general mean
# 1.0 = full type-specific (Celestial has uniform type coverage across all 35 slots)
_SHRINKAGE: float = 1.0


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


# ── SR ruler (mirrors rank_engine._get_ruler / _precompute_boundaries) ────────

def _build_ruler(chart_type: str | None = None) -> list[tuple[float, int]] | None:
    """Build 35-slot SR ruler from profiles.

    When chart_type is provided, uses sr_by_type for that type (with shrinkage
    toward the general mean), falling back to sr_mean where the type is absent.
    When chart_type is None, uses the general sr_mean.

    Returns list of (sr_mean, dp_int) sorted by dp (1–35), or None.
    """
    if chart_type in _ruler_caches:
        return _ruler_caches[chart_type]

    profiles = _load_profiles()
    if not profiles:
        return None

    # For type rulers, need the general ruler as fallback
    general = _build_ruler(None) if chart_type is not None else None
    general_map = {dp: sr for sr, dp in (general or [])}

    table: list[tuple[float, int]] = []
    for tier, cat in _SLOTS:
        slot = profiles.get(tier, {}).get(cat)
        dp_int = _SLOT_INDEX[(tier, cat)]

        if chart_type is None:
            if not slot or not slot.get("sr_mean"):
                _ruler_caches[chart_type] = None
                _boundaries_caches[chart_type] = None
                return None  # profiles lack SR data
            sr = float(slot["sr_mean"])
        else:
            type_sr = (slot.get("sr_by_type") or {}).get(chart_type) if slot else None
            gen_sr = general_map.get(dp_int)
            if type_sr is not None and gen_sr is not None:
                sr = _SHRINKAGE * float(type_sr) + (1.0 - _SHRINKAGE) * gen_sr
            elif type_sr is not None:
                sr = float(type_sr)
            elif gen_sr is not None:
                sr = gen_sr
            else:
                _ruler_caches[chart_type] = None
                _boundaries_caches[chart_type] = None
                return None

        table.append((sr, dp_int))

    # Enforce strict monotonicity
    for i in range(1, len(table)):
        if table[i][0] <= table[i - 1][0]:
            table[i] = (table[i - 1][0] + 0.001, table[i][1])

    # Precompute boundaries (midpoints between adjacent SR means)
    means = [sr for sr, _ in table]
    n = len(means)
    boundaries = []
    for i in range(n):
        lower = (means[i - 1] + means[i]) / 2.0 if i > 0 else means[0] - ((means[1] - means[0]) / 2.0 if n > 1 else 1.0)
        upper = (means[i] + means[i + 1]) / 2.0 if i < n - 1 else means[-1] + ((means[-1] - means[-2]) / 2.0 if n > 1 else 1.0)
        boundaries.append((lower, upper, table[i][1]))

    _ruler_caches[chart_type] = table
    _boundaries_caches[chart_type] = boundaries
    return table


def _sr_to_dp_celestial(sr: float, chart_type: str | None = None) -> float | None:
    """Convert primary SR → dp_celestial (1.0–35.0) via boundary interpolation.

    Uses chart_type-specific ruler when available, general otherwise.
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

    # Below first slot
    if sr < boundaries[0][0]:
        return max(0.5, float(boundaries[0][2]))

    # Above last slot
    if sr >= boundaries[-1][1]:
        return min(35.99, float(boundaries[-1][2]) + 0.99)

    # Within range — find the containing slot
    for low_sr, high_sr, dp_int in boundaries:
        if low_sr <= sr < high_sr:
            width = max(high_sr - low_sr, 1e-6)
            t = (sr - low_sr) / width
            return float(dp_int) + t

    return None


def _dp_to_slot(dp: float) -> tuple[str, str] | None:
    """Convert a dp_celestial value → (tier, category).

    int(dp) ensures the slot matches the integer part:
      dp ∈ [1.0, 2.0) → slot index 0 (Beginner I)
      dp ∈ [2.0, 3.0) → slot index 1 (Beginner II)
      ...
    """
    idx = max(0, min(34, int(dp) - 1))
    return _SLOTS[idx]


def _confidence_from_frac(frac: float) -> float:
    """Confidence from fractional position within slot boundary.

    frac=0.0 → at lower boundary (edge) → ~0.5 conf
    frac=0.5 → at center of slot → 1.0 conf
    frac=1.0 → at upper boundary (edge) → ~0.5 conf

    Uses a raised cosine so the center is clearly more confident.
    """
    # Map [0, 1] → center at 0.5 → confidence 1.0 at center, ~0.5 at edges
    conf = 0.5 * (1.0 + math.cos(math.pi * (frac - 0.5) * 2.0))
    return round(max(0.1, min(1.0, conf)), 3)


# ── MSD distance fallback (original algorithm, kept for SR-less profiles) ─────

def _weighted_distance(msd: dict, profile: dict) -> float:
    """Weighted RMS distance: map MSD vs profile slot (MSD-based fallback)."""
    prof_skillsets = profile.get("skillsets", {})
    prof_overall   = float(profile.get("overall_msd", 0.0) or 0.0)
    if prof_overall <= 0.0:
        return float("inf")

    map_overall = max((float(msd.get(k, 0.0) or 0.0) for k in SKILLSET_KEYS), default=0.0)
    overall_dist = (map_overall - prof_overall) ** 2 * 4.0

    skill_dist = 0.0
    total_weight = 0.0
    for k in SKILLSET_KEYS:
        pv = float(prof_skillsets.get(k, 0.0) or 0.0)
        mv = float(msd.get(k, 0.0) or 0.0)
        w = pv / max(prof_overall, 0.001)
        skill_dist += w * (mv - pv) ** 2
        total_weight += w
    if total_weight > 0:
        skill_dist /= total_weight

    return math.sqrt(max(0.0, overall_dist + skill_dist))


def _confidence_from_distance(dist: float, bandwidth: float) -> float:
    if bandwidth <= 0.001:
        bandwidth = 1.0
    conf = math.exp(-(dist / max(bandwidth, 0.001)) ** 2)
    return round(max(0.0, min(1.0, conf)), 3)


def _estimate_msd_fallback(msd: dict) -> "CelestialResult | None":
    """Original MSD distance-matching fallback — used when SR is unavailable."""
    profiles = _load_profiles()
    if not profiles:
        return None

    map_overall = max((float(msd.get(k, 0.0) or 0.0) for k in SKILLSET_KEYS), default=0.0)
    if map_overall < 0.5:
        return None

    best_slot = None
    best_dist = float("inf")

    for tier in TIERS:
        tier_data = profiles.get(tier, {})
        for cat in CATEGORIES:
            slot = tier_data.get(cat)
            if slot is None:
                continue
            dist = _weighted_distance(msd, slot)
            if dist < best_dist:
                best_dist = dist
                best_slot = (tier, cat, slot)

    if best_slot is None:
        return None

    tier, cat, slot = best_slot
    bandwidth = float(slot.get("upper", 0.0)) - float(slot.get("lower", 0.0))
    conf = _confidence_from_distance(best_dist, bandwidth)

    # Fractional DP from MSD
    prof_overall = float(slot.get("overall_msd", 0.0) or 0.0)
    dp = float(_SLOT_INDEX.get((tier, cat), 1))
    if prof_overall > 0.0:
        bw = float(slot.get("upper", prof_overall)) - float(slot.get("lower", prof_overall))
        diff = (max((float(msd.get(k, 0.0) or 0.0) for k in SKILLSET_KEYS), default=0.0) - prof_overall) / max(bw, 0.001)
        dp += max(-0.5, min(0.5, diff * 0.5))

    short = f"{_TIER_SHORT[tier]}-{cat}"
    label = f"{tier} {cat}"
    return CelestialResult(tier=tier, category=cat, short_label=short,
                           label=label, confidence=conf, dp_celestial=round(dp, 3))


# ── Public dataclass ───────────────────────────────────────────────────────────

@dataclass
class CelestialResult:
    tier: str            # e.g. "Expert"
    category: str        # e.g. "II"
    short_label: str     # e.g. "E-II"
    label: str           # e.g. "Expert II"
    confidence: float    # 0.0–1.0
    dp_celestial: float  # 1.0–35.0 (continuous)
    beyond: bool = False  # True when SR exceeds Singularity V ceiling

    def to_dict(self) -> dict:
        return {
            "tier":          self.tier,
            "category":      self.category,
            "short":         self.short_label,
            "label":         self.label,
            "confidence":    round(self.confidence, 3),
            "dp_celestial":  round(self.dp_celestial, 3),
            "beyond":        self.beyond,
        }


# ── Main estimate function ──────────────────────────────────────────────────────

def fields_from_dp(dp: float) -> dict:
    """Re-derive Celestial result fields from a ``dp_celestial`` value.

    Used by the pipeline's custom-rate interpolation: after the DP is
    interpolated between native rates, the tier/category/label fields
    must be refreshed — they would otherwise keep the NM-rate values.
    """
    beyond = dp > 35.99
    dp_clamped = max(0.5, min(35.99, dp))
    slot = _dp_to_slot(dp_clamped)
    if slot is None:
        return {}
    tier, cat = slot
    return {
        "tier":         tier,
        "category":     cat,
        "short":        f"{_TIER_SHORT[tier]}-{cat}",
        "label":        f"{tier} {cat}",
        "dp_celestial": round(dp_clamped, 3),
        "beyond":       beyond,
    }


def estimate(skillsets: dict, sr: float | None = None,
             family_hint: str | None = None) -> "CelestialResult | None":
    """Estimate Dan Celestial tier + category.

    Primary path (when SR available):
        SR → boundary interpolation on 35-slot ruler → dp_celestial → (tier, category)
        Identical architecture to rank_engine.py Reform calculation.

    Fallback (when SR unavailable or profiles lack sr_mean):
        MinaCalc MSD skillsets → weighted-distance matching → (tier, category)

    Parameters
    ----------
    skillsets : dict
        MinaCalc MSD output — "stream", "jackspeed", "technical", etc.
        Always required (used as fallback and for map_overall display).
    sr : float or None
        Primary SR from the same engine used for Reform dans.
        When provided and profiles have sr_mean, SR path is used.
    family_hint : str | None
        Chart family from classifier.  When a type-specific ruler exists,
        the hint selects it; otherwise falls back to the general ruler.

    Returns
    -------
    CelestialResult or None.
    """
    msd = {k: float((skillsets or {}).get(k, 0.0) or 0.0) for k in SKILLSET_KEYS}
    chart_type = _FAMILY_TO_TYPE.get(family_hint) if family_hint else None

    # ── Primary: SR ruler path ─────────────────────────────────────────────────
    if sr is not None and sr > 0.0:
        ruler = _build_ruler(chart_type)
        if ruler is None and chart_type is not None:
            chart_type = None
            ruler = _build_ruler(None)
        if ruler is not None:
            dp_raw = _sr_to_dp_celestial(sr, chart_type=chart_type)
            if dp_raw is not None:
                beyond = dp_raw > 35.99
                dp_clamped = max(0.5, min(35.99, dp_raw))
                tier, cat = _dp_to_slot(dp_clamped)

                # Fractional position within the exact slot boundary for confidence
                resolved_type = chart_type if _ruler_caches.get(chart_type) is not None else None
                boundaries = _boundaries_caches.get(resolved_type, [])
                slot_dp = _SLOT_INDEX[(tier, cat)]
                if slot_dp - 1 < len(boundaries):
                    low_sr, high_sr, _ = boundaries[slot_dp - 1]
                    slot_width = max(high_sr - low_sr, 0.001)
                    frac = (sr - low_sr) / slot_width
                    conf = _confidence_from_frac(max(0.0, min(1.0, frac)))
                else:
                    conf = 0.5

                short = f"{_TIER_SHORT[tier]}-{cat}"
                label = f"{tier} {cat}"
                return CelestialResult(
                    tier=tier,
                    category=cat,
                    short_label=short,
                    label=label,
                    confidence=conf,
                    dp_celestial=round(dp_clamped, 3),
                    beyond=beyond,
                )

    # ── Fallback: MSD distance matching ───────────────────────────────────────
    return _estimate_msd_fallback(msd)
