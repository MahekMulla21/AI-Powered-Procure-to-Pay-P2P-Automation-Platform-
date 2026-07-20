"""
SOW Unstructured Field Extractor — Zero Regex, Dictionary-Driven
================================================================
All extraction rules come from sow_rule_based_dictionary.py.
No re.compile / re.search / re.findall anywhere in this file.
"""
from __future__ import annotations
from sow_config.sow_fields import UNSTRUCTURED_FIELDS
from sow_processing.sow_rule_based_dictionary import (
    UNSTRUCTURED_FIELD_DICTIONARY,
    GLOBAL_NOISE_PREFIXES,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS  (zero regex)
# ═══════════════════════════════════════════════════════════════════════════════

def _normalise(s: str) -> str:
    return " ".join(s.lower().split())


def _is_noise_line(line: str, skip_prefixes: list[str]) -> bool:
    norm = _normalise(line)
    for prefix in skip_prefixes:
        if norm.startswith(_normalise(prefix)):
            return True
    if line.strip().isdigit():
        return True
    return False


def _line_starts_with_any(line: str, prefixes: list[str]) -> bool:
    norm = _normalise(line)
    for p in prefixes:
        if norm.startswith(_normalise(p)):
            return True
    return False


def _strip_number_prefix(norm: str) -> str:
    """
    Remove leading section numbers like '2. ', '3.1 ', '13. ' from a
    normalised line, so anchors match regardless of numbering.
    Works by scanning characters: digits + dots + space at the start.
    """
    i = 0
    while i < len(norm) and (norm[i].isdigit() or norm[i] == "."):
        i += 1
    if i > 0 and i < len(norm) and norm[i] == " ":
        return norm[i + 1:]
    return norm


# ═══════════════════════════════════════════════════════════════════════════════
#  ANCHOR / STOP DETECTION  (zero regex)
# ═══════════════════════════════════════════════════════════════════════════════

def _find_anchor_line(lines: list[str], anchors: list[str]) -> int:
    """
    Return the index of the best matching anchor line.

    Priority order:
      1. Exact full-line match (entire line == anchor, with or without number)
      2. Starts-with match

    This ensures "13. TERMINATION CLAUSE" in the body beats "Termination Clause"
    found inside a summary table row.
    """
    exact_idx    = -1
    startswith_idx = -1

    for i, line in enumerate(lines):
        norm = _normalise(line)
        norm_stripped = _strip_number_prefix(norm)

        for anchor in anchors:
            a = _normalise(anchor)

            # Exact full-line match
            if norm == a or norm_stripped == a:
                if exact_idx == -1:
                    exact_idx = i

            # Starts-with match
            elif (norm.startswith(a + " ") or norm.startswith(a + ":")
                  or norm_stripped.startswith(a + " ")
                  or norm_stripped.startswith(a + ":")):
                if startswith_idx == -1:
                    startswith_idx = i

    return exact_idx if exact_idx != -1 else startswith_idx


def _find_stop_line(lines: list[str], stops: list[str], start: int) -> int:
    """Return index of first stop-keyword line after `start`."""
    for i in range(start, len(lines)):
        norm         = _normalise(lines[i])
        norm_stripped = _strip_number_prefix(norm)
        for stop in stops:
            s = _normalise(stop)
            if norm.startswith(s) or norm_stripped.startswith(s):
                return i
    return len(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE SECTION EXTRACTOR  (zero regex)
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_section(lines: list[str], cfg: dict) -> str:
    """
    Locate the anchor, collect lines until the stop, apply noise filters.
    Returns raw multi-line string.
    """
    anchor_idx = _find_anchor_line(lines, cfg["anchors"])
    if anchor_idx == -1:
        return ""

    stop_idx = _find_stop_line(lines, cfg["stops"], anchor_idx + 1)

    raw_lines   = lines[anchor_idx + 1: stop_idx]
    skip_pfx    = cfg.get("skip_prefixes", GLOBAL_NOISE_PREFIXES)
    max_lines   = cfg.get("max_lines", 50)
    min_len     = cfg.get("min_line_len", 0)

    collected: list[str] = []
    blank_streak = 0

    for line in raw_lines:
        if _is_noise_line(line, skip_pfx):
            continue
        stripped = line.strip()
        if not stripped:
            blank_streak += 1
            if blank_streak == 1 and collected:
                collected.append("")   # keep one blank as paragraph break
            continue
        blank_streak = 0
        if len(stripped) < min_len:
            continue
        collected.append(stripped)
        if len([x for x in collected if x]) >= max_lines:
            break

    # Remove trailing blanks
    while collected and collected[-1] == "":
        collected.pop()

    return "\n".join(collected)


# ═══════════════════════════════════════════════════════════════════════════════
#  POST-PROCESSORS  (zero regex)
# ═══════════════════════════════════════════════════════════════════════════════

def _post_join_paragraphs(raw: str, cfg: dict) -> str:
    """Merge lines into flowing prose, respecting paragraph breaks."""
    if not raw:
        return ""
    paragraphs: list[list[str]] = [[]]
    for line in raw.splitlines():
        if line == "":
            paragraphs.append([])
        else:
            paragraphs[-1].append(line)
    result_parts = [" ".join(p) for p in paragraphs if p]
    # Keep only long enough lines
    min_len = cfg.get("min_line_len", 20)
    result_parts = [p for p in result_parts if len(p) >= min_len]
    return " ".join(result_parts[:cfg.get("max_lines", 10)])


def _post_format_phases(raw: str, cfg: dict) -> str:
    """
    Structure scope-of-work into phase headers + top bullets per phase.
    """
    if not raw:
        return ""

    phase_keywords   = cfg.get("phase_keywords", [])
    bullet_chars     = cfg.get("bullet_chars", ["•", "-", "–", "*"])
    max_bullets      = cfg.get("max_bullets_per_phase", 3)

    result:  list[str] = []
    current_phase: str = ""
    bullets: list[str] = []

    def flush() -> None:
        if current_phase:
            result.append(f"• {current_phase}")
            for b in bullets[:max_bullets]:
                result.append(f"  - {b}")

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        norm = _normalise(s)

        is_phase  = _line_starts_with_any(s, phase_keywords)
        is_bullet = s and s[0] in bullet_chars

        if is_phase:
            flush()
            current_phase = s
            bullets = []
        elif is_bullet and current_phase:
            bullets.append(s.lstrip("".join(bullet_chars) + " ").strip())
        elif not current_phase:
            result.append(s)

    flush()
    return "\n".join(result) if result else raw[:800]


def _post_extract_deliverable_items(raw: str, cfg: dict) -> str:
    """Extract D1–Dn deliverable items and bullet lines."""
    if not raw:
        return ""

    codes        = [c.lower() for c in cfg.get("deliverable_codes", [])]
    bullet_chars = cfg.get("bullet_chars", ["•", "-", "–", "*"])
    items: list[str] = []

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        norm = _normalise(s)

        # D1 – ... style
        is_code = False
        for code in codes:
            if norm.startswith(code):
                # check next char is space, dash, or end
                rest = norm[len(code):]
                if rest == "" or rest[0] in " –-":
                    is_code = True
                    break

        if is_code or (s[0] in bullet_chars):
            items.append(s.lstrip("".join(bullet_chars) + " ").strip())

    if items:
        return "\n".join(items[:10])
    # Fallback: any non-empty line
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    return "\n".join(lines[:10])


def _post_extract_milestone_rows(raw: str, cfg: dict) -> str:
    """Extract M1–Mn milestone rows and TOTAL line."""
    if not raw:
        return ""

    prefixes = [p.lower() for p in cfg.get("milestone_prefixes", [])]
    rows: list[str] = []

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        norm = _normalise(s)
        if _line_starts_with_any(s, prefixes):
            rows.append(s)

    return "\n".join(rows) if rows else raw[:600]


def _post_bullet_lines(raw: str, cfg: dict) -> str:
    """Prefix each non-noise line with a bullet point."""
    if not raw:
        return ""
    skip = cfg.get("skip_prefixes", GLOBAL_NOISE_PREFIXES)
    rows: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or _is_noise_line(s, skip) or len(s) < 4:
            continue
        rows.append(f"• {s}")
    return "\n".join(rows[:12]) if rows else raw[:400]


def _post_plain(raw: str, cfg: dict) -> str:
    """Return raw section with minimal cleanup."""
    if not raw:
        return ""
    min_len = cfg.get("min_line_len", 10)
    lines = [l.strip() for l in raw.splitlines()
             if l.strip() and len(l.strip()) >= min_len]
    return "\n".join(lines[:cfg.get("max_lines", 20)])


# ── Acceptance criteria fallback: scan full doc for fact_markers ──────────────
def _acceptance_with_fallback(text_full: str, raw: str, cfg: dict) -> str:
    if raw and len(raw.strip()) > 20:
        return _post_plain(raw, cfg)
    markers = cfg.get("fact_markers", [])
    hits: list[str] = []
    for line in text_full.splitlines():
        s = line.strip()
        norm = _normalise(s)
        for m in markers:
            if _normalise(m) in norm and s not in hits:
                hits.append(s)
    return "\n".join(hits[:6]) if hits else ""


# ═══════════════════════════════════════════════════════════════════════════════
#  POST-PROCESSOR DISPATCH TABLE  (dictionary — no if/elif chain)
# ═══════════════════════════════════════════════════════════════════════════════

POST_PROCESSORS: dict = {
    "join_paragraphs":            _post_join_paragraphs,
    "format_phases":              _post_format_phases,
    "extract_deliverable_items":  _post_extract_deliverable_items,
    "extract_milestone_rows":     _post_extract_milestone_rows,
    "bullet_lines":               _post_bullet_lines,
    "plain":                      _post_plain,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def extract_unstructured(text: str, currency: str = "") -> tuple[dict, dict]:
    """
    Extract all UNSTRUCTURED_FIELDS from SOW text.
    Uses only dictionary lookups and string operations — zero regex.

    Returns:
        (data_dict, confidence_dict)
    """
    lines = text.splitlines()
    d: dict = {}
    c: dict = {}

    for field in UNSTRUCTURED_FIELDS:
        cfg = UNSTRUCTURED_FIELD_DICTIONARY.get(field, {})
        if not cfg:
            d[field] = None
            c[field] = 0.0
            continue

        raw = _extract_section(lines, cfg)

        # Dispatch to the right post-processor via dictionary lookup
        post_name = cfg.get("post_process", "plain")

        if field == "acceptance_criteria":
            val = _acceptance_with_fallback(text, raw, cfg)
        else:
            processor = POST_PROCESSORS.get(post_name, _post_plain)
            val = processor(raw, cfg)

        val = val.strip() if val else ""
        d[field] = val if val else None
        c[field] = 1.0 if d[field] and len(d[field]) >= 10 else 0.0

    return d, c