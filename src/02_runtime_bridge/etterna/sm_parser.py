"""
sm_parser.py — StepMania / Etterna (.sm and .ssc) chart parser for DanOverlay.

Parses .sm and .ssc simfiles into DanOverlay's unified chart representation:
  - notes: [(time_ms, col), ...]
  - rows:  [{"t": time_ms, "cols": (col, ...)}, ...]
  - BPM profile, drain duration, LN stats, and metadata.

Supports:
  - Global and chart-specific (SSC split timing) BPMs, STOPS, DELAYS, and OFFSETS.
  - Multi-chart selection by difficulty ("Challenge", "Hard", etc.), meter, description, or index.
  - 4K dance-single note extraction (1=tap, 2=hold start, 4=roll start).
"""

import math
import os
import re
from pathlib import Path


def _read_file_text(path: str | Path) -> str:
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        return f.read()


def _read_tag(text: str, tag: str) -> str | None:
    """Extract StepMania/SSC tag value (#TAG:value;). Returns None if tag is missing."""
    pattern = rf"#{re.escape(tag)}\s*:\s*(.*?);"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _parse_float(raw: str | None, default: float = 0.0) -> float:
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_timing_pairs(raw: str | None) -> list[tuple[float, float]]:
    """Parse comma-separated 'beat=val' timing list (e.g. '0.000=180.000,64.000=200.000')."""
    if not raw:
        return []
    result = []
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        left, right = item.split("=", 1)
        try:
            result.append((float(left.strip()), float(right.strip())))
        except ValueError:
            continue
    result.sort(key=lambda x: x[0])
    return result


def _parse_measure_rows(note_data: str) -> list[tuple[float, str]]:
    """Parse comma-separated measures into [(beat, '1000'), ...] tuples."""
    measures = note_data.split(",")
    rows = []
    measure_start_beat = 0.0

    for measure in measures:
        clean_lines = []
        for line in measure.splitlines():
            line = re.sub(r"//.*$", "", line).strip()
            if line:
                clean_lines.append(line)

        if not clean_lines:
            measure_start_beat += 4.0
            continue

        row_count = len(clean_lines)
        beat_step = 4.0 / row_count

        for i, row in enumerate(clean_lines):
            beat = measure_start_beat + i * beat_step
            rows.append((beat, row))

        measure_start_beat += 4.0

    return rows


def _beat_to_seconds(beat: float, bpms: list[tuple[float, float]],
                     stops: list[tuple[float, float]],
                     delays: list[tuple[float, float]],
                     offset: float) -> float:
    """Calculate exact timestamp in seconds for a given beat in StepMania timing."""
    if not bpms:
        current_time = -offset
        current_bpm = 120.0
    else:
        current_time = -offset
        current_beat = 0.0
        current_bpm = bpms[0][1]

        for change_beat, new_bpm in bpms:
            if change_beat <= 0:
                current_bpm = new_bpm
                continue
            if change_beat >= beat:
                break
            beat_delta = change_beat - current_beat
            current_time += (beat_delta * 60.0 / current_bpm) if current_bpm > 0 else 0.0
            current_beat = change_beat
            current_bpm = new_bpm

        remaining_beats = beat - current_beat
        current_time += (remaining_beats * 60.0 / current_bpm) if current_bpm > 0 else 0.0

    for stop_beat, duration in stops:
        if stop_beat < beat:
            current_time += duration

    for delay_beat, duration in delays:
        if delay_beat <= beat:
            current_time += duration

    return current_time


def _build_rows(notes: list[tuple[int, int]], tolerance_ms: float = 2.0) -> list[dict]:
    """Group sorted notes into rows: [{'t': ms, 'cols': (c1, ...)}, ...]."""
    if not notes:
        return []
    ordered = sorted(notes, key=lambda n: (n[0], n[1]))
    rows = []
    t0 = ordered[0][0]
    cols = {ordered[0][1]}

    for t, c in ordered[1:]:
        if abs(t - t0) <= tolerance_ms:
            cols.add(c)
        else:
            rows.append({"t": t0, "cols": tuple(sorted(cols))})
            t0 = t
            cols = {c}
    rows.append({"t": t0, "cols": tuple(sorted(cols))})
    return rows


# ── .SM and .SSC Chart Parsers ───────────────────────────────────────────────

def _parse_sm_charts(text: str) -> list[dict]:
    """Extract all #NOTES:...; blocks from a .sm file."""
    blocks = re.findall(r"#NOTES\s*:\s*(.*?);", text, flags=re.IGNORECASE | re.DOTALL)
    charts = []
    for i, block in enumerate(blocks):
        parts = block.split(":", 5)
        if len(parts) < 6:
            continue
        charts.append({
            "index": i,
            "stepstype": parts[0].strip(),
            "description": parts[1].strip(),
            "difficulty": parts[2].strip(),
            "meter": parts[3].strip(),
            "radar": parts[4].strip(),
            "note_data": parts[5].strip(),
        })
    return charts


