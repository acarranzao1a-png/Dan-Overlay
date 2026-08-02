# events.py — Minimal thread-safe event bus.
# All overlay runtime communication goes through string-typed events.
# No module needs to import another module just to emit or subscribe.

import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Event names (string constants to avoid typos) ───────────────────────

TOSU_STATUS = "tosu_status"              # {"connected": bool}
MAP_CHANGED = "map_changed"              # MapInfo
MUSIC_TIME = "music_time"                # {"ms": int, "wall": float, "playing": bool, "speed": float}
ANALYSIS_STARTED = "analysis_started"    # {"md5": str}
ANALYSIS_COMPLETE = "analysis_complete"  # AnalysisResult
ANALYSIS_ERROR = "analysis_error"        # {"md5": str, "error": str}
AUDIO_BANDS = "audio_bands"              # {"bands": list[float], "active": bool}
NOTIFICATION = "notification"            # {"message": str}
OVERLAY_STATE = "overlay_state"          # {"state": str, "message": str}


class EventBus:
    """Thread-safe publish/subscribe bus for overlay runtime events."""

    def __init__(self):
        self._subs = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type, callback):
        """Register *callback* to be called when *event_type* is emitted."""
        with self._lock:
            self._subs[event_type].append(callback)

    def emit(self, event_type, data=None):
        """Emit an event.  Callbacks run in the emitter's thread."""
        with self._lock:
            callbacks = list(self._subs.get(event_type, []))
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                logger.exception("EventBus callback error on %s", event_type)

    def shutdown(self):
        """Clear all subscriptions."""
        with self._lock:
            self._subs.clear()
