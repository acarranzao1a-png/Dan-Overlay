"""
Audio visualizer service.

Downloads the current beatmap's audio file from tosu, decodes it to raw
samples, and computes FFT bands at the live playback position.  Pushes
band data directly to the overlay JS via pywebview ``evaluate_js``.

Design notes:
- Loading is done in a background thread so the render loop never blocks.
- Old samples are cleared IMMEDIATELY when the map changes so stale data
  is never shown during the download.
- A RMS-based silence gate rejects genuinely silent chunks before FFT,
  preventing noise from being amplified to 1.0 by the normalizer.
- Bars scale with actual amplitude relative to the song's loudness, so
  quiet passages draw smaller bars (not full-height noise).
"""

import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import requests

# ── Locate ffmpeg.exe ────────────────────────────────────────────────────
# PyInstaller --onefile extracts bundled files to sys._MEIPASS at startup.
# In development, fall back to PATH.
def _find_ffmpeg() -> str | None:
    if getattr(sys, "frozen", False):
        mei = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        p = os.path.join(mei, "ffmpeg.exe")
        if os.path.isfile(p):
            return p
    return shutil.which("ffmpeg")

_FFMPEG_PATH = _find_ffmpeg()

# ── constants ────────────────────────────────────────────────────────────
TOSU_AUDIO_URL = "http://127.0.0.1:24050/files/beatmap/audio"
SAMPLE_RATE    = 44100
NUM_BANDS      = 32
CHUNK_MS       = 10    # real audio window (ms); zero-padded to FFT_N for full resolution
FFT_N          = 8192  # zero-pad target: 5.38 Hz/bin, covers all log bands with only 10ms audio
FFT_FPS        = 30    # 30fps push keeps IPC overhead low; JS rAF lerp interpolates to 60fps smoothly
LOOKAHEAD_MS  = 33    # match 30fps cadence (~33ms/frame)

# RMS silence gate: chunks below this level are treated as silence.
# Calibrated for 16-bit audio normalised to [-1, 1].  Music is typically
# 0.05–0.5 RMS; digital silence is < 0.0005.
SILENCE_RMS  = 0.003
# Minimum reference level used for normalization.  Keeps noise from being
# amplified when the whole track is very quiet.
MIN_REF_RMS  = 0.005