def _parse_ssc_charts(text: str) -> tuple[str, list[dict]]:
    """Extract header and all #NOTEDATA blocks from a .ssc file."""
    matches = list(re.finditer(r"#NOTEDATA\s*:\s*;", text, flags=re.IGNORECASE))
    if not matches:
        return text, []

    header = text[:matches[0].start()]
    charts = []

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]

        stepstype = (_read_tag(block, "STEPSTYPE") or "").strip()
        description = (_read_tag(block, "DESCRIPTION") or _read_tag(block, "CHARTNAME") or "").strip()
        difficulty = (_read_tag(block, "DIFFICULTY") or "").strip()
        meter = (_read_tag(block, "METER") or "").strip()
        note_data = _read_tag(block, "NOTES")

        if note_data is None:
            continue

        bpms_tag = _read_tag(block, "BPMS")
        stops_tag = _read_tag(block, "STOPS")
        delays_tag = _read_tag(block, "DELAYS")
        offset_tag = _read_tag(block, "OFFSET")

        bpms = _parse_timing_pairs(bpms_tag if bpms_tag is not None else _read_tag(header, "BPMS"))
        stops = _parse_timing_pairs(stops_tag if stops_tag is not None else _read_tag(header, "STOPS"))
        delays = _parse_timing_pairs(delays_tag if delays_tag is not None else _read_tag(header, "DELAYS"))
        offset = _parse_float(offset_tag if offset_tag is not None else _read_tag(header, "OFFSET"), 0.0)

        charts.append({
            "index": i,
            "stepstype": stepstype,
            "description": description,
            "difficulty": difficulty,
            "meter": meter,
            "note_data": note_data.strip(),
            "bpms": bpms,
            "stops": stops,
            "delays": delays,
            "offset": offset,
        })

    return header, charts


# ── Chart Selector ───────────────────────────────────────────────────────────

def _normalize_diff_str(s: str) -> str:
    """Normalize difficulty names for matching (e.g. 'Difficulty_Challenge' -> 'challenge')."""
    if not s:
        return ""
    clean = (
        s.lower()
        .replace("[", "")
        .replace("]", "")
        .replace("(", "")
        .replace(")", "")
        .replace("difficulty_", "")
        .replace("difficulty", "")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )
    return clean


def _extract_diff_tokens(raw_str: str) -> tuple[str, str]:
    """Extract difficulty name (e.g. 'hard') and meter (e.g. '21') from a version string."""
    if not raw_str:
        return "", ""
    norm = _normalize_diff_str(raw_str)
    
    # Extract meter digits if present
    meter_match = re.search(r"\b(\d+)\b", norm)
    extracted_meter = meter_match.group(1) if meter_match else ""
    
    # Extract difficulty name without the meter
    diff_name = re.sub(r"\b\d+\b", "", norm).strip()
    
    # Common StepMania difficulty synonyms / keywords
    KNOWN_DIFFS = ["challenge", "expert", "oni", "hard", "maniac", "another", "medium", "trick", "basic", "easy", "beginner", "edit"]
    for kd in KNOWN_DIFFS:
        if kd in diff_name:
            diff_name = kd
            break
            
    return diff_name, extracted_meter


def _select_best_chart(charts: list[dict], difficulty: str = "", meter: str = "", description: str = "") -> dict | None:
    """Find the chart matching requested difficulty, meter, or description."""
    if not charts:
        return None

    # Filter for 4K (dance-single)
    single_charts = [c for c in charts if c.get("stepstype", "").lower() in ("dance-single", "")]
    pool = single_charts if single_charts else charts

    req_diff_name, req_diff_meter = _extract_diff_tokens(difficulty)
    target_meter = str(meter).strip() if meter else req_diff_meter
    target_diff = req_diff_name if req_diff_name else _normalize_diff_str(difficulty)
    target_desc = str(description).strip().lower() if description else ""

    # 1. Exact match on diff + meter + description
    if target_diff and target_meter and target_desc:
        for c in pool:
            c_diff = _normalize_diff_str(c.get("difficulty", ""))
            c_meter = str(c.get("meter", "")).strip()
            c_desc = c.get("description", "").lower()
            if (target_diff in c_diff or c_diff in target_diff) and c_meter == target_meter and c_desc == target_desc:
                return c

    # 2. Match on diff + meter
    if target_diff and target_meter:
        for c in pool:
            c_diff = _normalize_diff_str(c.get("difficulty", ""))
            c_meter = str(c.get("meter", "")).strip()
            if (target_diff in c_diff or c_diff in target_diff) and c_meter == target_meter:
                return c

    # 3. Match on meter alone (if meter was specified or extracted)
    if target_meter:
        for c in pool:
            if str(c.get("meter", "")).strip() == target_meter:
                return c

    # 4. Match on diff alone
    if target_diff:
        for c in pool:
            c_diff = _normalize_diff_str(c.get("difficulty", ""))
            if target_diff == c_diff or target_diff in c_diff or c_diff in target_diff:
                return c

    # 5. Match on description
    if target_desc:
        for c in pool:
            if target_desc in c.get("description", "").lower():
                return c

    # Fallback to highest meter or last chart in single_charts
    return pool[-1]


