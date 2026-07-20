"""
SOW Structured Field Extractor — Fully Generic Final
======================================================
Handles ANY SOW PDF format. Tested on:
  PDF A: TCS/STC (no-space concatenated labels: SOWStartDate February01,2024)
  PDF B: Pinnacle/NexaCore (Label: Value lines + header-then-value pattern)
"""
from __future__ import annotations
from sow_config.sow_fields import STRUCTURED_FIELDS
from sow_processing.sow_rule_based_dictionary import (
    STRUCTURED_FIELD_DICTIONARY,
    GLOBAL_NOISE_PREFIXES,
    MONTH_NAMES,
    CURRENCY_KEYWORDS,
    CURRENCY_SYMBOLS,
)


# ───────────────────────────────────────────────────────────────────────
#  HELPERS
# ───────────────────────────────────────────────────────────────────────

def _is_noise(line: str) -> bool:
    norm = " ".join(line.lower().split())
    return any(norm.startswith(p.lower()) for p in GLOBAL_NOISE_PREFIXES)


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _nsp(s: str) -> str:
    """Remove all spaces — for no-space label matching."""
    return s.lower().replace(" ", "").replace("_", "")



# Known label/header words that should never be extracted as values
_LABEL_WORDS = {
    "signature", "client", "vendor", "service", "provider", "supplier",
    "buyer", "customer", "authorized", "signatures", "date", "title",
    "name", "representative", "officer", "director", "manager",
}

def _looks_like_label(val: str) -> bool:
    """
    Return True if val looks like a section header / label (not a real value).
    e.g. "VENDOR/SERVICEPROVIDER", "CLIENT SIGNATURE  VENDOR SIGNATURE"
    """
    if not val:
        return False
    v = val.strip()
    # All uppercase with no digits = likely a label/header
    v_no_space = v.replace("/", "").replace("-", "").replace("_", "").replace(" ", "")
    if v_no_space.isupper() and not any(c.isdigit() for c in v) and len(v) < 80:
        return True
    # First word is a known label word (all caps)
    first_word = v.split()[0].lower().rstrip("/") if v.split() else ""
    if first_word in _LABEL_WORDS and v.split()[0].isupper():
        return True
    return False


def clean_text(text: str) -> str:
    out, blank = [], 0
    for line in text.splitlines():
        if _is_noise(line):
            continue
        if not line.strip():
            blank += 1
            if blank <= 2:
                out.append("")
        else:
            blank = 0
            out.append(line)
    return "\n".join(out).strip()


def _detect_currency(text: str) -> str:
    # 1. Currency symbols first ($ is most reliable for USD)
    # Scan larger portion of text since currency symbols may appear after page 1
    sample = text[:8000]
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in sample:
            return code
    # 2. Check keyword phrases with word boundaries
    sample_lower = " " + sample.lower() + " "
    # Also check full text for symbol
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in text:
            return code
    for kw, code in CURRENCY_KEYWORDS.items():
        # Use space-padded search to avoid partial matches (e.g. "sar" in "hadapsar")
        search = " " + kw.lower() + " "
        if search in sample_lower:
            return code
        # Also check with common delimiters
        for delim in ["(", ")", ",", ":", "."]:
            if kw.lower() + delim in sample_lower:
                return code
    return ""


# ───────────────────────────────────────────────────────────────────────
#  DATE
# ───────────────────────────────────────────────────────────────────────

def _fix_compressed(text: str) -> str:
    fixed = text
    for month in MONTH_NAMES:
        for v in [month.capitalize(), month.upper(), month]:
            idx = fixed.find(v)
            if idx == -1:
                continue
            after = fixed[idx + len(v):]
            if after and after[0].isdigit():
                fixed = fixed[:idx+len(v)] + " " + fixed[idx+len(v):]
                fixed = fixed.replace(",", ", ")
                break
    return fixed


