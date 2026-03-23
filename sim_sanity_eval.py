"""
sim_sanity_eval.py
==================
Sanity simulation: 6 Flat + 6 Jumps races covering diverse scenarios.
Evaluation only — no code modifications.
"""

import sys
sys.path.insert(0, '/home/user/peakpace-ai-clean')

from racing_ai_core import RacingAICore, RaceInfo, Runner, classify_wet_dry

engine = RacingAICore()
engine.dark_horse_enabled = True   # enable dark horse picks for all races


def print_race(label, race, runners, odds=None):
    result = engine.analyze(race, runners, odds=odds)

    gold   = result["gold_pick"]
    silver = result["silver_pick"]
    dark   = result["dark_horse"]
    ranked = result["full_rankings"]
    conf   = result["race_confidence"]
    wet    = result["wet_jumps_mode"]
    jf     = result["jumps_check_filter"]
    disc   = "jumps" if result["is_jumps"] else "flat"

    # score gap 1st-2nd
    gap = round(ranked[0]["score"] - ranked[1]["score"], 3) if len(ranked) >= 2 else "N/A"

    print(f"\n{'='*60}")
    print(f"=== RACE {label} ===")
    print(f"Discipline: {disc}")
    print(f"Wet Jumps:  {'yes' if wet else 'no'}")
    print(f"Race Confidence: {conf}")
    jf_display = jf if result["is_jumps"] else "N/A"
    print(f"Jumps Filter: {jf_display}")
    print()

    def fmt_pick(p):
        if p is None:
            return "N/A"
        return f"{p['name']} conf={p['confidence']}"

    print(f"Gold:   {fmt_pick(gold)}")
    print(f"Silver: {fmt_pick(silver)}")
    print(f"Dark:   {fmt_pick(dark)}")
    print()
    print("Full ranking top 5:")
    for i, h in enumerate(ranked[:5], 1):
        marker = ""
        if gold   and h["name"] == gold["name"]:   marker = " [Gold]"
        elif silver and h["name"] == silver["name"]: marker = " [Silver]"
        elif dark  and h["name"] == dark["name"]:   marker = " [Dark]"
        print(f"  {i}. {h['name']} score={h['score']:.3f}{marker}")
    print(f"Score gap 1st-2nd: {gap}")


# ============================================================
# F1: Clear favourite — 8 runner handicap, Newmarket 1m, Good
# ============================================================
race_f1 = RaceInfo(
    course="Newmarket", country="UK", race_type="flat",
    surface="turf", distance_f=8, going="good",
    runners=8, discipline="Flat", ground_bucket="Dry"
)
runners_f1 = [
    Runner("Kinross", 6, 134, "1121111", "Roger Varian",   "Oisin Murphy",  draw=4),
    Runner("Mutasaabeq", 5, 130, "21131",  "Charlie Appleby","William Buick", draw=7),
    Runner("Starman", 4, 128, "4321",   "Clive Cox",      "Adam Kirby",    draw=1),
    Runner("Scope", 4, 126, "35524",   "Ralph Beckett",  "Hollie Doyle",  draw=3),
    Runner("Alcazan", 5, 124, "55423",  "William Haggas", "Tom Marquand",  draw=6),
    Runner("Oscula", 5, 122, "66351",  "Andrew Balding", "David Probert", draw=2),
    Runner("Regal Reality", 6, 120, "77256", "Sir Michael Stoute", "Ryan Moore", draw=5),
    Runner("Dubawi Gold", 4, 118, "88673",  "Saeed Bin Suroor","James Doyle", draw=8),
]
print_race("F1: Clear favourite — Newmarket 1m handicap", race_f1, runners_f1)

