# ============================================================
# PEAKPACE AI — RACING CORE (DATA-DRIVEN VERSION)
# ============================================================

import os
import re
import math
from dataclasses import dataclass
from typing import List, Dict, Optional
import statistics


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class RaceInfo:
    course: str
    country: str
    race_type: str
    surface: str
    distance_f: int
    going: str
    runners: int
    discipline: str = "Unknown"           # "Flat" | "Jumps" | "Unknown"
    discipline_subtype: Optional[str] = None  # "Hurdle" | "Chase" | "NH Flat" | None
    ground_bucket: Optional[str] = None  # "Wet" | "Dry" | None (simple 2-way classification)


@dataclass
class Runner:
    name: str
    age: int
    weight_lbs: int
    form: str
    trainer: str
    jockey: str
    draw: int = None
    jockey_claim_lbs: int = 0
    # Optional racecard intelligence fields
    comment: str = ""         # analyst/Racing Post comment text
    equipment: str = ""       # equipment notes (e.g. "tongue strap", "hood removed")
    previous_runs: Optional[List[dict]] = None  # list of {going, distance_f, pos, field_size, discipline}
    pace_style: str = ""      # "hold_up" | "midfield" | "prominent" | "leader"
    # Racecard rating fields
    or_rating: Optional[int] = None   # Official Rating from racecard
    rpr: Optional[int] = None         # Racing Post Rating from racecard
    top_speed: Optional[int] = None   # TS — flat races only


# ============================================================
# DATA LOADING — parse all 8 Irish racing data files
# ============================================================

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _parse_odds(raw: str) -> Optional[float]:
    """Convert fractional or decimal odds string to a decimal float.

    "9/1"  → 10.0  |  "6/4"  → 2.5  |  "evs" → 2.0  |  "10.0" → 10.0
    Returns None if the string cannot be parsed.
    """
    s = str(raw).strip().lower()
    if s in ("evs", "evens", "1/1"):
        return 2.0
    if "/" in s:
        parts = s.split("/")
        try:
            num, den = float(parts[0]), float(parts[1])
            return round(num / den + 1, 4) if den != 0 else None
        except ValueError:
            return None
    try:
        val = float(s)
        return val if val >= 1.01 else None
    except ValueError:
        return None


def _parse_stats_file(filename: str) -> Dict[str, dict]:
    """Parse trainer/jockey/horse stats files.

    Handles two formats:
      Irish: Name (Runs: N | 1st: N | 2nd: N | ... | Total Prize Money: N)
      UK:    Name (Season: Y | Rank: N | Wins: N | Runs/Rides: N | ...)

    The stats block starts at the first '(' followed by one of the known field keys.
    Returns dict: lowercase normalised name → {runs, wins, prize}
    """
    result = {}
    filepath = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(filepath):
        return result

    _BLOCK_START = re.compile(r"\((Runs:|Season:|Wins:|Rides:|Rank:)")

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                m = _BLOCK_START.search(line)
                if not m:
                    continue

                raw_name = line[: m.start()].strip()
                stats_str = line[m.start():]

                runs_m  = re.search(r"\bRuns:\s*(\d+)",  stats_str)
                rides_m = re.search(r"\bRides:\s*(\d+)", stats_str)
                wins_m  = re.search(r"\b(?:Wins|1st):\s*(\d+)", stats_str)
                prize_m = re.search(r"Total Prize Money:\s*([\d,]+)", stats_str)

                run_match = runs_m or rides_m
                if not run_match:
                    continue
                runs  = int(run_match.group(1))
                wins  = int(wins_m.group(1)) if wins_m else 0
                prize = int(prize_m.group(1).replace(",", "")) if prize_m else 0

                if runs == 0:
                    continue

                name = _normalize_name(raw_name)
                if name:
                    result[name] = {"runs": runs, "wins": wins, "prize": prize}
            except Exception:
                continue
    return result


def _parse_ratings_file(filename: str) -> Dict[str, int]:
    """Parse horse ratings files.

    Handles three formats:
      Irish flat: HorseName YearBorn Sex DamName SireName Trainer (Rating: N)
      Irish NH:   HorseName (CountryCode)? (Rating: N)
      UK flat:    HORSE NAME (IRE) (Rank: N | Flat Rating: N | ...)
      UK jumps:   HORSE NAME (GB) (Rank: N | Best Jumps Rating: N | ...)

    The stats block starts at the first '(' followed by 'Rating:' or 'Rank:'.
    Returns dict: lowercase normalised name → rating (int)
    """
    result = {}
    filepath = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(filepath):
        return result

    _BLOCK_START = re.compile(r"\((Rating:|Rank:)")

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                m = _BLOCK_START.search(line)
                if not m:
                    continue

                raw_name_part = line[: m.start()].strip()
                stats_str = line[m.start():]

                # Try field names in priority order
                rating_m = re.search(
                    r"(?:Best Jumps Rating|Flat Rating|Rating):\s*(\d+)",
                    stats_str,
                )
                if not rating_m:
                    continue
                rating = int(rating_m.group(1))

                # Irish flat format includes year + extra tokens after the horse name;
                # strip year and everything that follows it.
                name_part = re.sub(r"\s+\d{4}\b.*$", "", raw_name_part).strip()
                name = _normalize_name(name_part)
                if name:
                    result[name] = rating
            except Exception:
                continue
    return result


def _win_rate_to_multiplier(wins: int, runs: int) -> float:
    """Convert wins/runs to a score multiplier.

    Baseline win rate ~10%. Each +10% above baseline adds +0.045.
    Capped at 1.12. Sample-size penalty for fewer than 20 runs.
    """
    if runs == 0:
        return 1.0
    win_rate = wins / runs
    raw = 1.0 + min(max(win_rate - 0.10, 0.0), 0.30) * 0.45

    # Discount tiny samples
    if runs < 10:
        raw = 1.0 + (raw - 1.0) * 0.4
    elif runs < 20:
        raw = 1.0 + (raw - 1.0) * 0.7

    return round(min(raw, 1.12), 4)


