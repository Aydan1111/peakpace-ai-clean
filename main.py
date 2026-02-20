from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import re
from racing_ai_core import RacingAICore, RaceInfo, Runner

app = FastAPI(title="PeakPace AI")

# -------------------------------------------------
# CORS (REQUIRED FOR FRONTEND)
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can lock this down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = RacingAICore()

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def parse_weight_to_lbs(weight_str: str) -> int:
    """
    Converts '10-3' (10 stone 3 lbs) into total lbs.
    """
    try:
        stone, pounds = weight_str.split("-")
        stone = int(stone.strip())
        pounds = int(pounds.strip())
        if pounds >= 14:
            raise ValueError("Pounds must be less than 14.")
        return stone * 14 + pounds
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid weight format: {weight_str}")


def parse_distance_to_furlongs(distance_str: str) -> int:
    """
    Accepts:
    - 6f
    - 1m
    - 1m4f
    - 2m
    """
    distance_str = distance_str.lower().strip()
    miles = 0
    furlongs = 0

    mile_match = re.search(r"(\d+)m", distance_str)
    furlong_match = re.search(r"(\d+)f", distance_str)

    if mile_match:
        miles = int(mile_match.group(1))
    if furlong_match:
        furlongs = int(furlong_match.group(1))

    total_furlongs = miles * 8 + furlongs
    if total_furlongs == 0:
        raise HTTPException(status_code=400, detail=f"Invalid distance format: {distance_str}")
    return total_furlongs


def normalize_going(going: str) -> str:
    g = going.lower().strip()
    allowed = [
        "heavy",
        "soft",
        "good to soft",
        "good",
        "good to firm",
        "firm",
        "standard"
    ]
    if g not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid going condition: {going}")
    return g


# -------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------
class RunnerInput(BaseModel):
    name: str
    age: int
    weight: str
    form: str
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
# MAIN ANALYZE ENDPOINT
# -------------------------------------------------
@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    race = RaceInfo(
        course=request.course,
        country=request.country,
        race_type=request.race_type,
        surface=request.surface,
        distance_f=parse_distance_to_furlongs(request.distance),
        going=normalize_going(request.going),
        runners=len(request.runners)
    )

    runner_objects = []
    for r in request.runners:
        total_lbs = parse_weight_to_lbs(r.weight)
        runner_objects.append(
            Runner(
                name=r.name,
                age=r.age,
                weight_lbs=total_lbs,
                form=r.form,
                draw=r.draw,
                trainer=r.trainer,
                jockey=r.jockey,
                jockey_claim_lbs=r.jockey_claim_lbs or 0,
            )
        )

    result = engine.analyze(race, runner_objects)
    return result


# -------------------------------------------------
# ANALYZE TEXT (RACECARD PASTE)
# -------------------------------------------------
@app.post("/analyze-text")
def analyze_text(request: AnalyzeTextRequest):
    """
    Accepts raw racecard text pasted from bookmaker site.
    Very lightweight parser – expects format like:

    Horse Name
    Jockey: X
    Trainer: Y
    F: 1234 | Age: 5 | Weight: 10-2
    """
    lines = request.racecard_text.split("\n")
    runners = []
    current = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "Jockey:" in line:
            current["jockey"] = line.replace("Jockey:", "").strip()
        elif "Trainer:" in line:
            current["trainer"] = line.replace("Trainer:", "").strip()
        elif "Age:" in line and "Weight:" in line:
            age_match = re.search(r"Age:\s*(\d+)", line)
            weight_match = re.search(r"Weight:\s*([\d\-]+)", line)
            form_match = re.search(r"F:\s*([0-9/\\-]+)", line)
            if age_match:
                current["age"] = int(age_match.group(1))
            if weight_match:
                current["weight"] = weight_match.group(1)
            if form_match:
                current["form"] = form_match.group(1)
            # Finalize runner
            if all(k in current for k in ["name", "trainer", "jockey", "age", "weight", "form"]):
                runners.append(current.copy())
                current = {}
        else:
            # Assume horse name
            current["name"] = line

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
        runners=len(runners)
    )

    runner_objects = []
    for r in runners:
        total_lbs = parse_weight_to_lbs(r["weight"])
        runner_objects.append(
            Runner(
                name=r["name"],
                age=r["age"],
                weight_lbs=total_lbs,
                form=r["form"],
                trainer=r["trainer"],
                jockey=r["jockey"],
            )
        )

    result = engine.analyze(race, runner_objects)
    return result