# ============================================================
# F2: Competitive sprint — 12 runner 5f, Ascot, Good to Firm
# ============================================================
race_f2 = RaceInfo(
    course="Ascot", country="UK", race_type="flat",
    surface="turf", distance_f=5, going="good to firm",
    runners=12, discipline="Flat", ground_bucket="Dry"
)
runners_f2 = [
    Runner("Bradsell",       4, 132, "112231", "Archie Watson",  "Rossa Ryan",    draw=1),
    Runner("Gale Force Maya",5, 130, "324112", "Clive Cox",      "Adam Kirby",    draw=5),
    Runner("Existent",       5, 128, "213543", "Roger Varian",   "Oisin Murphy",  draw=9),
    Runner("Perfect Power",  4, 126, "341215", "Richard Fahey",  "Paul Hanagan",  draw=12),
    Runner("Twilight Jet",   5, 124, "552436", "Tim Easterby",   "David Allan",   draw=3),
    Runner("Marshman",       6, 122, "423657", "Charlie Hills",  "Frankie Dettori",draw=7),
    Runner("Justanotherbottle",5,120,"675345", "Bryan Smart",    "Tony Hamilton", draw=2),
    Runner("Supremacy",      4, 118, "7565",   "Hugo Palmer",    "Hollie Doyle",  draw=11),
    Runner("Lethal Levi",    4, 116, "876456", "Julie Camacho",  "Tom Eaves",     draw=6),
    Runner("Art Power",      6, 114, "587865", "Tim Easterby",   "Connor Beasley",draw=4),
    Runner("Rohaan",         5, 112, "658976", "Ryan Sheather",  "David Probert", draw=10),
    Runner("Overtrump",      4, 110, "776887", "Gay Kelleway",   "Luke Morris",   draw=8),
]
print_race("F2: Competitive 12-runner sprint — Ascot 5f Good to Firm", race_f2, runners_f2)

# ============================================================
# F3: Small field conditions race — 5 runners, Chester 1m2f, Soft
# ============================================================
race_f3 = RaceInfo(
    course="Chester", country="UK", race_type="flat",
    surface="turf", distance_f=10, going="soft",
    runners=5, discipline="Flat", ground_bucket="Wet"
)
runners_f3 = [
    Runner("Arrest",         4, 134, "11121",  "John Gosden",    "Frankie Dettori", draw=2,
           comment="progressive, handled cut in ground last time"),
    Runner("Hukum",          6, 132, "11212",  "Owen Burrows",   "Jim Crowley",     draw=4,
           comment="won well on soft last season"),
    Runner("Al Qareem",      5, 128, "32231",  "Roger Varian",   "Oisin Murphy",    draw=1),
    Runner("Bedtime Story",  4, 126, "44352",  "William Haggas", "Tom Marquand",    draw=3),
    Runner("Quickthorn",     5, 124, "35443",  "Hughie Morrison","Rossa Ryan",      draw=5),
]
print_race("F3: Small field conditions — Chester 1m2f Soft", race_f3, runners_f3)

# ============================================================
# F4: Low data coverage — 6 runners, York 7f, Good
# ============================================================
race_f4 = RaceInfo(
    course="York", country="UK", race_type="flat",
    surface="turf", distance_f=7, going="good",
    runners=6, discipline="Flat", ground_bucket="Dry"
)
runners_f4 = [
    Runner("Silver Lining",  3, 124, "1",     "X. Unknown",      "A. Rider",    draw=3),
    Runner("Northern Dancer",4, 122, "3",     "Y. Trainer",      "B. Jockey",   draw=1),
    Runner("Morning Glory",  4, 120, "2",     "Z. Stable",       "C. Smith",    draw=5),
    Runner("Fleetwood Mac",  5, 118, "44",    "P. Anonymous",    "D. Jones",    draw=2),
    Runner("Swift Arrow",    4, 116, "31",    "Q. Obscure",      "E. Williams", draw=6),
    Runner("Quiet Storm",    5, 114, "52",    "R. Trainer",      "F. Brown",    draw=4),
]
print_race("F4: Low data coverage — York 7f Good (sparse names)", race_f4, runners_f4)