def _build_people_multipliers(filename: str) -> Dict[str, float]:
    """Build a name→multiplier dict from a single stats file."""
    combined = {}
    data = _parse_stats_file(filename)
    for name, d in data.items():
        m = _win_rate_to_multiplier(d["wins"], d["runs"])
        combined[name] = max(combined.get(name, 1.0), m)
    return combined


# ============================================================
# RACE-TYPE CLASSIFIER — used by all lookup methods
# ============================================================

_NH_KEYWORDS = ("hurdle", "chase", "nh", "national hunt", "national_hunt",
                "jump", "bumper", "steeplechase", "hunter chase",
                "cross country", "point-to-point")

# Going conditions considered testing (used for going confidence penalty)
_TESTING_GOING = frozenset({"heavy", "soft", "good to soft"})

# Matches country suffixes appended to horse names on racecards, e.g. (IRE), (GB)
_COUNTRY_SUFFIX_RE = re.compile(
    r"\s*\((?:ire|gb|fr|usa|ger|nz|aus|can|spa|ity|por)\)\s*$",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """Normalize a horse name for dictionary lookups.

    Strips country suffixes like (IRE), (GB), (FR) that appear on racecards
    but are absent from the stats/ratings files, then lowercases and trims.
    """
    n = _COUNTRY_SUFFIX_RE.sub("", name).strip().lower()
    return n


def _is_nh(race_type: str) -> bool:
    """Return True when race_type indicates National Hunt / Jumps."""
    if not race_type:
        return False
    rt = race_type.lower()
    return any(k in rt for k in _NH_KEYWORDS)


def _going_bucket(going: str) -> str:
    """Bucket a going string into 'soft', 'good', or 'firm' for comparison."""
    g = going.lower()
    if any(x in g for x in ("heavy", "soft", "yielding")):
        return "soft"
    if any(x in g for x in ("firm", "standard", "fast", "hard")):
        return "firm"
    return "good"


# ── Wet / Dry ground classification (simple 2-way layer) ─────────────────────
# This is an additional abstraction alongside the detailed going labels.
# It does NOT replace the detailed labels — it is used only for the Wet Jumps
# mode and can be populated from three sources (in priority order):
#   1. Explicit paste-text GROUND: Wet / GROUND: Dry field
#   2. Explicit manual-entry ground_bucket selection
#   3. Inferred from the detailed going string via classify_wet_dry()

def classify_wet_dry(going: str) -> Optional[str]:
    """Infer a simple Wet/Dry bucket from a detailed going string.

    Returns 'Wet', 'Dry', or None when going is empty/unknown.
    The detailed going labels are never modified — this is a separate layer.

    Ordered longest-first so compound phrases like "good to yielding" are
    matched before bare "yielding", preventing false Wet classification.
    """
    if not going:
        return None
    g = going.lower().strip()
    # Compound phrases that contain a wet keyword but are actually Dry/borderline
    # must be checked FIRST before the bare wet keywords below.
    _DRY_COMPOUNDS = (
        "good to yielding",   # Ireland — borderline but treated as Dry
        "good to soft",       # borderline — _TESTING_GOING handles penalty separately
    )
    for phrase in _DRY_COMPOUNDS:
        if phrase in g:
            return "Dry"
    # All clearly testing/wet conditions map to Wet
    if any(k in g for k in (
        "heavy", "soft", "yielding", "very soft", "sloppy", "testing"
    )):
        return "Wet"
    # All other recognisable conditions (firm, good, standard, etc.) → Dry
    return "Dry"


def _is_wet_jumps(race: RaceInfo) -> bool:
    """Return True when Wet Jumps mode should activate.

    Conditions: discipline is Jumps AND ground_bucket is Wet.
    The ground_bucket field is set by the caller (main.py) using the
    3-way priority logic: paste override → manual override → inferred.
    """
    is_jumps = race.discipline == "Jumps" or _is_nh(race.race_type)
    return is_jumps and race.ground_bucket == "Wet"


# ============================================================
# DATA LOADING — explicit Flat vs National Hunt separation
# ============================================================

# ---------- IRISH ----------
_TRAINER_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "Irish Trainers Stats Flat 2024 and 2025 and 2026.txt",
)
_TRAINER_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "Irish Trainers Stats National Hunt (Jumps) 2024 and 2025 and 2026.txt",
)

_JOCKEY_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "Irish Jockeys Stats Flat 2024 and 2025.txt",
)
_JOCKEY_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "Irish Jockeys Stats National Hunt 2024 and 2025 and 2026.txt",
)

_HORSE_RATINGS_FLAT: Dict[str, int] = _parse_ratings_file(
    "Irish Horse Ratings For Flat Racing - Engine Format.txt"
)
_HORSE_RATINGS_NH: Dict[str, int] = _parse_ratings_file(
    "Irish Horse Ratings For National Hunt Racing (Jumps) - Engine Format.txt"
)

_HORSE_STATS_FLAT: Dict[str, dict] = _parse_stats_file(
    "Irish Horses Flat 2024 and 2025 - Engine Format.txt"
)
_HORSE_STATS_NH: Dict[str, dict] = _parse_stats_file(
    "Irish Horses National Hunt (Jumps) 2024 and 2025 and 2026 - Engine Format.txt"
)

# ---------- UK (loaded when files exist; empty dict otherwise) ----------
_UK_TRAINER_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "UK_Trainers_Flat_clean.txt",
)
_UK_TRAINER_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "UK_Trainers_Jumps_clean.txt",
)

_UK_JOCKEY_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "UK_Jockeys_Flat_clean.txt",
)
_UK_JOCKEY_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "UK_Jockeys_Jumps_clean.txt",
)

_UK_HORSE_RATINGS_FLAT: Dict[str, int] = _parse_ratings_file(
    "UK_Ratings_Flat_Top500.txt"
)
_UK_HORSE_RATINGS_NH: Dict[str, int] = _parse_ratings_file(
    "UK_Ratings_Jumps_Top500.txt"
)