# ── Public API ───────────────────────────────────────────────────────────────

def parse_simfile(file_path: str | Path, difficulty: str = "", meter: str = "",
                  description: str = "", chart_index: int | None = None) -> dict:
    """Parses a .sm or .ssc file and returns a DanOverlay unified `parsed` structure.

    Parameters
    ----------
    file_path : str | Path
        Path to .sm or .ssc file.
    difficulty : str
        Target difficulty name ('Challenge', 'Hard', etc.).
    meter : str
        Target difficulty meter (e.g. '26').
    description : str
        Target chart description.
    chart_index : int | None
        Explicit chart index if known.

    Returns
    -------
    dict conforming to DanOverlay's `parsed` format (identical to `parsear_osu_v2`).
    """
    path = Path(file_path)
    if not path.is_file():
        return {
            "notes": [],
            "note_events": [],
            "rows": [],
            "rejected": True,
            "warnings": [f"File not found: {path}"],
        }

    ext = path.suffix.lower()
    text = _read_file_text(path)

    title = _read_tag(text, "TITLE") or path.stem
    artist = _read_tag(text, "ARTIST") or ""
    subtitle = _read_tag(text, "SUBTITLE") or ""
    credit = _read_tag(text, "CREDIT") or ""
    bg_file = _read_tag(text, "BACKGROUND") or ""
    banner_file = _read_tag(text, "BANNER") or ""
    offset = _parse_float(_read_tag(text, "OFFSET"), 0.0)
    bpms = _parse_timing_pairs(_read_tag(text, "BPMS"))
    stops = _parse_timing_pairs(_read_tag(text, "STOPS"))
    delays = _parse_timing_pairs(_read_tag(text, "DELAYS"))

    if ext == ".ssc":
        header, charts = _parse_ssc_charts(text)
    else:
        charts = _parse_sm_charts(text)

    if not charts:
        return {
            "notes": [],
            "note_events": [],
            "rows": [],
            "rejected": True,
            "warnings": ["No chart note data found in simfile"],
        }

    if chart_index is not None and 0 <= chart_index < len(charts):
        chosen_chart = charts[chart_index]
    else:
        chosen_chart = _select_best_chart(charts, difficulty=difficulty, meter=meter, description=description)

    if not chosen_chart:
        chosen_chart = charts[-1]

    # Chart-level timing overrides (for SSC split timing)
    chart_bpms = chosen_chart.get("bpms", bpms) or bpms
    chart_stops = chosen_chart.get("stops", stops) or stops
    chart_delays = chosen_chart.get("delays", delays) or delays
    chart_offset = chosen_chart.get("offset", offset) if "offset" in chosen_chart else offset

    note_rows = _parse_measure_rows(chosen_chart.get("note_data", ""))

    # Pre-sort timing lists for single-pass O(N) cursor advancement
    bpms_list = sorted(chart_bpms or [(0.0, 120.0)], key=lambda x: x[0])
    stops_list = sorted(chart_stops or [], key=lambda x: x[0])
    delays_list = sorted(chart_delays or [], key=lambda x: x[0])

    num_bpms = len(bpms_list)
    num_stops = len(stops_list)
    num_delays = len(delays_list)

    bpm_idx = 0
    stop_idx = 0
    delay_idx = 0

    accum_time = -chart_offset
    curr_beat = 0.0
    curr_bpm = bpms_list[0][1] if bpms_list else 120.0

    raw_notes = []
    note_events = []
    ln_count = 0
    object_count = 0
    hold_starts = [None] * 4

    for beat, row_str in note_rows:
        if len(row_str) != 4:
            continue

        # Advance BPM changes up to this beat
        while bpm_idx + 1 < num_bpms and bpms_list[bpm_idx + 1][0] <= beat:
            next_beat, next_bpm = bpms_list[bpm_idx + 1]
            beat_delta = next_beat - curr_beat
            if beat_delta > 0 and curr_bpm > 0:
                accum_time += beat_delta * 60.0 / curr_bpm
            curr_beat = next_beat
            curr_bpm = next_bpm
            bpm_idx += 1

        # Advance stops up to this beat (stop_beat < beat)
        while stop_idx < num_stops and stops_list[stop_idx][0] < beat:
            accum_time += stops_list[stop_idx][1]
            stop_idx += 1

        # Advance delays up to this beat (delay_beat <= beat)
        while delay_idx < num_delays and delays_list[delay_idx][0] <= beat:
            accum_time += delays_list[delay_idx][1]
            delay_idx += 1

        rem_beat = beat - curr_beat
        t_sec = accum_time + ((rem_beat * 60.0 / curr_bpm) if curr_bpm > 0 else 0.0)
        t_ms = int(round(t_sec * 1000.0))

        for col, sym in enumerate(row_str):
            if sym == "1":  # Tap
                raw_notes.append((t_ms, col))
                note_events.append({"time_ms": t_ms, "col": col, "event_type": "tap", "is_ln": False})
                object_count += 1
            elif sym in ("2", "4"):  # Hold start (2) or Roll start (4)
                raw_notes.append((t_ms, col))
                hold_starts[col] = t_ms
                ln_count += 1
                object_count += 1
            elif sym == "3":  # Hold / roll release tail
                start_ms = hold_starts[col]
                if start_ms is not None and t_ms > start_ms:
                    note_events.append({
                        "time_ms": start_ms,
                        "col": col,
                        "event_type": "ln_start",
                        "is_ln": True,
                        "ln_start_ms": start_ms,
                        "ln_end_ms": t_ms,
                        "duration_ms": t_ms - start_ms,
                    })
                    note_events.append({
                        "time_ms": t_ms,
                        "col": col,
                        "event_type": "ln_end",
                        "is_ln": True,
                        "ln_start_ms": start_ms,
                        "ln_end_ms": t_ms,
                        "duration_ms": t_ms - start_ms,
                    })
                    hold_starts[col] = None

    # Deduplicate and sort notes
    notes_sorted = sorted(raw_notes, key=lambda n: (n[0], n[1]))
    deduped = []
    prev = None
    for n in notes_sorted:
        if prev == n:
            continue
        deduped.append(n)
        prev = n

    rows = _build_rows(deduped, tolerance_ms=2.0)

    first_ms = deduped[0][0] if deduped else 0
    last_ms = deduped[-1][0] if deduped else 0
    drain_time_s = max(0.0, (last_ms - first_ms) / 1000.0)

    # BPM stats
    bpm_values = [bpm_val for _, bpm_val in chart_bpms] if chart_bpms else [120.0]
    bpm_base = bpm_values[0] if bpm_values else 120.0
    bpm_min = min(bpm_values) if bpm_values else bpm_base
    bpm_max = max(bpm_values) if bpm_values else bpm_base
    bpm_common = bpm_base

    chart_diff = chosen_chart.get("difficulty", "")
    chart_meter = chosen_chart.get("meter", "")
    chart_desc = chosen_chart.get("description", "")
    chart_credit = chosen_chart.get("credit", "")
    creator = chart_credit or chart_desc or credit or subtitle
    if not creator and path.parent:
        folder_match = re.search(r"\(([^)]+)\)$", path.parent.name)
        if folder_match:
            creator = folder_match.group(1).strip()
    creator = creator or ""
    version_label = f"[{chart_diff} {chart_meter}]".strip() if (chart_diff or chart_meter) else ""

    pack = ""
    if len(path.parents) >= 2:
        cand_pack = path.parents[1].name
        if cand_pack.lower() not in ("songs", "songs_current", "tests", "etterna maps", "test", "d:", "c:", ""):
            pack = cand_pack

    return {
        "notes": deduped,
        "note_events": sorted(note_events, key=lambda e: (int(e.get("time_ms", 0)), int(e.get("col", 0)))),
        "rows": rows,
        "bpm": bpm_base,
        "bpm_min": bpm_min,
        "bpm_max": bpm_max,
        "bpm_common": bpm_common,
        "od": 8.0,
        "hp": 8.0,
        "drain_time_s": drain_time_s,
        "offset": chart_offset,
        "note_count": len(deduped),
        "ln_count": ln_count,
        "ln_ratio": (ln_count / max(object_count, 1)) if object_count else 0.0,
        "metadata": {
            "title": title,
            "artist": artist,
            "version": version_label or chart_desc,
            "creator": creator,
            "difficulty": chart_diff,
            "meter": chart_meter,
            "pack": pack,
            "bg_file": bg_file,
            "banner_file": banner_file,
        },
        "is_7k": False,
        "rejected": False,
        "warnings": [],
        "format": ext.replace(".", ""),
    }