def _parse_date(s: str) -> str:
    for sep in ["-", "/"]:
        if sep in s:
            parts = s.strip().split(sep)
            if len(parts) == 3:
                p0,p1,p2 = [p.strip().rstrip(".,;") for p in parts]
                if len(p0)==4 and all(x.isdigit() for x in [p0,p1,p2]):
                    return f"{p0}-{p1.zfill(2)}-{p2.zfill(2)}"
                if len(p2)==4 and all(x.isdigit() for x in [p0,p1,p2]):
                    return f"{p2}-{p1.zfill(2)}-{p0.zfill(2)}"
    words = s.replace(",", " ").split()
    for i, w in enumerate(words):
        key = w.lower().rstrip(".,;")
        if key in MONTH_NAMES:
            mn = w.rstrip(".,;")
            if i+2 < len(words):
                d, y = words[i+1].strip(".,;"), words[i+2].strip(".,;")
                if d.isdigit() and y.isdigit() and len(y)==4:
                    return f"{mn} {d.zfill(2)}, {y}"
            elif i+1 < len(words):
                y = words[i+1].strip(".,;")
                if y.isdigit() and len(y)==4:
                    return f"{mn} {y}"
    return ""


def _find_date(text: str) -> str:
    fixed = _fix_compressed(text)
    words = fixed.split()
    for window in range(4, 0, -1):
        for i in range(len(words) - window + 1):
            r = _parse_date(" ".join(words[i:i+window]))
            if r:
                return r
    return ""


# ───────────────────────────────────────────────────────────────────────
#  AMOUNT
# ───────────────────────────────────────────────────────────────────────

def _amounts(text: str) -> list[str]:
    found = []
    for sym in CURRENCY_SYMBOLS:
        idx = 0
        while True:
            pos = text.find(sym, idx)
            if pos == -1: break
            rest = text[pos+len(sym):].lstrip()
            tok = ""
            for ch in rest:
                if ch.isdigit() or ch in ".,": tok += ch
                else: break
            tok = tok.rstrip(".,")
            if tok: found.append(tok)
            idx = pos+1
    return found


def _largest(a: list[str]) -> str:
    if not a: return ""
    def _f(s):
        try: return float(s.replace(",",""))
        except: return 0.0
    return max(a, key=_f)


# ───────────────────────────────────────────────────────────────────────
#  SEGMENT MATCHER — tries all 4 formats on a single text segment
# ───────────────────────────────────────────────────────────────────────

def _match(seg: str, labels: list[str], min_label_len: int = 5) -> str:
    seg   = seg.strip()
    nseg  = _norm(seg)
    nsp_s = _nsp(seg)

    for label in labels:
        nl  = _norm(label)
        nsp = _nsp(label)
        if len(nsp) < min_label_len:
            continue

        # Format 1: "Label => Value"
        if " => " in seg:
            parts = seg.split(" => ", 1)
            if _nsp(parts[0]) == nsp:
                val = parts[1].strip().rstrip(".,;")
                if val: return val
            continue

        # Format 2a: "Label: Value" (spaces normalised)
        if nseg.startswith(nl + ":"):
            cp  = seg.lower().find(":")
            val = seg[cp+1:].strip().rstrip(".,;").split("|")[0].strip()
            if val and len(val) < 300: return val

        # Format 2b: "Label:Value" (no spaces anywhere)
        elif nsp_s.startswith(nsp + ":") and not nseg.startswith(nl + ":"):
            count, pos = 0, 0
            for ci, ch in enumerate(seg):
                if ch != " ": count += 1
                if count > len(nsp): pos = ci+1; break
            val = seg[pos:].strip().rstrip(".,;").split("|")[0].strip()
            if val and len(val) < 300: return val

        # Format 3: "Label Value" (space, label at start)
        elif nseg.startswith(nl + " ") and not nseg.startswith(nl+":"):
            val = seg[len(label):].strip().rstrip(".,;").split("|")[0].strip()
            if val and 1 < len(val) < 300 and not _looks_like_label(val): return val

        # Format 4: "LabelValue" (no space at all — e.g. SOWStartDate)
        elif nsp_s.startswith(nsp) and len(nsp) >= 6 and not nseg.startswith(nl):
            count, pos = 0, 0
            for ci, ch in enumerate(seg):
                if ch != " ": count += 1
                if count >= len(nsp): pos = ci+1; break
            val = seg[pos:].strip().lstrip(":").strip().rstrip(".,;").split("|")[0].strip()
            # Guard: reject if remainder looks like a label or is just lowercase letters
            # (means we matched a prefix of a longer label word, e.g. "MSARef" in "MSAReference")
            if val and 1 < len(val) < 300 and not _looks_like_label(val):
                # Additional guard: first char should be uppercase, digit, $, or -
                first = val[0] if val else ""
                if first.isupper() or first.isdigit() or first in ("$", "-", "₹", "€", "£"):
                    return val

    return ""


