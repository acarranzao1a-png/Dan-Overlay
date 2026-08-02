# analysis_coordinator.py — Listens for MAP_CHANGED, runs the pipeline, and emits
# ANALYSIS_COMPLETE or ANALYSIS_ERROR.
#
# Resolves two main issues:
# 1) Avoids recalculating when revisiting a previously cached map.
# 2) Prevents race conditions where a slow/stale analysis overwrites a newer one.
#
# Optimisation (2026-06):
#   - Debounce 200ms: when the user scrolls rapidly through maps only the last one
#     is analysed.
#   - Single worker: one analysis thread at a time — no CPU contention with the UI.

import logging
import os
import threading
import time

from events import (
    MAP_CHANGED, ANALYSIS_STARTED, ANALYSIS_COMPLETE,
    ANALYSIS_ERROR, OVERLAY_STATE,
)
from contracts import AnalysisResult, STATE_ANALYZING, STATE_ERROR

logger = logging.getLogger(__name__)


class AnalysisCoordinator:
    """Listens for map changes and runs the analysis pipeline.

    * One analysis at a time; rapid map switches invalidate old results.
    * Results are cached by (path, mod_label) so revisiting a map is instant.
    * The pipeline import is deferred so the coordinator can be created early.
    """

    _DEBOUNCE_S = 0.2

    def __init__(self, event_bus, cache_size=200):
        self._bus = event_bus
        self._cache = {}
        self._cache_order = []
        self._cache_limit = cache_size
        self._seq = 0
        self._current_token = None
        self._lock = threading.Lock()

        event_bus.subscribe(MAP_CHANGED, self._on_map_changed)

        # Pre-import heavy modules (numpy, sr_core) in a background thread
        # so the first analysis doesn't pay the cold-start import cost.
        self._warmup_done = threading.Event()
        threading.Thread(target=self._warmup, daemon=True).start()

        # Debounce timer + latest pending request (must be set before worker starts)
        self._debounce_timer: threading.Timer | None = None
        self._pending_map = None
        self._pending_token = ""
        self._pending_event = threading.Event()

        # Single worker — no thread explosion on rapid map switches.
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    # ── warmup (cold-start elimination) ────────────────────────────

    def _warmup(self):
        """Pre-import heavy modules so the first analysis avoids cold-start cost."""
        try:
            import numpy           # ~100ms
            import pandas          # ~50ms
            from primary_sr_bridge import _import_sr_core
            _import_sr_core()      # pulls in algorithm + osu_file_parser
            # Lighter modules.  Still worth pre-loading so first
            # MAP_CHANGED doesn't pay parser/feature/classifier/rank import cost.
            import parser
            import feature_extractor
            import classifier
            import rank_engine
        except Exception:
            pass
        finally:
            self._warmup_done.set()

    # ── event handler ───────────────────────────────────────────────

    def _on_map_changed(self, map_info):
        cache_key = (map_info.path, map_info.mod_label, round(map_info.mod_speed, 4))

        with self._lock:
            self._seq += 1
            token = f"{map_info.md5}|{self._seq}"
            self._current_token = token

        # Cache hit — return instantly without debounce.
        if cache_key in self._cache:
            self._bus.emit(ANALYSIS_COMPLETE, self._cache[cache_key])
            return

        # Validate path exists
        if not map_info.path or not os.path.isfile(map_info.path):
            self._bus.emit(ANALYSIS_ERROR, {
                "md5": map_info.md5,
                "error": f"File not found: {map_info.path}",
            })
            self._bus.emit(OVERLAY_STATE, {
                "state": STATE_ERROR,
                "message": "Map file not found",
            })
            return

        # Debounce: store the latest map and schedule processing.
        self._pending_map = map_info
        self._pending_token = token

        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(
            self._DEBOUNCE_S, self._dispatch_to_worker
        )
        self._debounce_timer.start()

    def _dispatch_to_worker(self):
        """Called by the debounce timer — fires the start events and wakes
        the worker thread so it picks up the latest pending map."""
        if self._pending_map is None:
            return
        self._bus.emit(ANALYSIS_STARTED, {"md5": getattr(self._pending_map, "md5", "")})
        self._bus.emit(OVERLAY_STATE, {
            "state": STATE_ANALYZING,
            "message": "Computing...",
        })
        self._pending_event.set()

    # ── worker loop ──────────────────────────────────────────────────

    def _worker_loop(self):
        """Single-thread analysis loop — never more than one analysis at a time."""
        while True:
            self._pending_event.wait()
            self._pending_event.clear()

            map_info = self._pending_map
            token = self._pending_token
            if map_info is None:
                continue

            cache_key = (
                map_info.path,
                map_info.mod_label,
                round(map_info.mod_speed, 4),
            )

            # Wait for warmup so the first analysis is fast.
            # This blocks, but warmup is a background thread — it finishes
            # long before the first real MAP_CHANGED reaches us.
            self._warmup_done.wait(timeout=5)

            try:
                # Deferred import reduces startup overhead.
                from pipeline import analyze_map

                mod = map_info.mod_label or "NM"
                raw = analyze_map(
                    map_info.path, mod=mod, rate=map_info.mod_speed
                )
                raw["osu_sr"] = map_info.sr_official

                # Stale-result check — discard if active map changed
                # while we were computing.
                with self._lock:
                    if self._current_token != token:
                        continue

                result = AnalysisResult.from_pipeline(
                    raw, mod_label=map_info.mod_label
                )

                # Store in cache (LRU eviction)
                with self._lock:
                    if self._current_token != token:
                        continue
                    self._cache[cache_key] = result
                    if cache_key in self._cache_order:
                        self._cache_order.remove(cache_key)
                    self._cache_order.append(cache_key)
                    while len(self._cache_order) > self._cache_limit:
                        old = self._cache_order.pop(0)
                        self._cache.pop(old, None)

                self._bus.emit(ANALYSIS_COMPLETE, result)

            except Exception as exc:
                with self._lock:
                    if self._current_token != token:
                        continue

                logger.exception(
                    "Analysis failed for %s", getattr(map_info, "path", "?")
                )
                self._bus.emit(ANALYSIS_ERROR, {
                    "md5": getattr(map_info, "md5", ""),
                    "error": str(exc),
                })
                self._bus.emit(OVERLAY_STATE, {
                    "state": STATE_ERROR,
                    "message": f"Analysis error: {exc}",
                })

    def clear_cache(self):
        """Force-clear the result cache."""
        with self._lock:
            self._cache.clear()
            self._cache_order.clear()