class AudioVisualizer:
    """Analyse beatmap audio and push FFT bands to the overlay."""

    def __init__(self):
        self._samples: np.ndarray | None = None
        self._duration_ms: float = 0.0
        self._ref_rms: float = MIN_REF_RMS   # song-level reference set at load time
        self._loaded_md5: str | None = None
        self._loading_md5: str | None = None  # md5 currently being fetched

        self._lock = threading.Lock()

        # logarithmic band edges: 20 Hz → 18 kHz
        # Subtract a small epsilon from the lower bound so the 20 Hz FFT bin
        # (which lands at 19.9999... due to floating-point) is captured in band 0.
        self._band_edges = np.logspace(
            np.log10(20 - 0.5),
            np.log10(min(18000, SAMPLE_RATE // 2)),
            NUM_BANDS + 1,
        )

        # Set to False on first failed evaluate_js (window closed/disposed)
        # so we stop pushing immediately and suppress further pywebview errors.
        self._window_alive = True

    # ── main loop (runs in its own daemon thread) ─────────────────────
    def run(self, window, estado_global: dict, stop_event: threading.Event):
        interval = 1.0 / FFT_FPS

        while not stop_event.is_set() and self._window_alive:
            t0 = time.perf_counter()
            try:
                md5     = estado_global.get("music_md5", "")
                playing = estado_global.get("music_playing", False)

                # Trigger background load when the map changes.
                # Guard: don't start a second load for the same md5.
                if md5 and md5 != self._loaded_md5 and md5 != self._loading_md5:
                    self._trigger_load(md5, estado_global)

                with self._lock:
                    has_audio = self._samples is not None

                if playing and has_audio:
                    # Lookahead: analyze the audio that will be playing LOOKAHEAD_MS
                    # from now. Since the full audio is pre-loaded, this perfectly
                    # pre-compensates for the push interval + JS lerp delay so bars
                    # respond right as the transient hits the speakers.
                    current_ms = self._interpolate_time(estado_global) + LOOKAHEAD_MS
                    bands = self._compute_bands(current_ms)
                    self._push(window, bands, True, stop_event)
                else:
                    self._push(window, None, False, stop_event)

            except Exception:
                pass

            elapsed   = time.perf_counter() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    # ── map change: clear immediately, load in background ────────────
    def _trigger_load(self, md5: str, estado_global: dict):
        self._loading_md5 = md5

        # Wipe old samples right now so the render loop shows silence
        # instead of wrong audio while the new file is downloading.
        with self._lock:
            self._samples    = None
            self._loaded_md5 = None

        t = threading.Thread(
            target=self._load_audio, args=(md5, estado_global), daemon=True
        )
        t.start()

    def _load_audio(self, md5: str, estado_global: dict):
        try:
            if _FFMPEG_PATH is None:
                return   # ffmpeg not available — visualizer disabled

            resp = requests.get(TOSU_AUDIO_URL, timeout=15)
            if resp.status_code != 200:
                return

            # Map changed while we were downloading → discard this result.
            if estado_global.get("music_md5", "") != md5:
                return

            # Decode audio to raw 16-bit PCM via ffmpeg subprocess.
            # ffmpeg auto-detects the input format (mp3, ogg, etc.) so we
            # don't need ffprobe at all.  Output: mono, 44100 Hz, s16le.
            proc = subprocess.run(
                [
                    _FFMPEG_PATH,
                    "-i", "pipe:0",        # read from stdin
                    "-f", "s16le",         # raw PCM output
                    "-acodec", "pcm_s16le",
                    "-ar", str(SAMPLE_RATE),
                    "-ac", "1",            # mono
                    "pipe:1",              # write to stdout
                ],
                input=resp.content,
                capture_output=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if proc.returncode != 0:
                return

            raw = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32)
            raw /= 32768.0  # 16-bit → [-1, 1]

            if len(raw) < SAMPLE_RATE:
                return   # too short to be useful

            duration_ms = (len(raw) / SAMPLE_RATE) * 1000.0

            # ── Reference RMS ──────────────────────────────────────────
            # 90th-percentile RMS across 1-second windows captures the
            # song's loud level without being skewed by peaks or silence.
            win_size  = SAMPLE_RATE
            rms_vals  = [
                float(np.sqrt(np.mean(raw[i : i + win_size] ** 2)))
                for i in range(0, len(raw) - win_size, win_size)
            ]
            ref = float(np.percentile(rms_vals, 90)) if rms_vals else MIN_REF_RMS

            with self._lock:
                self._samples      = raw
                self._duration_ms  = duration_ms
                self._ref_rms      = max(ref, MIN_REF_RMS)
                self._loaded_md5   = md5

        except Exception:
            pass
        finally:
            if self._loading_md5 == md5:
                self._loading_md5 = None

    # ── time interpolation ───────────────────────────────────────────
    @staticmethod
    def _interpolate_time(estado_global: dict) -> float:
        """Advance past the last tosu poll using wall-clock elapsed time."""
        base_ms = estado_global.get("music_time_ms", 0)
        wall    = estado_global.get("music_time_wall", 0)
        speed   = estado_global.get("mod_speed_actual", 1.0)
        if wall:
            elapsed_wall_ms = (time.time() - wall) * 1000
            return base_ms + elapsed_wall_ms * speed
        return base_ms

    # ── FFT computation ──────────────────────────────────────────────
    def _compute_bands(self, time_ms: float) -> list[float]:
        with self._lock:
            if self._samples is None:
                return [0.0] * NUM_BANDS

            # Use a causal window: the chunk ends exactly at time_ms so the
            # FFT always represents audio up to the current moment.  This is
            # tighter for sync than a centered window (no future-audio leakage).
            N      = int((CHUNK_MS / 1000.0) * SAMPLE_RATE)
            end    = min(len(self._samples), int((time_ms / 1000.0) * SAMPLE_RATE))
            start  = max(0, end - N)

            if end - start < 64:
                return [0.0] * NUM_BANDS

            chunk   = self._samples[start:end].copy()
            ref_rms = self._ref_rms

        # ── Silence gate ────────────────────────────────────────────
        # Check BEFORE FFT. If the audio chunk is truly silent, return
        # zeros — don't feed noise through FFT+normalize.
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < SILENCE_RMS:
            return [0.0] * NUM_BANDS

        # Amplitude scale: how loud this moment is relative to the song.
        # Clamp to [0, 1] so peaks don't blast to infinity.
        amp_scale = min(1.0, rms / ref_rms)

        # ── FFT ─────────────────────────────────────────────────────
        # Apply Hanning window to the real audio chunk, then zero-pad to FFT_N.
        # Zero-padding keeps bin_hz = 44100/8192 = 5.38 Hz (same resolution
        # as a 150ms window) while the real audio window stays 50ms for sync.
        padded = np.zeros(FFT_N, dtype=np.float32)
        window = np.hanning(len(chunk))
        padded[:len(chunk)] = chunk * window
        fft_mag = np.abs(np.fft.rfft(padded))
        freqs   = np.fft.rfftfreq(FFT_N, 1.0 / SAMPLE_RATE)

        bands: list[float] = []
        for i in range(NUM_BANDS):
            mask = (freqs >= self._band_edges[i]) & (freqs < self._band_edges[i + 1])
            bands.append(float(np.mean(fft_mag[mask])) if np.any(mask) else -1.0)

        # Fill any bands that had no FFT bins (logarithmic gaps at low freq)
        # using linear interpolation from nearest valid neighbors.
        for i in range(NUM_BANDS):
            if bands[i] >= 0:
                continue
            lo = next((bands[j] for j in range(i - 1, -1, -1) if bands[j] >= 0), 0.0)
            hi = next((bands[j] for j in range(i + 1, NUM_BANDS) if bands[j] >= 0), 0.0)
            bands[i] = (lo + hi) / 2.0

        # ── Normalize ───────────────────────────────────────────────
        # Shape = frequency content (relative to each other).
        # Scale = actual loudness at this moment (amp_scale).
        # Result: quiet = small bars, loud = tall bars, silence = no bars.
        mx = max(bands)
        if mx == 0:
            return [0.0] * NUM_BANDS
        return [min(1.0, (b / mx) * amp_scale) for b in bands]

    # ── push to JS ───────────────────────────────────────────────────
    def _push(self, window, bands: list[float] | None, active: bool,
              stop_event: threading.Event | None = None):
        # Stop early if the window is already known-dead or shutting down.
        if not self._window_alive:
            return
        if stop_event is not None and stop_event.is_set():
            return
        try:
            payload = {"type": "visualizer", "active": active}
            if bands is not None:
                payload["bands"] = bands
            js = "window.__overlayFromPython(" + json.dumps(payload) + ");"
            window.evaluate_js(js)
        except Exception:
            # WebView2 raises ObjectDisposedException when the window has
            # been closed.  Mark the window as dead so we stop calling
            # evaluate_js (and stop pywebview from printing more tracebacks).
            self._window_alive = False