# ============================================================
# F5: Market vs model divergence — 10 runners, Haydock 1m, Good
# The model favourite (Shadwell Estate) has drifted in market
# ============================================================
race_f5 = RaceInfo(
    course="Haydock", country="UK", race_type="flat",
    surface="turf", distance_f=8, going="good",
    runners=10, discipline="Flat", ground_bucket="Dry"
)
runners_f5 = [
    Runner("Nashwa",         4, 132, "11121",  "John Gosden",    "Frankie Dettori",draw=5,
           comment="well handicapped, improving"),
    Runner("Shadwell Estate",5, 130, "21312",  "William Haggas", "Tom Marquand",   draw=3,
           comment="strong form, well treated in weights"),
    Runner("Bayside Boy",    4, 128, "32243",  "Roger Varian",   "Oisin Murphy",   draw=8),
    Runner("Inspiral",       4, 126, "12321",  "John Gosden",    "Frankie Dettori",draw=1),
    Runner("Kinross",        6, 124, "43512",  "Roger Varian",   "Hollie Doyle",   draw=6),
    Runner("Pearling",       5, 122, "554423", "Sir Mark Prescott","Luke Morris",  draw=9),
    Runner("Aidan",          4, 120, "665534", "Ed Dunlop",      "Jack Mitchell",  draw=2),
    Runner("Morning Mist",   5, 118, "376645", "Hugo Palmer",    "Kieran Shoemark",draw=7),
    Runner("Bold Move",      4, 116, "787556", "James Fanshawe", "Ray Dawson",     draw=4),
    Runner("Distant Star",   5, 114, "898677", "David Elsworth", "Callum Shepherd",draw=10),
]
# Market has Nashwa drifting to 8/1 but model should still rate her highly
odds_f5 = {
    "Inspiral":       "7/4",
    "Bayside Boy":    "5/2",
    "Shadwell Estate":"7/1",
    "Nashwa":         "8/1",   # drifted — model vs market divergence
    "Kinross":        "10/1",
    "Pearling":       "14/1",
    "Aidan":          "16/1",
    "Morning Mist":   "20/1",
    "Bold Move":      "25/1",
    "Distant Star":   "33/1",
}
print_race("F5: Market vs model divergence — Haydock 1m Good", race_f5, runners_f5, odds=odds_f5)

# ============================================================
# F6: 3yo conditions race — 6 runners, Haydock 1m2f, Good to Soft
# ============================================================
race_f6 = RaceInfo(
    course="Haydock", country="UK", race_type="flat",
    surface="turf", distance_f=10, going="good to soft",
    runners=6, discipline="Flat", ground_bucket="Dry"
)
runners_f6 = [
    Runner("Auguste Rodin",  3, 132, "111",   "A.P. O'Brien",   "Ryan Moore",   draw=4,
           comment="progressive and still improving"),
    Runner("Continuous",     3, 130, "112",   "A.P. O'Brien",   "Seamie Heffernan", draw=2),
    Runner("Iraq",           3, 128, "121",   "Aidan O'Brien",  "Wayne Lordan",  draw=6),
    Runner("Epictetus",      3, 126, "213",   "Charlie Appleby","William Buick", draw=1),
    Runner("Al Riffa",       3, 124, "231",   "William Haggas", "Tom Marquand",  draw=5),
    Runner("Docklands",      3, 122, "324",   "Roger Varian",   "Oisin Murphy",  draw=3),
]
print_race("F6: 3yo conditions — Haydock 1m2f Good to Soft", race_f6, runners_f6)

