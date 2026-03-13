from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import re
from racing_ai_core import RacingAICore, RaceInfo, Runner, classify_wet_dry

app = FastAPI(title="PeakPace AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = RacingAICore()


# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def parse_weight_to_lbs(weight_str: str) -> int:
    """Converts '10-3' (10 stone 3 lbs) into total lbs."""
    try:
        stone, pounds = weight_str.split("-")
        stone = int(stone.strip())
        pounds = int(pounds.strip())
        if pounds >= 14:
            raise ValueError()
        return stone * 14 + pounds
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid weight format: {weight_str}")


def parse_distance_to_furlongs(distance_str: str) -> int:
    """
    Accepts: 6f | 1m | 1m4f | 2m | 2m 4f
    """
    distance_str = distance_str.lower().strip().replace(" ", "")
    miles = 0
    furlongs = 0
    mile_match = re.search(r"(\d+)m", distance_str)
    furlong_match = re.search(r"(\d+)f", distance_str)
    if mile_match:
        miles = int(mile_match.group(1))
    if furlong_match:
        furlongs = int(furlong_match.group(1))
    total = miles * 8 + furlongs
    if total == 0:
        raise HTTPException(status_code=400, detail=f"Invalid distance format: {distance_str}")
    return total


def normalize_going(going: str) -> str:
    """Validate and normalise a going string.

    Accepts all standard going values plus "not_specified" (and empty string),
    which are treated as 'no detailed going available' and stored as "".
    """
    g = going.lower().strip()
    if g in ("not_specified", ""):
        return ""
    allowed = [
        "heavy", "soft", "good to soft", "good",
        "good to firm", "firm", "standard",
    ]
    if g not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid going condition: {going}")
    return g


# -------------------------------------------------
# MODELS
# -------------------------------------------------

class RunnerInput(BaseModel):
    name: str
    age: int
    weight: str
    form: Optional[str] = ""
    trainer: str
    jockey: str
    draw: Optional[int] = None
    jockey_claim_lbs: Optional[int] = 0
    comment: Optional[str] = ""
    equipment: Optional[str] = ""
    previous_runs: Optional[List[dict]] = None


class AnalyzeRequest(BaseModel):
    course: str
    country: str
    race_type: str
    surface: str
    distance: str
    going: str
    runners: List[RunnerInput]
    odds: Optional[Dict[str, str]] = None
    dark_horse_enabled: bool = False
    ground_bucket: Optional[str] = None  # "Wet" | "Dry" | None — explicit override


class TextRaceInput(BaseModel):
    course: str = "Unknown"
    country: str = "UK"
    race_type: str = "flat"
    surface: str = "aw"
    distance: str = "8f"
    going: str = "good"
    ground_bucket: Optional[str] = None  # "Wet" | "Dry" | None — explicit override


class AnalyzeTextRequest(BaseModel):
    race_info: TextRaceInput
    racecard_text: str
    odds: Optional[Dict[str, str]] = None
    dark_horse_enabled: bool = False


class RaceQualityRequest(BaseModel):
    course: str = "Unknown"
    country: str = "UK"
    race_type: str = "flat"
    surface: str = "aw"
    distance: str = "8f"
    going: str = "good"
    runners: List[RunnerInput]
    ground_bucket: Optional[str] = None  # "Wet" | "Dry" | None — explicit override


class RaceQualityTextRequest(BaseModel):
    race_info: TextRaceInput
    racecard_text: str


# -------------------------------------------------
# RACE HEADER PARSING — optional fields from the
# section that precedes the first HORSE: block.
# -------------------------------------------------

# Known UK courses for unstructured course extraction.
_UK_COURSES = frozenset({
    "ascot", "cheltenham", "goodwood", "york", "newmarket", "epsom", "sandown",
    "haydock", "newbury", "chester", "aintree", "doncaster", "leicester",
    "kempton", "lingfield", "wolverhampton", "nottingham", "windsor",
    "catterick", "pontefract", "carlisle", "musselburgh", "ayr", "perth",
    "chelmsford", "yarmouth", "brighton", "salisbury", "bath", "chepstow",
    "exeter", "taunton", "newton abbot", "hereford", "ludlow", "worcester",
    "stratford", "huntingdon", "wetherby", "uttoxeter", "market rasen",
    "fakenham", "cartmel", "towcester", "wincanton", "plumpton", "folkestone",
    "newcastle", "redcar", "thirsk", "ripon", "beverley", "hamilton",
    "musselburgh", "perth", "kelso", "hexham", "sedgefield", "bangor",
})

# Structured header line:  COURSE: Newcastle  /  DISTANCE: 6f  / …
# GROUND: Wet | GROUND: Dry is also supported as an explicit override.
# "GOING / GROUND:" must be listed before bare "GOING" and "GROUND" so the
# longer token matches first on lines like "GOING / GROUND: Good to Soft".
_HEADER_STRUCTURED_RE = re.compile(
    r"^(COURSE|DISTANCE|RUNNERS?|CLASS|TYPE|RACE(?:[\s_]NAME)?|GOING\s*/\s*GROUND|GOING|GROUND)\s*:\s*(.+)",
    re.I,
)

# Distance pattern used in the unstructured header (e.g. "6f", "2m4f", "1m 2f")
_DIST_HEADER_RE = re.compile(r"\b(\d+m(?:\s*\d+f)?|\d+f)\b", re.I)

# "8 Runners" / "12 runner"
_RUNNERS_HEADER_RE = re.compile(r"\b(\d+)\s+[Rr]unners?\b")

# "Class 6" / "Class A"
_CLASS_HEADER_RE = re.compile(r"\bClass\s+([1-9A-F])\b", re.I)

# Meeting-type keywords (what kind of race, not Flat vs Jumps)
_MEETING_TYPE_RE = re.compile(
    r"\b(Handicap|Hcap|Maiden|Novice|Stakes|Conditions|Listed|"
    r"Group\s+\d|Grade\s+\d|Claimer|Claiming|Selling|Seller|"
    r"Apprentice|Amateur)\b",
    re.I,
)

# ── Discipline detection — 3-level priority system ────────────────────────────
#
# Level 1: TYPE: field in the structured header (user override — highest priority)
# Level 2: Explicit keywords anywhere in the header text
# Level 3: Distance fallback (≥ 2m2f = 18f → Jumps, else → Flat)
#
# Check Jumps sub-types longest-first so "Novice Hurdle" beats bare "Hurdle".
_DISC_JUMPS_SUBTYPES: List[tuple] = [
    (re.compile(r"\b(hunter\s+chase)\b",                              re.I), "Chase"),
    (re.compile(r"\b(novice\s+chase|beginners?\s+chase)\b",           re.I), "Chase"),
    (re.compile(r"\b(steeplechase|chasing)\b",                        re.I), "Chase"),
    (re.compile(r"\b(chase)\b",                                       re.I), "Chase"),
    (re.compile(r"\b(novice\s+hurdle|maiden\s+hurdle)\b",             re.I), "Hurdle"),
    (re.compile(r"\b(hurdles?)\b",                                    re.I), "Hurdle"),
    (re.compile(r"\b(nh\s+flat|national\s+hunt\s+flat|bumper)\b",     re.I), "NH Flat"),
]

# Explicit Flat surface/discipline keywords
_DISC_FLAT_RE = re.compile(
    r"\b(flat\b|all[\s\-]weather|tapeta|polytrack)\b|\bAW\b", re.I
)

# TYPE: field values that map directly to a discipline (level 1 override)
_TYPE_OVERRIDE_MAP = {
    "flat":     {"discipline": "Flat",  "subtype": None},
    "hurdle":   {"discipline": "Jumps", "subtype": "Hurdle"},
    "hurdles":  {"discipline": "Jumps", "subtype": "Hurdle"},
    "chase":    {"discipline": "Jumps", "subtype": "Chase"},
    "nh flat":  {"discipline": "Jumps", "subtype": "NH Flat"},
    "nh_flat":  {"discipline": "Jumps", "subtype": "NH Flat"},
    "bumper":   {"discipline": "Jumps", "subtype": "NH Flat"},
    # "TYPE: Jumps" — generic jumps override without subtype
    "jumps":    {"discipline": "Jumps", "subtype": None},
    "national hunt": {"discipline": "Jumps", "subtype": None},
}

# Distance threshold for the distance fallback: 2m2f = 18 furlongs
_JUMPS_MIN_FURLONGS = 18


def _safe_parse_furlongs(dist_str: str) -> Optional[int]:
    """Parse a header distance string to furlongs without raising.

    Handles e.g. '6f', '2m', '2m4f', '2m 4f'. Returns None on failure.
    """
    try:
        s = dist_str.lower().strip().replace(" ", "")
        miles = 0
        furlongs = 0
        mm = re.search(r"(\d+)m", s)
        ff = re.search(r"(\d+)f", s)
        if mm:
            miles = int(mm.group(1))
        if ff:
            furlongs = int(ff.group(1))
        total = miles * 8 + furlongs
        return total if total > 0 else None
    except Exception:
        return None


def _extract_header_section(text: str) -> str:
    """Return the text that appears before the first HORSE: block."""
    m = re.search(r"^HORSE\s*:", text, re.I | re.M)
    return text[:m.start()].strip() if m else ""


def parse_racecard_header(text: str) -> dict:
    """Parse optional race-level metadata from the header section.

    The header is everything before the first ``HORSE:`` line.
    All returned fields may be ``None`` when not found.

    Supports both formats:
      Unstructured: "Newcastle Apprentice Handicap 6f • 8 Runners • Class 6"
      Structured:   "COURSE: Newcastle\\nDISTANCE: 6f\\n..."
    """
    header = _extract_header_section(text)
    result: dict = {
        "course":        None,
        "race_name":     None,
        "distance":      None,
        "field_size":    None,
        "race_class":    None,
        "race_type":     None,   # meeting type: Handicap / Maiden / etc.
        "going":         None,   # raw going string (from GOING / GROUND: or GOING:)
        "ground_bucket": None,   # "Wet" | "Dry" | None — from explicit GROUND: field
    }
    if not header:
        return result

    # ── Pass 1: structured key:value lines ───────────────────────────────────
    for line in header.split("\n"):
        m = _HEADER_STRUCTURED_RE.match(line.strip())
        if not m:
            continue
        key = m.group(1).strip().lower()
        val = m.group(2).strip()
        if "course" in key:
            result["course"] = val
        elif "distance" in key:
            result["distance"] = val
        elif "runner" in key:
            nm = re.search(r"\d+", val)
            if nm:
                result["field_size"] = int(nm.group())
        elif "class" in key:
            result["race_class"] = val
        elif "race" in key or "name" in key:
            result["race_name"] = val
        elif key == "type":
            result["race_type"] = val
        elif "going" in key:
            # Matches "going", "going / ground" — store raw going string and
            # derive the Wet/Dry bucket so downstream logic gets it even when
            # the racecard uses "GOING / GROUND: Good to Soft" instead of a
            # separate "GROUND: Wet" line.
            result["going"] = val
            if result["ground_bucket"] is None:
                result["ground_bucket"] = classify_wet_dry(val)
        elif key == "ground":
            # Explicit GROUND: Wet / GROUND: Dry field — highest priority
            gb = val.strip().capitalize()
            if gb in ("Wet", "Dry"):
                result["ground_bucket"] = gb

    # ── Pass 2: unstructured patterns on any non-structured line ─────────────
    all_known_courses = _IRISH_COURSES | _UK_COURSES
    for line in header.split("\n"):
        if _HEADER_STRUCTURED_RE.match(line.strip()):
            continue   # already handled above
        lt = line.lower()

        if result["course"] is None:
            for course in all_known_courses:
                if course in lt:
                    idx = lt.index(course)
                    result["course"] = line[idx: idx + len(course)].strip().title()
                    break

        if result["distance"] is None:
            dm = _DIST_HEADER_RE.search(line)
            if dm:
                result["distance"] = dm.group(1).replace(" ", "")

        if result["field_size"] is None:
            rm = _RUNNERS_HEADER_RE.search(line)
            if rm:
                result["field_size"] = int(rm.group(1))

        if result["race_class"] is None:
            cm = _CLASS_HEADER_RE.search(line)
            if cm:
                result["race_class"] = f"Class {cm.group(1).upper()}"

        if result["race_type"] is None:
            tm = _MEETING_TYPE_RE.search(line)
            if tm:
                result["race_type"] = tm.group(1).strip().title()

    return result


def detect_discipline(header_text: str) -> dict:
    """Detect race discipline using a strict 3-level priority system.

    Level 1 — TYPE: override (highest priority)
        TYPE: Flat / Hurdle / Chase / NH Flat in the structured header
        immediately resolves discipline; no further checks needed.

    Level 2 — Keyword detection
        Searches the header for explicit Jumps or Flat keywords.
        Jumps sub-types are matched longest-first to avoid ambiguity
        (e.g. "NH Flat" must not match bare "flat").

    Level 3 — Distance fallback (only when levels 1 & 2 both fail)
        distance ≥ 2m2f (18f) → Jumps
        distance < 2m2f       → Flat
        If no distance is in the header either → "Unknown".

    Returns:
        {"discipline": "Flat" | "Jumps" | "Unknown",
         "subtype":    "Hurdle" | "Chase" | "NH Flat" | None}
    """
    # ── Level 1: TYPE: field override ────────────────────────────────────────
    for line in header_text.split("\n"):
        m = re.match(r"^TYPE\s*:\s*(.+)", line.strip(), re.I)
        if m:
            type_val = m.group(1).strip().lower()
            if type_val in _TYPE_OVERRIDE_MAP:
                return dict(_TYPE_OVERRIDE_MAP[type_val])
            # TYPE: is present but its value is a meeting type (e.g. "Handicap"),
            # not a discipline word — fall through to keyword detection.
            break

    # ── Level 2: keyword detection ───────────────────────────────────────────
    # Jumps checked before Flat because "NH Flat" contains the word "flat".
    for pattern, subtype in _DISC_JUMPS_SUBTYPES:
        if pattern.search(header_text):
            return {"discipline": "Jumps", "subtype": subtype}

    if _DISC_FLAT_RE.search(header_text):
        return {"discipline": "Flat", "subtype": None}

    # ── Level 3: distance fallback ───────────────────────────────────────────
    dm = _DIST_HEADER_RE.search(header_text)
    if dm:
        dist_f = _safe_parse_furlongs(dm.group(1))
        if dist_f is not None:
            if dist_f >= _JUMPS_MIN_FURLONGS:
                return {"discipline": "Jumps", "subtype": None}
            return {"discipline": "Flat", "subtype": None}

    return {"discipline": "Unknown", "subtype": None}


def _discipline_display(discipline: str, subtype: Optional[str]) -> str:
    """Return the UI-facing discipline label."""
    if subtype:
        return f"Race: Jumps ({subtype})"
    if discipline != "Unknown":
        return f"Race: {discipline}"
    return "Race: Unknown"


def _discipline_from_race_type(race_type: str) -> dict:
    """Derive discipline for manual-entry mode from the user-selected race_type.

    Manual-entry users explicitly choose their race type, so the discipline
    is always known (never "Unknown").
    """
    if race_type == "national_hunt":
        return {"discipline": "Jumps", "subtype": None}
    if race_type == "flat":
        return {"discipline": "Flat", "subtype": None}
    return {"discipline": "Unknown", "subtype": None}


# -------------------------------------------------
# SHARED TEXT PARSER
# -------------------------------------------------

FIELD_KEYS = re.compile(
    r"(Age|Weight|Trainer|Jockey|Form|F|Odds|Comment|Equipment)\s*:", re.I
)

# Words that can appear directly before a field key but are NOT horse names.
# e.g. "Recent Form: 123" — "Recent" must not become a runner.
_LABEL_NOISE = frozenset({"recent", "last", "previous", "latest", "current"})

# Racing Post / racecard metadata lines that are NOT horse names and should be
# silently skipped rather than treated as new runner boundaries.
_NOISE_PREFIX_RE = re.compile(
    r"^(official\s+rating|pedigree|bred|colour|color|sex|owner|"
    r"prize|silks|rpr|or|sire|dam|breeder|rating|ran|p\.?p\.?|"
    r"weight\s+carried|trainer\s+form|jockey\s+form|stable|"
    r"date\s*\|?\s*course)\s*[:\|]",
    re.I,
)


def _extract_fields(current: dict, text: str):
    """Pull Age/Weight/Trainer/Jockey/Form from a text fragment.

    Splits on field-key boundaries so each regex only sees its own
    key:value pair — prevents greedy `.+` from swallowing later fields.
    """
    parts = FIELD_KEYS.split(text)
    tokens = []
    i = 1  # parts[0] is text before first key (usually empty)
    while i < len(parts) - 1:
        tokens.append(parts[i] + ":" + parts[i + 1])
        i += 2

    for token in (tokens if tokens else [text]):
        m = re.search(r"age[:\s]+(\d+)", token, re.I)
        if m:
            current["age"] = int(m.group(1))
        m = re.search(r"weight[:\s]+([\d\-]+)", token, re.I)
        if m:
            current["weight"] = m.group(1)
        m = re.search(r"trainer[:\s]+(.+)", token, re.I)
        if m:
            current["trainer"] = m.group(1).strip()
        m = re.search(r"jockey[:\s]+(.+)", token, re.I)
        if m:
            current["jockey"] = m.group(1).strip()
        m = re.search(r"(?:^f|form)[:\s]+([0-9A-Za-z/\-]+)", token, re.I)
        if m:
            current["form"] = m.group(1)
        m = re.search(r"odds[:\s]+([^\s]+)", token, re.I)
        if m:
            current["odds"] = m.group(1).strip()
        m = re.search(r"comment[:\s]+(.+)", token, re.I)
        if m:
            current["comment"] = m.group(1).strip().strip('"').strip("'")
        m = re.search(r"equipment[:\s]+(.+)", token, re.I)
        if m:
            current["equipment"] = m.group(1).strip()


def _prev_dist_to_furlongs(dist_str: str) -> Optional[float]:
    """Convert distance strings like '2m 4f 29y' or '1m 2f' to furlongs."""
    total = 0.0
    m = re.search(r"(\d+)\s*m", dist_str, re.I)
    if m:
        total += int(m.group(1)) * 8
    f = re.search(r"(\d+)\s*f", dist_str, re.I)
    if f:
        total += int(f.group(1))
    y = re.search(r"(\d+)\s*y", dist_str, re.I)
    if y:
        total += int(y.group(1)) / 220.0
    return round(total, 2) if total > 0 else None


# Recognise previous-run discipline labels
_DISCIPLINE_RE = re.compile(
    r"\b(chase|hurdle|flat|bumper|nh\s+flat|hunter\s+chase)\b", re.I
)

# Splits runs concatenated on a single line by date boundaries.
# Handles both "Jan 9 2026" (month-first) and "17 Jan 26" (day-first, canonical).
_DATE_BOUNDARY_RE = re.compile(
    r"\b(?:[A-Za-z]{3}\s+\d{1,2}|\d{1,2}\s+[A-Za-z]{3})\s+\d{2,4}\b"
)

# Matches the start of a previous-run line in either date order.
_DATE_LINE_RE = re.compile(
    r"^(?:[A-Za-z]{3}\s+\d{1,2}|\d{1,2}\s+[A-Za-z]{3})\s+\d{2,4}",
    re.I,
)


def _split_run_segments(text: str) -> list:
    """Return individual run-record strings from text that may contain several
    concatenated runs (each starting with a date token like 'Jan 9 2026')."""
    positions = [m.start() for m in _DATE_BOUNDARY_RE.finditer(text)]
    if not positions:
        return []
    chunks = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        chunks.append(text[pos:end].strip())
    return [c for c in chunks if c]

# Recognise going labels within a previous-run line segment
_GOING_WORDS = re.compile(
    r"\b(heavy|soft|good\s+to\s+soft|good\s+soft|good\s+to\s+firm|good|firm|"
    r"standard|yielding|soft\s+to\s+heavy|yielding\s+to\s+soft)\b", re.I
)


def _parse_prev_run_line(line: str) -> Optional[dict]:
    """Try to parse a previous run line such as:
        'Jan 9 26 — Naas — 2m 4f 29y — Soft — 7/7 — Chase'

    Identifies each segment by content rather than position so it is
    robust to different separator styles (em-dash, en-dash, plain dash).
    Returns a dict with going, distance_f, pos, field_size, discipline,
    or None if the line does not look like a previous run record.
    """
    # Must start with a date-like token in either order:
    #   "Jan 9 26" / "Jan 9 2026"  (month first)
    #   "17 Jan 26" / "17 Jan 2026" (day first — canonical format)
    if not _DATE_LINE_RE.match(line.strip()):
        return None

    # Split on em-dash / en-dash / spaced hyphen / pipe (|)
    parts = re.split(r"\s*[—–]\s*|\s+-\s+|\s*\|\s*", line)
    if len(parts) < 4:
        return None

    result: dict = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # N/A finish (fell, brought down, pulled up, etc.) — skip gracefully
        if re.match(r"^n/?a$", part, re.I):
            continue

        # pos/field_size  e.g. "7/7"  "6/13"
        pm = re.match(r"^(\d+)/(\d+)$", part)
        if pm:
            result["pos"]        = int(pm.group(1))
            result["field_size"] = int(pm.group(2))
            continue

        # distance  e.g. "2m 4f 29y"  "1m 2f"
        d = _prev_dist_to_furlongs(part)
        if d and d > 0:
            result["distance_f"] = d
            continue

        # discipline
        dm = _DISCIPLINE_RE.search(part)
        if dm:
            result["discipline"] = dm.group(1).lower().replace(" ", "_")
            continue

        # going (checked after discipline to avoid 'good to firm' confusion)
        gm = _GOING_WORDS.search(part)
        if gm:
            result["going"] = gm.group(1).lower()
            continue

    # Return if at least one useful signal was extracted.
    # pos+field_size may be absent for N/A finishes (falls etc.);
    # going and distance_f are still valuable for suitability scoring.
    if "going" in result or "distance_f" in result or "pos" in result:
        return result
    return None


def parse_racecard_text(text: str) -> list:
    """
    Tolerant parser for racecard-style text.

    Uses FIELD_KEYS regex to locate field boundaries in each line.
    If a field key starts after position 0, the text before it is the
    horse name.  This correctly handles both single-line-per-runner
    (e.g. "Horse A Age: 4 Weight: 9-4 Trainer: Smith Jockey: Doyle")
    and multi-line formats.

    Also extracts Comment:, Equipment:, and "Previous runs:" sections
    when present, attaching them to the most recent runner.

    Safe defaults are applied for any missing optional fields.
    Returns only entries that have a name AND at least one data field.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    runners = []
    current: dict = {}
    in_prev_runs = False
    comment_pending = False   # True when "COMMENT:" appeared alone on previous line

    for line in lines:
        # ── HORSE: prefix (Racing Post style) ────────────────────────────────
        # e.g. "HORSE: Karamoja" → name = "Karamoja"
        horse_m = re.match(r"^HORSE\s*:\s*(.+)", line, re.I)
        if horse_m:
            if current and "name" in current:
                runners.append(current)
            rest = horse_m.group(1).strip()
            # Single-line: "Karamoja JOCKEY: P. Townend TRAINER: ..."
            # Stop name at first field key; process the rest as fields.
            first_fk = FIELD_KEYS.search(rest)
            if first_fk:
                name = rest[:first_fk.start()].strip()
                # _from_horse_header=True: keep this runner even if all other
                # fields are blank (guided-entry mode where user leaves fields empty).
                current = {"name": name, "_from_horse_header": True}
                _extract_fields(current, rest[first_fk.start():])
            else:
                current = {"name": rest, "_from_horse_header": True}
            in_prev_runs = False
            comment_pending = False
            continue

        # ── Known Racing Post metadata lines — skip silently ─────────────────
        # e.g. "PEDIGREE: ...", "BRED: F", "OFFICIAL RATING: 0"
        # These must NOT become runner-name boundaries.
        if _NOISE_PREFIX_RE.match(line):
            continue

        # ── Comment text on the line following a bare "COMMENT:" label ───────
        if comment_pending and current:
            current["comment"] = line.strip().strip('"').strip("'")
            comment_pending = False
            continue

        # ── Previous runs section header ─────────────────────────────────────
        # Accepts: "Previous runs:", "Previous run:", "Recent runs:", "Recent run:"
        rr_m = re.match(r"(?:previous|recent)\s+runs?\s*:?\s*(.*)", line, re.I)
        if rr_m:
            in_prev_runs = True
            current.setdefault("previous_runs", [])
            # Runs may appear on the same line as the header (single-line format).
            # Multiple runs can be concatenated; split by date boundaries.
            inline = rr_m.group(1).strip()
            if inline:
                for seg in _split_run_segments(inline):
                    pr = _parse_prev_run_line(seg)
                    if pr is not None:
                        current["previous_runs"].append(pr)
            continue

        # ── Previous run record ──────────────────────────────────────────────
        if in_prev_runs and current:
            # Skip column-header lines (e.g. "Date | Course | Distance | …")
            if re.match(r"^date\b", line, re.I):
                continue
            pr = _parse_prev_run_line(line)
            if pr is not None:
                current["previous_runs"].append(pr)
                continue
            # Line didn't match a single run — try splitting as concatenated runs
            segments = _split_run_segments(line)
            if segments:
                any_parsed = False
                for seg in segments:
                    pr = _parse_prev_run_line(seg)
                    if pr is not None:
                        current["previous_runs"].append(pr)
                        any_parsed = True
                if any_parsed:
                    continue
            in_prev_runs = False   # non-matching line exits the section

        # ── Bare "COMMENT:" label with no inline text ─────────────────────────
        if re.match(r"^comment\s*:\s*$", line, re.I):
            comment_pending = True
            continue

        # ── Normal field parsing ─────────────────────────────────────────────
        first_field = FIELD_KEYS.search(line)

        if first_field and first_field.start() > 0:
            # Text before first field key = horse name (unless it's a known label word)
            name_part = line[:first_field.start()].strip()
            if name_part and name_part.lower() not in _LABEL_NOISE:
                if current and "name" in current:
                    runners.append(current)
                current = {"name": name_part}
                in_prev_runs = False
            _extract_fields(current, line[first_field.start():])

        elif first_field and first_field.start() == 0:
            # Line starts with a field key (e.g. "Age: 4" or "Comment: ...")
            _extract_fields(current, line)

        else:
            # No field key at all — entire line is a horse name
            if current and "name" in current:
                runners.append(current)
            current = {"name": line}
            in_prev_runs = False

    # Finalise the last runner
    if current and "name" in current:
        runners.append(current)

    # Build clean list.
    # Runners introduced by an explicit "HORSE:" line are kept even when all
    # other fields are blank — this supports guided/canonical-entry mode where
    # the user may leave optional fields empty.
    # Runners that appear only as bare name lines (freeform junk / headers) are
    # still filtered out unless they carry at least one data field.
    cleaned = []
    for r in runners:
        if "name" not in r:
            continue
        has_data = any(k in r for k in ("age", "weight", "jockey", "trainer", "form"))
        if not has_data and not r.get("_from_horse_header"):
            continue
        cleaned.append({
            "name":          r["name"],
            "age":           r.get("age", 4),
            "weight":        r.get("weight", "9-4"),
            "form":          r.get("form", ""),
            "trainer":       r.get("trainer", ""),
            "jockey":        r.get("jockey", ""),
            "odds":          r.get("odds", ""),
            "comment":       r.get("comment", ""),
            "equipment":     r.get("equipment", ""),
            "previous_runs": r.get("previous_runs") or None,
        })

    return cleaned


# -------------------------------------------------
# ANALYZE MANUAL
# -------------------------------------------------

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if len(request.runners) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 runners.")

    # Discipline is always known in manual mode — user explicitly chose race_type.
    disc = _discipline_from_race_type(request.race_type)

    # Ground bucket: explicit manual override, or inferred from going
    going_normalised = normalize_going(request.going)
    ground_bucket = _resolve_ground_bucket(
        text_ground=None,
        manual_ground=request.ground_bucket,
        inferred_going=going_normalised,
    )

    race = RaceInfo(
        course=request.course,
        country=request.country,
        race_type=request.race_type,
        surface=request.surface,
        distance_f=parse_distance_to_furlongs(request.distance),
        going=going_normalised,
        runners=len(request.runners),
        discipline=disc["discipline"],
        discipline_subtype=disc["subtype"],
        ground_bucket=ground_bucket,
    )

    runner_objects = []
    for r in request.runners:
        runner_objects.append(
            Runner(
                name=r.name,
                age=r.age,
                weight_lbs=parse_weight_to_lbs(r.weight),
                form=r.form or "",
                trainer=r.trainer,
                jockey=r.jockey,
                draw=r.draw,
                jockey_claim_lbs=r.jockey_claim_lbs or 0,
                comment=r.comment or "",
                equipment=r.equipment or "",
                previous_runs=r.previous_runs,
            )
        )

    engine.dark_horse_enabled = request.dark_horse_enabled
    result = engine.analyze(race, runner_objects, odds=request.odds)

    result["discipline"]         = disc["discipline"]
    result["discipline_subtype"] = disc["subtype"]
    result["discipline_display"] = _discipline_display(disc["discipline"], disc["subtype"])
    result["ground_bucket"]      = ground_bucket
    result["wet_jumps_mode"]     = (disc["discipline"] == "Jumps" and ground_bucket == "Wet")
    result["_build"]             = "tipster_v3"
    return result


# -------------------------------------------------
# RACE TYPE + COUNTRY AUTO-DETECTION (paste text only)
# -------------------------------------------------

_NH_DETECT = re.compile(
    r"hurdle|chase|steeplechase|novice\s+hurdle|novice\s+chase"
    r"|beginners?\s+chase|bumper|nh\s+flat|national\s+hunt"
    r"|hunter\s+chase|cross\s+country|point-to-point",
    re.I,
)

_IRISH_COURSES = frozenset({
    "leopardstown", "fairyhouse", "punchestown", "curragh", "the curragh",
    "galway", "cork", "limerick", "naas", "navan", "dundalk",
    "tipperary", "gowran park", "killarney", "sligo", "tramore",
    "wexford", "ballinrobe", "bellewstown", "clonmel", "downpatrick",
    "kilbeggan", "laytown", "listowel", "roscommon", "thurles",
})


def detect_race_type(text: str) -> str:
    """Classify pasted racecard text as national_hunt or flat."""
    if _NH_DETECT.search(text):
        return "national_hunt"
    return "flat"


def detect_country(text: str) -> str:
    """Detect country (ireland / uk) from pasted racecard text.

    Scans for known Irish course names and keywords.
    Defaults to 'uk' when no Irish indicators are found.
    """
    t = text.lower()
    if "ireland" in t or "irish" in t:
        return "ireland"
    for course in _IRISH_COURSES:
        if course in t:
            return "ireland"
    return "uk"


# Ordered longest-first so multi-word phrases match before single words
_GOING_MAP = [
    ("soft to heavy",    "heavy"),
    ("yielding to soft", "soft"),
    ("good to soft",     "good to soft"),
    ("good to yielding", "good to soft"),
    ("good to firm",     "good to firm"),
    ("heavy",            "heavy"),
    ("testing",          "heavy"),
    ("yielding",         "soft"),
    ("soft",             "soft"),
    ("firm",             "firm"),
    ("standard",         "standard"),
    ("good",             "good"),
]


def detect_going(text: str) -> Optional[str]:
    """Extract going condition from pasted racecard text.

    Maps phrases like 'yielding' → 'soft' so the result always satisfies
    normalize_going().  Returns None when nothing is detected.
    """
    t = text.lower()
    for keyword, canonical in _GOING_MAP:
        if keyword in t:
            return canonical
    return None


# Matches an explicit "GROUND: Wet" or "GROUND: Dry" field anywhere in the text.
_GROUND_BUCKET_RE = re.compile(r"^\s*GROUND\s*:\s*(Wet|Dry)\s*$", re.I | re.M)


def detect_ground_bucket(text: str) -> Optional[str]:
    """Return an explicit Wet/Dry ground bucket from pasted racecard text.

    Only matches explicit ``GROUND: Wet`` or ``GROUND: Dry`` lines.
    Returns None when the field is absent — the caller infers from going instead.
    This never over-rides going detection; the two fields are independent.
    """
    m = _GROUND_BUCKET_RE.search(text)
    if m:
        return m.group(1).capitalize()
    return None


def _resolve_ground_bucket(
    text_ground: Optional[str],   # from paste GROUND: field
    manual_ground: Optional[str], # from manual-entry field
    inferred_going: str,          # the going string to infer from as fallback
) -> Optional[str]:
    """Apply 3-way priority logic to resolve the final ground bucket.

    Priority:
      1. Explicit paste GROUND: Wet / GROUND: Dry  (highest)
      2. Explicit manual-entry ground_bucket
      3. Inferred from detailed going string
    """
    if text_ground is not None:
        return text_ground
    if manual_ground is not None:
        gb = manual_ground.capitalize()
        if gb in ("Wet", "Dry"):
            return gb
    return classify_wet_dry(inferred_going)


# -------------------------------------------------
# ANALYZE TEXT (PASTE MODE)
# -------------------------------------------------

@app.post("/analyze-text")
def analyze_text(request: AnalyzeTextRequest):
    # ── Header metadata (optional — never raises on failure) ─────────────────
    header_info = parse_racecard_header(request.racecard_text)

    # ── Discipline: from header only, no guessing ─────────────────────────────
    header_section = _extract_header_section(request.racecard_text)
    disc = detect_discipline(header_section)

    # ── Legacy auto-detects (unchanged) ──────────────────────────────────────
    detected_type    = detect_race_type(request.racecard_text)
    detected_country = detect_country(request.racecard_text)
    detected_going   = detect_going(request.racecard_text)

    runners = parse_racecard_text(request.racecard_text)

    if len(runners) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Found {len(runners)} runner(s). Need at least 2 to analyze a race.",
        )

    ri = request.race_info
    # Use detected going when found; fall back to header going, then user supplied.
    # Use header distance when found; fall back to what the user supplied.
    going_str    = detected_going or header_info.get("going") or ri.going or "good"
    distance_str = header_info["distance"] if header_info["distance"] is not None else ri.distance
    course_str   = header_info["course"]   if header_info["course"]   is not None else ri.course

    # ── Ground bucket: 3-way priority (paste > manual > inferred from going) ──
    ground_bucket = _resolve_ground_bucket(
        text_ground=header_info.get("ground_bucket") or detect_ground_bucket(request.racecard_text),
        manual_ground=ri.ground_bucket,
        inferred_going=going_str,
    )

    race = RaceInfo(
        course=course_str,
        country=detected_country,
        race_type=detected_type,
        surface=ri.surface,
        distance_f=parse_distance_to_furlongs(distance_str),
        going=normalize_going(going_str),
        runners=len(runners),
        discipline=disc["discipline"],
        discipline_subtype=disc["subtype"],
        ground_bucket=ground_bucket,
    )

    runner_objects = [
        Runner(
            name=r["name"],
            age=r["age"],
            weight_lbs=parse_weight_to_lbs(r["weight"]),
            form=r["form"],
            trainer=r["trainer"],
            jockey=r["jockey"],
            comment=r.get("comment", ""),
            equipment=r.get("equipment", ""),
            previous_runs=r.get("previous_runs"),
        )
        for r in runners
    ]

    # Build odds dict from inline ODDS: fields in the pasted racecard.
    # Request-level odds (if supplied) take precedence over inline ones.
    inline_odds = {r["name"]: r["odds"] for r in runners if r.get("odds")}
    merged_odds  = {**inline_odds, **(request.odds or {})}
    final_odds   = merged_odds if merged_odds else None

    engine.dark_horse_enabled = request.dark_horse_enabled
    result = engine.analyze(race, runner_objects, odds=final_odds)

    # ── Attach header + discipline + ground info to the response ─────────────
    result["race_header"]        = header_info
    result["discipline"]         = disc["discipline"]
    result["discipline_subtype"] = disc["subtype"]
    result["discipline_display"] = _discipline_display(disc["discipline"], disc["subtype"])
    result["ground_bucket"]      = ground_bucket
    result["wet_jumps_mode"]     = (disc["discipline"] == "Jumps" and ground_bucket == "Wet")
    result["_build"]             = "tipster_v3"
    return result


# -------------------------------------------------
# RACE QUALITY CHECK (pre-analysis endpoints)
# -------------------------------------------------

@app.post("/race-quality")
def race_quality(request: RaceQualityRequest):
    """Pre-analysis quality check for manually-entered runners."""
    going_normalised = normalize_going(request.going)
    ground_bucket = _resolve_ground_bucket(
        text_ground=None,
        manual_ground=request.ground_bucket,
        inferred_going=going_normalised,
    )
    race = RaceInfo(
        course=request.course,
        country=request.country,
        race_type=request.race_type,
        surface=request.surface,
        distance_f=parse_distance_to_furlongs(request.distance),
        going=going_normalised,
        runners=len(request.runners),
        ground_bucket=ground_bucket,
    )
    runner_objects = []
    for r in request.runners:
        runner_objects.append(Runner(
            name=r.name,
            age=r.age,
            weight_lbs=parse_weight_to_lbs(r.weight),
            form=r.form or "",
            trainer=r.trainer,
            jockey=r.jockey,
            draw=r.draw,
            jockey_claim_lbs=r.jockey_claim_lbs or 0,
        ))
    result = engine.race_quality_check(race, runner_objects)
    result["runner_names"] = [r.name for r in runner_objects]
    return result


@app.post("/race-quality-text")
def race_quality_text(request: RaceQualityTextRequest):
    """Pre-analysis quality check for paste-mode racecards."""
    header_info      = parse_racecard_header(request.racecard_text)
    header_section   = _extract_header_section(request.racecard_text)
    disc             = detect_discipline(header_section)

    detected_type    = detect_race_type(request.racecard_text)
    detected_country = detect_country(request.racecard_text)
    detected_going   = detect_going(request.racecard_text)

    runners = parse_racecard_text(request.racecard_text)
    if len(runners) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Found {len(runners)} runner(s). Need at least 2.",
        )

    ri           = request.race_info
    going_str    = detected_going    if detected_going    is not None else ri.going
    distance_str = header_info["distance"] if header_info["distance"] is not None else ri.distance
    course_str   = header_info["course"]   if header_info["course"]   is not None else ri.course

    ground_bucket = _resolve_ground_bucket(
        text_ground=header_info.get("ground_bucket") or detect_ground_bucket(request.racecard_text),
        manual_ground=ri.ground_bucket,
        inferred_going=going_str,
    )

    race = RaceInfo(
        course=course_str,
        country=detected_country,
        race_type=detected_type,
        surface=ri.surface,
        distance_f=parse_distance_to_furlongs(distance_str),
        going=normalize_going(going_str),
        runners=len(runners),
        discipline=disc["discipline"],
        discipline_subtype=disc["subtype"],
        ground_bucket=ground_bucket,
    )
    runner_objects = [
        Runner(
            name=r["name"],
            age=r["age"],
            weight_lbs=parse_weight_to_lbs(r["weight"]),
            form=r["form"],
            trainer=r["trainer"],
            jockey=r["jockey"],
        )
        for r in runners
    ]
    result = engine.race_quality_check(race, runner_objects)
    result["runner_names"]       = [r.name for r in runner_objects]
    result["race_header"]        = header_info
    result["discipline"]         = disc["discipline"]
    result["discipline_subtype"] = disc["subtype"]
    result["discipline_display"] = _discipline_display(disc["discipline"], disc["subtype"])
    result["ground_bucket"]      = ground_bucket
    return result


# -------------------------------------------------
# DEBUG PARSER (for troubleshooting paste/OCR)
# -------------------------------------------------

class DebugParseRequest(BaseModel):
    text: str


# ── Canonical template ────────────────────────────────────────────────────────
# Blank template using the exact guided-entry headers.  Returned by
# GET /canonical-template and pre-populated in the frontend's Guided Entry mode.
# Each HORSE: block contains every supported field; blank fields are kept as-is
# so the parser will use safe defaults.
_CANONICAL_TEMPLATE = """\
COURSE:
RACE:
TYPE:
DISTANCE:
RUNNERS:
CLASS:
GOING / GROUND:
GROUND:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:
"""


@app.get("/canonical-template")
def canonical_template():
    """Return the blank guided-entry racecard template."""
    return {"template": _CANONICAL_TEMPLATE}


@app.post("/debug-parse")
def debug_parse(request: DebugParseRequest):
    """Return raw + cleaned parser output for debugging."""
    lines = [l.strip() for l in request.text.split("\n") if l.strip()]

    # Run parser without the has_data filter to get raw runners
    raw_runners = []
    current = {}
    for line in lines:
        first_field = FIELD_KEYS.search(line)
        if first_field and first_field.start() > 0:
            name_part = line[:first_field.start()].strip()
            if name_part:
                if current and "name" in current:
                    raw_runners.append(current)
                current = {"name": name_part}
            _extract_fields(current, line[first_field.start():])
        elif first_field and first_field.start() == 0:
            _extract_fields(current, line)
        else:
            if current and "name" in current:
                raw_runners.append(current)
            current = {"name": line}
    if current and "name" in current:
        raw_runners.append(current)

    cleaned = parse_racecard_text(request.text)

    return {
        "lines": lines,
        "runners_raw": raw_runners,
        "runners_clean": cleaned,
        "count": len(cleaned),
    }
