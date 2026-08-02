# parser.py -- Reads and parses .osu files (rebuild v2)
# Single-pass parsing of notes, LN stats, metadata, drain time, BPM, etc.


def _safe_int(value, default=None):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=None):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _safe_str(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _map_x_to_col(x, keycount, warnings):
    if keycount <= 0:
        return 0
    x_clamped = x
    if x < 0 or x >= 512:
        warnings.append(f"x out of bounds ({x}), clamped to [0,511]")
        x_clamped = max(0, min(511, x))
    col = int((x_clamped * keycount) // 512)
    return max(0, min(keycount - 1, col))


def _remap_col(col_in, keycount_in, keycount_out):
    if keycount_in <= 0 or keycount_out <= 0:
        return 0
    out = int((col_in * keycount_out) // keycount_in)
    return max(0, min(keycount_out - 1, out))


def _build_rows(notes, tolerance_ms):
    if not notes:
        return []

    tol = max(0, int(tolerance_ms))
    ordered = sorted(notes, key=lambda n: (n[0], n[1]))
    rows = []

    t0 = int(ordered[0][0])
    cols = {int(ordered[0][1])}

    for t, c in ordered[1:]:
        t = int(t)
        c = int(c)
        if abs(t - t0) <= tol:
            cols.add(c)
        else:
            rows.append({"t": t0, "cols": tuple(sorted(cols))})
            t0 = t
            cols = {c}

    rows.append({"t": t0, "cols": tuple(sorted(cols))})
    return rows


def parsear_osu_v2(
    ruta_archivo,
    output_keycount=None,
    include_ln_tails=True,
    enforce_mode_mania=True,
    enforce_keycount=None,
    row_tolerance_ms=0,
    strict=False,
):
    """Parses an osu!mania .osu file and returns a parsed dictionary for the pipeline.

    Key fields:
    - notes: Sorted list of (time_ms, col)
    - note_events: tap/ln_start/ln_end event logs
    - bpm: base BPM from first uninherited timing point
    - metadata: {title, artist, version, creator, beatmap_id}
    - od, hp: floats from [Difficulty] section
    - note_count: total note count (excluding LN tails)
    - ln_count: total of long notes
    - ln_ratio: ln_count / max(object_count, 1)
    - drain_time_s: (last_note - first_note) / 1000
    - warnings: parsing warnings list
    - rejected: True if the mode or keycount filter fails
    """
    with open(ruta_archivo, encoding="utf-8", errors="ignore") as f:
        lineas = f.readlines()

    warnings = []
    bpm = 120.0
    _all_bpms = []  # all uninherited timing point BPM values
    mode = 3
    keycount_native = 4
    od = 8.0
    hp = 8.0

    # Metadata fields
    title = ""
    artist = ""
    version = ""
    creator = ""
    beatmap_id = ""

    section = ""
    notes = []
    note_events = []
    object_count = 0
    ln_count = 0

    for raw in lineas:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line
            continue

        if line.startswith("//"):
            continue

        if section == "[General]":
            if line.startswith("Mode:"):
                val = _safe_int(line.split(":", 1)[1], default=mode)
                mode = mode if val is None else val

        elif section == "[Metadata]":
            if line.startswith("Title:"):
                title = _safe_str(line.split(":", 1)[1])
            elif line.startswith("Artist:"):
                artist = _safe_str(line.split(":", 1)[1])
            elif line.startswith("Version:"):
                version = _safe_str(line.split(":", 1)[1])
            elif line.startswith("Creator:"):
                creator = _safe_str(line.split(":", 1)[1])
            elif line.startswith("BeatmapID:"):
                beatmap_id = _safe_str(line.split(":", 1)[1])

        elif section == "[Difficulty]":
            if line.startswith("CircleSize:"):
                cs = _safe_float(line.split(":", 1)[1], default=float(keycount_native))
                if cs is not None:
                    keycount_native = max(1, int(round(cs)))
            elif line.startswith("OverallDifficulty:"):
                val = _safe_float(line.split(":", 1)[1], default=None)
                if val is not None:
                    od = val
            elif line.startswith("HPDrainRate:"):
                val = _safe_float(line.split(":", 1)[1], default=None)
                if val is not None:
                    hp = val

        elif section == "[TimingPoints]":
            parts = line.split(",")
            if len(parts) >= 7:
                uninherited = _safe_int(parts[6], default=0)
                beat_length = _safe_float(parts[1], default=None)
                if uninherited == 1 and beat_length is not None and beat_length > 0:
                    _tp_bpm = 60000.0 / beat_length
                    if not _all_bpms:  # first timing point
                        bpm = _tp_bpm
                    _all_bpms.append(_tp_bpm)

        elif section == "[HitObjects]":
            parts = line.split(",")
            if len(parts) < 5:
                warnings.append(f"hitobject invalido: '{line[:48]}'")
                continue

            x = _safe_int(parts[0], default=None)
            t = _safe_int(parts[2], default=None)
            obj_type = _safe_int(parts[3], default=0)

            if x is None or t is None:
                warnings.append(f"hitobject no parseable: '{line[:48]}'")
                continue

            col_native = _map_x_to_col(x, keycount_native, warnings)
            keycount_output = (
                max(1, int(output_keycount))
                if output_keycount is not None
                else keycount_native
            )
            col = _remap_col(col_native, keycount_native, keycount_output)

            is_ln = bool(obj_type & 128)
            is_tap = bool(obj_type & 1)
            object_count += 1

            if is_ln:
                ln_count += 1
                if len(parts) < 6:
                    warnings.append("LN missing endTime, treated as tap")
                    notes.append((t, col))
                    note_events.append(
                        {"time_ms": t, "col": col, "event_type": "tap", "is_ln": False}
                    )
                    continue

                end_raw = parts[5].split(":", 1)[0]
                t_end = _safe_int(end_raw, default=None)
                if t_end is None:
                    warnings.append("LN with invalid endTime, treated as tap")
                    notes.append((t, col))
                    note_events.append(
                        {"time_ms": t, "col": col, "event_type": "tap", "is_ln": False}
                    )
                    continue

                if t_end <= t:
                    warnings.append(f"LN endTime <= start ({t_end} <= {t}), treated as tap")
                    notes.append((t, col))
                    note_events.append(
                        {"time_ms": t, "col": col, "event_type": "tap", "is_ln": False}
                    )
                    continue

                notes.append((t, col))
                note_events.append(
                    {
                        "time_ms": t,
                        "col": col,
                        "event_type": "ln_start",
                        "is_ln": True,
                        "ln_start_ms": t,
                        "ln_end_ms": t_end,
                        "duration_ms": t_end - t,
                    }
                )

                if include_ln_tails:
                    notes.append((t_end, col))
                    note_events.append(
                        {
                            "time_ms": t_end,
                            "col": col,
                            "event_type": "ln_end",
                            "is_ln": True,
                            "ln_start_ms": t,
                            "ln_end_ms": t_end,
                            "duration_ms": t_end - t,
                        }
                    )

            elif is_tap:
                notes.append((t, col))
                note_events.append(
                    {"time_ms": t, "col": col, "event_type": "tap", "is_ln": False}
                )

    notes_sorted = sorted(notes, key=lambda n: (n[0], n[1]))

    deduped = []
    dup_count = 0
    prev = None
    for n in notes_sorted:
        if prev == n:
            dup_count += 1
            continue
        deduped.append(n)
        prev = n
    if dup_count:
        warnings.append(f"{dup_count} duplicate notes deduplicated")

    rows = _build_rows(deduped, row_tolerance_ms)

    rejected = False
    if enforce_mode_mania and mode != 3:
        rejected = True
    if enforce_keycount is not None and int(enforce_keycount) != int(keycount_native):
        rejected = True

    if rejected:
        deduped = []
        note_events = []
        rows = []

    note_count = len(deduped)
    first_ms = deduped[0][0] if deduped else 0
    last_ms = deduped[-1][0] if deduped else 0
    drain_time_s = max(0.0, (last_ms - first_ms) / 1000.0)
    ln_ratio = ln_count / max(object_count, 1)

    # BPM range from all uninherited timing points
    _bpms_rounded = [round(b) for b in _all_bpms] if _all_bpms else [round(bpm)]
    _bpm_min = min(_bpms_rounded)
    _bpm_max = max(_bpms_rounded)
    from collections import Counter as _Counter
    _bpm_common = _Counter(_bpms_rounded).most_common(1)[0][0]

    out = {
        "notes": deduped,
        "note_events": sorted(note_events, key=lambda e: (int(e.get("time_ms", 0)), int(e.get("col", 0)))),
        "rows": rows,
        "bpm": float(bpm),
        "bpm_min": int(_bpm_min),
        "bpm_max": int(_bpm_max),
        "bpm_common": int(_bpm_common),
        "od": float(od),
        "hp": float(hp),
        "metadata": {
            "title": title,
            "artist": artist,
            "version": version,
            "creator": creator,
            "beatmap_id": beatmap_id,
        },
        "note_count": note_count,
        "ln_count": ln_count,
        "ln_ratio": ln_ratio,
        "drain_time_s": drain_time_s,
        "warnings": warnings,
        "rejected": bool(rejected),
        "mode": mode,
        "keycount_native": keycount_native,
        "keycount_output": (
            max(1, int(output_keycount))
            if output_keycount is not None
            else keycount_native
        ),
    }

    if strict and warnings:
        raise ValueError("Parser strict mode: se detectaron warnings")

    return out


def parsear_osu(ruta_archivo):
    """Legacy API: returns (notes, bpm)."""
    parsed = parsear_osu_v2(
        ruta_archivo,
        output_keycount=4,
        include_ln_tails=True,
        enforce_mode_mania=False,
        enforce_keycount=None,
        row_tolerance_ms=0,
        strict=False,
    )
    return parsed["notes"], parsed["bpm"]
