# validator.py -- Domain validation for 4K rice
# LN confidence bands, 4K enforcement, structured domain output


# ── LN auto-route thresholds ──────────────────────────────────────
# These are SEPARATE from the rice-confidence bands.
# ln_route is a per-map decision for the overlay mode router.
#   "rice"      — LN ratio ≤ 0.30 → use the user's preferred rice mode
#   "hybrid"    — 0.30 < LN ratio ≤ 0.45 → gray zone, still rice for now
#   "ln"        — LN ratio > 0.45 → auto-switch to LN Course mode
_LN_ROUTE_HYBRID_FLOOR = 0.30
_LN_ROUTE_LN_FLOOR = 0.45


def validate_domain(parsed):
    """Validates a parsed chart and produces a structured domain result.

    Parameters
    ----------
    parsed : dict
        Output from parsear_osu_v2().

    Returns
    -------
    dict containing:
        valid           : bool  — True if the chart passes minimum validation
        is_4k           : bool
        ln_ratio        : float (0-1)
        ln_confidence   : str — "high" | "degraded" | "gray" | "out_of_domain"
        note_count      : int
        drain_time_s    : float
        bpm             : float
        od              : float
        hp              : float
        warnings        : list[str]
        rejection_reason: str | None
    """
    warnings = list(parsed.get("warnings", []))

    mode = parsed.get("mode", -1)
    keycount = parsed.get("keycount_native", 0)
    note_count = parsed.get("note_count", 0)
    ln_ratio = parsed.get("ln_ratio", 0.0)
    drain_time_s = parsed.get("drain_time_s", 0.0)
    bpm = parsed.get("bpm", 0.0)
    od = parsed.get("od", 0.0)
    hp = parsed.get("hp", 0.0)
    rejected = parsed.get("rejected", False)

    is_4k = (keycount == 4)
    is_7k = (keycount == 7)
    rejection_reason = None

    # Rejected by parser (mode/keycount mismatch)
    if rejected:
        rejection_reason = f"parser rejected: mode={mode}, keycount={keycount}"

    # Must be mania mode
    if mode != 3:
        rejection_reason = rejection_reason or f"not mania mode (mode={mode})"

    # Must be 4K or 7K
    if not (is_4k or is_7k):
        rejection_reason = rejection_reason or f"not 4K or 7K (keycount={keycount})"

    # Minimum note count
    if note_count < 20:
        rejection_reason = rejection_reason or f"too few notes ({note_count})"

    # Minimum drain time
    if drain_time_s < 5.0:
        rejection_reason = rejection_reason or f"drain too short ({drain_time_s:.1f}s)"

    # LN confidence bands (rice-first system)
    ln_confidence = _ln_confidence_band(ln_ratio)

    if ln_confidence == "out_of_domain":
        warnings.append(f"LN ratio {ln_ratio:.1%} — out of rice domain")

    # LN auto-route (separate from rice confidence)
    ln_route = _ln_route(ln_ratio)

    valid = rejection_reason is None

    return {
        "valid": valid,
        "is_4k": is_4k,
        "is_7k": is_7k,
        "ln_ratio": ln_ratio,
        "ln_confidence": ln_confidence,
        "ln_route": ln_route,
        "note_count": note_count,
        "drain_time_s": drain_time_s,
        "bpm": bpm,
        "od": od,
        "hp": hp,
        "warnings": warnings,
        "rejection_reason": rejection_reason,
    }


def _ln_confidence_band(ln_ratio):
    """Classifies the rice domain confidence based on the LN ratio.

    Bands (from research + empirical evidence):
        0.00 - 0.10  → "high"           (pure rice, maximum confidence)
        0.10 - 0.30  → "degraded"       (LNs present, result usable but degraded)
        0.30 - 0.45  → "gray"           (gray zone, low confidence)
        0.45+        → "out_of_domain"  (outside rice domain)
    """
    if ln_ratio <= 0.10:
        return "high"
    if ln_ratio <= 0.30:
        return "degraded"
    if ln_ratio <= 0.45:
        return "gray"
    return "out_of_domain"


def confidence_multiplier(ln_confidence):
    """Returns a 0-1 multiplier associated with the LN band.

    Used to scale the confidence of the final rating.
    """
    return {
        "high": 1.0,
        "degraded": 0.75,
        "gray": 0.45,
        "out_of_domain": 0.15,
    }.get(ln_confidence, 0.0)


def _ln_route(ln_ratio):
    """Decide if this map should auto-route to LN Course mode.

    Separate from _ln_confidence_band (which measures rice-domain health).
    This is the per-map mode-routing decision:
        ≤ 0.30  → "rice"    (use user's preferred rice mode)
        ≤ 0.45  → "hybrid"  (gray zone — still rice for v1)
        > 0.45  → "ln"      (auto-switch to LN Course)
    """
    if ln_ratio <= _LN_ROUTE_HYBRID_FLOOR:
        return "rice"
    if ln_ratio <= _LN_ROUTE_LN_FLOOR:
        return "hybrid"
    return "ln"