# ───────────────────────────────────────────────────────────────────────
#  HEADER-THEN-VALUE: "VENDOR / SERVICE PROVIDER\nNexaCore Technologies"
# ───────────────────────────────────────────────────────────────────────

def _after_header(lines: list[str], labels: list[str]) -> str:
    """
    Match a line that IS exactly a label (like "CLIENT" or "VENDOR / SERVICE PROVIDER")
    and return the next non-empty line as the value.
    """
    for i, line in enumerate(lines):
        nl_line = _nsp(line.strip())
        for label in labels:
            if len(_nsp(label)) < 5:
                continue
            if nl_line == _nsp(label):
                for next_line in lines[i+1:i+4]:
                    nl = next_line.strip()
                    if nl and not _is_noise(nl) and len(nl) > 2:
                        # Skip address lines (contain digits at start or commas)
                        if not (nl[0].isdigit() or nl.startswith("P.O")):
                            return nl
    return ""


# ───────────────────────────────────────────────────────────────────────
#  SAME-LINE DUAL COLUMN: "CLIENT    NexaCore Technologies"
#  Handles lines where both CLIENT and VENDOR appear on same line
# ───────────────────────────────────────────────────────────────────────

def _same_line_dual(lines: list[str], labels: list[str], field: str) -> str:
    """
    For lines like: "  Pinnacle Digital Corp    NexaCore Technologies Pvt. Ltd."
    that appear IMMEDIATELY after a "CLIENT  VENDOR / SERVICE PROVIDER" header line.
    Client = left part, Vendor = right part.
    Only matches on the FIRST non-empty line after the dual header.
    """
    import re
    is_vendor = any(kw in field for kw in ["vendor", "provider", "supplier"])
    is_client = any(kw in field for kw in ["client", "customer", "buyer"])

    for i, line in enumerate(lines):
        if i == 0:
            continue
        prev = _norm(lines[i-1])
        # Previous line must be a dual-header (has both client and vendor keywords)
        has_client = "client" in prev
        has_vendor = "vendor" in prev or "service provider" in prev
        if not (has_client and has_vendor):
            continue

        stripped = line.strip()
        if not stripped:
            continue

        # Split by 3+ spaces (column separator in layout text)
        parts = [p.strip() for p in re.split(r"   +", stripped) if p.strip()]
        if len(parts) >= 2:
            left, right = parts[0], parts[-1]
            # Skip if looks like address or signature line
            if left and not left[0].isdigit() and "signature" not in left.lower():
                if is_client:
                    return left
                if is_vendor:
                    return right
        break  # Only check first line after header
    return ""


# ───────────────────────────────────────────────────────────────────────
#  MASTER EXTRACTOR
# ───────────────────────────────────────────────────────────────────────

