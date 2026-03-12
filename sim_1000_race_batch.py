"""
sim_1000_race_batch.py
======================
Runs 500 flat + 500 jumps races using real trainer / jockey / horse names
from the data files.  Reports selector behaviour patterns, smart picks,
and questionable picks.

Usage:  python sim_1000_race_batch.py
"""

import sys, os, re, random
from collections import Counter, defaultdict
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from racing_ai_core import RacingAICore, RaceInfo, Runner

random.seed(42)
engine = RacingAICore()
engine.dark_horse_enabled = True

# ── Load real names ────────────────────────────────────────────────────────────

def _parse_names(path):
    names = []
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r'^([^\(]+)\s*\(', line.strip())
                if m:
                    n = m.group(1).strip()
                    if n and len(n) > 2:
                        names.append(n)
    except Exception:
        pass
    return names

def _parse_horse_names(path):
    names = []
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r'^([^\(]+)\s*\(Season:', line.strip())
                if m:
                    n = m.group(1).strip()
                    if n and len(n) > 2:
                        names.append(n)
    except Exception:
        pass
    return names

FLAT_TRAINERS  = _parse_names('data/UK_Trainers_Flat_clean.txt')
JUMPS_TRAINERS = _parse_names('data/UK_Trainers_Jumps_clean.txt')
FLAT_JOCKEYS   = _parse_names('data/UK_Jockeys_Flat_clean.txt')
JUMPS_JOCKEYS  = _parse_names('data/UK_Jockeys_Jumps_clean.txt')
FLAT_HORSES    = _parse_horse_names('data/UK_Horses_Flat_2024_2025_2026_clean.txt')
JUMPS_HORSES   = _parse_horse_names('data/UK_Horses_Jumps_2024_2025_2026_clean.txt')

# Fallback filler names if we run out
FILLER_TRAINERS = ["Mark Johnston", "Roger Varian", "Andrew Balding",
                   "John & Thady Gosden", "William Haggas", "Ralph Beckett",
                   "Charlie Appleby", "Saeed bin Suroor", "Eve Johnson Houghton",
                   "Jim Boyle", "Brian Meehan", "Stuart Williams"]
FILLER_JOCKEYS  = ["Frankie Dettori", "Ryan Moore", "William Buick",
                   "Andrea Atzeni", "Tom Marquand", "Hollie Doyle",
                   "Tom Queally", "David Probert", "Kieran Shoemark",
                   "Jason Watson", "Rob Hornby", "Jim Crowley"]
FILLER_JUMPS_J  = ["Harry Skelton", "Nico de Boinville", "Harry Cobden",
                   "Jack Kennedy", "Paul Townend", "Rachael Blackmore",
                   "Sean Bowen", "Davy Russell", "Brian Hughes",
                   "Sam Twiston-Davies", "Adrian Heskin", "Nick Scholfield"]

# ── Race shape parameters ──────────────────────────────────────────────────────

FLAT_COURSES  = ["Newmarket","Ascot","Goodwood","Sandown","York","Epsom",
                 "Haydock","Leicester","Newbury","Chester","Nottingham","Lingfield"]
JUMPS_COURSES = ["Cheltenham","Ascot","Sandown","Kempton","Newbury","Exeter",
                 "Wetherby","Haydock","Huntingdon","Ayr","Aintree","Punchestown"]

FLAT_DISTS  = [5.0,6.0,7.0,8.0,10.0,12.0,14.0,16.0]
JUMPS_DISTS = [16.0,18.0,20.0,22.0,24.0,26.0,28.0,32.0]

GOINGS_FLAT  = [("firm","Good/Firm"),("good to firm","Good/Firm"),
                ("good","Good"),("good to soft","Good"),
                ("soft","Soft/Heavy"),("heavy","Soft/Heavy")]
GOINGS_JUMPS = [("good","Good"),("good to soft","Good"),
                ("soft","Soft/Heavy"),("heavy","Soft/Heavy"),
                ("good to firm","Good/Firm")]

FORM_POOL_GOOD = ["111","112","121","211","122","212","221","113","131","311"]
FORM_POOL_MID  = ["213","321","132","231","312","123","223","232","322","233",
                  "2131","1212","1121","2112","3121"]
FORM_POOL_POOR = ["345","435","456","546","657","768","567","678","789","3450",
                  "4350","5P6","67P","PUP","P67","FPU"]