# ============================================================
# J1: Good ground novice hurdle — 8 runners, Cheltenham 2m, Good
# ============================================================
race_j1 = RaceInfo(
    course="Cheltenham", country="UK", race_type="novice hurdle",
    surface="turf", distance_f=16, going="good",
    runners=8, discipline="Jumps", discipline_subtype="Hurdle",
    ground_bucket="Dry"
)
runners_j1 = [
    Runner("Constitution Hill", 6, 152, "111",  "Nicky Henderson","Nico de Boinville",
           comment="jumped well, looks a champion in the making"),
    Runner("Jonbon",         6, 148, "121",  "Nicky Henderson","Aidan Coleman",
           comment="fluent jumping, shaped with promise"),
    Runner("Dysart Dynamo",  5, 144, "2121", "Willie Mullins",  "Paul Townend"),
    Runner("Facile Vega",    5, 142, "132",  "Willie Mullins",  "Patrick Mullins"),
    Runner("Marine Nationale",6, 140, "213", "Gavin Cromwell",  "Keith Donoghue"),
    Runner("Monkfish",       5, 138, "2231", "Willie Mullins",  "Danny Mullins"),
    Runner("Ferny Hollow",   6, 136, "3321", "Willie Mullins",  "Patrick Mullins"),
    Runner("Gaillard Du Mesnil",6,134,"3432","Willie Mullins",  "Mark Walsh"),
],
print_race("J1: Novice hurdle — Cheltenham 2m Good (clear form horse)", race_j1, runners_j1[0])

# ============================================================
# J2: Wet ground chase — 7 runners, Leopardstown 2m4f, Soft
# ============================================================
race_j2 = RaceInfo(
    course="Leopardstown", country="Ireland", race_type="chase",
    surface="turf", distance_f=20, going="soft",
    runners=7, discipline="Jumps", discipline_subtype="Chase",
    ground_bucket="Wet"
)
runners_j2 = [
    Runner("Galopin Des Champs", 7, 168, "1111",  "Willie Mullins", "Paul Townend",
           comment="stayed on well, proven in testing ground",
           previous_runs=[
               {"going":"soft","distance_f":20,"pos":1,"field_size":8,"discipline":"chase"},
               {"going":"soft","distance_f":20,"pos":1,"field_size":7,"discipline":"chase"},
               {"going":"good","distance_f":20,"pos":1,"field_size":9,"discipline":"chase"},
           ]),
    Runner("Conflated",     7, 160, "1213",  "Gordon Elliott",  "Jack Kennedy",
           comment="jumped well under pressure",
           previous_runs=[
               {"going":"soft","distance_f":20,"pos":2,"field_size":8,"discipline":"chase"},
               {"going":"heavy","distance_f":20,"pos":1,"field_size":6,"discipline":"chase"},
           ]),
    Runner("Energumene",    8, 158, "1121",  "Willie Mullins",  "Paul Townend",
           comment="excellent jumper, handles most ground",
           previous_runs=[
               {"going":"good","distance_f":16,"pos":1,"field_size":8,"discipline":"chase"},
               {"going":"good to soft","distance_f":20,"pos":2,"field_size":7,"discipline":"chase"},
           ]),
    Runner("El Fabiolo",    6, 156, "1112",  "Willie Mullins",  "Patrick Mullins",
           comment="neat at hurdles, course form good",
           previous_runs=[
               {"going":"good","distance_f":16,"pos":1,"field_size":9,"discipline":"hurdle"},
               {"going":"soft","distance_f":20,"pos":3,"field_size":7,"discipline":"chase"},
           ]),
    Runner("Allaho",        8, 154, "1121",  "Willie Mullins",  "Rachael Blackmore",
           previous_runs=[
               {"going":"good","distance_f":20,"pos":1,"field_size":7,"discipline":"chase"},
               {"going":"soft","distance_f":20,"pos":5,"field_size":8,"discipline":"chase"},
           ]),
    Runner("Minella Indo",  9, 150, "2312",  "Henry De Bromhead","Rachael Blackmore",
           comment="keeps finding under pressure, genuine stayer",
           previous_runs=[
               {"going":"soft","distance_f":24,"pos":1,"field_size":10,"discipline":"chase"},
               {"going":"heavy","distance_f":24,"pos":2,"field_size":8,"discipline":"chase"},
           ]),
    Runner("A Plus Tard",   9, 148, "1223",  "Henry De Bromhead","Rachael Blackmore",
           previous_runs=[
               {"going":"good","distance_f":20,"pos":1,"field_size":8,"discipline":"chase"},
               {"going":"soft","distance_f":20,"pos":4,"field_size":9,"discipline":"chase"},
           ]),
]
print_race("J2: Wet chase — Leopardstown 2m4f Soft", race_j2, runners_j2)

