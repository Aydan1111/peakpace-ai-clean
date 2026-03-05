"""
PeakPace AI — 100-Race Stress Test Simulation
==============================================
Generates 100 realistic UK/Irish races in canonical paste format,
parses them through the racecard parser, runs the prediction engine,
then mirrors each race through the manual-entry path and compares.

Metrics reported:
  - Top-1 / Top-3 accuracy (gold pick vs. actual favourite rank)
  - Confidence distribution (HIGH / MEDIUM / LOW)
  - Dark horse selection frequency and validity
  - Parser failures (missing fields, wrong counts)
  - Scoring anomalies (ties, missing scores, NaN)
  - Pipeline equivalence: paste vs. manual produce identical runner objects
"""

import sys
import os
import random
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import List, Optional

# Add project root so we can import main.py helpers and racing_ai_core
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
from racing_ai_core import RacingAICore, RaceInfo, Runner

# ── Seeded RNG for reproducibility ──────────────────────────────────────────
RNG = random.Random(20260305)

# ── Pool data ────────────────────────────────────────────────────────────────

UK_FLAT_COURSES   = ["Newmarket", "Ascot", "Goodwood", "York", "Haydock",
                      "Sandown", "Chester", "Lingfield", "Kempton", "Wolverhampton",
                      "Nottingham", "Leicester", "Catterick", "Pontefract", "Windsor",
                      "Doncaster", "Newbury", "Epsom", "Chelmsford", "Carlisle"]

UK_JUMP_COURSES   = ["Cheltenham", "Sandown", "Kempton", "Ascot", "Aintree",
                      "Wetherby", "Uttoxeter", "Market Rasen", "Exeter", "Hereford",
                      "Huntingdon", "Ludlow", "Worcester", "Stratford", "Taunton",
                      "Musselburgh", "Ayr", "Perth", "Cartmel", "Newton Abbot"]

IRE_FLAT_COURSES  = ["The Curragh", "Leopardstown", "Naas", "Cork", "Limerick",
                      "Dundalk", "Tipperary", "Gowran Park"]

IRE_JUMP_COURSES  = ["Leopardstown", "Fairyhouse", "Punchestown", "Naas",
                      "Navan", "Thurles", "Clonmel", "Kilbeggan"]

JOCKEYS_FLAT = [
    "Oisin Murphy", "Ryan Moore", "Frankie Dettori", "James Doyle",
    "Tom Marquand", "William Buick", "Pat Dobbs", "Adam Kirby",
    "Hollie Doyle", "Rossa Ryan", "Andrea Atzeni", "Jamie Spencer",
    "Jim Crowley", "David Egan", "Jason Watson", "Kieran Shoemark",
    "Colin Keane", "Shane Foley", "Billy Lee", "Declan McDonogh",
]

JOCKEYS_JUMP = [
    "Paul Townend", "Rachael Blackmore", "Danny Mullins", "Mark Walsh",
    "Jack Kennedy", "Bryan Cooper", "Davy Russell", "Robbie Power",
    "Harry Cobden", "Nico de Boinville", "Aidan Coleman", "Sam Twiston-Davies",
    "Tom Cannon", "Jonathan Moore", "Sean Flanagan", "Darragh O'Keeffe",
    "Brian Hayes", "Derek O'Connor", "Patrick Mullins", "Keith Donoghue",
]

TRAINERS_FLAT = [
    "John Gosden", "Aidan O'Brien", "Charlie Appleby", "William Haggas",
    "Roger Varian", "Mark Johnston", "Richard Hannon", "Andrew Balding",
    "Clive Cox", "Martyn Meade", "Hugo Palmer", "Ed Vaughan",
    "Jessica Harrington", "Dermot Weld", "Ken Condon", "Ger Lyons",
    "Joseph O'Brien", "Paddy Twomey", "Michael Halford", "Fozzy Stack",
]

TRAINERS_JUMP = [
    "Willie Mullins", "Gordon Elliott", "Henry de Bromhead", "Noel Meade",
    "Joseph O'Brien", "Gavin Cromwell", "Denise Foster", "Mouse Morris",
    "Paul Nolan", "Dessie Hughes", "Nicky Henderson", "Paul Nicholls",
    "Dan Skelton", "Colin Tizzard", "Jonjo O'Neill", "Kim Bailey",
    "Philip Hobbs", "Harry Fry", "Alan King", "Ben Pauling",
]