ODDS_TIERS = [
    ("4/5",  1.80), ("evens", 2.00), ("6/5", 2.20), ("5/4", 2.25),
    ("11/8", 2.38), ("6/4",  2.50), ("13/8",2.63), ("7/4", 2.75),
    ("2/1",  3.00), ("9/4",  3.25), ("5/2", 3.50), ("11/4",3.75),
    ("3/1",  4.00), ("10/3", 4.33), ("7/2", 4.50), ("4/1", 5.00),
    ("9/2",  5.50), ("5/1",  6.00), ("11/2",6.50), ("6/1", 7.00),
    ("7/1",  8.00), ("8/1",  9.00), ("9/1", 10.0), ("10/1",11.0),
    ("12/1", 13.0), ("14/1",15.0), ("16/1",17.0), ("20/1",21.0),
    ("25/1", 26.0), ("33/1",34.0),
]

def _random_odds_ladder(n):
    """Generate n decreasing odds prices for a field."""
    ladders = [
        ["4/5","2/1","4/1","8/1","12/1","20/1","33/1","40/1","50/1"],
        ["evens","5/2","5/1","8/1","14/1","20/1","25/1","40/1","66/1"],
        ["5/4","3/1","6/1","10/1","16/1","25/1","33/1","50/1","66/1"],
        ["2/1","3/1","5/1","8/1","12/1","20/1","33/1","50/1","100/1"],
        ["5/2","4/1","7/1","10/1","14/1","25/1","40/1","66/1","100/1"],
        ["3/1","9/2","8/1","12/1","20/1","33/1","50/1","66/1","100/1"],
        ["4/1","6/1","9/1","14/1","20/1","33/1","50/1","66/1","100/1"],
    ]
    base = random.choice(ladders)
    # Extend if field > 9
    extras = ["66/1","100/1","125/1","150/1","200/1"]
    while len(base) < n:
        base.append(random.choice(extras))
    return base[:n]

def _make_runner(name, trainer, jockey, form, age, weight_lbs, draw, is_nh):
    return Runner(
        name=name, age=age, weight_lbs=weight_lbs,
        form=form, trainer=trainer, jockey=jockey,
        draw=draw, jockey_claim_lbs=0, comment="", equipment="",
        previous_runs=[]
    )

def _build_race(race_type, race_idx):
    """Return (RaceInfo, List[Runner], odds_dict)."""
    is_nh = (race_type == "jumps")

    course  = random.choice(JUMPS_COURSES if is_nh else FLAT_COURSES)
    dist    = random.choice(JUMPS_DISTS   if is_nh else FLAT_DISTS)
    going_raw, ground = random.choice(GOINGS_JUMPS if is_nh else GOINGS_FLAT)
    n_runners = random.randint(6, 14)

    rinfo = RaceInfo(
        course=course, country="uk",
        race_type="national_hunt" if is_nh else "flat",
        surface="turf",
        distance_f=dist, going=going_raw, runners=n_runners,
        discipline="Jumps" if is_nh else "Flat",
        discipline_subtype="Hurdle" if (is_nh and random.random() < 0.5) else ("Chase" if is_nh else None),
        ground_bucket=ground,
    )

    trainers = (JUMPS_TRAINERS or FILLER_TRAINERS)[:]
    jockeys  = (JUMPS_JOCKEYS  or FILLER_JUMPS_J )[:]  if is_nh else (FLAT_JOCKEYS or FILLER_JOCKEYS)[:]
    horses   = (JUMPS_HORSES   or [])[:]                if is_nh else (FLAT_HORSES  or [])[:]

    random.shuffle(trainers); random.shuffle(jockeys); random.shuffle(horses)

    # Assign form: 1-3 "good" form, 2-4 "mid", rest "poor"
    n_good = random.randint(1, 3)
    n_mid  = random.randint(2, min(4, n_runners - n_good))
    n_poor = n_runners - n_good - n_mid

    forms = (
        [random.choice(FORM_POOL_GOOD) for _ in range(n_good)] +
        [random.choice(FORM_POOL_MID)  for _ in range(n_mid)]  +
        [random.choice(FORM_POOL_POOR) for _ in range(n_poor)]
    )
    random.shuffle(forms)

    odds_ladder = _random_odds_ladder(n_runners)

    used_horse_names = set()
    runners = []
    odds = {}

    for i in range(n_runners):
        # Pick a unique horse name
        hname = None
        for _ in range(20):
            candidate = horses[i % len(horses)] if i < len(horses) else f"Runner {i+1}"
            if candidate not in used_horse_names:
                hname = candidate; break
            horses.append(f"{horses[i % max(1,len(horses))] } {i}")
        if hname is None:
            hname = f"Runner {race_idx}_{i}"
        used_horse_names.add(hname)

        trainer = trainers[i % len(trainers)]
        jockey  = jockeys[i % len(jockeys)]
        age     = random.randint(5, 11) if is_nh else random.randint(3, 8)
        weight  = random.randint(148, 168) if is_nh else random.randint(119, 133)
        draw    = i + 1 if not is_nh else 0
        form    = forms[i]

        r = _make_runner(hname, trainer, jockey, form, age, weight, draw, is_nh)
        runners.append(r)
        odds[hname] = odds_ladder[i]

    # 15% of races: no odds provided
    if random.random() < 0.15:
        odds = {}

    return rinfo, runners, odds if odds else None


