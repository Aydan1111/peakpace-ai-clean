from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import re
from racing_ai_core import RacingAICore, RaceInfo, Runner

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
    allowed = [
        "heavy", "soft", "good to soft", "good",
        "good to firm", "firm", "standard",
    ]
    g = going.lower().strip()
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


class TextRaceInput(BaseModel):
    course: str = "Unknown"
    country: str = "UK"
    race_type: str = "flat"
    surface: str = "aw"
    distance: str = "8f"
    going: str = "good"


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


class RaceQualityTextRequest(BaseModel):
    race_info: TextRaceInput
    racecard_text: str


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
# e.g. "Jan 9 2026 | Naas | ... | Chase Dec 13 2025 | ..." → two segments.
_DATE_BOUNDARY_RE = re.compile(r"\b[A-Za-z]{3}\s+\d{1,2}\s+\d{4}\b")


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
    # Must start with a date-like token
    if not re.match(r"\w{3}\s+\d{1,2}\s+\d{2,4}", line.strip(), re.I):
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

    if "pos" in result and "field_size" in result:
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
                current = {"name": name}
                _extract_fields(current, rest[first_fk.start():])
            else:
                current = {"name": rest}
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

    # Build clean list — skip entries with ONLY a name (headers/junk)
    cleaned = []
    for r in runners:
        if "name" not in r:
            continue
        has_data = any(k in r for k in ("age", "weight", "jockey", "trainer", "form"))
        if not has_data:
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

    race = RaceInfo(
        course=request.course,
        country=request.country,
        race_type=request.race_type,
        surface=request.surface,
        distance_f=parse_distance_to_furlongs(request.distance),
        going=normalize_going(request.going),
        runners=len(request.runners),
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
    return engine.analyze(race, runner_objects, odds=request.odds)


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


# -------------------------------------------------
# ANALYZE TEXT (PASTE MODE)
# -------------------------------------------------

@app.post("/analyze-text")
def analyze_text(request: AnalyzeTextRequest):
    # Auto-detect race type, country, and going from the pasted text
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
    # Use detected going when found; fall back to what the user supplied
    going_str = detected_going if detected_going is not None else ri.going
    race = RaceInfo(
        course=ri.course,
        country=detected_country,
        race_type=detected_type,
        surface=ri.surface,
        distance_f=parse_distance_to_furlongs(ri.distance),
        going=normalize_going(going_str),
        runners=len(runners),
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
    return engine.analyze(race, runner_objects, odds=final_odds)


# -------------------------------------------------
# RACE QUALITY CHECK (pre-analysis endpoints)
# -------------------------------------------------

@app.post("/race-quality")
def race_quality(request: RaceQualityRequest):
    """Pre-analysis quality check for manually-entered runners."""
    race = RaceInfo(
        course=request.course,
        country=request.country,
        race_type=request.race_type,
        surface=request.surface,
        distance_f=parse_distance_to_furlongs(request.distance),
        going=normalize_going(request.going),
        runners=len(request.runners),
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
    detected_type    = detect_race_type(request.racecard_text)
    detected_country = detect_country(request.racecard_text)
    detected_going   = detect_going(request.racecard_text)

    runners = parse_racecard_text(request.racecard_text)
    if len(runners) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Found {len(runners)} runner(s). Need at least 2.",
        )

    ri = request.race_info
    going_str = detected_going if detected_going is not None else ri.going
    race = RaceInfo(
        course=ri.course,
        country=detected_country,
        race_type=detected_type,
        surface=ri.surface,
        distance_f=parse_distance_to_furlongs(ri.distance),
        going=normalize_going(going_str),
        runners=len(runners),
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
    result["runner_names"] = [r.name for r in runner_objects]
    return result


# -------------------------------------------------
# DEBUG PARSER (for troubleshooting paste/OCR)
# -------------------------------------------------

class DebugParseRequest(BaseModel):
    text: str


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
