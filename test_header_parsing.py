"""
Header parsing + discipline detection — 4-scenario validation.

Verifies:
  1. Flat header (unstructured + explicit "Flat" keyword)         → discipline=Flat
  2. Hurdle header                                                → discipline=Jumps, subtype=Hurdle
  3. Chase header                                                 → discipline=Jumps, subtype=Chase
  4. Header with no discipline keywords (classic flat handicap)   → discipline=Unknown
  Each scenario also confirms runners parse correctly and the engine runs.
"""

import sys, json
sys.path.insert(0, "/home/user/peakpace-ai-clean")

from main import (
    parse_racecard_header,
    detect_discipline,
    _extract_header_section,
    _discipline_display,
    parse_racecard_text,
    parse_distance_to_furlongs,
    normalize_going,
    detect_race_type,
    detect_country,
    detect_going,
)
from racing_ai_core import RacingAICore, RaceInfo, Runner, _parse_odds

engine = RacingAICore()
engine.dark_horse_enabled = True

# ── Shared minimal runner block (2 runners — minimum for the engine) ──────────
RUNNER_BLOCK = """
HORSE: Silver Arrow
JOCKEY: Oisin Murphy
TRAINER: John Gosden
FORM: 11-21
AGE: 4
WEIGHT: 9-2
ODDS: 5/2
COMMENT: Course winner, goes well on this ground.

HORSE: Golden Prince
JOCKEY: Ryan Moore
TRAINER: Aidan O'Brien
FORM: 213-1
AGE: 4
WEIGHT: 9-0
ODDS: 3/1
COMMENT: Consistent type, should run his race.
"""

# ── SCENARIO 1 — Flat header with explicit "Flat" keyword ────────────────────
FLAT_RACECARD = """\
Newcastle Midnite Flat Race: All-Weather Apprentice Handicap Flat 6f • 8 Runners • Class 6
Going: Standard
""" + RUNNER_BLOCK

# ── SCENARIO 2 — Hurdle header ────────────────────────────────────────────────
HURDLE_RACECARD = """\
Cheltenham Festival — Novice Hurdle 2m • 12 Runners • Class 1
Going: Good to Soft
""" + RUNNER_BLOCK

# ── SCENARIO 3 — Chase header ─────────────────────────────────────────────────
CHASE_RACECARD = """\
Aintree Grand National Chase 4m2f • 40 Runners • Class 1
Going: Good
""" + RUNNER_BLOCK

# ── SCENARIO 4 — No discipline keywords (classic handicap, no "Flat" stated) ──
UNKNOWN_RACECARD = """\
Newcastle Midnite: Built For 2026 Not 2006 Apprentice Handicap 6f Hcap • 8 Runners • Class 6
Going: Standard
""" + RUNNER_BLOCK

SCENARIOS = [
    ("1 — Flat (explicit)",    FLAT_RACECARD,    "Flat",    None),
    ("2 — Hurdle",             HURDLE_RACECARD,  "Jumps",   "Hurdle"),
    ("3 — Chase",              CHASE_RACECARD,   "Jumps",   "Chase"),
    ("4 — No discipline kw",   UNKNOWN_RACECARD, "Unknown", None),
]


def _run_scenario(label, racecard, expect_disc, expect_subtype):
    print(f"\n{'─'*60}")
    print(f"  SCENARIO {label}")
    print(f"{'─'*60}")

    # ── Header parse ─────────────────────────────────────────────
    header   = parse_racecard_header(racecard)
    hdr_text = _extract_header_section(racecard)
    disc     = detect_discipline(hdr_text)
    display  = _discipline_display(disc["discipline"], disc["subtype"])

    print(f"  Header fields:")
    for k, v in header.items():
        print(f"    {k:<12}: {v}")
    print(f"  Discipline   : {disc['discipline']}")
    print(f"  Subtype      : {disc['subtype']}")
    print(f"  Display label: {display}")

    # ── Assertion ────────────────────────────────────────────────
    disc_ok    = disc["discipline"] == expect_disc
    subtype_ok = disc["subtype"]    == expect_subtype
    print(f"  discipline == '{expect_disc}'  : {'PASS' if disc_ok    else 'FAIL'}")
    print(f"  subtype    == '{expect_subtype}': {'PASS' if subtype_ok else 'FAIL'}")

    # ── Runner parse ─────────────────────────────────────────────
    runners_raw = parse_racecard_text(racecard)
    parse_ok    = len(runners_raw) == 2
    print(f"  Runners parsed: {len(runners_raw)} (expected 2) — {'PASS' if parse_ok else 'FAIL'}")

    # ── Engine run ───────────────────────────────────────────────
    engine_ok = False
    try:
        going_detected = detect_going(racecard)
        going_str      = going_detected if going_detected else "good"
        dist_str       = header.get("distance") or "8f"

        race_info = RaceInfo(
            course=header.get("course") or "Unknown",
            country=detect_country(racecard),
            race_type=detect_race_type(racecard),
            surface="turf",
            distance_f=parse_distance_to_furlongs(dist_str),
            going=normalize_going(going_str),
            runners=len(runners_raw),
            discipline=disc["discipline"],
            discipline_subtype=disc["subtype"],
        )
        runner_objects = [
            Runner(
                name=r["name"],
                age=r["age"],
                weight_lbs=int(r["weight"].replace("-", "")) if "-" in r["weight"] else 120,
                form=r["form"],
                trainer=r["trainer"],
                jockey=r["jockey"],
                comment=r.get("comment", ""),
                equipment=r.get("equipment", ""),
                previous_runs=r.get("previous_runs"),
            )
            for r in runners_raw
        ]
        odds = {r["name"]: r["odds"] for r in runners_raw if r.get("odds")}
        result = engine.analyze(race_info, runner_objects, odds=odds or None)
        gold = result.get("gold_pick", {}).get("name", "N/A")
        conf = result.get("race_confidence", "?")
        disc_in_result = result.get("discipline", "—")
        print(f"  Engine gold  : {gold} ({conf})")
        print(f"  discipline in RaceInfo.discipline: {race_info.discipline}")
        engine_ok = True
    except Exception as e:
        print(f"  ENGINE ERROR : {e}")

    overall = "PASS" if (disc_ok and subtype_ok and parse_ok and engine_ok) else "FAIL"
    print(f"  Overall      : {overall}")
    return overall


def main():
    print(f"\n{'='*60}")
    print(f"  PeakPace AI — Header Parsing + Discipline Detection Tests")
    print(f"{'='*60}")

    results = []
    for label, racecard, expect_disc, expect_subtype in SCENARIOS:
        outcome = _run_scenario(label, racecard, expect_disc, expect_subtype)
        results.append(outcome)

    print(f"\n{'─'*60}")
    print(f"  Summary: {results.count('PASS')}/{len(results)} scenarios passed")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
