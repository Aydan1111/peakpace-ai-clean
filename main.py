from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import re
import tempfile
import easyocr
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

# OCR reader — initialised once at startup (downloads model on first run)
ocr_reader = easyocr.Reader(["en"])


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
# Reused by /analyze-text and /analyze-image
# -------------------------------------------------

def parse_racecard_text(text: str) -> list:
    """
    Tolerant parser for racecard-style text.

    Recognises lines with any of:
        Jockey: X   Trainer: Y   Age: N   Weight: S-P   F: form / Form: form

    Lines with NO colon are treated as a horse name; encountering one
    finalises the previous runner and starts a new one.

    Safe defaults are applied for any missing optional fields.
    Returns only entries that have a name.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    runners = []
    current = {}

    for line in lines:
        if ":" not in line:
            # New horse name — finalise previous runner if it has data
            if current:
                runners.append(current)
            current = {"name": line}
            continue

        # Try to extract individual fields from this line
        age_m    = re.search(r"age[:\s]+(\d+)", line, re.I)
        weight_m = re.search(r"weight[:\s]+([\d\-]+)", line, re.I)
        trainer_m= re.search(r"trainer[:\s]+(.+)", line, re.I)
        jockey_m = re.search(r"jockey[:\s]+(.+)", line, re.I)
        form_m   = re.search(r"(?:^f|form)[:\s]+([0-9/\-]+)", line, re.I)

        if age_m:     current["age"]     = int(age_m.group(1))
        if weight_m:  current["weight"]  = weight_m.group(1)
        if trainer_m: current["trainer"] = trainer_m.group(1).strip()
        if jockey_m:  current["jockey"]  = jockey_m.group(1).strip()
        if form_m:    current["form"]    = form_m.group(1)

    # Finalise the last runner
    if current:
        runners.append(current)

    # Build clean list — skip any entry with no name or no real runner data
    cleaned = []
    for r in runners:
        if "name" not in r:
            continue
        # Skip header/title lines that have no runner-specific data at all
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
# ANALYZE TEXT (PASTE MODE)
# -------------------------------------------------

@app.post("/analyze-text")
def analyze_text(request: AnalyzeTextRequest):
    runners = parse_racecard_text(request.racecard_text)

    if len(runners) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Found {len(runners)} runner(s). Need at least 2 to analyze a race.",
        )

    ri = request.race_info
    race = RaceInfo(
        course=ri.course,
        country=ri.country,
        race_type=ri.race_type,
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
# ANALYZE IMAGE (SCREENSHOT MODE)
# -------------------------------------------------

@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    """
    Upload a screenshot → OCR → shared racecard parser → analyze.
    Reuses parse_racecard_text() — no duplicate parsing logic.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(await file.read())
            path = tmp.name

        text_lines = ocr_reader.readtext(path, detail=0)
        extracted_text = "\n".join(text_lines)

        runners = parse_racecard_text(extracted_text)

        if len(runners) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"OCR found {len(runners)} runner(s). Try a clearer screenshot.",
            )

        race = RaceInfo(
            course="Unknown",
            country="UK",
            race_type="flat",
            surface="aw",
            distance_f=8,
            going="good",
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
