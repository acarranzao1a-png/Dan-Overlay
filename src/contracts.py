# contracts.py — Canonical data contracts for the overlay runtime.
# Every module that produces or consumes analysis results uses these types.
# All types are JSON-serializable via .to_dict().

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from celestial_estimator import CelestialResult

# ── Overlay states ──────────────────────────────────────────────────────
# Used by the UI to know what to render at any moment.

STATE_IDLE = "idle"                  # no map loaded yet
STATE_WAITING_TOSU = "waiting_tosu"  # tosu not reachable
STATE_ANALYZING = "analyzing"        # computation in progress
STATE_READY = "ready"                # result available, normal confidence
STATE_WARNING = "warning"            # result available, low confidence / caveats
STATE_ERROR = "error"                # computation failed

# Confidence threshold below which the overlay shows a range, not a point.
RANGE_CONFIDENCE_THRESHOLD = 0.50

# ── Dan label table (mirrors anchors.json dan_order) ───────────────────

DAN_ORDER = [
    "1st", "2nd", "3rd", "4th", "5th",
    "6th", "7th", "8th", "9th", "10th",
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon",
    "Zeta", "Eta", "Theta", "Iota", "Kappa",
]


def _dp_to_short(dp):
    """DP float → short label string."""
    idx = max(0, min(len(DAN_ORDER) - 1, int(dp) - 1))
    return DAN_ORDER[idx]


def _compute_dan_range(dp, confidence):
    """When confidence is low, return a two-label range string or None."""
    if confidence >= RANGE_CONFIDENCE_THRESHOLD:
        return None
    # Uncertainty band widens as confidence drops
    spread = (1.0 - confidence) * 1.5  # at conf=0 → ±1.5 dp
    lo = max(0.5, dp - spread)
    hi = min(20.5, dp + spread)
    label_lo = _dp_to_short(lo)
    label_hi = _dp_to_short(hi)
    if label_lo == label_hi:
        return None
    return f"{label_lo}–{label_hi}"


# ── MapInfo ─────────────────────────────────────────────────────────────

@dataclass
class MapInfo:
    """Metadata about the currently selected beatmap from tosu."""
    md5: str
    path: str                # full path to .osu file
    artist: str = ""
    title: str = ""
    version: str = ""
    mapper: str = ""
    sr_official: float = 0.0
    keycount: int = 4
    mod_speed: float = 1.0
    mod_label: str = ""      # "" | "DT" | "NC" | "HT"
    bg_path: str = ""        # full path to background image file

    # Live playback info (updated every poll)
    music_time_ms: int = 0
    music_playing: bool = False
    total_time_ms: int = 0
    game_state: int = 0

    def to_dict(self):
        return {
            "md5": self.md5,
            "path": self.path,
            "artist": self.artist,
            "title": self.title,
            "version": self.version,
            "mapper": self.mapper,
            "sr_official": self.sr_official,
            "keycount": self.keycount,
            "mod_speed": self.mod_speed,
            "mod_label": self.mod_label,
        }