# ============================================================
# J3: Tight competitive handicap hurdle — 10 runners, Sandown 2m4f, Good to Soft
# ============================================================
race_j3 = RaceInfo(
    course="Sandown", country="UK", race_type="handicap hurdle",
    surface="turf", distance_f=20, going="good to soft",
    runners=10, discipline="Jumps", discipline_subtype="Hurdle",
    ground_bucket="Dry"
)
runners_j3 = [
    Runner("Triumph Hurdle Winner",5,148,"121",   "Nicky Henderson","Nico de Boinville"),
    Runner("Buzz",                6,146,"213",   "Nicky Henderson","Barry Geraghty"),
    Runner("Paisley Park",        9,144,"1122",  "Emma Lavelle",   "Aidan Coleman"),
    Runner("Champ",               8,142,"2132",  "Nicky Henderson","Nico de Boinville"),
    Runner("Thyme Hill",          7,140,"3213",  "Philip Hobbs",   "Richard Johnson"),
    Runner("Sire Du Berlais",     9,138,"2321",  "Gordon Elliott",  "Mark Walsh"),
    Runner("Winter Fog",          6,136,"3342",  "David Pipe",      "Tom Scudamore"),
    Runner("Dame De Compagnie",   7,134,"4423",  "Nicky Henderson","Barry Geraghty"),
    Runner("Stormy Ireland",      7,132,"5534",  "Willie Mullins",  "Paul Townend"),
    Runner("Flooring Porter",     7,130,"4445",  "Gavin Cromwell",  "Danny Mullins"),
]
print_race("J3: Tight competitive handicap hurdle — Sandown 2m4f Good to Soft", race_j3, runners_j3)

# ============================================================
# J4: Small field Grade 1 — 5 runners, Punchestown 3m, Good
# ============================================================
race_j4 = RaceInfo(
    course="Punchestown", country="Ireland", race_type="Grade 1 chase",
    surface="turf", distance_f=24, going="good",
    runners=5, discipline="Jumps", discipline_subtype="Chase",
    ground_bucket="Dry"
)
runners_j4 = [
    Runner("Galopin Des Champs",7, 168, "1111",  "Willie Mullins",  "Paul Townend",
           comment="jumped well on good ground, flawless jumper"),
    Runner("Shishkin",          8, 164, "1112",  "Nicky Henderson", "Nico de Boinville",
           comment="accurate at obstacles, stays well"),
    Runner("Rachael's Cottage", 7, 158, "2121",  "Henry De Bromhead","Rachael Blackmore"),
    Runner("Ginto",             6, 154, "2132",  "Gordon Elliott",   "Davy Russell"),
    Runner("Gentleman De Mee",  6, 150, "3243",  "Willie Mullins",   "Patrick Mullins"),
]
print_race("J4: Small field Grade 1 — Punchestown 3m Good", race_j4, runners_j4)

