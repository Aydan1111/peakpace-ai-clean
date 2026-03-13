"""
test_guided_entry.py
====================
Tests for:
1. GOING / GROUND: header parsing
2. TYPE: Jumps parsing → discipline = Jumps
3. Blank guided fields — runner kept when only HORSE: is present
4. Existing freeform paste mode still works
5. Wet jumps outsider promotion (strong wet/stamina evidence)
6. Flat / dry-ground regression (no regression from wet-jumps logic)

Run:  python test_guided_entry.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from main import (
    parse_racecard_header,
    parse_racecard_text,
    detect_discipline,
    _extract_header_section,
)
from racing_ai_core import RacingAICore, RaceInfo, Runner

PASS = "✓ PASS"
FAIL = "✗ FAIL"
results = []


def check(label, cond, detail=""):
    status = PASS if cond else FAIL
    print(f"  {status}  {label}" + (f"  [{detail}]" if detail else ""))
    results.append((label, cond))
    return cond


def section(title):
    print(f"\n{'='*68}")
    print(f"  {title}")
    print(f"{'='*68}")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  GOING / GROUND: parsing
# ─────────────────────────────────────────────────────────────────────────────
section("1 — GOING / GROUND: header parsing")

text_going = """\
COURSE: Cheltenham
RACE: Sky Bet Supreme Novices' Hurdle
TYPE: Jumps
DISTANCE: 2m
RUNNERS: 6
CLASS: Class 1
GOING / GROUND: Good to Soft
GROUND: Wet

HORSE: Test Horse A
JOCKEY: Nico De Boinville
TRAINER: Nicky Henderson
FORM: 111
AGE: 6
WEIGHT: 11-7
ODDS: 2/1

HORSE: Test Horse B
JOCKEY: Harry Skelton
TRAINER: Dan Skelton
FORM: 212
AGE: 5
WEIGHT: 11-7
ODDS: 4/1
"""

hdr = parse_racecard_header(text_going)
check("going stored from GOING / GROUND:",
      hdr.get("going") == "Good to Soft",
      f"got going={hdr.get('going')!r}")
check("ground_bucket=Wet from explicit GROUND: Wet (takes priority)",
      hdr.get("ground_bucket") == "Wet",
      f"got ground_bucket={hdr.get('ground_bucket')!r}")

# Without explicit GROUND: Wet line — should derive from going string
text_going_only = """\
COURSE: Cheltenham
TYPE: Jumps
DISTANCE: 2m
GOING / GROUND: Soft

HORSE: Test Horse A
JOCKEY: Harry Skelton
TRAINER: Dan Skelton
FORM: 111
AGE: 5
WEIGHT: 11-7
ODDS: 2/1

HORSE: Test Horse B
JOCKEY: Sean Bowen
TRAINER: Olly Murphy
FORM: 212
AGE: 6
WEIGHT: 11-7
ODDS: 4/1
"""

hdr2 = parse_racecard_header(text_going_only)
check("going stored when only GOING / GROUND: present",
      hdr2.get("going") == "Soft",
      f"got going={hdr2.get('going')!r}")
check("ground_bucket derived from going=Soft → Wet",
      hdr2.get("ground_bucket") == "Wet",
      f"got ground_bucket={hdr2.get('ground_bucket')!r}")

# ─────────────────────────────────────────────────────────────────────────────
# 2.  TYPE: Jumps → discipline = Jumps
# ─────────────────────────────────────────────────────────────────────────────
section("2 — TYPE: Jumps discipline detection")

disc = detect_discipline("TYPE: Jumps\nDISTANCE: 2m\nCOURSE: Cheltenham\n")
check("TYPE: Jumps → discipline=Jumps",
      disc["discipline"] == "Jumps",
      f"got {disc['discipline']!r}")

disc2 = detect_discipline("TYPE: Flat\nDISTANCE: 6f\nCOURSE: Newmarket\n")
check("TYPE: Flat → discipline=Flat",
      disc2["discipline"] == "Flat",
      f"got {disc2['discipline']!r}")

disc3 = detect_discipline("TYPE: Chase\nDISTANCE: 3m\n")
check("TYPE: Chase → discipline=Jumps, subtype=Chase",
      disc3["discipline"] == "Jumps" and disc3.get("subtype") == "Chase",
      f"got discipline={disc3['discipline']!r} subtype={disc3.get('subtype')!r}")

disc4 = detect_discipline("TYPE: National Hunt\nDISTANCE: 2m4f\n")
check("TYPE: National Hunt → discipline=Jumps",
      disc4["discipline"] == "Jumps",
      f"got {disc4['discipline']!r}")

# ─────────────────────────────────────────────────────────────────────────────
# 3.  Blank guided fields — runner kept when HORSE: present, all else blank
# ─────────────────────────────────────────────────────────────────────────────
section("3 — Blank guided fields: runner kept if only HORSE: present")

blank_guided = """\
COURSE: Cheltenham
TYPE: Jumps
DISTANCE: 2m
GOING / GROUND: Good to Soft