# ── Run batch ─────────────────────────────────────────────────────────────────

def _dec(frac):
    try:
        if "/" in str(frac):
            n, d = str(frac).split("/"); return int(n)/int(d)+1
        return float(frac)
    except Exception:
        return 0.0

stats = {
    "flat": defaultdict(int),
    "jumps": defaultdict(int),
}

# For detailed examples
examples = {"flat": {"smart": [], "weak": []}, "jumps": {"smart": [], "weak": []}}

RACE_TYPES = [("flat",500), ("jumps",500)]
all_races  = []  # (race_type, race_idx, rinfo, runners, odds, result)

print("Building and running 1,000 races...")
total = 0
errors = 0

for rtype, count in RACE_TYPES:
    label = rtype
    for idx in range(count):
        rinfo, runners, odds = _build_race(rtype, idx)
        try:
            result = engine.analyze(rinfo, runners, odds=odds)
        except Exception as e:
            errors += 1
            stats[label]["errors"] += 1
            continue

        g = result.get("gold_pick")
        s = result.get("silver_pick")
        d = result.get("dark_horse")
        ranked = result.get("full_rankings", [])

        stats[label]["total"] += 1

        # ── Gold stats ────────────────────────────────────────────────────────
        if g:
            stats[label]["gold_present"] += 1
            # Gold rank in full field
            gold_rank = next((i+1 for i,h in enumerate(ranked) if h["name"]==g["name"]), None)
            if gold_rank:
                stats[label][f"gold_rank_{gold_rank}"] += 1
                if gold_rank <= 3: stats[label]["gold_top3"] += 1
            # Gold odds
            if odds and g["name"] in odds:
                gd = _dec(odds[g["name"]])
                if gd <= 3.0:   stats[label]["gold_evens_2to1"] += 1
                elif gd <= 5.0: stats[label]["gold_3to1_4to1"] += 1
                elif gd <= 7.0: stats[label]["gold_5to1_6to1"] += 1
                else:           stats[label]["gold_7plus"] += 1
        else:
            stats[label]["gold_none"] += 1

        # ── Silver stats ──────────────────────────────────────────────────────
        if s:
            stats[label]["silver_present"] += 1
            silver_rank = next((i+1 for i,h in enumerate(ranked) if h["name"]==s["name"]), None)
            if silver_rank:
                if silver_rank <= 3: stats[label]["silver_top3"] += 1
                if silver_rank >= 4: stats[label]["silver_outside_top3"] += 1
            # Trainer diversity: silver trainer ≠ gold trainer
            if g:
                gt = next((r.trainer for r in runners if r.name==g["name"]), "")
                st = next((r.trainer for r in runners if r.name==s["name"]), "")
                if gt and st and gt.lower()!=st.lower():
                    stats[label]["silver_diff_trainer"] += 1
                else:
                    stats[label]["silver_same_trainer"] += 1
        else:
            stats[label]["silver_none"] += 1

        # ── Dark horse stats ──────────────────────────────────────────────────
        if d:
            stats[label]["dark_present"] += 1
            dark_rank = next((i+1 for i,h in enumerate(ranked) if h["name"]==d["name"]), None)
            if odds and d["name"] in odds:
                dd = _dec(odds[d["name"]])
                if dd >= 6.0 and dd <= 10.0:  stats[label]["dark_5to1_9to1"]  += 1
                elif dd > 10.0 and dd <= 17.0: stats[label]["dark_10to1_16to1"] += 1
                elif dd > 17.0 and dd <= 34.0: stats[label]["dark_17to1_33to1"] += 1
                elif dd > 34.0:                stats[label]["dark_over_33to1"]  += 1
                else:                          stats[label]["dark_short"]       += 1
        else:
            stats[label]["dark_none"] += 1

        # ── Three distinct picks? ─────────────────────────────────────────────
        names = [x["name"] for x in [g, s, d] if x]
        if len(names) == len(set(names)):
            stats[label]["all_distinct"] += 1
        else:
            stats[label]["overlap_detected"] += 1

        # ── Collect interesting examples ──────────────────────────────────────
        if g and s and d and odds:
            gd = _dec(odds.get(g["name"], "0"))
            sd = _dec(odds.get(s["name"], "0"))
            dd = _dec(odds.get(d["name"], "0"))
            gold_rank = next((i+1 for i,h in enumerate(ranked) if h["name"]==g["name"]), 99)

            example = {
                "course": rinfo.course, "dist": rinfo.distance_f,
                "going": rinfo.going, "ground": rinfo.ground_bucket,
                "n": len(runners), "odds": odds,
                "gold": g["name"], "silver": s["name"], "dark": d["name"],
                "gold_odds": odds.get(g["name"],"?"),
                "silver_odds": odds.get(s["name"],"?"),
                "dark_odds": odds.get(d["name"],"?"),
                "gold_dec": gd, "silver_dec": sd, "dark_dec": dd,
                "gold_rank": gold_rank, "ranked": ranked,
                "runners": runners,
            }

            # Smart: gold at 2/1-4/1, silver a credible market rival (≤8/1),
            #        dark in 8/1-25/1 range, all in different price bands
            is_smart = (
                2.5 <= gd <= 5.0
                and sd <= 10.0
                and 8.0 <= dd <= 26.0
                and gd < sd < dd
                and gold_rank == 1
            )
            # Weak: gold at very long odds, or dark at short odds,
            #       or silver same price band as gold
            is_weak = (
                gd >= 9.0                    # Gold too long
                or dd < 5.0                  # Dark too short
                or abs(sd - gd) < 0.5        # Silver and Gold same price
                or (sd > 15.0 and gd < 4.0)  # Silver very long vs short Gold
            )

            if is_smart and len(examples[label]["smart"]) < 30:
                examples[label]["smart"].append(example)
            if is_weak and len(examples[label]["weak"]) < 30:
                examples[label]["weak"].append(example)

        total += 1
        if total % 100 == 0:
            print(f"  {total}/1000 done...")


