"""
ISOR -- Isotonic Strain Organic Residual.

Alternate dan-estimation engine for DanOverlay (osu!mania 4K rice).
Triangulates three continuous human-aligned difficulty vectors
(dp_sr, dp_choke, dp_msd), refines them with an isotonic-trained ridge
corrector (dual-band, benchmark-calibrated), and rescues the official
dan-ladder top scale with a continuous gate. Rate-aware and monotonic
in rate (isotonic SR clamp + native-anchor DP floor, ported from the
legacy pipeline). The user can switch between this engine and the
legacy one in the overlay settings; nothing is replaced.

Runtime files: isor_engine.py, strain.py (this folder);
config/vsrg_ridge_model.json + config/celestial_ruler.json (models).
"""

__all__ = ["isor_engine", "strain"]