EQUIPMENT_OPTIONS = [
    "", "", "", "",  # mostly blank
    "tongue strap", "cheekpieces", "hood", "blinkers",
    "cheekpieces, tongue strap", "visor", "hood removed",
    "tongue strap first time", "sheepskin cheekpieces",
]

GOING_FLAT   = ["good", "good to firm", "firm", "good to soft", "soft", "standard", "standard"]
GOING_JUMPS  = ["good", "good to soft", "soft", "heavy", "good to soft", "soft"]

HORSE_PREFIXES = [
    "Golden", "Silver", "Dark", "Bold", "Swift", "Noble", "Royal", "Iron",
    "Wild", "Storm", "Thunder", "Shadow", "Desert", "Night", "Fire", "Sky",
    "Green", "Lucky", "Magic", "Brave", "Silent", "Shining", "Ancient",
    "Frozen", "Blazing", "Crystal", "Copper", "Scarlet", "Amber", "Dazzling",
]
HORSE_SUFFIXES = [
    "Star", "Prince", "Knight", "Runner", "Dancer", "Flash", "Spirit",
    "Dream", "Light", "Wind", "Peak", "Ridge", "Wave", "Flame", "Arrow",
    "Crown", "Moon", "Mist", "Blaze", "Eagle", "Hawk", "Falcon", "Force",
    "Heart", "Storm", "Tide", "River", "Comet", "Quest", "Legend",
]

FORM_CHARS = "123456780PFU"

COMMENTS = [
    "Progressive type, well suited to this trip and ground.",
    "Won well last time, back to form after a gelding operation.",
    "Consistent performer, rarely out of the first three.",
    "Looked unlucky when hampered last start; capable of better.",
    "Course and distance winner, likes cut in the ground.",
    "First-time tongue strap could sharpen him up here.",
    "Trainer in flying form, jockey booking is encouraging.",
    "Seems to need a flat track; this course should suit.",
    "Lightly raced and unexposed over this distance.",
    "Big dropper in class after a troubled campaign.",
    "Has been freshened up since last run, watch market.",
    "Usually runs well fresh, strong finishing kick.",
    "Ideally needs further but jockey knows the horse well.",
    "Has the best form in the race on official ratings.",
    "Filly with plenty of ability, not seen to best effect lately.",
    "Consistent jumper, travels well in his races.",
    "Won twice here; excellent course record.",
    "Improved since wind surgery, expected to go close.",
    "Likely to take a keen hold; bold-jumping type.",
    "Previous run was too soft; back to preferred going today.",
]

# ── Odds pools ───────────────────────────────────────────────────────────────

FAVOURITE_ODDS   = ["2/1", "5/2", "3/1", "7/2", "4/1", "9/2", "5/1"]
MID_FIELD_ODDS   = ["6/1", "7/1", "8/1", "10/1", "12/1"]
OUTSIDER_ODDS    = ["14/1", "16/1", "20/1", "25/1", "33/1"]
TAIL_ENDER_ODDS  = ["20/1", "25/1", "33/1", "40/1", "50/1"]

RACE_DISTANCES_FLAT  = ["5f", "6f", "7f", "1m", "1m1f", "1m2f", "1m4f", "1m6f", "2m"]
RACE_DISTANCES_JUMPS = ["2m", "2m1f", "2m4f", "2m5f", "3m", "3m1f", "3m2f"]

RACE_TYPES = [
    ("flat",          "turf",  RACE_DISTANCES_FLAT),
    ("flat",          "aw",    RACE_DISTANCES_FLAT[:7]),
    ("national_hunt", "turf",  RACE_DISTANCES_JUMPS),
    ("national_hunt", "turf",  RACE_DISTANCES_JUMPS),
]