def _extract(full_text: str, lines: list[str], labels: list[str], field: str = "") -> str:
    candidates: list[tuple[int, str]] = []

    for line in lines:
        if _is_noise(line): continue
        stripped = line.strip()
        if not stripped: continue

        segs = [s.strip() for s in stripped.split("|")] if "|" in stripped else [stripped]
        for seg in segs:
            val = _match(seg, labels)
            if val:
                candidates.append((len(val), val))

    # Add _after_header as candidate (included in sort so shortest wins)
    val_ah = _after_header(lines, labels)
    if val_ah:
        candidates.append((len(val_ah), val_ah))

    # Add same-line dual as candidate
    if field in ("vendor_name", "client_name"):
        val_sd = _same_line_dual(lines, labels, field)
        if val_sd:
            candidates.append((len(val_sd), val_sd))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # Full-text inline scan (last resort)
    text_lower = full_text.lower()
    for label in labels:
        nl  = _norm(label)
        nsp = _nsp(label)
        if len(nsp) < 4: continue
        for search in [nl + ":", nsp + ":"]:
            pos = text_lower.find(search)
            if pos == -1: continue
            after = full_text[pos+len(search):].strip()
            val = ""
            for ch in after:
                if ch in "\n|": break
                val += ch
            val = val.strip().rstrip(".,;)")
            if val and 1 < len(val) < 300:
                return val

    return ""


def _fallback_scan(lines: list[str], known: list[str]) -> str:
    for line in lines:
        norm = _norm(line)
        for val in known:
            nv = val.lower()
            if nv.endswith("-") or len(nv) <= 7:
                for word in norm.split():
                    if word.startswith(nv): return word
            if nv in norm.split() or norm == nv: return val
    return ""


# ───────────────────────────────────────────────────────────────────────
#  TOTAL AMOUNT
# ───────────────────────────────────────────────────────────────────────

def _extract_total(full_text: str, lines: list[str], labels: list[str]) -> str:
    val = _extract(full_text, lines, labels)
    if val:
        for sym in CURRENCY_SYMBOLS:
            if sym in val:
                pos = val.find(sym)
                rest = val[pos+1:].lstrip()
                num = ""
                for ch in rest:
                    if ch.isdigit() or ch == ",": num += ch
                    else: break
                if num: return f"{sym}{num}"
        return val
    for line in lines:
        if _norm(line).startswith("total"):
            a = _amounts(line)
            if a: return f"${_largest(a)}"
    a = _amounts(full_text)
    if a: return f"${_largest(a)}"
    return ""


# ───────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ───────────────────────────────────────────────────────────────────────

def extract_structured(text: str) -> tuple[dict, dict]:
    """Extract all structured fields. Generic — works on any PDF format."""
    clean = clean_text(text)
    lines = clean.splitlines()

    d: dict = {f: None for f in STRUCTURED_FIELDS}
    c: dict = {f: 0.0  for f in STRUCTURED_FIELDS}

    for field in STRUCTURED_FIELDS:
        cfg   = STRUCTURED_FIELD_DICTIONARY.get(field, {})
        labels     = cfg.get("labels", [])
        value_type = cfg.get("value_type", "text")
        fallback   = cfg.get("fallback_scan", [])

        if field == "total_amount":
            val = _extract_total(clean, lines, labels)
            if val: d[field]=val; c[field]=1.0
            continue

        # Special: if currency not found via labels, detect from doc context
        if field == "currency" and not d.get("currency"):
            pass  # handled below with fallback

        raw = _extract(clean, lines, labels, field)

        if not raw and fallback:
            raw = _fallback_scan(lines, fallback)

        if not raw:
            continue

        if value_type == "date":
            dv = _find_date(raw)
            if dv: d[field]=dv; c[field]=1.0

        elif value_type == "currency_code":
            nr = _norm(raw)
            resolved = CURRENCY_KEYWORDS.get(nr, "")
            if not resolved:
                for sym, code in CURRENCY_SYMBOLS.items():
                    if sym in raw: resolved=code; break
            if not resolved and len(raw.strip())==3 and raw.strip().isalpha():
                resolved = raw.strip().upper()
            d[field] = resolved or raw
            c[field] = 1.0

        else:
            d[field] = raw
            c[field] = 1.0

    # Currency fallback: if not extracted via labels, detect from document
    if not d.get("currency"):
        detected = _detect_currency(clean)
        if detected:
            d["currency"] = detected
            c["currency"] = 0.8

    return d, c