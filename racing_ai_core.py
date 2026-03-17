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
# CONFIDENCE SYSTEM  (race + per-pick)
# ============================================================

def _race_confidence_label(
    scored: list,
    race: RaceInfo,
    runners: List[Runner],
    gold_entry: Optional[dict],
    norm_prob: Dict[str, float],
    odds_decimal: Dict[str, float],
) -> str:
    """Rate how trustworthy / clear / playable this race is as a betting medium.

    Returns 'HIGH', 'MEDIUM', or 'LOW'.
    Points-based: HIGH ≥ 50 · MEDIUM ≥ 20 · LOW < 20.

    Ingredients
    -----------
    1. Top-vs-second score gap        (max +25)
    2. Top-vs-third score gap         (max +15)
    3. Average data coverage, top 3   (max +20)
    4. Market corroboration for Gold  (−15 to +15)
    5. Chaos / volatility penalties   (cumulative negatives)
    """
    pts = 0
    n   = len(scored)

    # 1. Top-vs-second score gap
    if n >= 2 and scored[1]["score"] > 0:
        gap12 = (scored[0]["score"] - scored[1]["score"]) / scored[1]["score"]
        if gap12 >= 0.05:
            pts += 25
        elif gap12 >= 0.025:
            pts += 15
        elif gap12 >= 0.01:
            pts += 5
    elif n == 1:
        pts += 15

    # 2. Top-vs-third score gap
    if n >= 3 and scored[2]["score"] > 0:
        gap13 = (scored[0]["score"] - scored[2]["score"]) / scored[2]["score"]
        if gap13 >= 0.08:
            pts += 15
        elif gap13 >= 0.04:
            pts += 8
        elif gap13 >= 0.02:
            pts += 3

    # 3. Average data coverage of top 3
    top3 = scored[:min(3, n)]
    if top3:
        avg_cov = sum(h.get("_coverage", 0.0) for h in top3) / len(top3)
        if avg_cov >= 0.60:
            pts += 20
        elif avg_cov >= 0.40:
            pts += 12
        elif avg_cov >= 0.20:
            pts += 5

    # 4. Market corroboration for Gold
    if gold_entry and norm_prob and len(norm_prob) >= 2:
        gname     = _normalize_name(gold_entry["name"])
        gold_prob = norm_prob.get(gname, 0.0)
        avg_prob  = 1.0 / len(norm_prob)
        gold_dec  = odds_decimal.get(gname, 0.0)
        if gold_prob >= 2.0 * avg_prob:
            pts += 15   # model and market both back same clear favourite
        elif gold_prob >= 1.3 * avg_prob:
            pts += 8    # near-agreement
        if gold_dec > 51.0:
            pts -= 15   # 50/1+ → market strongly disagrees
        elif gold_dec > 20.0:
            pts -= 5

    # 5. Chaos / volatility penalties
    if _is_nh(race.race_type):
        pts -= 5   # National Hunt: naturally higher variance than Flat
        rt_low = race.race_type.lower()
        if "handicap" in rt_low and "chase" in rt_low:
            pts -= 5   # handicap chases: wide-open, form often inverts
        elif race.distance_f >= 20.0:
            pts -= 5   # extreme-distance NH: stamina/fitness hard to model
    if _is_wet_jumps(race):
        pts -= 5   # attritional wet-jumps conditions flip form reliably

    if norm_prob and len(norm_prob) >= 2:
        max_p = max(norm_prob.values())
        avg_p = 1.0 / len(norm_prob)
        if max_p < 1.5 * avg_p:
            pts -= 10  # no dominant price — genuinely open field

    if n >= 3 and scored[2]["score"] > 0:
        spread13 = (scored[0]["score"] - scored[2]["score"]) / scored[2]["score"]
        if spread13 < 0.01:
            pts -= 10  # top 3 within 1% — no meaningful separation

    # Missing pace context (Flat races only)
    if race.discipline == "Flat" and _pace_shape(runners) == "unknown":
        pts -= 3

    if pts >= 50:
        return "HIGH"
    if pts >= 20:
        return "MEDIUM"
    return "LOW"


def _gold_pick_confidence(
    gold: dict,
    scored: list,
    race: RaceInfo,
    race_conf: str,
    norm_prob: Dict[str, float],
    odds_decimal: Dict[str, float],
) -> int:
    """How confident are we that Gold is the right main selection?

    Components: score edge · data quality · going suitability ·
                market corroboration · race-level adjustment.
    Returns int [70, 95].
    """
    pts = 78   # base: solid but not certain

    # Score edge over 2nd
    if len(scored) >= 2 and scored[1]["score"] > 0:
        gap = (gold["score"] - scored[1]["score"]) / scored[1]["score"]
        if gap >= 0.05:
            pts += 6
        elif gap >= 0.025:
            pts += 4
        elif gap >= 0.01:
            pts += 2
        elif gap < 0.005:
            pts -= 3   # nip-and-tuck with 2nd — less certain

    # Additional credit for gap over 3rd (modest — confirms Gold is clear of the pack)
    if len(scored) >= 3 and scored[2]["score"] > 0:
        gap3 = (gold["score"] - scored[2]["score"]) / scored[2]["score"]
        if gap3 >= 0.08:
            pts += 3
        elif gap3 >= 0.04:
            pts += 2
        elif gap3 >= 0.02:
            pts += 1

    # Data coverage
    cov = gold.get("_coverage", 0.0)
    if cov >= 0.60:
        pts += 3
    elif cov >= 0.35:
        pts += 1
    elif cov < 0.20:
        pts -= 4

    # Going suitability
    gpen = gold.get("_going_pen", 0)
    if gpen >= 3:
        pts -= 3
    elif gpen >= 1:
        pts -= 1

    # Market corroboration
    if norm_prob and len(norm_prob) >= 2 and odds_decimal:
        gname     = _normalize_name(gold["name"])
        gold_prob = norm_prob.get(gname, 0.0)
        avg_prob  = 1.0 / len(norm_prob)
        gold_dec  = odds_decimal.get(gname, 0.0)
        if gold_prob >= 2.0 * avg_prob:
            pts += 4   # market backs same horse — corroborating signal
        elif gold_prob >= 1.3 * avg_prob:
            pts += 2
        if gold_dec > 51.0:
            pts -= 5   # 50/1+ → market strongly disagrees
        elif gold_dec > 20.0:
            pts -= 2

    # Race-level adjustment
    if race_conf == "HIGH":
        pts += 2
    elif race_conf == "LOW":
        pts -= 4

    return max(70, min(95, pts))


def _silver_pick_confidence(
    silver: dict,
    gold: dict,
    scored: list,
    race: RaceInfo,
    race_conf: str,
    norm_prob: Dict[str, float],
    odds_decimal: Dict[str, float],
) -> int:
    """How confident are we that Silver is the right secondary pick?

    Components: score proximity to Gold · profile distinctiveness ·
                data quality · going suitability · market plausibility ·
                race-level adjustment.
    Returns int [70, 95].  Usually below Gold confidence.
    """
    pts = 74   # base: below Gold by default

    # Score proximity to Gold
    gold_sc = gold.get("score", 0.0) if gold else 0.0
    if gold_sc > 0:
        ratio = silver["score"] / gold_sc
        if ratio >= 0.95:
            pts += 6   # near-equal — very close race
        elif ratio >= 0.85:
            pts += 4
        elif ratio >= 0.75:
            pts += 2
        # < 0.75 → 0  (plausibility gate already applied in pick selection)

    # Profile distinctiveness: form-driven vs class-driven
    n = len(scored)
    if n > 0 and gold:
        avg_form  = sum(h["form"] for h in scored) / n
        avg_class = sum(h["_rating_b"] * h["_perf_b"] for h in scored) / n
        if avg_form > 0 and avg_class > 0:
            g_form_rel  = gold["form"]   / avg_form
            g_class_rel = (gold["_rating_b"]   * gold["_perf_b"])   / avg_class
            s_form_rel  = silver["form"] / avg_form
            s_class_rel = (silver["_rating_b"] * silver["_perf_b"]) / avg_class
            # Different dominant strength → genuinely contrasting danger
            if (g_form_rel > g_class_rel) != (s_form_rel > s_class_rel):
                pts += 2

    # Data coverage
    cov = silver.get("_coverage", 0.0)
    if cov >= 0.60:
        pts += 2
    elif cov >= 0.35:
        pts += 1
    elif cov < 0.20:
        pts -= 3

    # Going suitability
    gpen = silver.get("_going_pen", 0)
    if gpen >= 3:
        pts -= 3
    elif gpen >= 1:
        pts -= 1

    # Market plausibility relative to Gold
    if odds_decimal and gold:
        gname = _normalize_name(gold["name"])
        sname = _normalize_name(silver["name"])
        gdec  = odds_decimal.get(gname, 0.0)
        sdec  = odds_decimal.get(sname, 0.0)
        if gdec > 0 and sdec > 0:
            price_ratio = sdec / gdec
            if price_ratio <= 3.0:
                pts += 2   # credible market challenger
            elif price_ratio > 10.0:
                pts -= 2   # much bigger price → less likely secondary pick

    # Race-level adjustment
    if race_conf == "HIGH":
        pts += 1
    elif race_conf == "LOW":
        pts -= 3

    return max(70, min(95, pts))