_UK_HORSE_STATS_FLAT: Dict[str, dict] = _parse_stats_file(
    "UK_Horses_Flat_2024_2025_2026_clean.txt"
)
_UK_HORSE_STATS_NH: Dict[str, dict] = _parse_stats_file(
    "UK_Horses_Jumps_2024_2025_2026_clean.txt"
)

# ---------- RAW STATS for strike-rate calculations ----------
_TRAINER_STATS_RAW_FLAT: Dict[str, dict] = _parse_stats_file(
    "Irish Trainers Stats Flat 2024 and 2025 and 2026.txt",
)
_TRAINER_STATS_RAW_NH: Dict[str, dict] = _parse_stats_file(
    "Irish Trainers Stats National Hunt (Jumps) 2024 and 2025 and 2026.txt",
)
_JOCKEY_STATS_RAW_FLAT: Dict[str, dict] = _parse_stats_file(
    "Irish Jockeys Stats Flat 2024 and 2025.txt",
)
_JOCKEY_STATS_RAW_NH: Dict[str, dict] = _parse_stats_file(
    "Irish Jockeys Stats National Hunt 2024 and 2025 and 2026.txt",
)
_UK_TRAINER_STATS_RAW_FLAT: Dict[str, dict] = _parse_stats_file(
    "UK_Trainers_Flat_clean.txt",
)
_UK_TRAINER_STATS_RAW_NH: Dict[str, dict] = _parse_stats_file(
    "UK_Trainers_Jumps_clean.txt",
)
_UK_JOCKEY_STATS_RAW_FLAT: Dict[str, dict] = _parse_stats_file(
    "UK_Jockeys_Flat_clean.txt",
)
_UK_JOCKEY_STATS_RAW_NH: Dict[str, dict] = _parse_stats_file(
    "UK_Jockeys_Jumps_clean.txt",
)


# ============================================================
# COUNTRY CLASSIFIER
# ============================================================

def _is_uk(country: str) -> bool:
    """Return True when the race is in the UK (not Ireland)."""
    if not country:
        return False
    c = country.lower().strip()
    if c in ("ireland", "ire", "ie", "irish"):
        return False
    # Anything else (uk, gb, england, scotland, wales, etc.) → UK
    return True


# ============================================================
# TRAINER + JOCKEY COMBO BOOSTS
# (data-backed key pairings)
# ============================================================

TRAINER_JOCKEY_COMBOS = {
    ("a.p. o'brien", "ryan moore"):           1.08,
    ("w.p. mullins", "paul townend"):          1.08,
    ("w.p. mullins", "p. townend"):            1.08,
    ("w.p. mullins", "p.w. mullins"):          1.06,
    ("gordon elliott", "jack kennedy"):        1.06,
    ("gordon elliott", "j.w. kennedy"):        1.06,
    ("dan skelton", "harry skelton"):          1.06,
    ("paul nicholls", "harry cobden"):         1.06,
    ("john & thady gosden", "william buick"): 1.05,
    ("joseph patrick o'brien", "m.p. walsh"): 1.04,
    ("henry de bromhead", "rachael blackmore"): 1.05,
}


# ============================================================
# UK TRAINER / JOCKEY HARDCODED FALLBACK
# (used for UK races only, when name is not in UK data files)
# ============================================================

_UK_TRAINER_FALLBACK: Dict[str, float] = {
    "dan skelton":           1.08,
    "paul nicholls":         1.08,
    "nicky henderson":       1.07,
    "olly murphy":           1.06,
    "ben pauling":           1.06,
    "joe tizzard":           1.05,
    "nigel twiston-davies":  1.05,
    "jamie snowden":         1.04,
    "fergal o'brien":        1.05,
    "john & thady gosden":   1.08,
    "andrew balding":        1.07,
    "richard hannon":        1.06,
    "charlie johnston":      1.05,
    "james tate":            1.05,
    "michael appleby":       1.05,
    "david o'meara":         1.04,
    "k. r. burke":           1.04,
    "richard fahey":         1.04,
    "ed walker":             1.03,
    "david simcock":         1.03,
    "jamie osborne":         1.03,
    "james fanshawe":        1.03,
    "jim goldie":            1.03,
    "archie watson":         1.04,
    "robert cowell":         1.03,
    "anthony honeyball":     1.04,
    "jonjo o'neill":         1.04,
    "harry derham":          1.04,
    "lucinda russell":       1.04,
    "gary moore":            1.03,
    "emma lavelle":          1.03,
    "donald mccain":         1.03,
    "neil mulholland":       1.03,
    "sam thomas":            1.03,
    "alan king":             1.04,
    "venetia williams":      1.04,
    "chris gordon":          1.03,
    "tom lacey":             1.03,
    "warren greatrex":       1.03,
}

_UK_JOCKEY_FALLBACK: Dict[str, float] = {
    "ryan moore":            1.08,
    "william buick":         1.06,
    "dettori":               1.06,
    "james doyle":           1.04,
    "tom marquand":          1.03,
    "danny tudhope":         1.03,
    "hollie doyle":          1.03,
    "harry cobden":          1.05,
    "harry skelton":         1.05,
    "nico de boinville":     1.04,
    "aidan coleman":         1.03,
    "sam twiston-davies":    1.03,
    "rachael blackmore":     1.06,
    "paul townend":          1.07,
    "jack kennedy":          1.06,
    "davy russell":          1.04,
}


# ============================================================
# DRAW SCORING HELPERS  (Flat races only)
# ============================================================