# ============================================================
# J5: Heavy ground chase — 6 runners, Haydock 2m4f, Heavy
# ============================================================
race_j5 = RaceInfo(
    course="Haydock", country="UK", race_type="chase",
    surface="turf", distance_f=20, going="heavy",
    runners=6, discipline="Jumps", discipline_subtype="Chase",
    ground_bucket="Wet"
)
runners_j5 = [
    Runner("Many Clouds",    9, 158, "1121",  "Oliver Sherwood","Leighton Aspell",
           comment="genuine stayer, handled heavy perfectly before",
           previous_runs=[
               {"going":"heavy","distance_f":20,"pos":1,"field_size":9,"discipline":"chase"},
               {"going":"soft","distance_f":20,"pos":1,"field_size":8,"discipline":"chase"},
               {"going":"heavy","distance_f":24,"pos":2,"field_size":7,"discipline":"chase"},
           ]),
    Runner("Clan Des Obeaux",9, 156, "1212",  "Paul Nicholls",  "Harry Cobden",
           comment="stays well in testing conditions",
           previous_runs=[
               {"going":"soft","distance_f":20,"pos":2,"field_size":9,"discipline":"chase"},
               {"going":"heavy","distance_f":20,"pos":3,"field_size":8,"discipline":"chase"},
           ]),
    Runner("Santini",        8, 154, "2132",  "Nicky Henderson","Nico de Boinville",
           previous_runs=[
               {"going":"good","distance_f":20,"pos":1,"field_size":9,"discipline":"chase"},
               {"going":"soft","distance_f":20,"pos":5,"field_size":8,"discipline":"chase"},
           ]),
    Runner("Native River",  12, 152, "2211",  "Colin Tizzard",  "Richard Johnson",
           comment="kept on dourly, loves testing ground",
           previous_runs=[
               {"going":"heavy","distance_f":24,"pos":1,"field_size":11,"discipline":"chase"},
               {"going":"heavy","distance_f":20,"pos":1,"field_size":8, "discipline":"chase"},
               {"going":"soft","distance_f":20, "pos":2,"field_size":9, "discipline":"chase"},
           ]),
    Runner("Tiger Roll",     11, 148, "3312",  "Gordon Elliott",  "Davy Russell",
           comment="faded in the heavy ground, uncertain stamina at this trip",
           previous_runs=[
               {"going":"good","distance_f":20,"pos":1,"field_size":12,"discipline":"chase"},
               {"going":"heavy","distance_f":24,"pos":6,"field_size":9, "discipline":"chase"},
           ]),
    Runner("Bristol De Mai",10, 150, "1121",  "Nigel Twiston-Davies","Daryl Jacob",
           comment="spectacular in the heavy at Haydock previously, jumped impeccably",
           previous_runs=[
               {"going":"heavy","distance_f":20,"pos":1,"field_size":8,"discipline":"chase"},
               {"going":"heavy","distance_f":20,"pos":1,"field_size":7,"discipline":"chase"},
               {"going":"soft","distance_f":20,"pos":2,"field_size":9,"discipline":"chase"},
           ]),
]
print_race("J5: Heavy ground chase — Haydock 2m4f Heavy (stamina test)", race_j5, runners_j5)

# ============================================================
# J6: Bumper/NH Flat — 8 runners, Leopardstown 2m, Yielding
# ============================================================
race_j6 = RaceInfo(
    course="Leopardstown", country="Ireland", race_type="bumper",
    surface="turf", distance_f=16, going="yielding",
    runners=8, discipline="Jumps", discipline_subtype="NH Flat",
    ground_bucket="Wet"
)
runners_j6 = [
    Runner("Facile Vega",       4, 150, "11",   "Willie Mullins",  "Patrick Mullins",
           comment="lightly raced, still improving"),
    Runner("American Mike",     4, 148, "121",  "Gordon Elliott",  "Davy Russell"),
    Runner("Appreciate It",     4, 146, "112",  "Willie Mullins",  "Paul Townend",
           comment="progressive, excellent attitude"),
    Runner("Kilcruit",          4, 144, "123",  "Willie Mullins",  "Danny Mullins"),
    Runner("Jeff Kidder",       5, 142, "2213", "Noel Meade",      "Sean Flanagan"),
    Runner("Riviere D'Etel",    4, 140, "231",  "Willie Mullins",  "Mark Walsh"),
    Runner("Royal Kahala",      4, 138, "342",  "Henry De Bromhead","Rachael Blackmore"),
    Runner("Walk In The Mill",  5, 136, "3432", "Robert Walford",  "James Best"),
]
print_race("J6: Bumper — Leopardstown 2m Yielding", race_j6, runners_j6)


print("\n\n" + "="*60)
print("EVALUATION COMPLETE — See individual race outputs above")
print("="*60)