def _dark_horse_confidence(
    dark: dict,
    gold: dict,
    scored: list,
    race: RaceInfo,
    race_conf: str,
    norm_prob: Dict[str, float],
    odds_decimal: Dict[str, float],
) -> int:
    """How confident are we this is the right speculative outsider pick?

    Components: plausibility · upside signals · data quality ·
                market / odds context · race-level adjustment.
    Returns int [70, 95].  Usually below Gold.
    Chaotic race does NOT inflate dark horse confidence.
    """
    pts = 71   # base: inherently speculative

    # Plausibility — score relative to Gold
    gold_sc = gold.get("score", 0.0) if gold else 0.0
    if gold_sc > 0:
        ratio = dark["score"] / gold_sc
        if ratio >= 0.80:
            pts += 5
        elif ratio >= 0.70:
            pts += 3
        elif ratio >= 0.60:
            pts += 1

    # Upside signals — evidence the model may underestimate this horse
    rating_edge = dark.get("_rating_edge", 0.0)
    if rating_edge >= 5:
        pts += 4   # rated above field average but ranked lower by model
    elif rating_edge >= 2:
        pts += 2

    perf_b = dark.get("_perf_b", 1.0)
    if perf_b >= 1.05:
        pts += 2   # win-rate stats show ability not fully captured in score

    # Data coverage
    cov = dark.get("_coverage", 0.0)
    if cov >= 0.50:
        pts += 2
    elif cov < 0.20:
        pts -= 3

    # Odds context — must be an outsider but not hopeless
    if odds_decimal:
        dname = _normalize_name(dark["name"])
        ddec  = odds_decimal.get(dname, 0.0)
        if ddec > 0:
            if ddec > 34.0:
                pts -= 4   # 33/1+ — very hard to win
            elif ddec > 20.0:
                pts -= 1
            elif ddec < 6.0:
                pts -= 3   # too short to qualify as a value dark horse

    # Race-level adjustment (chaos does NOT inflate dark horse confidence)
    if race_conf == "HIGH":
        pts += 1
    elif race_conf == "LOW":
        pts -= 2

    return max(70, min(95, pts))


# ============================================================
# CORE ENGINE
# ============================================================