# Sparse draw-bias table.
# Key: (course_key, distance_f, surface_key, runner_band)
# Value: {"low": mult, "mid": mult, "high": mult}
# runner_band is one of: "le7", "8_12", "13_plus"
# Course and surface keys are lowercase-normalised.
DRAW_BIAS: Dict[tuple, dict] = {
    # Chester — very tight track, low draws strongly favoured at sprint-ish trips
    ("chester", 5, "turf", "8_12"):    {"low": 1.03, "mid": 1.01, "high": 0.97},
    ("chester", 6, "turf", "8_12"):    {"low": 1.03, "mid": 1.01, "high": 0.97},
    ("chester", 5, "turf", "13_plus"): {"low": 1.04, "mid": 1.01, "high": 0.96},
    # Ascot — wide track, high draw can be advantageous in big sprints
    ("ascot",   5, "turf", "13_plus"): {"low": 0.98, "mid": 1.00, "high": 1.02},
    ("ascot",   6, "turf", "13_plus"): {"low": 0.98, "mid": 1.01, "high": 1.01},
    # Epsom — undulating, mid/low draws slightly favoured over 1m
    ("epsom",   8, "turf", "8_12"):    {"low": 1.02, "mid": 1.01, "high": 0.98},
    # Goodwood — low draws favoured over 6f in big fields
    ("goodwood",6, "turf", "13_plus"): {"low": 1.02, "mid": 1.00, "high": 0.98},
    # AW tracks — generally more neutral, very mild effects
    ("kempton", 6, "aw",   "8_12"):    {"low": 1.01, "mid": 1.00, "high": 0.99},
    ("kempton", 8, "aw",   "8_12"):    {"low": 1.01, "mid": 1.01, "high": 0.99},
}


def _runner_band(field_size: int) -> str:
    """Classify field size: 'le7', '8_12', or '13_plus'."""
    if field_size <= 7:
        return "le7"
    if field_size <= 12:
        return "8_12"
    return "13_plus"


def _draw_position(stall: int, field_size: int) -> str:
    """Classify raw stall into 'low', 'mid', or 'high'."""
    if field_size <= 1:
        return "mid"
    ratio = (stall - 1) / (field_size - 1)   # 0.0 = stall 1, 1.0 = highest stall
    if ratio <= 0.33:
        return "low"
    if ratio <= 0.67:
        return "mid"
    return "high"


def _normalize_surface_for_draw(surface: str) -> str:
    """Normalize a surface string to a DRAW_BIAS table key: 'aw' or 'turf'."""
    s = surface.lower().strip().replace("-", " ").replace("_", " ")
    if s in ("aw", "all weather", "standard", "tapeta", "polytrack",
             "fibresand", "dirt"):
        return "aw"
    return "turf"


def _draw_bias_key(race: RaceInfo) -> tuple:
    """Build the DRAW_BIAS lookup key for a race."""
    return (
        race.course.lower().strip(),
        race.distance_f,
        _normalize_surface_for_draw(race.surface),
        _runner_band(race.runners),
    )


def _draw_favourability(runner: Runner, race: RaceInfo) -> str:
    """Return 'favourable', 'neutral', 'unfavourable', or 'unknown'.

    Uses the actual DRAW_BIAS entry so favourability is course/distance
    specific rather than assuming low draw = good.
    'unknown' is returned when no bias row exists for this race configuration.
    """
    if runner.draw is None:
        return "unknown"
    bias = DRAW_BIAS.get(_draw_bias_key(race))
    if bias is None:
        return "unknown"
    pos  = _draw_position(runner.draw, race.runners)
    mult = bias.get(pos, 1.0)
    if mult > 1.005:
        return "favourable"
    if mult < 0.995:
        return "unfavourable"
    return "neutral"


def _draw_multiplier(runner: Runner, race: RaceInfo) -> float:
    """Small draw-bias multiplier for Flat races only.  Returns 1.0 otherwise."""
    if race.discipline != "Flat":
        return 1.0
    if runner.draw is None:
        return 1.0

    bias = DRAW_BIAS.get(_draw_bias_key(race))
    if bias is None:
        return 1.0

    pos  = _draw_position(runner.draw, race.runners)
    mult = bias.get(pos, 1.0)
    # Hard cap: ±4% max
    return max(0.96, min(1.04, mult))


# ============================================================
# PACE SCORING HELPERS  (Flat races primarily)
# ============================================================

_PACE_ORDER = {"hold_up": 1, "midfield": 2, "prominent": 3, "leader": 4}


def _pace_counts(runners: List["Runner"]) -> dict:
    """Count runners by pace style."""
    counts: dict = {"hold_up": 0, "midfield": 0, "prominent": 0, "leader": 0}
    for r in runners:
        ps = (r.pace_style or "").lower().strip()
        if ps in counts:
            counts[ps] += 1
    return counts


def _pace_shape(runners: List["Runner"]) -> str:
    """Classify the race pace shape from the field.

    Returns 'unknown' when fewer than 2 runners have a known pace style OR
    fewer than 40% of the field do — not enough signal to infer shape reliably.
    Otherwise returns: 'strong' | 'controlled' | 'steady' | 'weak'
    """
    known = sum(1 for r in runners
                if (r.pace_style or "").lower().strip() in _PACE_ORDER)
    if known < 2 or (len(runners) > 0 and known / len(runners) < 0.40):
        return "unknown"
    c = _pace_counts(runners)
    if c["leader"] >= 2:
        return "strong"
    if c["leader"] == 1:
        return "controlled"
    if c["prominent"] >= 1:
        return "steady"
    return "weak"


def _pace_multiplier(runner: Runner, runners: List["Runner"],
                     race: RaceInfo) -> float:
    """Small pace-context multiplier.  Flat only; ±4% max."""
    if race.discipline != "Flat":
        return 1.0
    ps = (runner.pace_style or "").lower().strip()
    if not ps or ps not in _PACE_ORDER:
        return 1.0

    shape = _pace_shape(runners)
    if shape == "unknown":
        return 1.0

    delta = 0.0

    if shape == "weak":
        # Cheap pace — front runners get a small lift; closers get small penalty
        if ps in ("leader", "prominent"):
            delta = +0.025
        elif ps == "hold_up":
            delta = -0.020
        # midfield neutral

    elif shape == "strong":
        # Hot pace — closers get a small lift; leaders may fade
        if ps == "hold_up":
            delta = +0.025
        elif ps == "leader":
            delta = -0.020
        # prominent / midfield neutral

    elif shape in ("controlled", "steady"):
        # Only very small effects in neutral pace situations
        if ps in ("leader", "prominent"):
            delta = +0.010
        elif ps == "hold_up":
            delta = -0.010

    return max(0.96, min(1.04, 1.0 + delta))