HORSE: Karamoja
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:

HORSE: Solo Performer
JOCKEY: Harry Skelton
TRAINER: Dan Skelton
FORM: 112
AGE: 6
WEIGHT: 11-7
ODDS: 3/1

HORSE: Empty Fields
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
ODDS:
"""

runners = parse_racecard_text(blank_guided)
names = [r["name"] for r in runners]
check("HORSE: Karamoja kept despite all blank fields",
      "Karamoja" in names, f"names={names}")
check("HORSE: Solo Performer kept (has data)",
      "Solo Performer" in names, f"names={names}")
check("HORSE: Empty Fields kept despite all blank fields",
      "Empty Fields" in names, f"names={names}")
check("3 runners total from guided template",
      len(runners) == 3, f"got {len(runners)}")
# Blank fields should have safe defaults
k = next(r for r in runners if r["name"] == "Karamoja")
check("Karamoja has default age",        isinstance(k["age"], int))
check("Karamoja has default weight",     isinstance(k["weight"], str))
check("Karamoja form is empty string",   k["form"] == "")
check("Karamoja trainer is empty string",k["trainer"] == "")

# ─────────────────────────────────────────────────────────────────────────────
# 4.  Freeform paste mode still works
# ─────────────────────────────────────────────────────────────────────────────
section("4 — Freeform paste mode regression")

freeform = """\
Cheltenham 2m Chase Good to Soft  8 Runners  Class 1