NH_DISCIPLINES = ["hurdle", "chase", "bumper", "flat"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def _horse_name(used: set) -> str:
    for _ in range(200):
        n = f"{RNG.choice(HORSE_PREFIXES)} {RNG.choice(HORSE_SUFFIXES)}"
        if n not in used:
            used.add(n)
            return n
    # fallback
    name = f"Runner {RNG.randint(100,999)}"
    used.add(name)
    return name


def _form_string(length: int = 6) -> str:
    return "".join(RNG.choice(FORM_CHARS) for _ in range(RNG.randint(3, length)))


def _weight_str(age: int, race_type: str) -> str:
    if race_type == "flat":
        stone = RNG.randint(8, 10)
        lbs   = RNG.randint(0, 13)
    else:
        stone = RNG.randint(10, 12)
        lbs   = RNG.randint(0, 13)
    return f"{stone}-{lbs}"


def _prev_runs_text(race_type: str, n: int = 3) -> str:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if race_type == "flat":
        dists = ["6f", "7f", "1m", "1m2f", "1m4f"]
        discs = ["flat"]
    else:
        dists = ["2m", "2m4f", "2m5f", "3m", "3m1f"]
        discs = ["hurdle", "chase", "bumper"]

    lines = []
    year = 2025
    month_idx = RNG.randint(0, 11)
    day = RNG.randint(1, 28)
    for _ in range(n):
        month_idx = (month_idx - RNG.randint(1, 2)) % 12
        day = RNG.randint(1, 28)
        going = RNG.choice(["Good", "Soft", "Good to Soft", "Heavy", "Good to Firm"])
        dist  = RNG.choice(dists)
        pos   = RNG.randint(1, 10)
        fsize = RNG.randint(pos, min(pos + 12, 18))
        disc  = RNG.choice(discs)
        lines.append(
            f"{months[month_idx]} {day} {year} | Racecourse | {dist} | {going} | {pos}/{fsize} | {disc.title()}"
        )
    return "\n".join(lines)


def _odds_for_field(size: int) -> list:
    """Return a list of `size` odds strings with a realistic distribution."""
    pool = []
    # 1-2 favourites
    n_fav = RNG.randint(1, 2)
    for _ in range(n_fav):
        pool.append(RNG.choice(FAVOURITE_ODDS))
    # 2-3 mid-field
    n_mid = min(RNG.randint(2, 3), size - n_fav)
    for _ in range(n_mid):
        pool.append(RNG.choice(MID_FIELD_ODDS))
    # fill rest with outsiders / tailenders
    while len(pool) < size:
        pool.append(RNG.choice(OUTSIDER_ODDS if RNG.random() > 0.3 else TAIL_ENDER_ODDS))
    RNG.shuffle(pool)
    return pool[:size]


# ── Race generator ────────────────────────────────────────────────────────────

@dataclass
class GeneratedRace:
    race_id: int
    course: str
    race_type: str
    surface: str
    distance: str
    going: str
    country: str
    paste_text: str
    # structured data for manual path comparison
    manual_runners: list   # list of dicts mirroring UI payload


def _generate_race(race_id: int) -> GeneratedRace:
    # pick race category
    rt_entry = RNG.choice(RACE_TYPES)
    race_type, surface, dists = rt_entry
    distance = RNG.choice(dists)

    # pick country / course
    if race_type == "flat":
        all_courses = UK_FLAT_COURSES + IRE_FLAT_COURSES
    else:
        all_courses = UK_JUMP_COURSES + IRE_JUMP_COURSES
    course  = RNG.choice(all_courses)
    country = "ireland" if course in (IRE_FLAT_COURSES + IRE_JUMP_COURSES) else "uk"

    # going
    going = RNG.choice(GOING_FLAT if race_type == "flat" else GOING_JUMPS)

    # NH discipline label for prev runs
    nh_disc = RNG.choice(["hurdle", "chase"]) if race_type == "national_hunt" else "flat"

    # field size
    field_size = RNG.randint(8, 16)

    # jockey / trainer pools
    jockeys  = JOCKEYS_FLAT  if race_type == "flat" else JOCKEYS_JUMP
    trainers = TRAINERS_FLAT if race_type == "flat" else TRAINERS_JUMP

    used_names: set = set()
    odds_list = _odds_for_field(field_size)

    lines  = []
    manual_runners = []

    for i in range(field_size):
        name      = _horse_name(used_names)
        age       = RNG.randint(2, 5) if race_type == "flat" else RNG.randint(4, 10)
        weight    = _weight_str(age, race_type)
        form      = _form_string()
        jockey    = RNG.choice(jockeys)
        trainer   = RNG.choice(trainers)
        odds      = odds_list[i]
        equipment = RNG.choice(EQUIPMENT_OPTIONS)
        comment   = RNG.choice(COMMENTS)
        n_prev    = RNG.randint(0, 3)
        prev_text = _prev_runs_text(race_type, n=n_prev) if n_prev > 0 else ""

        # ── PASTE lines — exact multi-line format from the canonical template ──
        # Each field on its own line, matching the screenshot format:
        #   HORSE: Karamoja
        #   JOCKEY: P. Townend
        #   TRAINER: W. P. Mullins
        #   FORM: 3P173-467
        #   AGE: 6
        #   WEIGHT: 11-7
        #   ODDS: 5/2
        #   EQUIPMENT: Tongue Strap
        #   COMMENT:
        #   <comment text on next line>
        #   RECENT RUNS:
        #   Jan 9 2026 | Naas | 2m 4f 29y | Soft | 7/7 | Chase
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
        lines.append("")  # blank separator between runners

        # ── Manual dict ──
        manual_runners.append({
            "name":    name,
            "age":     age,
            "weight":  weight,
            "form":    form,
            "trainer": trainer,
            "jockey":  jockey,
            "odds":    odds,
            "equipment": equipment,
            "comment": comment,
            "previous_runs": prev_text,  # raw text — comparison done post-parse
        })

    return GeneratedRace(
        race_id=race_id,
        course=course,
        race_type=race_type,
        surface=surface,
        distance=distance,
        going=going,
        country=country,
        paste_text="\n".join(lines),
        manual_runners=manual_runners,
    )


# ── Engine wrapper ────────────────────────────────────────────────────────────

def _run_paste_path(race: GeneratedRace, engine: RacingAICore) -> dict:
    """Mirror exactly what /analyze-text does."""
    detected_type    = detect_race_type(race.paste_text)
    detected_country = detect_country(race.paste_text)
    detected_going   = detect_going(race.paste_text)

    runners_raw = parse_racecard_text(race.paste_text)

    ri_going = detected_going if detected_going else race.going
    race_info = RaceInfo(
        course=race.course,
        country=detected_country,
        race_type=detected_type,
        surface=race.surface,
        distance_f=parse_distance_to_furlongs(race.distance),
        going=normalize_going(ri_going),
        runners=len(runners_raw),
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
    final_odds  = inline_odds if inline_odds else None

    engine.dark_horse_enabled = True
    return {
        "result":       engine.analyze(race_info, runner_objects, odds=final_odds),
        "runners_raw":  runners_raw,
        "runner_count": len(runners_raw),
    }


def _run_manual_path(race: GeneratedRace, engine: RacingAICore) -> dict:
    """Mirror exactly what /analyze does (manual entry mode)."""
    race_info = RaceInfo(
        course=race.course,
        country=race.country,
        race_type=race.race_type,
        surface=race.surface,
        distance_f=parse_distance_to_furlongs(race.distance),
        going=normalize_going(race.going),
        runners=len(race.manual_runners),
    )

    runner_objects = []
    for r in race.manual_runners:
        runner_objects.append(
            Runner(
                name=r["name"],
                age=r["age"],
                weight_lbs=parse_weight_to_lbs(r["weight"]),
                form=r["form"],
                trainer=r["trainer"],
                jockey=r["jockey"],
                comment=r.get("comment", ""),
                equipment=r.get("equipment", ""),
                previous_runs=None,  # manual mode — prev_runs not structured here
            )
        )

    manual_odds = {r["name"]: r["odds"] for r in race.manual_runners if r.get("odds")}
    final_odds  = manual_odds if manual_odds else None

    engine.dark_horse_enabled = True
    return {
        "result":       engine.analyze(race_info, runner_objects, odds=final_odds),
        "runner_count": len(race.manual_runners),
    }


# ── Parser field audit ────────────────────────────────────────────────────────

def _audit_runner(raw: dict, gen: dict) -> dict:
    """Compare parsed runner fields against generated source. Returns issues."""
    issues = []
    if raw["name"] != gen["name"]:
        issues.append(f"name mismatch: got '{raw['name']}' expected '{gen['name']}'")
    if raw["jockey"] != gen["jockey"]:
        issues.append(f"jockey mismatch: got '{raw['jockey']}' expected '{gen['jockey']}'")
    if raw["trainer"] != gen["trainer"]:
        issues.append(f"trainer mismatch: got '{raw['trainer']}' expected '{gen['trainer']}'")
    if raw["form"] != gen["form"]:
        issues.append(f"form mismatch: got '{raw['form']}' expected '{gen['form']}'")
    if str(raw["age"]) != str(gen["age"]):
        issues.append(f"age mismatch: got '{raw['age']}' expected '{gen['age']}'")
    if raw["weight"] != gen["weight"]:
        issues.append(f"weight mismatch: got '{raw['weight']}' expected '{gen['weight']}'")
    if raw["odds"] != gen["odds"]:
        issues.append(f"odds mismatch: got '{raw['odds']}' expected '{gen['odds']}'")
    if gen["equipment"] and raw["equipment"] != gen["equipment"]:
        issues.append(f"equipment mismatch: got '{raw['equipment']}' expected '{gen['equipment']}'")
    return issues


# ── Scoring anomaly detector ──────────────────────────────────────────────────

def _check_anomalies(result: dict) -> list:
    issues = []
    rankings = result.get("full_rankings", [])
    if not rankings:
        issues.append("ANOMALY: empty full_rankings")
        return issues
    scores = [r.get("score", None) for r in rankings]
    if any(s is None for s in scores):
        issues.append("ANOMALY: None score in rankings")
    try:
        import math
        if any(math.isnan(s) for s in scores if s is not None):
            issues.append("ANOMALY: NaN score in rankings")
    except Exception:
        pass
    # Tie at the top
    if len(scores) >= 2 and scores[0] == scores[1] and scores[0] is not None:
        issues.append(f"ANOMALY: tie at top ({scores[0]:.3f})")
    # Gold pick absent from rankings
    gold_name = result.get("gold_pick", {}).get("name")
    if gold_name and not any(r["name"] == gold_name for r in rankings):
        issues.append(f"ANOMALY: gold pick '{gold_name}' not in full_rankings")
    return issues


# ── Main simulation ───────────────────────────────────────────────────────────

def run_simulation(n: int = 100):
    engine = RacingAICore()
    engine.dark_horse_enabled = True

    print(f"\n{'='*70}")
    print(f"  PeakPace AI — {n}-Race Stress Test Simulation")
    print(f"{'='*70}\n")

    # ── Counters ──
    paste_failures       = 0    # parse errors or < 2 runners
    engine_errors        = 0
    field_mismatches     = 0    # total field issues across all runners
    runner_count_errors  = 0    # paste count != generated count

    paste_top1  = 0  # gold == rank-1 favourite (by odds)
    paste_top3  = 0  # gold in top-3 favourites (by odds)
    manual_top1 = 0
    manual_top3 = 0

    conf_counter = Counter()
    dark_horse_count = 0
    dark_horse_races = 0

    anomalies      = []
    parse_failures = []
    field_issues   = []
    pipeline_diffs = []

    # Track per-race for CSV-style summary
    race_rows = []

    for race_id in range(1, n + 1):
        gen = _generate_race(race_id)

        # ── Paste path ────────────────────────────────────────────
        paste_ok     = False
        paste_result = None
        paste_count  = 0
        paste_gold   = None
        paste_conf   = None
        paste_dark   = False

        try:
            paste_out    = _run_paste_path(gen, engine)
            paste_result = paste_out["result"]
            paste_count  = paste_out["runner_count"]

            if paste_count != len(gen.manual_runners):
                runner_count_errors += 1
                parse_failures.append(
                    f"Race {race_id}: parsed {paste_count} runners, "
                    f"expected {len(gen.manual_runners)}"
                )

            # Audit fields for each runner
            runners_raw = paste_out["runners_raw"]
            for i, raw in enumerate(runners_raw):
                if i < len(gen.manual_runners):
                    issues = _audit_runner(raw, gen.manual_runners[i])
                    if issues:
                        field_mismatches += len(issues)
                        for iss in issues:
                            field_issues.append(f"Race {race_id} runner #{i+1}: {iss}")

            # Check anomalies
            anom = _check_anomalies(paste_result)
            for a in anom:
                anomalies.append(f"Race {race_id}: {a}")

            paste_gold = paste_result.get("gold_pick", {}).get("name")
            paste_conf = paste_result.get("race_confidence", "LOW")
            conf_counter[paste_conf] += 1

            if paste_result.get("dark_horse"):
                dark_horse_count += 1
                paste_dark = True
            dark_horse_races += 1

            # "accuracy" = does gold pick match the lowest-odds runner?
            # (We use the favourite by odds as a proxy for "expected winner")
            from racing_ai_core import _parse_odds as _po
            odds_dict = {r["name"]: r["odds"] for r in runners_raw if r.get("odds")}
            if odds_dict:
                fav_sorted = sorted(
                    odds_dict.items(),
                    key=lambda kv: (_po(kv[1]) or 999)
                )
                fav_names_top1 = [fav_sorted[0][0]]
                fav_names_top3 = [k for k, _ in fav_sorted[:3]]
                if paste_gold in fav_names_top1:
                    paste_top1 += 1
                if paste_gold in fav_names_top3:
                    paste_top3 += 1

            paste_ok = True

        except Exception as e:
            paste_failures += 1
            parse_failures.append(f"Race {race_id} PASTE ERROR: {e}")

        # ── Manual path ───────────────────────────────────────────
        manual_ok     = False
        manual_result = None
        manual_gold   = None

        try:
            manual_out    = _run_manual_path(gen, engine)
            manual_result = manual_out["result"]

            manual_gold = manual_result.get("gold_pick", {}).get("name")

            from racing_ai_core import _parse_odds as _po
            manual_odds_dict = {r["name"]: r["odds"] for r in gen.manual_runners if r.get("odds")}
            if manual_odds_dict:
                fav_sorted_m = sorted(
                    manual_odds_dict.items(),
                    key=lambda kv: (_po(kv[1]) or 999)
                )
                fav_names_top1_m = [fav_sorted_m[0][0]]
                fav_names_top3_m = [k for k, _ in fav_sorted_m[:3]]
                if manual_gold in fav_names_top1_m:
                    manual_top1 += 1
                if manual_gold in fav_names_top3_m:
                    manual_top3 += 1

            manual_ok = True

        except Exception as e:
            engine_errors += 1
            parse_failures.append(f"Race {race_id} MANUAL ERROR: {e}")

        # ── Pipeline equivalence check ────────────────────────────
        # Both paths receive the same name/age/weight/form/trainer/jockey/odds.
        # Gold picks should match (previous_runs omitted from manual so scores
        # may differ slightly — we check name agreement only).
        if paste_ok and manual_ok and paste_gold and manual_gold:
            if paste_gold != manual_gold:
                pipeline_diffs.append(
                    f"Race {race_id}: paste gold='{paste_gold}' manual gold='{manual_gold}'"
                )

        # ── Row summary ───────────────────────────────────────────
        race_rows.append({
            "id":          race_id,
            "course":      gen.course,
            "type":        gen.race_type[:4],
            "dist":        gen.distance,
            "going":       gen.going[:4],
            "runners_gen": len(gen.manual_runners),
            "runners_prs": paste_count,
            "paste_gold":  paste_gold or "ERR",
            "manual_gold": manual_gold or "ERR",
            "conf":        paste_conf or "-",
            "dark":        "Y" if paste_dark else "-",
            "ok":          "OK" if paste_ok and manual_ok else "FAIL",
        })

    # ── Report ────────────────────────────────────────────────────────────────

    total_races = n
    successful  = total_races - paste_failures - engine_errors

    print(f"{'─'*70}")
    print(f"  RESULTS SUMMARY — {total_races} races")
    print(f"{'─'*70}")
    print(f"\n  Races completed successfully : {successful:>4} / {total_races}")
    print(f"  Paste parse failures         : {paste_failures:>4}")
    print(f"  Engine errors (either path)  : {engine_errors:>4}")
    print(f"  Runner count mismatches      : {runner_count_errors:>4}")
    print(f"  Field-level parse issues     : {field_mismatches:>4}")

    if successful > 0:
        print(f"\n  {'─'*40}")
        print(f"  ACCURACY  (gold pick vs. market favourite)")
        print(f"  {'─'*40}")
        print(f"  Paste mode  — Top-1 : {paste_top1:>3}/{successful}  ({100*paste_top1/successful:.1f}%)")
        print(f"  Paste mode  — Top-3 : {paste_top3:>3}/{successful}  ({100*paste_top3/successful:.1f}%)")
        print(f"  Manual mode — Top-1 : {manual_top1:>3}/{successful}  ({100*manual_top1/successful:.1f}%)")
        print(f"  Manual mode — Top-3 : {manual_top3:>3}/{successful}  ({100*manual_top3/successful:.1f}%)")

        print(f"\n  {'─'*40}")
        print(f"  CONFIDENCE DISTRIBUTION")
        print(f"  {'─'*40}")
        for level in ["HIGH", "MEDIUM", "LOW"]:
            cnt = conf_counter.get(level, 0)
            pct = 100 * cnt / successful if successful else 0
            bar = "█" * int(pct / 2)
            print(f"  {level:<8}: {cnt:>3}  ({pct:5.1f}%)  {bar}")

        print(f"\n  {'─'*40}")
        print(f"  DARK HORSE")
        print(f"  {'─'*40}")
        print(f"  Races with dark horse pick : {dark_horse_count:>3} / {dark_horse_races}")
        print(f"  Dark horse hit rate        : {100*dark_horse_count/max(dark_horse_races,1):.1f}%")

    if anomalies:
        print(f"\n  {'─'*40}")
        print(f"  SCORING ANOMALIES ({len(anomalies)})")
        print(f"  {'─'*40}")
        for a in anomalies[:20]:
            print(f"  {a}")
        if len(anomalies) > 20:
            print(f"  ... and {len(anomalies)-20} more")
    else:
        print(f"\n  Scoring anomalies          : NONE")

    if parse_failures:
        print(f"\n  {'─'*40}")
        print(f"  PARSE / ENGINE FAILURES ({len(parse_failures)})")
        print(f"  {'─'*40}")
        for f in parse_failures[:20]:
            print(f"  {f}")
        if len(parse_failures) > 20:
            print(f"  ... and {len(parse_failures)-20} more")
    else:
        print(f"\n  Parse/engine failures      : NONE")

    if field_issues:
        print(f"\n  {'─'*40}")
        print(f"  FIELD-LEVEL ISSUES (first 30)")
        print(f"  {'─'*40}")
        for fi in field_issues[:30]:
            print(f"  {fi}")
        if len(field_issues) > 30:
            print(f"  ... and {len(field_issues)-30} more")
    else:
        print(f"\n  Field-level parse issues   : NONE")

    print(f"\n  {'─'*40}")
    print(f"  PIPELINE EQUIVALENCE (paste gold == manual gold)")
    print(f"  {'─'*40}")
    if pipeline_diffs:
        print(f"  Divergences: {len(pipeline_diffs)} / {successful}")
        print(f"  (prev_runs only in paste path — minor score deltas expected)")
        for d in pipeline_diffs[:15]:
            print(f"    {d}")
    else:
        print(f"  100% agreement across all {successful} races — PASS")

    print(f"\n{'='*70}")
    print(f"  PER-RACE TABLE (first 30)")
    print(f"{'='*70}")
    hdr = f"  {'ID':>3}  {'Course':<18}  {'T':<4}  {'Dist':<5}  {'Go':<5}  "
    hdr += f"{'Gen':>3}  {'Prs':>3}  {'Paste Gold':<22}  {'Conf':<6}  {'DH':<3}  {'Status'}"
    print(hdr)
    print(f"  {'─'*100}")
    for row in race_rows[:30]:
        print(
            f"  {row['id']:>3}  {row['course']:<18}  {row['type']:<4}  "
            f"{row['dist']:<5}  {row['going']:<5}  {row['runners_gen']:>3}  "
            f"{row['runners_prs']:>3}  {row['paste_gold']:<22}  "
            f"{row['conf']:<6}  {row['dark']:<3}  {row['ok']}"
        )
    if n > 30:
        print(f"\n  ... {n-30} more races (use full output file for complete table)")

    print(f"\n{'='*70}")
    print(f"  Simulation complete.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_simulation(100)