class RacingAICore:

    # Set to True to include a dark horse pick in analyze() output.
    # When False (default), only gold and silver picks are returned;
    # the dark horse is still evaluated internally but suppressed.
    dark_horse_enabled: bool = False

    # --------------------------------------------------------
    # TRAINER POWER
    # --------------------------------------------------------
    def trainer_style_boost(self, trainer: str, race_type: str = "",
                            country: str = "") -> float:
        t = trainer.lower().strip()
        uk = _is_uk(country)

        # Select primary dataset by country + race type
        if uk:
            data = _UK_TRAINER_DATA_NH if _is_nh(race_type) else _UK_TRAINER_DATA_FLAT
        else:
            data = _TRAINER_DATA_NH if _is_nh(race_type) else _TRAINER_DATA_FLAT

        # 1. Exact match
        if t in data:
            return data[t]

        # 2. Partial match
        for name, boost in data.items():
            if name in t or t in name:
                return boost

        # 3. UK hardcoded fallback (UK races only)
        if uk:
            if t in _UK_TRAINER_FALLBACK:
                return _UK_TRAINER_FALLBACK[t]
            for name, boost in _UK_TRAINER_FALLBACK.items():
                if name in t or t in name:
                    return boost

        return 1.0

    # --------------------------------------------------------
    # JOCKEY STRENGTH
    # --------------------------------------------------------
    def jockey_boost(self, jockey: str, race_type: str = "",
                     country: str = "") -> float:
        j = jockey.lower().strip()
        uk = _is_uk(country)

        if uk:
            data = _UK_JOCKEY_DATA_NH if _is_nh(race_type) else _UK_JOCKEY_DATA_FLAT
        else:
            data = _JOCKEY_DATA_NH if _is_nh(race_type) else _JOCKEY_DATA_FLAT

        # 1. Exact match
        if j in data:
            return data[j]

        # 2. Partial match
        for name, boost in data.items():
            if name in j or j in name:
                return boost

        # 3. UK hardcoded fallback (UK races only)
        if uk:
            for name, boost in _UK_JOCKEY_FALLBACK.items():
                if name in j:
                    return boost

        return 1.0

    # --------------------------------------------------------
    # TRAINER + JOCKEY CHEMISTRY
    # --------------------------------------------------------
    def combo_boost(self, trainer: str, jockey: str) -> float:
        t = trainer.lower().strip()
        j = jockey.lower().strip()

        for (tt, jj), boost in TRAINER_JOCKEY_COMBOS.items():
            if tt in t and jj in j:
                return boost

        return 1.0

    # --------------------------------------------------------
    # HORSE RATING BOOST
    # --------------------------------------------------------
    def horse_rating_boost(self, horse_name: str, race_type: str,
                           country: str = "") -> float:
        """Look up official rating and convert to a score multiplier.

        Flat ratings (100-126): max +8%.
        NH ratings (140-164): max +8%.
        Uses only the dataset that matches the country + race type.
        """
        name = _normalize_name(horse_name)
        uk = _is_uk(country)

        if uk:
            rating = (_UK_HORSE_RATINGS_NH if _is_nh(race_type)
                      else _UK_HORSE_RATINGS_FLAT).get(name)
        else:
            rating = (_HORSE_RATINGS_NH if _is_nh(race_type)
                      else _HORSE_RATINGS_FLAT).get(name)

        if rating is None:
            return 1.0

        if rating <= 130:
            # Flat scale: 100 → 0%, 126 → +8%
            boost = (rating - 100) / 26.0 * 0.08
        else:
            # NH scale: 140 → 0%, 164 → +8%
            boost = (rating - 140) / 24.0 * 0.08

        return round(1.0 + max(0.0, boost), 4)

    # --------------------------------------------------------
    # HORSE PERFORMANCE BOOST
    # --------------------------------------------------------
    def horse_performance_boost(self, horse_name: str, race_type: str = "",
                                country: str = "") -> float:
        """Derive a multiplier from the horse's own win-rate in stats files."""
        name = _normalize_name(horse_name)
        uk = _is_uk(country)

        if uk:
            stats = (_UK_HORSE_STATS_NH if _is_nh(race_type)
                     else _UK_HORSE_STATS_FLAT).get(name)
        else:
            stats = (_HORSE_STATS_NH if _is_nh(race_type)
                     else _HORSE_STATS_FLAT).get(name)

        if not stats:
            return 1.0
        return _win_rate_to_multiplier(stats["wins"], stats["runs"])

    # --------------------------------------------------------
    # FORM SCORE
    # --------------------------------------------------------
    def form_score(self, form: str) -> float:
        # In racing form strings, 0 means finished 10th or worse (unplaced).
        # Treat it as 10 so bad form doesn't score better than a 1st.
        digits = [10 if c == "0" else int(c) for c in form if c.isdigit()]
        if not digits:
            return 0.5

        avg = statistics.mean(digits)
        score = max(0.3, 1.2 - (avg * 0.12))

        # Improving trend bonus — only when last run is genuinely better
        if len(digits) >= 2 and digits[-1] < digits[-2]:
            score *= 1.05

        return score

    # --------------------------------------------------------
    # WEIGHT SCORE
    # --------------------------------------------------------
    def weight_score(self, runner: Runner) -> float:
        net_weight = runner.weight_lbs - runner.jockey_claim_lbs
        # Cap at 1.12 so a very light weight cannot inflate the score
        # beyond a realistic +12% advantage.
        return min(1.12, max(0.75, 1.2 - ((net_weight - 126) * 0.01)))

    # --------------------------------------------------------
    # AGE SCORE
    # --------------------------------------------------------
    def age_score(self, age: int) -> float:
        if 4 <= age <= 6:
            return 1.05
        if age >= 9:
            return 0.95
        return 1.0

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
        The deduction also drives adaptive racecard weighting and a direct
        score penalty in analyze(), so unknown horses rank lower and are
        deprioritised for Gold/Silver picks.
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
    # AI PICK WRITEUP
    # --------------------------------------------------------
    @staticmethod
    def _build_writeup(
        form: float,
        trainer_b: float, jockey_b: float, combo_b: float,
        structural: float, fitness: float,
        rating_boost: float, perf_boost: float,
        conf_deduction: int = 0,
        going_penalty: int = 0,
        rating_edge: float = 0.0,
    ) -> str:
        """Generate a 1–2 sentence Racing Post-style writeup from scoring factors.

        Sentence 1 — strongest positive reasons (up to 2 factors).
        Sentence 2 — uncertainty caveat when confidence was reduced.
        Score and ranking are never referenced; only analytical factors.
        """
        strengths = []

        # Form
        if form >= 0.95:
            strengths.append("strong recent form")
        elif form >= 0.75:
            strengths.append("solid form figures")

        # Official rating
        if rating_boost >= 1.05:
            strengths.append("high official rating")
        elif rating_boost >= 1.02:
            strengths.append("solid official rating")

        # Connections — most specific descriptor first
        if combo_b > 1.0:
            strengths.append("proven trainer/jockey partnership")
        elif trainer_b >= 1.07:
            strengths.append("in-form training operation")
        elif jockey_b >= 1.06:
            strengths.append("top jockey booking")
        elif trainer_b >= 1.04 or jockey_b >= 1.04:
            strengths.append("positive connections")

        # Historical performance
        if perf_boost >= 1.05:
            strengths.append("strong winning record")
        elif perf_boost >= 1.02:
            strengths.append("decent win rate")

        # Weight / structural
        if structural >= 1.08:
            strengths.append("favourable weight")

        # Age / fitness
        if fitness >= 1.04:
            strengths.append("prime age profile")

        # Fallback concerns (used only when no strengths)
        weight_concern = structural <= 0.82
        form_concern = form < 0.50

        # --- Sentence 1: primary assessment ---
        if strengths:
            top = strengths[:2]
            if len(top) == 1:
                sentence1 = top[0].capitalize() + "."
            else:
                sentence1 = (top[0].capitalize() + " alongside "
                             + top[1] + ".")
        elif weight_concern:
            sentence1 = "Carries a significant weight burden."
        elif form_concern:
            sentence1 = "Recent form figures are a concern."
        else:
            sentence1 = "Limited historical data available for assessment."

        # --- Sentence 2: uncertainty caveats ---
        unc_parts = []
        if conf_deduction >= 5:
            unc_parts.append("Confidence notably reduced due to limited profile data")
        elif conf_deduction >= 2:
            unc_parts.append("Confidence slightly reduced due to limited profile data")
        if going_penalty > 0:
            unc_parts.append("testing ground adds further uncertainty")

        if unc_parts:
            unc = unc_parts[0]
            if len(unc_parts) > 1:
                unc += "; " + unc_parts[1]
            return sentence1 + " " + unc + "."

        # Field-strength context phrase (only when no uncertainty sentence)
        if rating_edge >= 5:
            return sentence1 + " Holds a clear ratings edge over this field."
        if rating_edge <= -5:
            return sentence1 + " Faces stronger opposition on ratings."

        # Minor concern note when no other second sentence
        if weight_concern and strengths:
            return sentence1 + " Weight burden may be a factor."
        if form_concern and strengths:
            return sentence1 + " Form is worth monitoring."

        return sentence1

    # --------------------------------------------------------
    # GOING / GROUND CONFIDENCE PENALTY
    # --------------------------------------------------------
    def _going_penalty(self, runner: Runner, going: str,
                       race_type: str = "", country: str = "",
                       wet_jumps: bool = False) -> int:
        """Confidence deduction when going is testing (soft/heavy/good-to-soft).

        Also applies a small score reduction in the caller.
        Deductions (max combined 5, or 3 in Wet Jumps mode):
          +2  horse has fewer than 10 career runs (inexperience on testing ground)
               OR has no historical stats at all
          +3  horse carries more than 135 lbs net (heavy burden harder on soft)

        In Wet Jumps mode the cap is reduced from 5 → 3.  We already know the
        race is on testing ground, so the generic "uncertainty" penalty is less
        appropriate; the model instead uses the wet-ground scoring layer to
        identify which runners are better suited to the conditions.
        """
        if going.lower().strip() not in _TESTING_GOING:
            return 0

        penalty = 0
        name = _normalize_name(runner.name)
        uk = _is_uk(country)
        is_nh_flag = _is_nh(race_type)

        # Look up career run count from stats files
        if uk:
            stats = (_UK_HORSE_STATS_NH if is_nh_flag
                     else _UK_HORSE_STATS_FLAT).get(name)
        else:
            stats = (_HORSE_STATS_NH if is_nh_flag
                     else _HORSE_STATS_FLAT).get(name)

        # No data at all, or fewer than 10 career runs → uncertain on testing ground
        if stats is None or stats["runs"] < 10:
            penalty += 2

        # High net weight is a greater physical burden on soft/heavy ground
        net_weight = runner.weight_lbs - runner.jockey_claim_lbs
        if net_weight > 135:
            penalty += 3

        # In Wet Jumps mode the base uncertainty penalty is softened — the
        # wet-ground scoring layer handles differentiation between runners.
        cap = 3 if wet_jumps else 5
        return min(penalty, cap)

    # --------------------------------------------------------
    # WET JUMPS MODE — contextual score adjustment
    # --------------------------------------------------------
    def _wet_jumps_adjustment(self, runner: Runner, race: RaceInfo) -> float:
        """Score multiplier applied only in Wet Jumps mode.

        Re-weights runners based on evidence specifically relevant to wet,
        attritional National Hunt races.  The adjustment is deliberately
        signal-driven: it can move an outsider with strong wet-ground evidence
        ahead of a shorter-priced rival with no such evidence, but does not
        blindly boost big prices.

        Factors boosted:
          • Repeated good finishes on soft/heavy/testing ground
          • Combined wet + today's trip stamina (strongest signal)
          • High completion reliability (few F/P/U in form string)
          • Comment phrases: jumping accuracy, staying-on, finishing strength

        Factors reduced:
          • No wet-ground history when enough runs exist (genuine unknown)
            — unless comment indicates clear stayer/stamina evidence
          • Frequent non-finishers (F/P/U > 50% of form)
          • Negative jumping / stopping comments

        Range: approximately 0.93 – 1.15 depending on evidence stack.
        """
        prev = runner.previous_runs or []
        cmt  = (runner.comment or "").lower()
        mult = 1.0

        # ── Wet-ground evidence from previous runs ───────────────────────────
        wet_runs = [
            p for p in prev
            if _going_bucket(p.get("going", "")) == "soft"
            and isinstance(p.get("pos"), int)
            and isinstance(p.get("field_size"), int)
            and p["field_size"] > 1
        ]
        if len(wet_runs) >= 2:
            avg_rel = statistics.mean(
                p["pos"] / p["field_size"] for p in wet_runs
            )
            if avg_rel <= 0.20:
                mult *= 1.06   # dominant on wet ground — repeated top-fifth
            elif avg_rel <= 0.30:
                mult *= 1.04   # solid wet-ground performer
            elif avg_rel <= 0.50:
                mult *= 1.02   # above-average on wet
            elif avg_rel >= 0.70:
                mult *= 0.96   # consistently poor on wet ground
        elif len(wet_runs) == 1:
            p1 = wet_runs[0]
            rel1 = p1["pos"] / p1["field_size"]
            if rel1 <= 0.25:
                mult *= 1.025  # won or placed on only wet run — encouraging
            elif rel1 >= 0.75:
                mult *= 0.98   # ran poorly in sole wet outing
        elif len(wet_runs) == 0 and len(prev) >= 3:
            # Has run enough times but never on wet ground — genuine unknown.
            # Reduce penalty if comment indicates the horse is a stayer/stout type.
            _STAYER_HINTS = (
                "stayed on", "kept on", "stays well", "stout stayer",
                "genuine stayer", "stays every yard", "stays this trip",
                "handles cut", "handles soft",
            )
            if not any(h in cmt for h in _STAYER_HINTS):
                mult *= 0.97

        # ── Combined wet-ground + trip stamina (strongest signal) ─────────────
        # A horse that has run on wet ground AND stayed today's trip on that
        # occasion is the clearest evidence for wet-jumps performance.
        if prev and race.distance_f > 0:
            wet_trip_runs = [
                p for p in prev
                if _going_bucket(p.get("going", "")) == "soft"
                and isinstance(p.get("distance_f"), (int, float))
                and p["distance_f"] >= race.distance_f * 0.95
                and isinstance(p.get("pos"), int)
                and isinstance(p.get("field_size"), int)
                and p["field_size"] > 1
            ]
            # Separately: has run at today's trip on any ground
            max_dist = max(
                (p.get("distance_f", 0) for p in prev
                 if isinstance(p.get("distance_f"), (int, float))),
                default=0,
            )
            if wet_trip_runs:
                # Proven at the trip on wet going
                wet_trip_top = sum(
                    1 for p in wet_trip_runs
                    if p["pos"] / p["field_size"] <= 0.30
                )
                if wet_trip_top >= 2:
                    mult *= 1.05   # multiple top-third finishes at trip on wet
                elif wet_trip_top == 1:
                    mult *= 1.03   # one strong run at trip on wet
                else:
                    mult *= 1.01   # ran at trip on wet but not placed
            elif max_dist >= race.distance_f:
                mult *= 1.02   # has proven the trip on any ground

        # ── Completion reliability ────────────────────────────────────────────
        # Falls / PUs / Unseated / Refused are dangerous signals in testing
        # ground — a horse that frequently doesn't finish is a bigger liability.
        if runner.form:
            digits     = sum(1 for c in runner.form if c.isdigit())
            non_finish = sum(1 for c in runner.form.upper()
                             if c in ("F", "P", "U", "R"))
            total = digits + non_finish
            if total >= 4:
                finish_rate = digits / total
                if finish_rate >= 0.85:
                    mult *= 1.025  # very reliable finisher — valuable in testing ground
                elif finish_rate <= 0.50:
                    mult *= 0.96   # frequent non-finisher — higher risk on heavy going

        # ── Jumping reliability (comment-based) ──────────────────────────────
        _JUMP_NEG = (
            "made mistakes", "bad mistake", "not fluent", "sloppy",
            "jumped left", "jumped right", "sketchy jumping",
            "error-prone", "clumsy", "blundered", "serious error",
            "put in a bad one", "hit the last", "untidy",
        )
        _JUMP_POS = (
            "jumped well", "sound jumper", "accurate at obstacles",
            "fluent jumping", "jumping accurately", "stood up well",
            "slick jumping", "great jump", "jumped impeccably",
            "measured his fences", "neat at hurdles", "slick at his hurdles",
        )
        if cmt:
            for phrase in _JUMP_NEG:
                if phrase in cmt:
                    mult *= 0.97   # unreliable jumper — extra risk in testing conditions
                    break
            for phrase in _JUMP_POS:
                if phrase in cmt:
                    mult *= 1.02   # accurate jumper — a material edge on wet ground
                    break

        # ── Finishing strength / stamina (comment-based) ──────────────────────
        _STAMINA_POS = (
            "stayed on", "kept on", "stayed well", "plugged on",
            "finished strongly", "kept on dourly", "found plenty",
            "stays every yard", "stout stayer", "ran on well",
            "keeps finding", "genuine stayer", "hit the line",
            "never gave up", "battled on", "dug deep",
        )
        _STAMINA_NEG = (
            "weakened approaching finish",   # longer phrase first
            "weakened", "tired", "emptied", "folded quickly",
            "faded", "no extra", "stopped quickly", "found nothing",
            "ran flat", "no more to give",
        )
        if cmt:
            for phrase in _STAMINA_POS:
                if phrase in cmt:
                    mult *= 1.02   # keeps finding under pressure — key wet-jumps trait
                    break
            for phrase in _STAMINA_NEG:
                if phrase in cmt:
                    mult *= 0.97   # stopped — a worry in attritional conditions
                    break

        return mult

    # --------------------------------------------------------
    # RAW RATING LOOKUP (for field-context calculation)
    # --------------------------------------------------------
    def _get_horse_rating(self, horse_name: str, race_type: str,
                          country: str = "") -> Optional[int]:
        """Return the raw official rating integer for a horse, or None.

        Reuses the same rating dicts as horse_rating_boost() — no new data.
        Used only for the field-average context layer; never alters scoring.
        """
        name = _normalize_name(horse_name)
        uk = _is_uk(country)
        if uk:
            return (_UK_HORSE_RATINGS_NH if _is_nh(race_type)
                    else _UK_HORSE_RATINGS_FLAT).get(name)
        return (_HORSE_RATINGS_NH if _is_nh(race_type)
                else _HORSE_RATINGS_FLAT).get(name)

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
        # Partial credit (0.5) for runners missing only one source.
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
        # Runners where at least trainer/jockey is known AND form exists.
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
    # ODDS INTELLIGENCE LAYER
    # --------------------------------------------------------
    @staticmethod
    def _odds_multiplier(norm_name: str,
                         norm_probs: Dict[str, float],
                         n_with_odds: int,
                         coverage: float) -> float:
        """Compute a small score adjustment from field-relative implied probability.

        Uses the runner's normalized implied probability (raw implied prob divided
        by the field total, removing bookmaker overround) relative to the field
        average (1 / n_with_odds).

        ratio = norm_prob / avg_prob
          > 1  → shorter-priced than average → small positive
          = 1  → exactly average price       → neutral
          < 1  → longer-priced than average  → small negative

        A log curve is applied so the adjustment tapers smoothly:
          log(ratio) is positive for short-priced runners, negative for outsiders.

        Sensitivity (k) and cap scale with data coverage:
          Normal coverage (≥0.5): k=0.025, cap=±0.030 → multiplier [0.97, 1.03]
          Low coverage (0.0):     k=0.060, cap=±0.060 → multiplier [0.94, 1.06]

        Returns 1.0 if odds are unavailable or the field has fewer than 2 prices.
        """
        if not norm_probs or n_with_odds < 2:
            return 1.0
        prob = norm_probs.get(norm_name)
        if prob is None:
            return 1.0

        avg_prob = 1.0 / n_with_odds
        ratio    = prob / avg_prob          # 1.0 = market-average price

        # Scale sensitivity and cap from coverage
        if coverage < 0.5:
            strength = 1.0 - coverage / 0.5          # 0.0 at cov=0.5, 1.0 at cov=0
            k   = 0.025 + 0.035 * strength            # 0.025 → 0.060
            cap = 0.030 + 0.030 * strength            # 0.030 → 0.060
        else:
            k   = 0.025
            cap = 0.030

        delta = k * math.log(max(ratio, 0.01))        # log(0) guard
        delta = max(-cap, min(cap, delta))
        return round(1.0 + delta, 5)

    # --------------------------------------------------------
    # RACECARD INTELLIGENCE LAYER
    # --------------------------------------------------------
    def _racecard_intel_multiplier(self, runner: Runner,
                                   race: RaceInfo) -> float:
        """Derive a small score multiplier from racecard intelligence signals.

        Six signal families — each contributes a signed delta.
        Total clamped to [0.94, 1.06] so racecard data never dominates.

        A. Distance suitability (previous_runs)
        B. Going preference (previous_runs)
        C. Field-adjusted form (previous_runs)
        D. Discipline change penalty (hurdle→chase debut)
        E. Equipment signals (comment/equipment string)
        F. Comment keyword signals
        """
        delta = 0.0
        prev  = runner.previous_runs or []

        # ── A. Distance suitability ──────────────────────────────────────────
        if prev:
            dists = [p["distance_f"] for p in prev
                     if isinstance(p.get("distance_f"), (int, float))
                     and p["distance_f"] > 0]
            if dists:
                median_d = statistics.median(dists)
                gap = abs(float(race.distance_f) - median_d)
                if gap <= 1.0:
                    delta += 0.025   # ran at almost identical trip
                elif gap <= 3.0:
                    delta += 0.010   # within 3f — familiar territory
                elif gap > 5.0:
                    delta -= 0.015   # significant step up/down in trip

        # ── B. Going preference ──────────────────────────────────────────────
        # Skipped when going is blank ("not_specified") — no signal to use.
        if prev and race.going:
            curr_bucket = _going_bucket(race.going)
            same = [p for p in prev
                    if _going_bucket(p.get("going", "")) == curr_bucket
                    and isinstance(p.get("pos"), int)
                    and isinstance(p.get("field_size"), int)
                    and p["field_size"] > 1]
            if len(same) >= 2:
                # Relative finishing position on today's going type
                avg_rel = statistics.mean(
                    p["pos"] / p["field_size"] for p in same
                )
                if avg_rel <= 0.30:
                    delta += 0.020   # top 30% on this going — genuine preference
                elif avg_rel <= 0.50:
                    delta += 0.010   # above average on this going
            elif len(same) == 0 and len(prev) >= 3:
                delta -= 0.010       # never run on today's going — uncertainty

        # ── C. Field-adjusted form ───────────────────────────────────────────
        # Normalises finishing position by field size — catches big-field 5ths
        # that are better than a small-field 3rd.
        if prev and len(prev) >= 2:
            adj = []
            for p in prev:
                pos = p.get("pos")
                fs  = p.get("field_size")
                if isinstance(pos, int) and isinstance(fs, int) and fs > 1:
                    adj.append(1.0 - (pos - 1) / (fs - 1))
            if adj:
                avg_adj = statistics.mean(adj)
                if avg_adj >= 0.80:
                    delta += 0.020   # consistently in the top 20% of fields
                elif avg_adj >= 0.65:
                    delta += 0.010   # solidly above average
                elif avg_adj <= 0.25:
                    delta -= 0.015   # consistently at the back of fields

        # ── D. Discipline change penalty ─────────────────────────────────────
        if prev:
            rt = race.race_type.lower()
            if "chase" in rt:
                chase_runs  = [p for p in prev
                               if "chase" in p.get("discipline", "").lower()]
                hurdle_runs = [p for p in prev
                               if "hurdle" in p.get("discipline", "").lower()]
                if len(chase_runs) == 0 and len(hurdle_runs) > 0:
                    delta -= 0.025   # chase debut/very inexperienced over fences
                    # Partial offset if comment suggests shaped well at debut
                    cmt = (runner.comment or "").lower()
                    if any(kw in cmt for kw in
                           ("shaped", "promising", "jumped", "schooled")):
                        delta += 0.010

        # ── E. Equipment signals ──────────────────────────────────────────────
        equip = (runner.equipment or "").lower()
        if equip:
            if any(kw in equip for kw in
                   ("blinkers", "cheekpieces", "visor", "first time")):
                delta += 0.020       # focus aid added — often a positive change
            elif "hood removed" in equip or ("hood" in equip and "remov" in equip):
                delta += 0.015       # Racing Post often flags hood removal as positive
            elif any(kw in equip for kw in ("tongue strap", "tongue tie")):
                delta += 0.010       # routine breathing aid — mild positive signal

        # ── F. Comment keyword signals ───────────────────────────────────────
        cmt = (runner.comment or "").lower()
        if cmt:
            # Positive — take the first matching signal to avoid double-counting
            _pos = [
                ("keeps the faith",  0.025),  # jockey sticking with horse
                ("significant",      0.020),
                ("progressive",      0.020),
                ("improving",        0.020),
                ("eye-catching",     0.020),
                ("well treated",     0.020),
                ("well handicapped", 0.020),
                ("lightly raced",    0.015),
                ("promising",        0.015),
                ("bounce back",      0.015),
                ("needed run",       0.015),  # next run expected to be sharper
                ("step up",          0.010),
                ("returns to",       0.010),
            ]
            for kw, boost in _pos:
                if kw in cmt:
                    delta += boost
                    break

            # Negative — independent of the positive scan
            _neg = [
                ("heavily eased",  -0.030),
                ("distressed",     -0.025),
                ("amiss",          -0.020),
                ("pulled up",      -0.020),
                ("disappointed",   -0.020),
                ("failed off",     -0.020),
                ("fell",           -0.015),
                ("unseated",       -0.015),
            ]
            for kw, penalty in _neg:
                if kw in cmt:
                    delta += penalty
                    break

        return max(0.94, min(1.06, 1.0 + delta))

    # --------------------------------------------------------
    # MAIN ANALYSIS
    # --------------------------------------------------------
    def analyze(self, race: RaceInfo, runners: List[Runner],
                odds: Optional[Dict[str, str]] = None):

        scored = []

        # ── Pre-process odds ─────────────────────────────────────────────────
        # Parse once before the loop; derive field-relative normalized implied
        # probabilities so each runner's odds signal is independent of
        # bookmaker overround and field size.
        _odds_decimal: Dict[str, float] = {}   # norm_name → decimal odds
        _norm_prob:    Dict[str, float] = {}   # norm_name → normalized implied prob
        if odds:
            _raw_probs: Dict[str, float] = {}
            for _oname, _oraw in odds.items():
                _dec = _parse_odds(_oraw)
                if _dec is not None and _dec >= 1.01:
                    _key = _normalize_name(_oname)
                    _odds_decimal[_key] = _dec
                    _raw_probs[_key]    = 1.0 / _dec
            if len(_raw_probs) >= 2:
                _total     = sum(_raw_probs.values())
                _norm_prob = {k: v / _total for k, v in _raw_probs.items()}

        for r in runners:

            form    = self.form_score(r.form)
            weight  = self.weight_score(r)
            age     = self.age_score(r.age)

            trainer = self.trainer_style_boost(r.trainer, race.race_type,
                                                race.country)
            jockey  = self.jockey_boost(r.jockey, race.race_type,
                                        race.country)
            combo   = self.combo_boost(r.trainer, r.jockey)
            rating  = self.horse_rating_boost(r.name, race.race_type,
                                              race.country)
            perf    = self.horse_performance_boost(r.name, race.race_type,
                                                   race.country)

            # Data quality check done early so it drives both weighting and
            # the score penalty below.
            conf_deduction = self._confidence_deduction(
                r.trainer, r.jockey, r.name, race.race_type, race.country)

            # Option 3 — Form quality: how many numeric results are in the string.
            # A horse with no or single-run form gets reduced weight on that
            # factor; the surplus is redistributed to structural/fitness so a
            # blank form string can't pad the score for an unknown horse.
            _form_digits = [c for c in (r.form or "") if c.isdigit()]
            form_quality = min(1.0, len(_form_digits) / 2)  # 0=none 0.5=1-run 1=2+

            # Adaptive racecard weights: when historical data is sparse, shift
            # weight toward observable racecard factors (form, age, weight).
            # Full data → standard split.  Partial gap → moderate shift.
            # Severely limited → maximise racecard factor influence.
            if conf_deduction >= 5:
                w_base, w_form, w_age, w_wt = 0.05, 0.50, 0.23, 0.22
            elif conf_deduction >= 2:
                w_base, w_form, w_age, w_wt = 0.15, 0.42, 0.22, 0.21
            else:
                w_base, w_form, w_age, w_wt = 0.25, 0.35, 0.20, 0.20

            # Thin form: redistribute unused form weight to structural factors.
            if form_quality < 1.0:
                _surplus = w_form * (1.0 - form_quality)
                w_form -= _surplus
                w_wt   += _surplus * 0.55
                w_age  += _surplus * 0.45

            final_score = (
                1.0    * w_base +
                form   * w_form +
                age    * w_age +
                weight * w_wt
            )

            final_score *= trainer
            final_score *= jockey
            final_score *= combo
            final_score *= rating
            final_score *= perf

            # Score penalty for missing data: pushes unknown horses down the
            # ranking so well-documented runners are preferred for top picks.
            # 1.5% per deduction point, floor at 0.88 (~12% max reduction).
            if conf_deduction > 0:
                final_score *= max(0.88, 1.0 - conf_deduction * 0.015)

            # ── Smart fallback for low-data runners ──────────────────────────
            # Compute a data-coverage score (0.0 = nothing known, 1.0 = full).
            # We derive it from multipliers already calculated so there are no
            # extra lookups.  Signals and their weights:
            #   form digits (2+)   → 0.25
            #   official rating    → 0.35   (rating > 1.0 means it was found)
            #   win-rate stats     → 0.25   (perf   > 1.0 means it was found)
            #   trainer in data    → 0.075  (multiplier ≠ 1.0)
            #   jockey in data     → 0.075  (multiplier ≠ 1.0)
            _form_cov   = min(1.0, len(_form_digits) / 2) * 0.25
            _rating_cov = 0.35  if rating  > 1.005 else 0.0
            _perf_cov   = 0.25  if perf    > 1.005 else 0.0
            _train_cov  = 0.075 if abs(trainer - 1.0) > 0.005 else 0.0
            _jock_cov   = 0.075 if abs(jockey  - 1.0) > 0.005 else 0.0
            coverage    = (_form_cov + _rating_cov + _perf_cov
                           + _train_cov + _jock_cov)

            if coverage < 0.5:
                # How deep into the "unknown" zone (0.0 at cov=0.5, 1.0 at 0)
                fallback_strength = 1.0 - (coverage / 0.5)
                connections_mult  = trainer * jockey * combo
                # Apply the connections multiplier a second time (fractionally).
                # Strong connections (>1.0) get a bonus; weak ones (<1.0) get
                # a further penalty.  Neutral (=1.0) is unaffected.
                # Max additional effect ≈ ±8% for a 10% connection edge.
                extra = connections_mult ** (fallback_strength * 0.8)
                final_score *= extra

            # ── Racecard intelligence layer ──────────────────────────────────
            # Secondary signals from previous_runs, equipment, and comment text.
            # Applied at face value when data coverage is good; scaled up by
            # up to 1.5× when coverage is low (racecard data is then the best
            # available signal for the runner).
            rc_mult = self._racecard_intel_multiplier(r, race)
            if rc_mult != 1.0:
                if coverage < 0.5:
                    rc_edge = rc_mult - 1.0
                    # Amplify: more racecard influence at lower coverage
                    rc_mult = max(0.92, min(1.08,
                                           1.0 + rc_edge * (1.0 + (0.5 - coverage))))
                final_score *= rc_mult

            # ── Draw / Pace signals (Flat races; secondary contextual layer) ──
            draw_mult  = _draw_multiplier(r, race)
            pace_mult  = _pace_multiplier(r, runners, race)
            combo_mult = _draw_pace_combo_multiplier(r, runners, race)
            final_score *= draw_mult * pace_mult * combo_mult

            # ── Odds: confidence layer only — score is never touched ─────────
            # Odds are applied AFTER sorting as a confidence corroboration
            # signal only (see post-sort block below).  They do not affect
            # final_score or sort order.

            # ── Wet Jumps mode: apply contextual score adjustment ─────────────
            wet_jumps = _is_wet_jumps(race)
            if wet_jumps:
                final_score *= self._wet_jumps_adjustment(r, race)

            going_pen = self._going_penalty(r, race.going, race.race_type,
                                            race.country, wet_jumps=wet_jumps)
            # Score reduction for testing ground: 1% per penalty point,
            # floor at 0.95 (~5% max reduction on score).
            if going_pen > 0:
                final_score *= max(0.95, 1.0 - going_pen * 0.01)
            confidence = min(95, max(70, int(final_score * 80)
                                     - conf_deduction - going_pen))

            conn = round(trainer * jockey * combo, 3)
            raw_rating = self._get_horse_rating(r.name, race.race_type,
                                                race.country)
            scored.append({
                "name":        r.name,
                "score":       round(final_score, 3),
                "confidence":  confidence,
                "form":        round(form, 3),
                "connections": conn,
                "structural":  round(weight, 3),
                "fitness":     round(age, 3),
                # Temporary — used for writeups, stripped before return
                "_rating_b":   rating,
                "_perf_b":     perf,
                "_trainer_b":  trainer,
                "_jockey_b":   jockey,
                "_combo_b":    combo,
                "_conf_ded":   conf_deduction,
                "_going_pen":  going_pen,
                "_raw_rating": raw_rating,   # raw int or None
                "_coverage":   round(coverage, 3),
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # ── Odds corroboration (post-sort, display only) ─────────────────────
        # Odds NEVER touch model scores or sort order.  This block only
        # adjusts displayed confidence ±3 pts and attaches market_flag so
        # the UI can surface market agreement/disagreement as context.
        if _odds_decimal:
            _mkt_sorted = sorted(
                scored,
                key=lambda h: _odds_decimal.get(_normalize_name(h["name"]), 9999.0),
            )
            _mkt_rank = {h["name"]: i for i, h in enumerate(_mkt_sorted)}
            for _mrank, _horse in enumerate(scored):
                _dec = _odds_decimal.get(_normalize_name(_horse["name"]))
                if _dec is None:
                    continue
                _mpos = _mkt_rank.get(_horse["name"], len(scored))
                if _mrank == 0:
                    if _dec > 51.0:       # 50/1+ — market still strongly disagrees
                        _horse["confidence"] = max(70, _horse["confidence"] - 5)
                        _horse["market_flag"] = "model_vs_market"
                    elif _mpos == 0:      # market and model both favour same horse
                        _horse["confidence"] = min(95, _horse["confidence"] + 3)
                        _horse["market_flag"] = "market_confirms"
                    elif _mpos <= 2:
                        _horse["confidence"] = min(95, _horse["confidence"] + 1)
                        _horse["market_flag"] = "market_near_agreement"
                elif _mrank == 1 and _dec > 51.0:
                    _horse["confidence"] = max(70, _horse["confidence"] - 3)
                    _horse["market_flag"] = "model_vs_market"

        # Field-strength context — confidence ±1 when a horse is clearly
        # above or below the field average on official ratings.
        # Score and sort order are never touched.
        raw_ratings = [e["_raw_rating"] for e in scored
                       if e["_raw_rating"] is not None]
        field_avg = (sum(raw_ratings) / len(raw_ratings)
                     if raw_ratings else None)
        for entry in scored:
            raw_r = entry["_raw_rating"]
            if field_avg is not None and raw_r is not None:
                edge = raw_r - field_avg
                if edge >= 5:
                    entry["confidence"] = min(95, entry["confidence"] + 1)
                elif edge <= -5:
                    entry["confidence"] = max(70, entry["confidence"] - 1)
                entry["_rating_edge"] = round(edge, 1)
            else:
                entry["_rating_edge"] = 0.0

        # Helper to build a writeup from a scored entry
        def _wp(entry):
            return self._build_writeup(
                entry["form"],
                entry["_trainer_b"], entry["_jockey_b"], entry["_combo_b"],
                entry["structural"], entry["fitness"],
                entry["_rating_b"], entry["_perf_b"],
                entry["_conf_ded"], entry["_going_pen"],
                entry["_rating_edge"],
            )

        # ── Three-problem pick selection (tipster_v3) ─────────────────────────
        #
        # Gold, Silver, and Dark Horse are THREE SEPARATE SELECTION PROBLEMS.
        # Each has its own scoring model using different signals and weights.
        # Odds are NEVER used here — they only touch confidence display above.
        #
        # ── GOLD: Best win bet ────────────────────────────────────────────────
        #   Problem: which horse is most likely to WIN?
        #   Signals: class (rating × perf) + form + connections + going fit + data
        #   Race-shape: longer/softer → class weighted higher; shorter/firmer → form.
        #   Plausibility gate: minimum data coverage 0.20.
        #
        # ── SILVER: Pairwise threat to Gold ──────────────────────────────────
        #   Problem: which horse is most likely to BEAT GOLD SPECIFICALLY?
        #   Not rank-2 by score. Uses pairwise threat logic:
        #   (1) Contention: score ≥ 75% of Gold (genuine challenger).
        #   (2) Profile contrast: dominant strength DIFFERENT from Gold's.
        #       Gold is form-driven vs Silver is class-driven → genuine different
        #       danger; same profile = Gold clone, less new information.
        #   (3) Going suitability + data reliability.
        #   Field averages computed per-race so contrast is truly relative.
        #
        # ── DARK HORSE: Hidden upside ─────────────────────────────────────────
        #   Problem: which horse does the model UNDERESTIMATE?
        #   NOT odds-based. Upside signals (all intrinsic):
        #   • rating_edge > 0: rated above field average but ranked lower by model
        #   • perf_b > 1.0: win-rate data shows ability not reflected in score
        #   • form > field average: in-form horse ranked outside top 2
        #   • connections > field average: quality trainer/jockey underexposed
        #   • going suitability: conditions favour this horse specifically
        #   Plausibility: score ≥ 60% of Gold, rank ≥ 3, some data coverage.
        #   Overlap prevention: never Gold or Silver.
        # ─────────────────────────────────────────────────────────────────────

        # Exclude from quality pool only when BOTH trainer AND jockey are
        # unknown (deduction ≥ 6). A single known entity (famous trainer or
        # jockey) still provides meaningful signal so a deduction of 5 is
        # not sufficient reason to bar a horse from Gold/Silver consideration.
        _PICK_DED_LIMIT = 6

        def _qpool(ranked, exclude_names):
            pool = [h for h in ranked if h["name"] not in exclude_names]
            q    = [h for h in pool if h["_conf_ded"] < _PICK_DED_LIMIT]
            return q if q else pool

        # ── Field averages (used by Silver profile-contrast and Dark upside) ──
        _n         = len(scored)
        _avg_form  = sum(h["form"]                       for h in scored) / _n if _n else 1.0
        _avg_class = sum(h["_rating_b"] * h["_perf_b"]  for h in scored) / _n if _n else 1.0
        _avg_conn  = sum(h["connections"]                for h in scored) / _n if _n else 1.0

        # ── Race-shape weights for Gold ───────────────────────────────────────
        # Longer distances and wet/soft ground reward class and stamina.
        # Shorter distances and good/firm ground reward recent form and speed.
        # Wet jumps races get the strongest shift toward class because attritional
        # conditions favour proven ability and stamina over raw recent form.
        _is_long     = race.distance_f >= 12.0
        _is_soft     = race.ground_bucket == "Wet"   # uses the Wet/Dry system
        _is_wet_nh   = _is_wet_jumps(race)
        if _is_wet_nh:
            # Wet National Hunt: class and proven stamina dominate
            _class_wt = 0.35
            _form_wt  = 0.18
        elif _is_long or _is_soft:
            # Long flat or soft-ground race: class/stamina more important
            _class_wt = 0.30
            _form_wt  = 0.22
        else:
            # Normal flat or good-ground race: recent form drives the pick
            _class_wt = 0.22
            _form_wt  = 0.30
        _conn_wt  = 0.20
        _suit_wt  = 0.18
        _qual_wt  = max(0.0, 1.0 - _class_wt - _form_wt - _conn_wt - _suit_wt)

        # ── GOLD ──────────────────────────────────────────────────────────────
        def _gold_win_score(h):
            class_sig = h["_rating_b"] * h["_perf_b"]
            form_sig  = h["form"]
            conn_sig  = h["connections"]
            suit_sig  = max(0.0, 1.0 - h["_going_pen"] * 0.08)   # 0 at pen ≥ 12.5
            qual_sig  = min(1.0, h["_coverage"] / 0.5)
            return (class_sig * _class_wt + form_sig * _form_wt
                    + conn_sig * _conn_wt  + suit_sig * _suit_wt
                    + qual_sig * _qual_wt)

        def _select_gold(ranked):
            pool = _qpool(ranked, set())
            if not pool:
                return None
            plausible = [h for h in pool if h["_coverage"] >= 0.20]
            return max(plausible or pool, key=_gold_win_score)

        # ── SILVER ────────────────────────────────────────────────────────────
        def _select_silver(ranked, gold_entry):
            if gold_entry is None:
                return None
            gname   = gold_entry["name"]
            gold_sc = gold_entry["score"]
            pool    = _qpool(ranked, {gname})
            if not pool:
                return None

            # Plausibility gate: score ≥ 75% of Gold.
            contenders = [
                h for h in pool
                if gold_sc == 0.0 or h["score"] / gold_sc >= 0.75
            ]
            if not contenders:
                contenders = pool[:3]

            # Gold's dominant strength dimension (form / class / connections).
            g_form_rel  = gold_entry["form"]                          / _avg_form  if _avg_form  > 0 else 1.0
            g_class_rel = (gold_entry["_rating_b"] * gold_entry["_perf_b"]) / _avg_class if _avg_class > 0 else 1.0
            g_conn_rel  = gold_entry["connections"]                   / _avg_conn  if _avg_conn  > 0 else 1.0
            gold_dominant = max(
                {"form": g_form_rel, "class": g_class_rel, "conn": g_conn_rel},
                key=lambda k: {"form": g_form_rel, "class": g_class_rel, "conn": g_conn_rel}[k],
            )

            # Build runner map for trainer-diversity check.
            _rmap_silver = {r.name: r for r in runners}
            gold_runner  = _rmap_silver.get(gold_entry["name"])
            gold_trainer = gold_runner.trainer.strip().lower() if gold_runner else ""

            # Hard-reject same trainer as Gold when alternatives exist.
            # A horse from the same stable brings the same information as Gold;
            # Silver should represent a genuinely independent danger.
            if gold_trainer:
                non_clone = [
                    h for h in contenders
                    if not (gold_trainer and
                            (_rmap_silver.get(h["name"]) and
                             _rmap_silver[h["name"]].trainer.strip().lower() == gold_trainer))
                ]
                if non_clone:
                    contenders = non_clone

            # Gold's decimal odds — used for Silver's market plausibility gate.
            gold_dec_v = (_odds_decimal.get(_normalize_name(gname), 0.0)
                          if gname else 0.0)

            def _silver_threat(h):
                # (1) Contention²: score proximity to Gold is the dominant signal.
                #     Squaring amplifies the gap so a horse at 79% of Gold can't
                #     beat one at 95% just by having a different strength profile.
                ratio      = h["score"] / gold_sc if gold_sc > 0 else 1.0
                contention = 0.88 + min(0.20, max(0.0, (ratio - 0.75) / 0.25) * 0.20)
                cont_sq    = contention ** 2   # amplify proximity advantage

                # (2) Profile distance: secondary tiebreaker for close scores.
                #     Normalised vectors; distance 0.0 = identical, 2.0 = opposite.
                h_form_rel  = h["form"]                       / _avg_form  if _avg_form  > 0 else 1.0
                h_class_rel = (h["_rating_b"] * h["_perf_b"]) / _avg_class if _avg_class > 0 else 1.0
                h_conn_rel  = h["connections"]                / _avg_conn  if _avg_conn  > 0 else 1.0
                g_tot = g_form_rel + g_class_rel + g_conn_rel
                h_tot = h_form_rel + h_class_rel + h_conn_rel
                if g_tot > 0 and h_tot > 0:
                    gv   = (g_form_rel/g_tot, g_class_rel/g_tot, g_conn_rel/g_tot)
                    hv   = (h_form_rel/h_tot, h_class_rel/h_tot, h_conn_rel/h_tot)
                    dist = sum(abs(gv[i] - hv[i]) for i in range(3))
                else:
                    dist = 0.0
                contrast = 1.0 + dist * 0.06   # max +12% — secondary, not dominant

                # (3) Market plausibility: Silver must be a realistic challenger.
                #     In wet jumps the market is less reliable — conditions can
                #     flip form, so the price penalty starts later and is gentler.
                if gold_dec_v > 0 and _odds_decimal:
                    h_dec       = _odds_decimal.get(_normalize_name(h["name"]), gold_dec_v)
                    price_ratio = h_dec / gold_dec_v
                    if _is_wet_jumps(race):
                        # Wet NH: allow credible rivals up to 3× Gold price,
                        # soft penalty only beyond 6×
                        if price_ratio <= 3.0:
                            mkt_plaus = 1.06
                        elif price_ratio <= 6.0:
                            mkt_plaus = 1.02
                        else:
                            mkt_plaus = max(0.90, 1.0 - (price_ratio - 6.0) * 0.02)
                    else:
                        # Normal flat / dry NH: standard plausibility
                        if price_ratio <= 2.0:
                            mkt_plaus = 1.06
                        elif price_ratio <= 4.0:
                            mkt_plaus = 1.02
                        else:
                            mkt_plaus = max(0.85, 1.0 - (price_ratio - 4.0) * 0.04)
                else:
                    mkt_plaus = 1.0

                # (4) Going suitability and data reliability.
                suitability = max(0.85, 1.0 - h["_going_pen"] * 0.06)
                reliability = min(1.0, 0.82 + h["_coverage"] * 0.36)

                return cont_sq * contrast * mkt_plaus * suitability * reliability

            contenders.sort(key=_silver_threat, reverse=True)
            return contenders[0]

        # ── DARK HORSE ────────────────────────────────────────────────────────
        def _select_dark(ranked, gold_entry, silver_entry):
            if not self.dark_horse_enabled:
                return None
            gname   = gold_entry["name"]  if gold_entry  else None
            sname   = silver_entry["name"] if silver_entry else None
            excl    = {gname, sname}
            gold_sc = gold_entry["score"] if gold_entry else 0.0
            pool    = [h for h in ranked if h["name"] not in excl]
            if not pool:
                return None

            # Plausibility: score ≥ 60% of Gold, some data known.
            plausible = [
                h for h in pool
                if h["score"] >= 0.60 * gold_sc and h["_coverage"] >= 0.15
            ]
            if not plausible:
                plausible = pool

            # ── Price gate (when odds are available) ─────────────────────────
            # A dark horse must be longer-priced than Gold.  A 2/1 shot with
            # great connections is not a dark horse — it is simply a well-fancied
            # contender.  The gate is applied in three tiers, relaxing each time
            # no qualifying horses are found:
            #
            #   Tier 1: > Gold odds AND ≥ 5/1 (strict — genuine dark horse price)
            #   Tier 2: ≥ 5/1 absolute minimum (same stable as Gold may appear)
            #   Tier 3: no price constraint (e.g. race has only short-priced horses)
            if _odds_decimal:
                gold_dec_v  = (_odds_decimal.get(_normalize_name(gname), 0.0)
                               if gname else 0.0)
                _DH_ABS_MIN = 6.0   # 5/1 in decimal — hard minimum for tier 1 & 2

                # Tier 1: must be strictly longer than Gold AND ≥ 5/1
                tier1 = [
                    h for h in plausible
                    if (_odds_decimal.get(_normalize_name(h["name"]), 0.0) > gold_dec_v
                        and _odds_decimal.get(_normalize_name(h["name"]), 0.0) >= _DH_ABS_MIN)
                ]
                # Tier 2: just ≥ 5/1 absolute minimum
                tier2 = [
                    h for h in plausible
                    if _odds_decimal.get(_normalize_name(h["name"]), 0.0) >= _DH_ABS_MIN
                ]
                if tier1:
                    plausible = tier1
                elif tier2:
                    plausible = tier2
                # else tier 3: keep full plausible pool (very short-priced fields)

                # Hard cap: if every remaining candidate is > 33/1 (dec > 34),
                # there is no credible dark horse in this field — return None
                # rather than recommending a near-hopeless punt.
                _DH_HARD_MAX = 34.0  # 33/1 in decimal
                non_extreme = [
                    h for h in plausible
                    if _odds_decimal.get(_normalize_name(h["name"]), 0.0) <= _DH_HARD_MAX
                ]
                if non_extreme:
                    plausible = non_extreme
                else:
                    return None

            def _upside_score(h):
                # (a) Rating above field average but ranked lower by model.
                #     This is the clearest sign of a model underestimate.
                rating_bonus = min(0.15, max(0.0, h.get("_rating_edge", 0.0) * 0.025))

                # (b) Win-rate stats show ability the raw score undersells.
                perf_bonus = max(0.0, (h["_perf_b"] - 1.0) * 0.50)

                # (c) Form above field average for a horse ranked outside top 2.
                form_rel   = h["form"] / _avg_form if _avg_form > 0 else 1.0
                form_bonus = max(0.0, (form_rel - 1.0) * 0.12)

                # (d) Trainer/jockey/combo strength above field average.
                conn_rel   = h["connections"] / _avg_conn if _avg_conn > 0 else 1.0
                conn_bonus = max(0.0, (conn_rel - 1.0) * 0.10)

                # (e) Going suitability: conditions favour this specific horse.
                suit_bonus = max(0.0, 0.05 - h["_going_pen"] * 0.015)

                total_upside = (1.0 + rating_bonus + perf_bonus
                                + form_bonus + conn_bonus + suit_bonus)

                # Data quality weight: need some basis to trust the upside signal.
                cov_factor = min(1.0, 0.78 + h["_coverage"] * 0.44)

                return h["score"] * total_upside * cov_factor

            plausible.sort(key=_upside_score, reverse=True)
            best = plausible[0]
            return {**best, "label": "Value Play", "writeup": _wp(best)}

        gold_entry   = _select_gold(scored)
        gold_name    = gold_entry["name"] if gold_entry else None
        silver_entry = _select_silver(scored, gold_entry) if gold_entry else None
        silver_name  = silver_entry["name"] if silver_entry else None
        dark         = _select_dark(scored, gold_entry, silver_entry)

        gold   = ({**gold_entry,   "label": "Good E/W Bet",
                   "writeup": _wp(gold_entry)}   if gold_entry   else None)
        silver = ({**silver_entry, "label": "Good Place Bet",
                   "writeup": _wp(silver_entry)} if silver_entry else None)

        # ── New race confidence + per-pick confidences ────────────────────────
        # race_confidence: replaces the old spread-only inline block.
        # Pick confidences: override the generic per-horse value with a
        # pick-specific score.  Temp fields are still present at this point.
        race_confidence = _race_confidence_label(
            scored, race, runners, gold_entry, _norm_prob, _odds_decimal)
        if gold and gold_entry:
            gold["confidence"] = _gold_pick_confidence(
                gold, scored, race, race_confidence, _norm_prob, _odds_decimal)
        if silver and silver_entry:
            silver["confidence"] = _silver_pick_confidence(
                silver, gold, scored, race, race_confidence, _norm_prob, _odds_decimal)
        if dark:
            dark["confidence"] = _dark_horse_confidence(
                dark, gold, scored, race, race_confidence, _norm_prob, _odds_decimal)

        dark_name = dark["name"] if dark else None

        # Embed position-based labels into full_rankings so the UI
        # can read them directly without any score-threshold logic.
        # Strip all temporary writeup-helper fields from every entry.
        _temp = ("_rating_b", "_perf_b", "_trainer_b", "_jockey_b",
                 "_combo_b", "_conf_ded", "_going_pen",
                 "_raw_rating", "_rating_edge", "_coverage")
        for i, entry in enumerate(scored):
            for f in _temp:
                entry.pop(f, None)
            if i == 0:
                entry["label"] = "Good E/W Bet"
            elif i == 1:
                entry["label"] = "Good Place Bet"
            elif entry["name"] == dark_name:
                entry["label"] = "Value Play"
            else:
                entry["label"] = ""

        # Strip temp fields from picks too (they were spread-copied)
        for pick in (gold, silver, dark):
            if pick:
                for f in _temp:
                    pick.pop(f, None)

        return {
            "gold_pick":       gold,
            "silver_pick":     silver,
            "dark_horse":      dark,
            "race_confidence": race_confidence,
            "full_rankings":   scored,
            "wet_jumps_mode":  _is_wet_jumps(race),
        }