Jonbon JOCKEY: Nico de Boinville TRAINER: Nicky Henderson FORM: 1211 AGE: 9 WEIGHT: 11-7 ODDS: 2/1
Galopin Des Champs JOCKEY: Paul Townend TRAINER: W.P. Mullins FORM: 1111 AGE: 8 WEIGHT: 11-10 ODDS: 7/4
El Fabiolo JOCKEY: P. Townend TRAINER: W.P. Mullins FORM: 3121 AGE: 7 WEIGHT: 11-7 ODDS: 5/1
"""

runners_ff = parse_racecard_text(freeform)
names_ff = [r["name"] for r in runners_ff]
check("Freeform: Jonbon parsed",               "Jonbon" in names_ff, f"names={names_ff}")
check("Freeform: Galopin Des Champs parsed",   "Galopin Des Champs" in names_ff)
check("Freeform: Jonbon trainer correct",
      next((r["trainer"] for r in runners_ff if r["name"] == "Jonbon"), "") == "Nicky Henderson")
check("Freeform: Jonbon form correct",
      next((r["form"] for r in runners_ff if r["name"] == "Jonbon"), "") == "1211")

# ─────────────────────────────────────────────────────────────────────────────
# 5.  Wet jumps outsider promotion
# ─────────────────────────────────────────────────────────────────────────────
section("5 — Wet jumps: outsider promoted when evidence is strong")

engine = RacingAICore()
engine.dark_horse_enabled = True

WET_CHASE = RaceInfo(
    course="Cheltenham", country="uk", race_type="national_hunt", surface="turf",
    distance_f=24.0, going="heavy", runners=8,
    discipline="Jumps", discipline_subtype="Chase", ground_bucket="Wet",
)

# Market favourite: strong connections, decent form, NO wet evidence
fav = Runner(
    name="Market Fav", age=8, weight_lbs=160, form="1121",
    trainer="Dan Skelton", jockey="Harry Skelton",
    draw=0, jockey_claim_lbs=0, equipment="",
    comment="Handy sort. No previous runs on soft or heavy ground.",
    previous_runs=[
        {"going": "good", "distance_f": 24.0, "pos": 1, "field_size": 8, "discipline": "Chase"},
        {"going": "good to firm", "distance_f": 20.0, "pos": 2, "field_size": 9, "discipline": "Chase"},
        {"going": "good", "distance_f": 24.0, "pos": 1, "field_size": 7, "discipline": "Chase"},
    ],
)

# Outsider: strong wet-ground evidence, proven at the trip on soft, stays on
wet_specialist = Runner(
    name="Wet Specialist", age=9, weight_lbs=158, form="1121",
    trainer="Gordon Elliott", jockey="Jack Kennedy",
    draw=0, jockey_claim_lbs=0, equipment="",
    comment="Jumped well throughout. Stayed on dourly to win on heavy going. Genuine stayer.",
    previous_runs=[
        {"going": "heavy",   "distance_f": 24.0, "pos": 1, "field_size": 9, "discipline": "Chase"},
        {"going": "soft",    "distance_f": 24.0, "pos": 1, "field_size": 8, "discipline": "Chase"},
        {"going": "soft",    "distance_f": 20.0, "pos": 2, "field_size": 10, "discipline": "Chase"},
        {"going": "soft",    "distance_f": 24.0, "pos": 1, "field_size": 7, "discipline": "Chase"},
    ],
)

# Filler horses
fillers_wet = [
    Runner(f"Filler {i}", age=7, weight_lbs=155, form="345",
           trainer="Nicky Henderson", jockey="Nico de Boinville",
           draw=0, jockey_claim_lbs=0, equipment="", comment="",
           previous_runs=[])
    for i in range(1, 7)
]

all_wet_runners = [fav, wet_specialist] + fillers_wet
odds_wet = {
    "Market Fav":     "2/1",
    "Wet Specialist": "10/1",
    **{f"Filler {i}": f"{10+i*3}/1" for i in range(1, 7)},
}

result_wet = engine.analyze(WET_CHASE, all_wet_runners, odds=odds_wet)
ranked_wet = result_wet["full_rankings"]

fav_rank = next((i+1 for i, h in enumerate(ranked_wet) if h["name"] == "Market Fav"), 99)
spec_rank = next((i+1 for i, h in enumerate(ranked_wet) if h["name"] == "Wet Specialist"), 99)

print(f"\n  Wet Chase ranking:")
for i, h in enumerate(ranked_wet, 1):
    print(f"    #{i:2d}  {h['name']:<20s}  score={h['score']:.4f}")

check("wet_jumps_mode=True confirmed", result_wet.get("wet_jumps_mode") is True,
      f"wet_jumps_mode={result_wet.get('wet_jumps_mode')}")
check("Wet Specialist ranks in top 3 despite 10/1 price",
      spec_rank <= 3,
      f"Wet Specialist rank={spec_rank}, Market Fav rank={fav_rank}")

# ─────────────────────────────────────────────────────────────────────────────
# 6.  Flat / dry-ground regression
# ─────────────────────────────────────────────────────────────────────────────
section("6 — Flat / dry regression: wet-jumps logic must NOT activate")

FLAT_RACE = RaceInfo(
    course="Newmarket", country="uk", race_type="flat", surface="turf",
    distance_f=8.0, going="good to firm", runners=8,
    discipline="Flat", discipline_subtype=None, ground_bucket="Dry",
)

flat_fav = Runner(
    name="Flat Fav", age=4, weight_lbs=130, form="112",
    trainer="Charlie Appleby", jockey="William Buick",
    draw=1, jockey_claim_lbs=0, equipment="", comment="",
    previous_runs=[
        {"going": "good",     "distance_f": 8.0, "pos": 1, "field_size": 8},
        {"going": "good",     "distance_f": 8.0, "pos": 1, "field_size": 9},
        {"going": "firm",     "distance_f": 7.0, "pos": 2, "field_size": 10},
    ],
)

flat_wet_horse = Runner(
    name="Flat Wet Horse", age=5, weight_lbs=128, form="321",
    trainer="Roger Varian", jockey="Andrea Atzeni",
    draw=2, jockey_claim_lbs=0, equipment="",
    comment="Stayed on dourly. Strong in soft ground. Genuine stayer.",
    previous_runs=[
        {"going": "heavy",   "distance_f": 10.0, "pos": 1, "field_size": 8},
        {"going": "soft",    "distance_f": 8.0,  "pos": 1, "field_size": 9},
        {"going": "soft",    "distance_f": 8.0,  "pos": 1, "field_size": 7},
    ],
)

flat_fillers = [
    Runner(f"Flat Filler {i}", age=4, weight_lbs=126, form="456",
           trainer="Mark Johnston", jockey="Joe Fanning",
           draw=i+2, jockey_claim_lbs=0, equipment="", comment="",
           previous_runs=[])
    for i in range(1, 7)
]

all_flat_runners = [flat_fav, flat_wet_horse] + flat_fillers
odds_flat = {
    "Flat Fav":       "2/1",
    "Flat Wet Horse": "8/1",
    **{f"Flat Filler {i}": f"{10+i*3}/1" for i in range(1, 7)},
}

result_flat = engine.analyze(FLAT_RACE, all_flat_runners, odds=odds_flat)
check("wet_jumps_mode=False on flat/dry race",
      result_flat.get("wet_jumps_mode") is False,
      f"wet_jumps_mode={result_flat.get('wet_jumps_mode')}")

ranked_flat = result_flat["full_rankings"]
fav_flat_rank = next((i+1 for i, h in enumerate(ranked_flat) if h["name"] == "Flat Fav"), 99)
wet_flat_rank = next((i+1 for i, h in enumerate(ranked_flat) if h["name"] == "Flat Wet Horse"), 99)
check("Flat Fav still beats Flat Wet Horse on good/firm (no wet boost)",
      fav_flat_rank <= wet_flat_rank,
      f"Flat Fav rank={fav_flat_rank}, Flat Wet Horse rank={wet_flat_rank}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n\n{'='*68}")
print("  SUMMARY")
print(f"{'='*68}")
total  = len(results)
passed = sum(1 for _, ok in results if ok)
for label, ok in results:
    print(f"  {'✓' if ok else '✗'}  {label}")
print(f"\n  {passed}/{total} checks passed")
print()

if passed < total:
    sys.exit(1)