# ============================================================
# DRAW + PACE COMBINATION MULTIPLIER  (Flat only)
# ============================================================

def _draw_pace_combo_multiplier(runner: Runner, runners: List["Runner"],
                                race: RaceInfo) -> float:
    """Tiny draw+pace interaction.  Flat only; ±3% max.

    Uses actual DRAW_BIAS favourability rather than assuming low = good.
    Returns 1.0 when pace shape is unknown or no bias row exists for the race.
    """
    if race.discipline != "Flat":
        return 1.0
    if runner.draw is None:
        return 1.0

    shape = _pace_shape(runners)
    if shape == "unknown":
        return 1.0

    favour = _draw_favourability(runner, race)
    if favour == "unknown":
        # No DRAW_BIAS entry for this course/distance/surface — no combo signal
        return 1.0

    ps    = (runner.pace_style or "").lower().strip()
    delta = 0.0

    if shape == "weak":
        if favour == "favourable" and ps in ("leader", "prominent", "midfield"):
            delta = +0.020
        elif favour == "unfavourable" and ps == "hold_up":
            delta = -0.015

    # Strong pace handled by _pace_multiplier; no additional combo signal here.
    # Controlled / steady: neutral.

    return max(0.97, min(1.03, 1.0 + delta))


# ============================================================
# CORE ENGINE
# ============================================================

