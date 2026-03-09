"""
sim_wet_dry_jumps_comparison.py
================================
Targeted 100-vs-100 comparison simulation:
  SET A  — 100 Jumps races on Wet / bad ground
  SET B  — 100 Jumps races on Dry / good ground

Goals
-----
  • Verify Wet Jumps improvements are working as intended.
  • Confirm Dry Jumps behaviour is stable (no leakage from wet-jumps logic).
  • Compare confidence distributions, selection patterns, comment-signal
    influence, and outsider suppression between the two sets.

Run as: python sim_wet_dry_jumps_comparison.py
"""

import sys
import math
import re
import os
import random
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

sys.path.insert(0, "/home/user/peakpace-ai-clean")

from main import (
    parse_racecard_text,
    parse_weight_to_lbs,
    parse_distance_to_furlongs,
    normalize_going,
    detect_race_type,
    detect_country,
    detect_going,
)
from racing_ai_core import (
    RacingAICore, RaceInfo, Runner,
    _normalize_name, _parse_odds, _is_wet_jumps,
    classify_wet_dry,
    _TRAINER_DATA_NH, _UK_TRAINER_DATA_NH,
    _JOCKEY_DATA_NH,  _UK_JOCKEY_DATA_NH,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
RACES_PER_SET = 100
RNG = random.Random(20260309)   # fixed seed for reproducibility

# ─────────────────────────────────────────────────────────────────────────────
# LOAD REAL NAMES FROM HISTORICAL DATASETS
# ─────────────────────────────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _extract_names(filename: str, pattern: str) -> list:
    names = []
    path = os.path.join(_DATA_DIR, filename)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(pattern, line.strip())
                if m:
                    names.append(m.group(1).strip())
    except OSError:
        pass
    return names


_runs_pat   = r'^([A-Za-z].+?) \(Runs:'
_season_pat = r'^([A-Za-z].+?) \(Season:'

_REAL_TRAINERS_JUMP = list(dict.fromkeys(
    _extract_names("Irish Trainers Stats National Hunt (Jumps) 2024 and 2025 and 2026.txt", _runs_pat) +
    _extract_names("UK_Trainers_Jumps_clean.txt", _season_pat)
))

_REAL_JOCKEYS_JUMP = list(dict.fromkeys(
    _extract_names("Irish Jockeys Stats National Hunt 2024 and 2025 and 2026.txt", _runs_pat) +
    _extract_names("UK_Jockeys_Jumps_clean.txt", _season_pat)
))

_REAL_HORSES_JUMP = list(dict.fromkeys(
    _extract_names("Irish Horses National Hunt (Jumps) 2024 and 2025 and 2026 - Engine Format.txt", _runs_pat) +
    _extract_names("UK_Horses_Jumps_2024_2025_2026_clean.txt", _season_pat)
))

# Strip parenthetical country tags from horse names  e.g. "Bowensonfire (FR)"
_REAL_HORSES_JUMP = [re.sub(r'\s*\([A-Z]{2,3}\)\s*$', '', h).strip()
                     for h in _REAL_HORSES_JUMP if h]

# Fallback in case files are missing / empty
_FALLBACK_TRAINERS = [
    "Willie Mullins", "Gordon Elliott", "Henry de Bromhead", "Nicky Henderson",
    "Paul Nicholls", "Dan Skelton", "Gavin Cromwell", "Joseph O'Brien",
    "Olly Murphy", "Ben Pauling", "Philip Hobbs", "Harry Fry", "Alan King",
]
_FALLBACK_JOCKEYS = [
    "Paul Townend", "Rachael Blackmore", "Danny Mullins", "Mark Walsh",
    "Harry Cobden", "Nico de Boinville", "Aidan Coleman", "Sean Bowen",
    "Harry Skelton", "Brian Hughes", "Sam Twiston-Davies", "Tom Cannon",
]
_FALLBACK_HORSES = [
    "Constitution Hill", "Jonbon", "Galopin Des Champs", "State Man",
    "Energumene", "I Am Maximus", "Corbetts Cross", "El Fabiolo",
    "Ballyburn", "Fact To File", "Quilixios", "Ferny Hollow",
]

TRAINERS_JUMP = _REAL_TRAINERS_JUMP or _FALLBACK_TRAINERS
JOCKEYS_JUMP  = _REAL_JOCKEYS_JUMP  or _FALLBACK_JOCKEYS
HORSES_JUMP   = _REAL_HORSES_JUMP   or _FALLBACK_HORSES

UK_JUMP_COURSES = [
    "Cheltenham", "Sandown", "Kempton", "Ascot", "Aintree",
    "Wetherby", "Uttoxeter", "Market Rasen", "Exeter", "Hereford",
    "Huntingdon", "Ludlow", "Worcester", "Taunton", "Musselburgh",
    "Ayr", "Perth", "Cartmel", "Newton Abbot", "Newbury",
]
IRE_JUMP_COURSES = [
    "Leopardstown", "Fairyhouse", "Punchestown", "Naas",
    "Navan", "Thurles", "Clonmel", "Kilbeggan",
]
ALL_JUMP_COURSES = UK_JUMP_COURSES + IRE_JUMP_COURSES

# Trainer/jockey/horse pools are now loaded from the historical datasets above.
# The TRAINERS_JUMP, JOCKEYS_JUMP, HORSES_JUMP names are all real names that
# exist in the engine's lookup tables, so ratings/stats lookups will fire.

FORM_CHARS = "123456780PFU"
JUMP_DISTANCES = ["2m", "2m1f", "2m4f", "2m5f", "3m", "3m1f", "3m2f"]

# Going pools — clearly separated
WET_GOINGS = ["soft", "heavy", "soft to heavy", "yielding", "yielding to soft", "very soft"]
DRY_GOINGS = ["good", "good to soft", "good to yielding", "good to firm"]

# Comment pools — realistic analyst notes
COMMENTS_NEUTRAL = [
    "Consistent performer over this sort of trip.",
    "Course winner last season, connections hopeful.",
    "Ran well fresh last time, expected to build on that.",
    "Solid jumper who travels well in his races.",
    "Trainer in good form, interesting contender.",
    "Lightly raced and still with scope for improvement.",
    "Has the best official rating in the field.",
    "Big dropper in class after a troubled campaign.",
    "Won twice at this course; excellent record here.",
    "Improved since wind surgery, expected to go close.",
    "Usually runs well fresh; bold-jumping type.",
    "Consistent jumper, rarely out of the first four.",
    "Likely to take a keen hold early.",
    "Course and distance winner in similar conditions.",
]
COMMENTS_JUMP_NEG = [
    "Made mistakes at crucial fences last time.",
    "Not fluent at obstacles, needs to improve jumping.",
    "Clumsy at the last two fences when tired.",
    "Jumped left repeatedly, cost him ground.",
    "Bad mistake three out effectively ended his chance.",
    "Error-prone jumper, hard to trust in testing ground.",
    "Sloppy early in the race, lacked fluency.",
    "Sketchy jumping proved costly, ran out of race.",
    "Jumped right consistently, hampered rivals.",
]
COMMENTS_JUMP_POS = [
    "Jumped well throughout, gained ground at every fence.",
    "Sound jumper who rarely makes mistakes.",
    "Accurate at obstacles, handles wet ground well.",
    "Fluent jumping is his biggest asset.",
    "Jumped well and travelled strongly throughout.",
]
COMMENTS_STAMINA_POS = [
    "Stayed on strongly up the hill to win decisively.",
    "Kept on dourly in the testing conditions.",
    "Found plenty when asked, genuine stayer.",
    "Stayed well over three miles last time out.",
    "Plugged on gamely after the last to hold on.",
    "Finished strongly in the closing stages.",
    "Kept on under pressure, couldn't be pegged back.",
]
COMMENTS_STAMINA_NEG = [
    "Weakened approaching the final fence when pressure applied.",
    "Faded badly on the run-in despite travelling well.",
    "Tired after jumping the last and was readily passed.",
    "Emptied quickly once headed, nothing left.",
    "Folded quickly when the race began in earnest.",
    "No extra over this trip, may need shorter.",
    "Weakened in the straight, looked one-paced.",
]

FAVOURITE_ODDS  = ["2/1", "5/2", "3/1", "7/2", "4/1", "9/2", "5/1"]
MID_FIELD_ODDS  = ["6/1", "7/1", "8/1", "10/1", "12/1"]
OUTSIDER_ODDS   = ["14/1", "16/1", "20/1", "25/1", "33/1"]
TAIL_ENDER_ODDS = ["20/1", "25/1", "33/1", "40/1", "50/1"]

EQUIPMENT_OPTIONS = [
    "", "", "", "",
    "tongue strap", "cheekpieces", "hood", "blinkers",
    "cheekpieces, tongue strap", "visor",
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _horse_name(used: set) -> str:
    """Pick a real horse name from the dataset pool, falling back to synthetic."""
    pool = HORSES_JUMP
    # Try real names first (shuffled for variety)
    candidates = list(pool)
    RNG.shuffle(candidates)
    for n in candidates:
        if n and n not in used:
            used.add(n)
            return n
    # Fallback: synthetic name if all real names exhausted
    for _ in range(300):
        n = f"Horse {RNG.randint(1000, 9999)}"
        if n not in used:
            used.add(n)
            return n
    return f"Runner {RNG.randint(10000, 99999)}"


def _form_string() -> str:
    length = RNG.randint(3, 8)
    return "".join(RNG.choice(FORM_CHARS) for _ in range(length))


def _weight_str() -> str:
    stone = RNG.randint(10, 12)
    lbs   = RNG.randint(0, 13)
    return f"{stone}-{lbs}"


def _prev_runs_text(going_pool: list, n: int = 3) -> str:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dists  = ["2m", "2m4f", "2m5f", "3m", "3m1f"]
    discs  = ["Hurdle", "Chase"]
    lines  = []
    month_idx = RNG.randint(0, 11)
    for _ in range(n):
        month_idx = (month_idx - RNG.randint(1, 2)) % 12
        day   = RNG.randint(1, 28)
        going = RNG.choice(going_pool)
        dist  = RNG.choice(dists)
        pos   = RNG.randint(1, 10)
        fsize = RNG.randint(pos, min(pos + 12, 18))
        disc  = RNG.choice(discs)
        lines.append(
            f"{months[month_idx]} {day} 2025 | Racecourse | {dist} | {going} | {pos}/{fsize} | {disc}"
        )
    return "\n".join(lines)


def _pick_comment() -> Tuple[str, str]:
    """Return (comment_text, comment_category)."""
    weights = [35, 15, 12, 18, 20]   # neutral, jump_neg, jump_pos, stamina_neg, stamina_pos
    cat = RNG.choices(
        ["neutral", "jump_neg", "jump_pos", "stamina_neg", "stamina_pos"],
        weights=weights,
    )[0]
    pool = {
        "neutral":     COMMENTS_NEUTRAL,
        "jump_neg":    COMMENTS_JUMP_NEG,
        "jump_pos":    COMMENTS_JUMP_POS,
        "stamina_neg": COMMENTS_STAMINA_NEG,
        "stamina_pos": COMMENTS_STAMINA_POS,
    }[cat]
    return RNG.choice(pool), cat


def _odds_for_field(size: int) -> list:
    pool = []
    for _ in range(RNG.randint(1, 2)):
        pool.append(RNG.choice(FAVOURITE_ODDS))
    for _ in range(min(RNG.randint(2, 3), size - len(pool))):
        pool.append(RNG.choice(MID_FIELD_ODDS))
    while len(pool) < size:
        pool.append(RNG.choice(OUTSIDER_ODDS if RNG.random() > 0.3 else TAIL_ENDER_ODDS))
    RNG.shuffle(pool)
    return pool[:size]


# ─────────────────────────────────────────────────────────────────────────────
# RACE DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SimRace:
    race_id:    int
    condition:  str    # "Wet" or "Dry"
    course:     str
    country:    str
    going:      str
    distance:   str
    distance_f: float
    field_size: int
    paste_text: str
    runner_cats: list  # per-runner comment category


# ─────────────────────────────────────────────────────────────────────────────
# RACE GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_race(race_id: int, condition: str) -> SimRace:
    going_pool = WET_GOINGS if condition == "Wet" else DRY_GOINGS
    going      = RNG.choice(going_pool)
    distance   = RNG.choice(JUMP_DISTANCES)
    distance_f = parse_distance_to_furlongs(distance)
    course     = RNG.choice(ALL_JUMP_COURSES)
    country    = "ireland" if course in IRE_JUMP_COURSES else "uk"
    field_size = RNG.randint(5, 14)
    odds_list  = _odds_for_field(field_size)
    nh_disc    = RNG.choice(["Hurdle", "Chase"])

    # Prev runs use realistic going matching the condition
    prev_going_pool = (
        ["Soft", "Heavy", "Yielding"] if condition == "Wet"
        else ["Good", "Good to Soft", "Good to Firm"]
    )

    used_names:  set  = set()
    runner_cats: list = []
    lines:       list = []

    # Header block
    lines += [
        f"COURSE: {course}",
        f"DISTANCE: {distance}",
        f"GOING: {going}",
        f"TYPE: {nh_disc}",
        "",
    ]

    for i in range(field_size):
        name      = _horse_name(used_names)
        age       = RNG.randint(4, 11)
        weight    = _weight_str()
        form      = _form_string()
        jockey    = RNG.choice(JOCKEYS_JUMP)
        trainer   = RNG.choice(TRAINERS_JUMP)
        odds      = odds_list[i]
        equipment = RNG.choice(EQUIPMENT_OPTIONS)
        comment, cat = _pick_comment()
        n_prev    = RNG.randint(0, 4)
        prev_text = _prev_runs_text(prev_going_pool, n=n_prev) if n_prev > 0 else ""

        runner_cats.append(cat)

        lines.append(f"HORSE: {name}")
        lines.append(f"JOCKEY: {jockey}")
        lines.append(f"TRAINER: {trainer}")
        lines.append(f"FORM: {form}")
        lines.append(f"AGE: {age}")
        lines.append(f"WEIGHT: {weight}")
        lines.append(f"ODDS: {odds}")
        if equipment:
            lines.append(f"EQUIPMENT: {equipment}")
        lines.append("COMMENT:")
        lines.append(comment)
        if prev_text:
            lines.append("RECENT RUNS:")
            for run_line in prev_text.split("\n"):
                if run_line.strip():
                    lines.append(run_line)
        lines.append("")

    return SimRace(
        race_id=race_id,
        condition=condition,
        course=course,
        country=country,
        going=going,
        distance=distance,
        distance_f=distance_f,
        field_size=field_size,
        paste_text="\n".join(lines),
        runner_cats=runner_cats,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_race(sim: SimRace, engine: RacingAICore) -> Optional[dict]:
    """Parse paste text and run analysis. Returns result dict or None on error."""
    detected_type    = detect_race_type(sim.paste_text)
    detected_country = detect_country(sim.paste_text)
    detected_going   = detect_going(sim.paste_text)

    runners_raw = parse_racecard_text(sim.paste_text)
    if not runners_raw:
        raise ValueError("parse returned 0 runners")

    ri_going = detected_going if detected_going else sim.going
    ri_going = normalize_going(ri_going)

    # Resolve ground_bucket: infer from going
    from racing_ai_core import classify_wet_dry
    inferred_bucket = classify_wet_dry(ri_going)

    race_info = RaceInfo(
        course=sim.course,
        country=detected_country,
        race_type=detected_type,
        surface="Turf",
        distance_f=int(sim.distance_f),
        going=ri_going,
        runners=len(runners_raw),
        ground_bucket=inferred_bucket,
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
        for r in runners_raw
    ]

    inline_odds = {r["name"]: r["odds"] for r in runners_raw if r.get("odds")}
    engine.dark_horse_enabled = True
    result = engine.analyze(race_info, runner_objects, odds=inline_odds or None)
    result["_race_info"]   = race_info
    result["_runners_raw"] = runners_raw
    result["_runner_objs"] = runner_objects
    return result


# ─────────────────────────────────────────────────────────────────────────────
# METRICS COLLECTOR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SetMetrics:
    condition:         str
    parse_errors:      int = 0
    engine_errors:     int = 0
    anomalies:         list = field(default_factory=list)
    conf_counter:      Counter = field(default_factory=Counter)
    top1_fav:          int = 0   # gold == shortest-odds runner
    top3_fav:          int = 0   # gold in top-3 shortest-odds runners
    valid_races:       int = 0
    dark_horse_count:  int = 0
    outsider_top1:     int = 0   # gold pick is an outsider (14/1+)
    total_runners:     int = 0
    # comment-signal tracking (Wet only meaningful but collected for both)
    cat_score_sums:    dict = field(default_factory=lambda: defaultdict(list))
    # wet-jumps activation verification
    wet_jumps_active:  int = 0   # races where _is_wet_jumps returned True
    wet_jumps_inactive:int = 0
    # per-race multiplier gap (max - min within a race, from wet_jumps_adjustment)
    mult_gaps:         list = field(default_factory=list)
    scores_by_cat:     dict = field(default_factory=lambda: defaultdict(list))
    # outsider analysis
    outsider_threshold: float = 14.0   # decimal odds ≥14 = outsider


def _check_anomalies(result: dict) -> list:
    issues = []
    rankings = result.get("full_rankings", [])
    if not rankings:
        return ["empty full_rankings"]
    scores = [r.get("score") for r in rankings]
    if any(s is None for s in scores):
        issues.append("None score in rankings")
    if any(isinstance(s, float) and math.isnan(s) for s in scores if s is not None):
        issues.append("NaN score in rankings")
    if len(scores) >= 2 and scores[0] == scores[1]:
        issues.append(f"tie at top ({scores[0]:.3f})")
    gold = result.get("gold_pick", {}).get("name")
    if gold and not any(r["name"] == gold for r in rankings):
        issues.append(f"gold '{gold}' missing from full_rankings")
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION LOOP
# ─────────────────────────────────────────────────────────────────────────────

def simulate_set(condition: str, engine: RacingAICore) -> Tuple[SetMetrics, list]:
    metrics   = SetMetrics(condition=condition)
    examples  = []   # interesting example races for the report

    for race_id in range(1, RACES_PER_SET + 1):
        sim = generate_race(race_id, condition)

        try:
            result = run_race(sim, engine)
        except Exception as e:
            if "parse" in str(e).lower() or "runner" in str(e).lower():
                metrics.parse_errors += 1
            else:
                metrics.engine_errors += 1
            continue

        # Anomaly check
        for a in _check_anomalies(result):
            metrics.anomalies.append(f"Race {race_id}: {a}")

        metrics.valid_races += 1
        race_info = result["_race_info"]
        runners   = result["_runner_objs"]
        rankings  = result.get("full_rankings", [])

        # ── Wet Jumps activation ────────────────────────────────────────────
        if _is_wet_jumps(race_info):
            metrics.wet_jumps_active += 1
        else:
            metrics.wet_jumps_inactive += 1

        # ── Confidence ─────────────────────────────────────────────────────
        conf = result.get("race_confidence", "LOW")
        metrics.conf_counter[conf] += 1

        # ── Gold pick ──────────────────────────────────────────────────────
        gold_name = result.get("gold_pick", {}).get("name")
        runners_raw = result["_runners_raw"]
        odds_dict   = {r["name"]: r.get("odds", "") for r in runners_raw}

        if odds_dict and gold_name:
            sorted_by_odds = sorted(
                odds_dict.items(),
                key=lambda kv: (_parse_odds(kv[1]) or 9999),
            )
            top1_names = [sorted_by_odds[0][0]]
            top3_names = [k for k, _ in sorted_by_odds[:3]]

            if gold_name in top1_names:
                metrics.top1_fav += 1
            if gold_name in top3_names:
                metrics.top3_fav += 1

            # Outsider check
            gold_odds_str = odds_dict.get(gold_name, "")
            gold_odds_dec = _parse_odds(gold_odds_str)
            if gold_odds_dec is not None and gold_odds_dec >= metrics.outsider_threshold:
                metrics.outsider_top1 += 1

        # Dark horse
        if result.get("dark_horse"):
            metrics.dark_horse_count += 1

        # ── Total runners ──────────────────────────────────────────────────
        metrics.total_runners += len(runners)

        # ── Per-category score tracking ────────────────────────────────────
        score_by_name = {r["name"]: r.get("score", 0.0) for r in rankings}
        for i, runner in enumerate(runners):
            cat = sim.runner_cats[i] if i < len(sim.runner_cats) else "neutral"
            sc  = score_by_name.get(runner.name, 0.0)
            metrics.scores_by_cat[cat].append(sc)

        # ── Wet-jumps multiplier gap (to show signal influence) ────────────
        if _is_wet_jumps(race_info) and len(runners) >= 2:
            mults = [engine._wet_jumps_adjustment(r, race_info) for r in runners]
            gap   = max(mults) - min(mults)
            metrics.mult_gaps.append(gap)

        # ── Collect interesting example races ──────────────────────────────
        cats = sim.runner_cats
        has_jneg = "jump_neg"    in cats
        has_spos = "stamina_pos" in cats
        has_jpos = "jump_pos"    in cats
        has_sneg = "stamina_neg" in cats

        if len(examples) < 8 and (has_jneg or has_spos) and has_jpos or has_sneg:
            mults_for_ex = {}
            if _is_wet_jumps(race_info):
                mults_for_ex = {
                    runners[i].name: engine._wet_jumps_adjustment(runners[i], race_info)
                    for i in range(len(runners))
                }
            examples.append({
                "race_id":  race_id,
                "condition": condition,
                "going":    sim.going,
                "distance": sim.distance,
                "field_sz": sim.field_size,
                "runners":  runners,
                "cats":     sim.runner_cats,
                "mults":    mults_for_ex,
                "scores":   score_by_name,
                "gold":     gold_name,
                "conf":     conf,
            })

    return metrics, examples


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────

BAR_WIDTH = 40

def _bar(n: int, total: int) -> str:
    if total == 0:
        return ""
    filled = round(BAR_WIDTH * n / total)
    return "█" * filled


def _pct(n: int, d: int) -> str:
    if d == 0:
        return "  n/a"
    return f"{100*n/d:5.1f}%"


def _mean(lst: list) -> float:
    return sum(lst) / len(lst) if lst else 0.0


def print_set_report(m: SetMetrics, examples: list):
    label = f"SET {'A' if m.condition=='Wet' else 'B'}  —  {m.condition.upper()} GROUND JUMPS"
    print(f"\n{'─'*68}")
    print(f"  {label}")
    print(f"{'─'*68}")

    # ── Health ─────────────────────────────────────────────────────────────
    print(f"\n  Parser / engine health")
    print(f"    Valid races        : {m.valid_races} / {RACES_PER_SET}")
    print(f"    Parse errors       : {m.parse_errors}")
    print(f"    Engine errors      : {m.engine_errors}")
    print(f"    Scoring anomalies  : {len(m.anomalies)}")
    for a in m.anomalies[:5]:
        print(f"      ⚠  {a}")

    # ── Wet Jumps activation ────────────────────────────────────────────────
    if m.condition == "Wet":
        print(f"\n  Wet Jumps mode activation")
        print(f"    Active   (_is_wet_jumps=True)  : {m.wet_jumps_active}")
        print(f"    Inactive (_is_wet_jumps=False) : {m.wet_jumps_inactive}")
        if m.wet_jumps_inactive > 0:
            print(f"    ⚠  {m.wet_jumps_inactive} wet races did NOT activate Wet Jumps mode — check going values")
    else:
        print(f"\n  Wet Jumps leakage check (must be 0)")
        print(f"    _is_wet_jumps=True in Dry set  : {m.wet_jumps_active}  {'✓ clean' if m.wet_jumps_active==0 else '⚠ LEAKAGE DETECTED'}")

    # ── Confidence ─────────────────────────────────────────────────────────
    print(f"\n  Confidence distribution")
    total = m.valid_races
    for lv in ("HIGH", "MEDIUM", "LOW"):
        n = m.conf_counter.get(lv, 0)
        print(f"    {lv:<6}  {n:>3}  {_bar(n, total)}  {_pct(n, total)}")

    # ── Selection behaviour ─────────────────────────────────────────────────
    print(f"\n  Selection behaviour")
    print(f"    Top-1 (gold == fav)     : {m.top1_fav:>3} / {total}  {_pct(m.top1_fav, total)}")
    print(f"    Top-3 (gold in fav-3)   : {m.top3_fav:>3} / {total}  {_pct(m.top3_fav, total)}")
    print(f"    Dark horse returned     : {m.dark_horse_count:>3} / {total}  {_pct(m.dark_horse_count, total)}")
    print(f"    Outsider (14/1+) top-1  : {m.outsider_top1:>3} / {total}  {_pct(m.outsider_top1, total)}")

    # ── Comment signal scores ───────────────────────────────────────────────
    print(f"\n  Average engine score by comment category")
    cat_order = ["jump_pos", "stamina_pos", "neutral", "jump_neg", "stamina_neg"]
    cat_means = {}
    for cat in cat_order:
        lst = m.scores_by_cat.get(cat, [])
        if lst:
            mn = _mean(lst)
            cat_means[cat] = mn
            print(f"    {cat:<16} n={len(lst):>4}   avg_score={mn:.4f}")
        else:
            cat_means[cat] = None
            print(f"    {cat:<16} n=   0   avg_score=  n/a")

    # ── Wet-jumps multiplier gap ────────────────────────────────────────────
    if m.condition == "Wet" and m.mult_gaps:
        avg_gap = _mean(m.mult_gaps)
        max_gap = max(m.mult_gaps)
        print(f"\n  Wet-jumps multiplier spread (per race — shows signal breadth)")
        print(f"    Avg gap (max−min mult within race) : {avg_gap:.4f}")
        print(f"    Max gap observed                   : {max_gap:.4f}")

    # ── Example races ───────────────────────────────────────────────────────
    if examples:
        print(f"\n  Illustrative examples ({min(len(examples), 4)} shown)")
        for ex in examples[:4]:
            print(f"\n    Race #{ex['race_id']}  |  {ex['going'].upper()}  "
                  f"|  {ex['distance']}  |  {ex['field_sz']} runners  "
                  f"|  gold={ex['gold']}  |  conf={ex['conf']}")
            print(f"    {'Horse':<18} {'Cat':<14} {'Score':>7}  {'WJ-mult':>7}")
            print(f"    {'-'*18} {'-'*14} {'-'*7}  {'-'*7}")
            for i, r in enumerate(ex["runners"]):
                cat   = ex["cats"][i] if i < len(ex["cats"]) else "neutral"
                sc    = ex["scores"].get(r.name, 0.0)
                mult  = ex["mults"].get(r.name, "-")
                mult_s = f"{mult:.4f}" if isinstance(mult, float) else "  n/a"
                marker = " ← GOLD" if r.name == ex["gold"] else ""
                print(f"    {r.name:<18} {cat:<14} {sc:>7.4f}  {mult_s:>7}{marker}")


def print_comparison(mw: SetMetrics, md: SetMetrics):
    print(f"\n{'='*68}")
    print(f"  COMPARISON SUMMARY  —  Wet Jumps vs Dry Jumps")
    print(f"{'='*68}")

    def diff(wet_val, dry_val, label, fmt=".1f"):
        sign = "+" if wet_val >= dry_val else ""
        d = wet_val - dry_val
        print(f"  {label:<40} Wet={wet_val:{fmt}}  Dry={dry_val:{fmt}}  diff={sign}{d:{fmt}}")

    w = mw.valid_races
    d = md.valid_races

    print(f"\n  Selection & confidence")
    diff(100*mw.top1_fav/w,   100*md.top1_fav/d,   "Top-1 (with fav) %")
    diff(100*mw.top3_fav/w,   100*md.top3_fav/d,   "Top-3 (with fav-3) %")
    diff(100*mw.outsider_top1/w, 100*md.outsider_top1/d, "Outsider top-1 %")
    diff(100*mw.dark_horse_count/w, 100*md.dark_horse_count/d, "Dark horse %")

    for lv in ("HIGH", "MEDIUM", "LOW"):
        diff(100*mw.conf_counter.get(lv,0)/w,
             100*md.conf_counter.get(lv,0)/d,
             f"Confidence {lv} %")

    print(f"\n  Comment signal influence (avg engine score)")
    cat_order = ["jump_pos", "stamina_pos", "neutral", "jump_neg", "stamina_neg"]
    for cat in cat_order:
        wl = mw.scores_by_cat.get(cat, [])
        dl = md.scores_by_cat.get(cat, [])
        wm = _mean(wl)
        dm = _mean(dl)
        if wl and dl:
            diff(wm, dm, f"  avg_score [{cat}]", fmt=".4f")

    # Direction check for Wet set
    print(f"\n  Wet set — comment signal direction check")
    cats = mw.scores_by_cat
    pos_avg  = _mean(cats.get("jump_pos",    []) + cats.get("stamina_pos", []))
    neg_avg  = _mean(cats.get("jump_neg",    []) + cats.get("stamina_neg", []))
    neu_avg  = _mean(cats.get("neutral",     []))
    print(f"    Positive comment avg score : {pos_avg:.4f}")
    print(f"    Neutral  comment avg score : {neu_avg:.4f}")
    print(f"    Negative comment avg score : {neg_avg:.4f}")
    if pos_avg > neu_avg > neg_avg:
        print(f"    ✓ Direction correct — pos > neutral > neg")
    elif pos_avg > neg_avg:
        print(f"    ✓ Directional — pos > neg (neutral ordering may vary)")
    else:
        print(f"    ⚠ Unexpected ordering — review signal weights")

    # Wet-jumps multiplier gap summary
    if mw.mult_gaps:
        print(f"\n  Wet-jumps multiplier spread (avg per race)")
        print(f"    Wet set avg gap : {_mean(mw.mult_gaps):.4f}")
        print(f"    (n/a for Dry set — wet-jumps logic not active)")

    print(f"\n  Leakage confirmation")
    print(f"    Wet Jumps active in Dry set : {md.wet_jumps_active}  "
          f"{'✓ no leakage' if md.wet_jumps_active==0 else '⚠ LEAKAGE'}")

    print(f"\n  Overall assessment")
    if (pos_avg > neg_avg and
            md.wet_jumps_active == 0 and
            mw.parse_errors == 0 and mw.engine_errors == 0 and
            md.parse_errors == 0 and md.engine_errors == 0):
        print(f"    ✓ Wet Jumps enhancements working as intended.")
        print(f"    ✓ Dry Jumps logic stable — no regression detected.")
    else:
        print(f"    ⚠ Issues detected — see details above.")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    engine = RacingAICore()

    print(f"\n{'='*68}")
    print(f"  PeakPace AI — Wet vs Dry Jumps Comparison ({RACES_PER_SET} races each)")
    print(f"{'='*68}")

    print(f"\n  Running SET A — {RACES_PER_SET} WET / bad-ground Jumps races...")
    metrics_wet, examples_wet = simulate_set("Wet", engine)

    print(f"  Running SET B — {RACES_PER_SET} DRY / good-ground Jumps races...")
    metrics_dry, examples_dry = simulate_set("Dry", engine)

    print_set_report(metrics_wet, examples_wet)
    print_set_report(metrics_dry, examples_dry)
    print_comparison(metrics_wet, metrics_dry)

    print(f"\n{'='*68}\n")
    exit_code = 0
    if metrics_wet.parse_errors or metrics_wet.engine_errors:
        exit_code = 1
    if metrics_dry.parse_errors or metrics_dry.engine_errors:
        exit_code = 1
    if metrics_dry.wet_jumps_active > 0:
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
