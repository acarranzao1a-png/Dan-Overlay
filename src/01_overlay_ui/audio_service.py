# audio_service.py — Wraps AudioVisualizer to use the event bus instead of
# direct evaluate_js calls and shared state reads.

import logging
import threading
import time

from events import MAP_CHANGED, MUSIC_TIME, AUDIO_BANDS

logger = logging.getLogger(__name__)


class AudioService:
    """Bridges the existing AudioVisualizer to the event-driven runtime.

    Subscribes to MAP_CHANGED and MUSIC_TIME events to track the current
    beatmap and playback position.  Emits AUDIO_BANDS events instead of
    calling evaluate_js directly.
    """

    def __init__(self, event_bus, stop_event):
        self._bus = event_bus
        self._stop = stop_event

        # Shared state written by event callbacks, read by the viz loop
        self._state = {
            "music_md5": "",
            "music_time_ms": 0,
            "music_time_wall": 0,
            "music_playing": False,
            "mod_speed_actual": 1.0,
        }
        self._lock = threading.Lock()

        event_bus.subscribe(MAP_CHANGED, self._on_map_changed)
        event_bus.subscribe(MUSIC_TIME, self._on_music_time)

    def _on_map_changed(self, map_info):
        with self._lock:
            self._state["music_md5"] = map_info.md5
            self._state["music_playing"] = map_info.music_playing
            self._state["mod_speed_actual"] = map_info.mod_speed

    def _on_music_time(self, data):
        with self._lock:
            self._state["music_time_ms"] = data["ms"]
            self._state["music_time_wall"] = data["wall"]
            self._state["music_playing"] = data["playing"]
            self._state["mod_speed_actual"] = data["speed"]
            if data.get("md5"):
                self._state["music_md5"] = data["md5"]

    def run(self):
        """Main loop.  Runs in a daemon thread.

        Creates an AudioVisualizer internally and adapts its push method
        to emit events instead of calling window.evaluate_js.
        """
        try:
            from audio_visualizer import AudioVisualizer
        except ImportError:
            logger.warning("AudioVisualizer not available (missing numpy/ffmpeg?)")
            return

        viz = AudioVisualizer()
        self._viz = viz
        bus = self._bus
        interval = 1.0 / 30  # 30 fps

        while not self._stop.is_set():
            t0 = time.perf_counter()

            try:
                with self._lock:
                    state_snap = dict(self._state)

                md5 = state_snap.get("music_md5", "")
                playing = state_snap.get("music_playing", False)

                # Trigger background audio load on map change
                if md5 and md5 != viz._loaded_md5 and md5 != viz._loading_md5:
                    viz._trigger_load(md5, state_snap)

                with viz._lock:
                    has_audio = viz._samples is not None

                if has_audio:
                    # Emit bands whenever audio is loaded — this covers active
                    # play (state=2), menu preview, and song selection browsing.
                    from audio_visualizer import LOOKAHEAD_MS
                    current_ms = viz._interpolate_time(state_snap) + LOOKAHEAD_MS
                    bands = viz._compute_bands(current_ms)
                    bus.emit(AUDIO_BANDS, {"bands": bands, "active": True})
                else:
                    bus.emit(AUDIO_BANDS, {"bands": None, "active": False})

            except Exception:
                pass

            elapsed = time.perf_counter() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    def start(self):
        """Start the audio service in a daemon thread."""
        threading.Thread(target=self.run, daemon=True, name="audio-service").start()

    def shutdown(self):
        """Signal the audio loop to stop."""
        self._stop.set()
