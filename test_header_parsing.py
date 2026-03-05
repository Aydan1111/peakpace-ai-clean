"""
Header parsing + discipline detection — 5-scenario validation.

Scenarios:
  1. TYPE: Flat override                → discipline=Flat      (level 1)
  2. TYPE: Hurdle override              → discipline=Jumps, Hurdle (level 1)
  3. Chase keyword (no TYPE: field)     → discipline=Jumps, Chase  (level 2)
  4. Flat race, no keywords, 6f dist    → discipline=Flat     (level 3 fallback)
  5. Header missing entirely            → discipline=Unknown, engine still runs
"""

import sys
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
from racing_ai_core import RacingAICore, RaceInfo, Runner

engine = RacingAICore()
engine.dark_horse_enabled = False

# ── Minimal 2-runner block shared by all scenarios ───────────────────────────
RUNNERS = """
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

# ── Five racecards ────────────────────────────────────────────────────────────

# 1. TYPE: Flat override — should beat any distance heuristic
RACECARD_1 = """\
COURSE: Newcastle
DISTANCE: 6f
RUNNERS: 8
CLASS: Class 6
TYPE: Flat
Going: Standard
""" + RUNNERS

# 2. TYPE: Hurdle override
RACECARD_2 = """\
COURSE: Cheltenham
DISTANCE: 2m
RUNNERS: 12
CLASS: Class 1
TYPE: Hurdle
Going: Good to Soft
""" + RUNNERS

# 3. Chase keyword — no TYPE: field, keyword detection fires
RACECARD_3 = """\
Aintree Grand National Chase 4m2f • 40 Runners • Class 1
Going: Good
""" + RUNNERS

# 4. Flat race — no TYPE:, no keywords, 6f distance → fallback → Flat
RACECARD_4 = """\
Newcastle Midnite: Built For 2026 Apprentice Handicap 6f Hcap • 8 Runners • Class 6
Going: Standard
""" + RUNNERS

# 5. Header missing entirely — only runner block, no header at all
RACECARD_5 = RUNNERS.strip()

SCENARIOS = [
    # (label, racecard, expect_disc, expect_subtype, expect_level)
    ("1 — TYPE: Flat override",      RACECARD_1, "Flat",    None,     "level 1"),
    ("2 — TYPE: Hurdle override",    RACECARD_2, "Jumps",   "Hurdle", "level 1"),
    ("3 — Chase keyword",            RACECARD_3, "Jumps",   "Chase",  "level 2"),
    ("4 — Distance fallback (6f)",   RACECARD_4, "Flat",    None,     "level 3"),
    ("5 — No header at all",         RACECARD_5, "Unknown", None,     "n/a"),
]


def _run(label, racecard, expect_disc, expect_subtype, expect_level):
    print(f"\n{'─'*62}")
    print(f"  SCENARIO {label}")
    print(f"{'─'*62}")

    header_info = parse_racecard_header(racecard)
    hdr_text    = _extract_header_section(racecard)
    disc        = detect_discipline(hdr_text)
    display     = _discipline_display(disc["discipline"], disc["subtype"])

    print(f"  Header: course={header_info['course']!r}  "
          f"distance={header_info['distance']!r}  "
          f"class={header_info['race_class']!r}  "
          f"race_type={header_info['race_type']!r}")
    print(f"  Detected : discipline={disc['discipline']!r}  "
          f"subtype={disc['subtype']!r}")
    print(f"  Display  : {display}")
    print(f"  Level    : {expect_level}")

    disc_ok    = disc["discipline"] == expect_disc
    subtype_ok = disc["subtype"]    == expect_subtype
    print(f"  discipline == {expect_disc!r}  : {'PASS' if disc_ok    else 'FAIL'}")
    print(f"  subtype    == {expect_subtype!r}: {'PASS' if subtype_ok else 'FAIL'}")

    # Runner parse
    runners_raw = parse_racecard_text(racecard)
    parse_ok    = len(runners_raw) == 2
    print(f"  Runners parsed : {len(runners_raw)} (expected 2) — {'PASS' if parse_ok else 'FAIL'}")

    # Engine run
    engine_ok = False
    try:
        going_raw    = detect_going(racecard)
        going_str    = going_raw if going_raw else "good"
        dist_str     = header_info.get("distance") or "8f"
        course_str   = header_info.get("course")   or "Unknown"

        race_info = RaceInfo(
            course=course_str,
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
                weight_lbs=parse_distance_to_furlongs(r["weight"].replace("-", "f")) * 0 + (
                    int(r["weight"].split("-")[0]) * 14 + int(r["weight"].split("-")[1])
                    if "-" in r["weight"] else 120
                ),
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
        print(f"  Engine gold    : {gold} ({conf})")
        print(f"  RaceInfo.discipline stored : {race_info.discipline!r}")
        engine_ok = True
    except Exception as e:
        print(f"  ENGINE ERROR   : {e}")

    overall = "PASS" if (disc_ok and subtype_ok and parse_ok and engine_ok) else "FAIL"
    print(f"  Overall        : {overall}")
    return overall


def main():
    print(f"\n{'='*62}")
    print(f"  PeakPace AI — 3-Level Discipline Detection Tests")
    print(f"{'='*62}")

    results = []
    for args in SCENARIOS:
        results.append(_run(*args))

    passed = results.count("PASS")
    print(f"\n{'─'*62}")
    print(f"  Summary : {passed}/{len(results)} scenarios passed")
    if passed == len(results):
        print(f"  All tests PASS")
    else:
        failed = [SCENARIOS[i][0] for i, r in enumerate(results) if r != "PASS"]
        print(f"  FAILED  : {failed}")
    print(f"{'─'*62}\n")


if __name__ == "__main__":
    main()
