from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
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


class AnalyzeRequest(BaseModel):
    course: str
    country: str
    race_type: str
    surface: str
    distance: str
    going: str
    runners: List[RunnerInput]


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


# -------------------------------------------------
# SHARED TEXT PARSER
# -------------------------------------------------

FIELD_KEYS = re.compile(
    r"(Age|Weight|Trainer|Jockey|Form|F)\s*:", re.I
)

# Words that can appear directly before a field key but are NOT horse names.
# e.g. "Recent Form: 123" — "Recent" must not become a runner.
_LABEL_NOISE = frozenset({"recent", "last", "previous", "latest", "current"})


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
        m = re.search(r"(?:^f|form)[:\s]+([0-9/\-]+)", token, re.I)
        if m:
            current["form"] = m.group(1)


def parse_racecard_text(text: str) -> list:
    """
    Tolerant parser for racecard-style text.

    Uses FIELD_KEYS regex to locate field boundaries in each line.
    If a field key starts after position 0, the text before it is the
    horse name.  This correctly handles both single-line-per-runner
    (e.g. "Horse A Age: 4 Weight: 9-4 Trainer: Smith Jockey: Doyle")
    and multi-line formats.

    Safe defaults are applied for any missing optional fields.
    Returns only entries that have a name AND at least one data field.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    runners = []
    current = {}

    for line in lines:
        first_field = FIELD_KEYS.search(line)

        if first_field and first_field.start() > 0:
            # Text before first field key = horse name (unless it's a known label word)
            name_part = line[:first_field.start()].strip()
            if name_part and name_part.lower() not in _LABEL_NOISE:
                if current and "name" in current:
                    runners.append(current)
                current = {"name": name_part}
            _extract_fields(current, line[first_field.start():])

        elif first_field and first_field.start() == 0:
            # Line starts with a field key (e.g. "Age: 4")
            _extract_fields(current, line)

        else:
            # No field key at all — entire line is a horse name
            if current and "name" in current:
                runners.append(current)
            current = {"name": line}

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
            "name":    r["name"],
            "age":     r.get("age", 4),
            "weight":  r.get("weight", "9-4"),
            "form":    r.get("form", ""),
            "trainer": r.get("trainer", ""),
            "jockey":  r.get("jockey", ""),
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
            )
        )

    return engine.analyze(race, runner_objects)


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


# -------------------------------------------------
# ANALYZE TEXT (PASTE MODE)
# -------------------------------------------------

@app.post("/analyze-text")
def analyze_text(request: AnalyzeTextRequest):
    # Auto-detect race type and country from the pasted text
    detected_type = detect_race_type(request.racecard_text)
    detected_country = detect_country(request.racecard_text)

    runners = parse_racecard_text(request.racecard_text)

    if len(runners) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Found {len(runners)} runner(s). Need at least 2 to analyze a race.",
        )

    ri = request.race_info
    race = RaceInfo(
        course=ri.course,
        country=detected_country,
        race_type=detected_type,
        surface=ri.surface,
        distance_f=parse_distance_to_furlongs(ri.distance),
        going=normalize_going(ri.going),
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

    return engine.analyze(race, runner_objects)


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