# ── Report ─────────────────────────────────────────────────────────────────────

SEP  = "=" * 72
SEP2 = "-" * 72

def pct(n, d):
    return f"{100*n/d:.1f}%" if d > 0 else "n/a"

def report(label, s):
    n = s["total"]
    print(f"\n{SEP}")
    print(f"  {label.upper()} RACES  —  {n} analysed  ({s['errors']} errors)")
    print(SEP)

    print(f"\n  ── PICK AVAILABILITY ───────────────────────────────────────────")
    print(f"    Gold present    : {s['gold_present']:4d} / {n}  ({pct(s['gold_present'],n)})")
    print(f"    Silver present  : {s['silver_present']:4d} / {n}  ({pct(s['silver_present'],n)})")
    print(f"    Dark present    : {s['dark_present']:4d} / {n}  ({pct(s['dark_present'],n)})")
    print(f"    Dark absent     : {s['dark_none']:4d} / {n}  ({pct(s['dark_none'],n)})  ← price gate + rag cap")
    print(f"    All 3 distinct  : {s['all_distinct']:4d} / {n}  ({pct(s['all_distinct'],n)})")
    print(f"    Overlap (bug)   : {s['overlap_detected']:4d} / {n}  ({pct(s['overlap_detected'],n)})")

    print(f"\n  ── GOLD SELECTOR ───────────────────────────────────────────────")
    g_tot = s['gold_present']
    print(f"    Rank 1 in field : {s.get('gold_rank_1',0):4d} / {g_tot}  ({pct(s.get('gold_rank_1',0),g_tot)})")
    print(f"    Rank 2 in field : {s.get('gold_rank_2',0):4d} / {g_tot}  ({pct(s.get('gold_rank_2',0),g_tot)})")
    print(f"    Rank 3 in field : {s.get('gold_rank_3',0):4d} / {g_tot}  ({pct(s.get('gold_rank_3',0),g_tot)})")
    print(f"    Top-3 total     : {s['gold_top3']:4d} / {g_tot}  ({pct(s['gold_top3'],g_tot)})")
    print(f"    Evens–2/1       : {s['gold_evens_2to1']:4d} / {g_tot}  ({pct(s['gold_evens_2to1'],g_tot)})")
    print(f"    3/1–4/1         : {s['gold_3to1_4to1']:4d} / {g_tot}  ({pct(s['gold_3to1_4to1'],g_tot)})")
    print(f"    5/1–6/1         : {s['gold_5to1_6to1']:4d} / {g_tot}  ({pct(s['gold_5to1_6to1'],g_tot)})")
    print(f"    7/1+            : {s['gold_7plus']:4d} / {g_tot}  ({pct(s['gold_7plus'],g_tot)})")

    print(f"\n  ── SILVER SELECTOR ─────────────────────────────────────────────")
    sv_tot = s['silver_present']
    print(f"    Top 3 in field  : {s['silver_top3']:4d} / {sv_tot}  ({pct(s['silver_top3'],sv_tot)})")
    print(f"    Outside top 3   : {s['silver_outside_top3']:4d} / {sv_tot}  ({pct(s['silver_outside_top3'],sv_tot)})")
    print(f"    Diff trainer    : {s['silver_diff_trainer']:4d} / {sv_tot}  ({pct(s['silver_diff_trainer'],sv_tot)})")
    print(f"    Same trainer !!  : {s['silver_same_trainer']:4d} / {sv_tot}  ({pct(s['silver_same_trainer'],sv_tot)})")

    print(f"\n  ── DARK HORSE SELECTOR ─────────────────────────────────────────")
    d_tot = s['dark_present']
    print(f"    5/1–9/1         : {s['dark_5to1_9to1']:4d} / {d_tot}  ({pct(s['dark_5to1_9to1'],d_tot)})")
    print(f"    10/1–16/1       : {s['dark_10to1_16to1']:4d} / {d_tot}  ({pct(s['dark_10to1_16to1'],d_tot)})")
    print(f"    17/1–33/1       : {s['dark_17to1_33to1']:4d} / {d_tot}  ({pct(s['dark_17to1_33to1'],d_tot)})")
    print(f"    34/1+  (rags)   : {s['dark_over_33to1']:4d} / {d_tot}  ({pct(s['dark_over_33to1'],d_tot)})  ← should be ~0")
    print(f"    Too short (<5/1): {s['dark_short']:4d} / {d_tot}  ({pct(s['dark_short'],d_tot)})  ← should be ~0")