# ── AnalysisResult ──────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    """Structured output from one analysis pass.

    The UI bridge serialises this to JSON and sends it to overlay.js
    as a single ``type: "analysis"`` payload.  No string parsing needed.
    """
    state: str                         # STATE_READY | STATE_WARNING
    dp: float = 0.0
    dan_label: str = ""
    dan_short: str = ""
    sublevel: str = ""
    confidence: float = 1.0
    dan_range: Optional[str] = None    # "Alpha–Beta" when low confidence
    sr: float = 0.0                    # overall_msd, exposed as "sr" for JS compat
    family: str = ""
    mod: str = ""
    corrections: list = field(default_factory=list)
    nps: float = 0.0
    peak_nps: float = 0.0
    nps_curve: list = field(default_factory=list)
    duration_s: float = 0.0
    note_count: int = 0
    warnings: list = field(default_factory=list)
    error: Optional[str] = None
    debug: dict = field(default_factory=dict)
    
    # ── Role-based fields (MinaCalc path) ──────────────────────────
    overall_msd: float = 0.0
    primary_role: str = ""
    role_estimates: dict = field(default_factory=dict)
    skillsets: dict = field(default_factory=dict)
    composite_dan: str = ""
    bottleneck_role: str = ""
    is_generalist: bool = False
    role_breakdown_text: str = ""

    # ── Celestial mode estimate ────────────────────────────────────
    celestial: Optional[dict] = None   # CelestialResult.to_dict() or None

    # ── Signicial mode estimate ───────────────────────────────────
    signicial: Optional[dict] = None   # SignicialResult.to_dict() or None

    # ── Shoegazer mode estimate ───────────────────────────────────
    shoegazer: Optional[dict] = None   # ShoegazerResult.to_dict() or None

    # ── LN Course mode estimate ───────────────────────────────────
    ln_course: Optional[dict] = None   # LnCourseResult.to_dict() or None
    ln_route: str = "rice"              # "rice" | "hybrid" | "ln"

    # ── Strain graph for ui-3 density display ──────────────────────
    strain_graph: Optional[dict] = None  # {"values": [float], "times": [float]}

    # ── Map-level stats (from .osu file) ────────────────────────
    bpm: float = 0.0
    bpm_min: int = 0
    bpm_max: int = 0
    bpm_common: int = 0
    osu_sr: float = 0.0    # official osu! star rating from tosu
    od: float = 0.0
    # ── 7K support fields ──────────────────────────────────────
    mode_7k: bool = False
    tier_7k: str = ""
    sublevel_7k: str = ""
    dp_7k: float = 0.0

    def to_dict(self):
        return {
            "type": "analysis",
            "state": self.state,
            "mode": "7k" if self.mode_7k else "",
            "tier_7k": self.tier_7k,
            "sublevel_7k": self.sublevel_7k,
            "dp_7k": round(self.dp_7k, 2),
            "dp": round(self.dp, 3),
            "dan_label": self.dan_label,
            "dan_short": self.dan_short,
            "sublevel": self.sublevel,
            "confidence": round(self.confidence, 3),
            "dan_range": self.dan_range,
            "sr": round(self.sr, 3),
            "family": self.family,
            "mod": self.mod,
            "corrections": self.corrections,
            "nps": round(self.nps, 1),
            "peak_nps": round(self.peak_nps, 1),
            "nps_curve": self.nps_curve,
            "duration_s": round(self.duration_s, 1),
            "note_count": self.note_count,
            "warnings": self.warnings,
            # Role-based extras (MinaCalc path)
            "overall_msd": round(self.overall_msd, 3),
            "primary_role": self.primary_role,
            "role_estimates": self.role_estimates,
            "skillsets": self.skillsets,
            "composite_dan": self.composite_dan,
            "bottleneck_role": self.bottleneck_role,
            "is_generalist": self.is_generalist,
            "role_breakdown": self.role_breakdown_text,
            "celestial": self.celestial,
            "signicial": self.signicial,
            "shoegazer": self.shoegazer,
            "ln_course": self.ln_course,
            "ln_route": self.ln_route,
            "strain_graph": self.strain_graph,
            "bpm": round(self.bpm, 1),
            "bpm_min": self.bpm_min,
            "bpm_max": self.bpm_max,
            "bpm_common": self.bpm_common,
            "osu_sr": round(self.osu_sr, 2),
            "od": round(self.od, 1),
        }

    @staticmethod
    def from_pipeline(raw, mod_label=""):
        """Build an AnalysisResult from pipeline.analyze_map() output."""
        if raw.get("error") and raw.get("dp") is None:
            return AnalysisResult(
                state=STATE_ERROR,
                error=str(raw["error"]),
                warnings=raw.get("warnings", []),
            )

        dp = float(raw.get("dp", 0) or 0)
        confidence = float(raw.get("confidence", 0) or 0)
        warnings = list(raw.get("warnings", []))

        if raw.get("error"):
            warnings.append(str(raw["error"]))

        state = STATE_WARNING if confidence < RANGE_CONFIDENCE_THRESHOLD else STATE_READY
        dan_range = _compute_dan_range(dp, confidence)

        overall_msd = float(raw.get("overall_msd", 0) or 0)
        sr_value = float(raw.get("sr", 0) or 0)
        duration_s = float(raw.get("duration_s", 0) or 0)
        note_count = int(raw.get("note_count", 0) or 0)
        # Average NPS proxy: total notes / drain time (MinaCalc has no per-interval NPS)
        avg_nps = (note_count / duration_s) if duration_s > 0 else 0.0
        peak_nps = float(raw.get("peak_nps", 0) or 0)

        return AnalysisResult(
            state=state,
            dp=dp,
            dan_label=raw.get("dan_label", ""),
            dan_short=raw.get("dan_short", ""),
            sublevel=raw.get("sublevel", ""),
            confidence=confidence,
            dan_range=dan_range,
            sr=sr_value or overall_msd,
            family=raw.get("family", ""),
            mod=mod_label,
            corrections=raw.get("corrections", []),
            nps=avg_nps,
            peak_nps=peak_nps,
            nps_curve=list(raw.get("nps_curve") or []),
            duration_s=duration_s,
            note_count=note_count,
            warnings=warnings,
            debug=raw.get("debug", {}),
            overall_msd=overall_msd,
            primary_role=str(raw.get("primary_role", "") or ""),
            role_estimates=dict(raw.get("role_estimates", {}) or {}),
            skillsets=dict(raw.get("skillsets", {}) or {}),
            composite_dan=str(raw.get("composite_dan", "") or ""),
            bottleneck_role=str(raw.get("bottleneck_role", "") or ""),
            is_generalist=bool(raw.get("is_generalist", False)),
            role_breakdown_text=str(raw.get("role_breakdown_text", "") or ""),
            celestial=raw.get("celestial"),
            signicial=raw.get("signicial"),
            shoegazer=raw.get("shoegazer"),
            ln_course=raw.get("ln_course"),
            ln_route=str(raw.get("ln_route", "rice") or "rice"),
            strain_graph=raw.get("strain_graph"),
            bpm=float(raw.get("bpm", 0) or 0),
            bpm_min=int(raw.get("bpm_min", 0) or 0),
            bpm_max=int(raw.get("bpm_max", 0) or 0),
            bpm_common=int(raw.get("bpm_common", 0) or 0),
            osu_sr=float(raw.get("osu_sr", 0) or 0),
            od=float(raw.get("od", 0) or 0),
            mode_7k=(raw.get("mode") == "7k"),
            tier_7k=str(raw.get("tier_7k", "") or ""),
            sublevel_7k=str(raw.get("sublevel_7k", "") or ""),
            dp_7k=float(raw.get("dp_7k", 0) or 0),
        )