class RacingAICore:

    # Optional pick toggles (off by default).
    silver_enabled: bool = False
    dark_horse_enabled: bool = False

    # --------------------------------------------------------
    # RAW-STATS LOOKUP (trainer / jockey / horse)
    # --------------------------------------------------------
    @staticmethod
    def _lookup_stats(name: str, data: Dict[str, dict]) -> Optional[dict]:
        """Look up raw stats {runs, wins, prize} by name with partial matching."""
        n = name.lower().strip()
        if n in data:
            return data[n]
        for key, val in data.items():
            if key in n or n in key:
                return val
        return None

    def _get_trainer_stats(self, trainer: str, race_type: str,
                           country: str) -> Optional[dict]:
        uk = _is_uk(country)
        if uk:
            data = _UK_TRAINER_STATS_RAW_NH if _is_nh(race_type) else _UK_TRAINER_STATS_RAW_FLAT
        else:
            data = _TRAINER_STATS_RAW_NH if _is_nh(race_type) else _TRAINER_STATS_RAW_FLAT
        return self._lookup_stats(trainer, data)

    def _get_jockey_stats(self, jockey: str, race_type: str,
                          country: str) -> Optional[dict]:
        uk = _is_uk(country)
        if uk:
            data = _UK_JOCKEY_STATS_RAW_NH if _is_nh(race_type) else _UK_JOCKEY_STATS_RAW_FLAT
        else:
            data = _JOCKEY_STATS_RAW_NH if _is_nh(race_type) else _JOCKEY_STATS_RAW_FLAT
        return self._lookup_stats(jockey, data)

    def _get_horse_stats(self, horse_name: str, race_type: str,
                         country: str) -> Optional[dict]:
        name = _normalize_name(horse_name)
        uk = _is_uk(country)
        if uk:
            return (_UK_HORSE_STATS_NH if _is_nh(race_type)
                    else _UK_HORSE_STATS_FLAT).get(name)
        return (_HORSE_STATS_NH if _is_nh(race_type)
                else _HORSE_STATS_FLAT).get(name)

    # --------------------------------------------------------
    # FORM PARSING
    # --------------------------------------------------------
    @staticmethod
    def _parse_form_positions(form: str) -> List[int]:
        """Parse form string into finishing positions.

        Numeric digits: 1-9 = finishing position, 0 = also ran (counts as 10).
        Non-numeric chars (F=fell, P=pulled up, U=unseated, R=refused,
        B=brought down, S=slipped up, C=carried out, D=disqualified)
        all count as penalty value of 10.
        """
        positions = []
        for c in (form or "").upper():
            if c.isdigit():
                positions.append(10 if c == "0" else int(c))
            elif c in ("F", "P", "U", "R", "B", "S", "C", "D"):
                positions.append(10)
        return positions

    # --------------------------------------------------------
    # FIELD NORMALISATION  (0-100 scale)
    # --------------------------------------------------------
    @staticmethod
    def _normalize_field(values: List[Optional[float]],
                         higher_is_better: bool = True) -> List[float]:
        """Normalise a list of values to a 0-100 scale across the field.

        None values receive 50.0 (neutral mid-point).
        When all valid values are equal, everyone gets 50.0.
        """
        valid = [v for v in values if v is not None]
        if len(valid) < 2 or max(valid) == min(valid):
            return [50.0 for _ in values]
        lo, hi = min(valid), max(valid)
        rng = hi - lo
        result = []
        for v in values:
            if v is None:
                result.append(50.0)
            else:
                norm = (v - lo) / rng * 100.0
                result.append(norm if higher_is_better else 100.0 - norm)
        return result

    # --------------------------------------------------------
    # FACTOR 1: OR Rating  (higher = better)
    # --------------------------------------------------------
    def _score_or_ratings(self, runners: List[Runner]) -> List[float]:
        values = [float(r.or_rating) if r.or_rating is not None else None
                  for r in runners]
        return self._normalize_field(values, higher_is_better=True)

    # --------------------------------------------------------
    # FACTOR 2: RPR Rating  (higher = better, fallback to OR)
    # --------------------------------------------------------
    def _score_rpr_ratings(self, runners: List[Runner]) -> List[float]:
        values = []
        for r in runners:
            if r.rpr is not None:
                values.append(float(r.rpr))
            elif r.or_rating is not None:
                values.append(float(r.or_rating))
            else:
                values.append(None)
        return self._normalize_field(values, higher_is_better=True)

    # --------------------------------------------------------
    # FACTOR 3: Overall Form Average  (lower avg = better)
    # --------------------------------------------------------
    def _score_overall_form(self, runners: List[Runner]) -> List[float]:
        averages: List[Optional[float]] = []
        for r in runners:
            positions = self._parse_form_positions(r.form)
            if positions:
                averages.append(statistics.mean(positions))
            else:
                averages.append(None)
        return self._normalize_field(averages, higher_is_better=False)

    # --------------------------------------------------------
    # FACTOR 4: Last 3 Runs Form  (with trend bonus/penalty)
    # --------------------------------------------------------
    def _score_last3_form(self, runners: List[Runner]) -> List[float]:
        """Last 3 runs average, adjusted for trend vs overall form.

        Improving (last-3 avg better than overall) → small bonus.
        Declining (last-3 avg worse than overall) → small penalty.
        Lower adjusted average = better score (inverted in normalisation).
        """
        adjusted: List[Optional[float]] = []
        for r in runners:
            positions = self._parse_form_positions(r.form)
            if not positions:
                adjusted.append(None)
                continue

            last3 = positions[-3:] if len(positions) >= 3 else positions
            last3_avg = statistics.mean(last3)
            overall_avg = statistics.mean(positions)

            # Trend adjustment (only meaningful with 3+ total runs)
            if len(positions) >= 3:
                diff = overall_avg - last3_avg
                # diff > 0 → improving, diff < 0 → declining
                trend = diff * 0.15  # 15% of the gap
                trend = max(-1.0, min(1.0, trend))
                last3_avg = max(1.0, last3_avg - trend)

            adjusted.append(last3_avg)

        return self._normalize_field(adjusted, higher_is_better=False)

    # --------------------------------------------------------
    # FACTOR 5: Historical Data  (trainer SR + jockey SR + horse SR)
    # --------------------------------------------------------
    def _score_historical_data(self, runners: List[Runner],
                               race: RaceInfo) -> List[float]:
        """Average of trainer strike-rate, jockey strike-rate, and horse
        win-rate.  Each sub-score is the raw strike-rate percentage
        (wins / runs × 100).  The final averages are then field-normalised.
        """
        raw_averages: List[Optional[float]] = []
        for r in runners:
            sub_scores: List[float] = []

            # Trainer strike rate
            t_stats = self._get_trainer_stats(
                r.trainer, race.race_type, race.country)
            if t_stats and t_stats["runs"] > 0:
                sub_scores.append(t_stats["wins"] / t_stats["runs"] * 100.0)

            # Jockey strike rate
            j_stats = self._get_jockey_stats(
                r.jockey, race.race_type, race.country)
            if j_stats and j_stats["runs"] > 0:
                sub_scores.append(j_stats["wins"] / j_stats["runs"] * 100.0)

            # Horse win rate
            h_stats = self._get_horse_stats(
                r.name, race.race_type, race.country)
            if h_stats and h_stats["runs"] > 0:
                sub_scores.append(h_stats["wins"] / h_stats["runs"] * 100.0)

            if sub_scores:
                raw_averages.append(statistics.mean(sub_scores))
            else:
                raw_averages.append(None)

        return self._normalize_field(raw_averages, higher_is_better=True)

    # --------------------------------------------------------
    # FACTOR 6 (Flat only): Top Speed  (higher = better)
    # --------------------------------------------------------
    def _score_top_speed(self, runners: List[Runner]) -> List[float]:
        values = [float(r.top_speed) if r.top_speed is not None else None
                  for r in runners]
        return self._normalize_field(values, higher_is_better=True)

    # --------------------------------------------------------
    # FACTOR 7 (Flat only): Draw Bias
    # --------------------------------------------------------
    @staticmethod
    def _score_draw_bias(runners: List[Runner],
                         race: RaceInfo) -> List[float]:
        """Convert existing _draw_multiplier (0.96–1.04) to 0-100 scale."""
        scores = []
        for r in runners:
            mult = _draw_multiplier(r, race)
            # 0.96 → 0, 1.0 → 50, 1.04 → 100
            score = (mult - 0.96) / 0.08 * 100.0
            scores.append(max(0.0, min(100.0, score)))
        return scores

    # --------------------------------------------------------
    # FACTOR 8 (Flat only): Pace Profile
    # --------------------------------------------------------
    @staticmethod
    def _score_pace_profile(runners: List[Runner],
                            race: RaceInfo) -> List[float]:
        """Convert existing _pace_multiplier (0.96–1.04) to 0-100 scale."""
        scores = []
        for r in runners:
            mult = _pace_multiplier(r, runners, race)
            # 0.96 → 0, 1.0 → 50, 1.04 → 100
            score = (mult - 0.96) / 0.08 * 100.0
            scores.append(max(0.0, min(100.0, score)))
        return scores

    # --------------------------------------------------------
    # CONFIDENCE DEDUCTION FOR MISSING DATA
    # --------------------------------------------------------
    def _confidence_deduction(self, trainer: str, jockey: str,
                              horse_name: str, race_type: str = "",
                              country: str = "") -> int:
        """Return confidence points to deduct when historical data is absent.

        Missing trainer in all sources  → -3 points
        Missing jockey in all sources   → -3 points
        Horse absent from the country/type-
          specific rating AND stats file → -2 points

        Maximum total deduction: 8 points.
        """
        deduction = 0
        is_nh = _is_nh(race_type)
        uk = _is_uk(country)

        # Trainer check — country-specific data + UK fallback for UK races
        if uk:
            td = _UK_TRAINER_DATA_NH if is_nh else _UK_TRAINER_DATA_FLAT
        else:
            td = _TRAINER_DATA_NH if is_nh else _TRAINER_DATA_FLAT
        t = trainer.lower().strip()
        trainer_found = (
            t in td
            or any(n in t or t in n for n in td)
        )
        if not trainer_found and uk:
            trainer_found = (
                t in _UK_TRAINER_FALLBACK
                or any(n in t or t in n for n in _UK_TRAINER_FALLBACK)
            )
        if not trainer_found:
            deduction += 3

        # Jockey check
        if uk:
            jd = _UK_JOCKEY_DATA_NH if is_nh else _UK_JOCKEY_DATA_FLAT
        else:
            jd = _JOCKEY_DATA_NH if is_nh else _JOCKEY_DATA_FLAT
        j = jockey.lower().strip()
        jockey_found = (
            j in jd
            or any(n in j or j in n for n in jd)
        )
        if not jockey_found and uk:
            jockey_found = any(n in j for n in _UK_JOCKEY_FALLBACK)
        if not jockey_found:
            deduction += 3

        # Horse check
        name = _normalize_name(horse_name)
        if uk:
            rats = _UK_HORSE_RATINGS_NH if is_nh else _UK_HORSE_RATINGS_FLAT
            stats = _UK_HORSE_STATS_NH if is_nh else _UK_HORSE_STATS_FLAT
        else:
            rats = _HORSE_RATINGS_NH if is_nh else _HORSE_RATINGS_FLAT
            stats = _HORSE_STATS_NH if is_nh else _HORSE_STATS_FLAT
        horse_has_data = (
            rats.get(name) is not None
            or stats.get(name) is not None
        )
        if not horse_has_data:
            deduction += 2

        return deduction

    # --------------------------------------------------------
    # RACE QUALITY CHECK  (pre-analysis, multi-signal)
    # --------------------------------------------------------
    def race_quality_check(self, race: RaceInfo,
                           runners: List[Runner]) -> dict:
        """Five-signal pre-analysis quality gate.

        Each signal scores 0–3.  Total 0–15:
          HIGH   = 11+   well-documented, analysable race
          MEDIUM = 7–10  enough signal, some gaps
          LOW    = 0–6   limited data, treat picks with caution

        Signals
        -------
        data_coverage   % of field with trainer + jockey in our data
        form_quality    % of field with ≥2 recorded form results
        field_size      sweet spot is 6–12 runners
        race_type       flat > NH for modelling confidence
        field_richness  runners with at least one traceable signal
                        (trainer OR jockey known) AND ≥1 form digit
        """
        n = len(runners)
        if n == 0:
            return {
                "level": "LOW",
                "headline": "No runners found.",
                "total_score": 0,
                "signals": {},
            }

        # ── Signal 1: Data coverage ──────────────────────────────────
        known: float = 0.0
        for r in runners:
            ded = self._confidence_deduction(
                r.trainer, r.jockey, r.name, race.race_type, race.country)
            if ded == 0:
                known += 1.0
            elif ded <= 2:
                known += 0.5
        cov_pct = known / n
        if cov_pct >= 0.80:
            data_s, data_l = 3, "Strong data coverage across the field"
        elif cov_pct >= 0.55:
            data_s, data_l = 2, "Decent coverage — a few runners untracked"
        elif cov_pct >= 0.35:
            data_s, data_l = 1, "Patchy data — several runners untracked"
        else:
            data_s, data_l = 0, "Limited data across most of the field"

        # ── Signal 2: Form quality ────────────────────────────────────
        form_rich = sum(
            1 for r in runners
            if len([c for c in (r.form or "") if c.isdigit()]) >= 2
        )
        form_pct = form_rich / n
        if form_pct >= 0.70:
            form_s, form_l = 3, "Good form figures available across the field"
        elif form_pct >= 0.50:
            form_s, form_l = 2, "Reasonable form data for most runners"
        elif form_pct >= 0.30:
            form_s, form_l = 1, "Thin form — limited runs to compare"
        else:
            form_s, form_l = 0, "Very sparse form — most runners unraced or unknown"

        # ── Signal 3: Field size ──────────────────────────────────────
        if 6 <= n <= 12:
            size_s, size_l = 3, f"Good field size ({n} runners)"
        elif 4 <= n <= 5 or 13 <= n <= 16:
            size_s, size_l = 2, f"Workable field size ({n} runners)"
        elif 2 <= n <= 3 or 17 <= n <= 20:
            size_s, size_l = 1, f"Edge-case field size ({n} runners)"
        else:
            size_s, size_l = 0, f"Very large field ({n} runners) — difficult to model"

        # ── Signal 4: Race type ───────────────────────────────────────
        is_nh = _is_nh(race.race_type)
        if not is_nh:
            type_s, type_l = 3, "Flat race — well-structured for modelling"
        elif _is_uk(race.country):
            type_s, type_l = 2, "National Hunt — solid UK data available"
        else:
            type_s, type_l = 1, "National Hunt — more variance than flat"

        # ── Signal 5: Mixed signal richness ──────────────────────────
        rich = sum(
            1 for r in runners
            if (
                self._confidence_deduction(
                    r.trainer, r.jockey, r.name,
                    race.race_type, race.country) < 5
                and len([c for c in (r.form or "") if c.isdigit()]) >= 1
            )
        )
        rich_pct = rich / n
        if rich_pct >= 0.65:
            rich_s, rich_l = 3, "Most runners have traceable signals"
        elif rich_pct >= 0.40:
            rich_s, rich_l = 2, "A core group of runners have enough signal"
        elif rich_pct >= 0.20:
            rich_s, rich_l = 1, "Only a handful of runners have usable signal"
        else:
            rich_s, rich_l = 0, "Very few runners have any traceable signal"

        total = data_s + form_s + size_s + type_s + rich_s

        if total >= 11:
            level = "HIGH"
            headline = "This looks like a well-documented, analysable race."
        elif total >= 7:
            level = "MEDIUM"
            headline = "Enough signal to analyse, but some gaps in the data."
        else:
            level = "LOW"
            headline = "Limited data across this field — treat picks with caution."

        return {
            "level":       level,
            "headline":    headline,
            "total_score": total,
            "signals": {
                "data_coverage":  {"score": data_s, "label": data_l},
                "form_quality":   {"score": form_s, "label": form_l},
                "field_size":     {"score": size_s, "label": size_l},
                "race_type":      {"score": type_s, "label": type_l},
                "field_richness": {"score": rich_s, "label": rich_l},
            },
        }

    # --------------------------------------------------------
    # MAIN ANALYSIS
    # --------------------------------------------------------
    def analyze(self, race: RaceInfo, runners: List[Runner],
                odds: Optional[Dict[str, str]] = None):

        is_flat = race.discipline == "Flat" and not _is_nh(race.race_type)
        is_jumps = race.discipline == "Jumps" or _is_nh(race.race_type)

        # If discipline is Unknown, infer from race_type keywords
        if not is_flat and not is_jumps:
            is_jumps = _is_nh(race.race_type)
            is_flat = not is_jumps

        # ── Compute all factor scores (lists of 0-100, one per runner) ───
        or_scores       = self._score_or_ratings(runners)
        rpr_scores      = self._score_rpr_ratings(runners)
        form_scores     = self._score_overall_form(runners)
        last3_scores    = self._score_last3_form(runners)
        hist_scores     = self._score_historical_data(runners, race)

        # Flat-only additional factors
        ts_scores   = self._score_top_speed(runners)     if is_flat else None
        draw_scores = self._score_draw_bias(runners, race) if is_flat else None
        pace_scores = self._score_pace_profile(runners, race) if is_flat else None

        num_factors = 8 if is_flat else 5

        # ── Build scored list ────────────────────────────────────────────
        scored = []
        for i, r in enumerate(runners):
            factors = {
                "or_rating":       round(or_scores[i], 1),
                "rpr_rating":      round(rpr_scores[i], 1),
                "overall_form":    round(form_scores[i], 1),
                "last_3_form":     round(last3_scores[i], 1),
                "historical_data": round(hist_scores[i], 1),
            }

            all_vals = [
                or_scores[i], rpr_scores[i], form_scores[i],
                last3_scores[i], hist_scores[i],
            ]

            if is_flat:
                factors["top_speed"]    = round(ts_scores[i], 1)
                factors["draw_bias"]    = round(draw_scores[i], 1)
                factors["pace_profile"] = round(pace_scores[i], 1)
                all_vals.extend([
                    ts_scores[i], draw_scores[i], pace_scores[i],
                ])

            final_score = statistics.mean(all_vals)

            scored.append({
                "name":    r.name,
                "score":   round(final_score, 1),
                "factors": factors,
            })

        # ── Sort by composite score descending ───────────────────────────
        scored.sort(key=lambda x: x["score"], reverse=True)

        # ── Gold pick = highest score (always produced) ──────────────────
        gold = None
        if scored:
            gold = {
                "name":    scored[0]["name"],
                "score":   scored[0]["score"],
                "factors": scored[0]["factors"],
                "label":   "Gold Pick",
            }

        # ── Silver pick (optional) ───────────────────────────────────────
        silver = None
        if self.silver_enabled and gold and len(scored) >= 2:
            gold_top_factor = max(gold["factors"].items(), key=lambda kv: kv[1])[0]
            threshold = gold["score"] * 0.85
            for cand in scored[1:]:
                if cand["score"] < threshold:
                    break
                cand_top = max(cand["factors"].items(), key=lambda kv: kv[1])[0]
                if cand_top != gold_top_factor:
                    silver = {
                        "name":    cand["name"],
                        "score":   cand["score"],
                        "factors": cand["factors"],
                        "label":   "Silver Pick",
                    }
                    break

        # ── Dark Horse pick (optional) ───────────────────────────────────
        dark_horse = None
        if self.dark_horse_enabled and len(scored) > 3:
            # Map name -> Runner for trend inspection
            runner_by_name = {r.name: r for r in runners}
            best_dh = None
            best_dh_reason_strength = 0.0

            for cand in scored[3:]:
                # Plausibility gate: must score within 70% of Gold's score
                if not gold or cand["score"] < gold["score"] * 0.70:
                    continue

                r = runner_by_name.get(cand["name"])
                reason = None
                strength = 0.0

                # Improving trend: last 3 form > overall form by a margin
                last3 = cand["factors"].get("last_3_form", 0)
                overall = cand["factors"].get("overall_form", 0)
                if last3 - overall >= 15:
                    reason = "improving_trend"
                    strength = last3 - overall

                # Notably high single factor (>=80)
                top_key, top_val = max(cand["factors"].items(), key=lambda kv: kv[1])
                if top_val >= 80 and top_val > strength:
                    reason = f"high_{top_key}"
                    strength = top_val

                if reason and strength > best_dh_reason_strength:
                    best_dh_reason_strength = strength
                    best_dh = {
                        "name":    cand["name"],
                        "score":   cand["score"],
                        "factors": cand["factors"],
                        "label":   "Dark Horse",
                        "reason":  reason,
                    }

            dark_horse = best_dh

        # ── Labels on full rankings ──────────────────────────────────────
        silver_name = silver["name"] if silver else None
        dh_name = dark_horse["name"] if dark_horse else None
        for i, entry in enumerate(scored):
            if i == 0:
                entry["label"] = "Gold Pick"
            elif entry["name"] == silver_name:
                entry["label"] = "Silver Pick"
            elif entry["name"] == dh_name:
                entry["label"] = "Dark Horse"
            else:
                entry["label"] = ""

        return {
            "gold_pick":           gold,
            "silver_pick":         silver,
            "dark_horse":          dark_horse,
            "silver_available":    silver is not None,
            "dark_horse_available": dark_horse is not None,
            "full_rankings":       scored,
            "is_jumps":            is_jumps,
            "is_flat":             is_flat,
            "num_factors":         num_factors,
        }