def show_examples(label, exs, kind, n=8):
    items = exs[label][kind][:n]
    if not items:
        print(f"  (none collected)")
        return
    for ex in items:
        g_rank_str = f"rank#{ex['gold_rank']}" if ex['gold_rank'] < 10 else "rank??"
        print(f"\n    {ex['course']} {ex['dist']:.0f}f {ex['going']} | {ex['n']} rnrs")
        print(f"    GOLD   : {ex['gold']:<22s} @{ex['gold_odds']:<6s}  ({g_rank_str})")
        print(f"    SILVER : {ex['silver']:<22s} @{ex['silver_odds']:<6s}")
        print(f"    DARK   : {ex['dark']:<22s} @{ex['dark_odds']:<6s}")


for label, s in stats.items():
    s["errors"] = s.get("errors", 0)
    report(label, s)

print(f"\n\n{SEP}")
print("  SMART EXAMPLES — Gold short, Silver credible, Dark in value range")
print(SEP)
for label in ("flat", "jumps"):
    print(f"\n  {label.upper()} (first 8 of {len(examples[label]['smart'])} collected):")
    show_examples(label, examples, "smart")

print(f"\n\n{SEP}")
print("  WEAK / QUESTIONABLE EXAMPLES")
print(SEP)
for label in ("flat", "jumps"):
    print(f"\n  {label.upper()} (first 8 of {len(examples[label]['weak'])} collected):")
    show_examples(label, examples, "weak")

print(f"\n\n{SEP}")
print(f"  TOTAL: {total} races  |  {errors} errors  |  {total-errors} clean runs")
print(SEP)
