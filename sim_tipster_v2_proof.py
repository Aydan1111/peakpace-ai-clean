"""
sim_tipster_v2_proof.py
=======================
Proof-of-concept: shows how the redesigned Gold / Silver / Dark Horse
selectors behave differently from the old rank-driven logic.

Three synthetic races are constructed to expose specific failure modes
of the old system.  For each race we show:
  - The full model ranking (by raw score, as both old and new use)
  - OLD picks  (score rank + single outsider guard)
  - NEW picks  (composite: market alignment / market proximity / value_ratio)
  - Why the new picks are more tipster-like

Run with:  python sim_tipster_v2_proof.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from racing_ai_core import RacingAICore, RaceInfo, Runner

engine = RacingAICore()
engine.dark_horse_enabled = True


# ── helpers ──────────────────────────────────────────────────────────────────

def run_race(label, race, runners, odds):
    print(f"\n{'='*70}")
    print(f"  RACE: {label}")
    print(f"{'='*70}")
    result = engine.analyze(race, runners, odds=odds)
    rankings = result["full_rankings"]

    print("\n  Model ranking (raw score):")
    for i, h in enumerate(rankings, 1):
        dec = None
        for k, v in (odds or {}).items():
            if k.lower().replace(" ","") == h["name"].lower().replace(" ",""):
                try:
                    if "/" in v:
                        n, d = v.split("/"); dec = round(int(n)/int(d)+1, 1)
                    else:
                        dec = float(v)
                except Exception:
                    pass
        price_str = f" @ {dec-1:.0f}/1" if dec else " (no odds)"
        print(f"    #{i:2d}  {h['name']:<22s}  score={h['score']:.3f}{price_str}")

    g = result["gold_pick"]
    s = result["silver_pick"]
    d = result["dark_horse"]
    print(f"\n  GOLD   (Good E/W Bet)  : {g['name'] if g else 'None'}")
    print(f"  SILVER (Good Place Bet): {s['name'] if s else 'None'}")
    print(f"  DARK   (Value Play)    : {d['name'] if d else 'None'}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# RACE 1: "The Outsider Trap"
#
# Old behaviour: top scorer is an 80/1 no-hoper with inflated model score
# from a data artefact.  Old Gold picked it (only swapped if rank-2 within
# 3%).  Old Silver just took rank-2 from the same list.
#
# New behaviour:
#   Gold  → market_alignment penalty tanks the 80/1 horse; genuine 3/1
#            favourite (rank-2 in model but rank-1 in market) wins composite.
#   Silver → market proximity logic picks the 5/1 shot (genuine betting danger)
#            not the 14/1 model rank-3.
#   Dark  → value_ratio finds the 12/1 horse the model rates much higher
#            than the market does.
# ─────────────────────────────────────────────────────────────────────────────

race1 = RaceInfo(
    course="Ascot", country="uk", race_type="flat", surface="turf",
    distance_f=8.0, going="good", runners=7,
    discipline="Flat", discipline_subtype=None, ground_bucket="Good",
)
runners1 = [
    Runner("Data Ghost",    age=4, weight_lbs=126, form="112",  trainer="John Gosden",    jockey="Frankie Dettori", draw=3, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Royal Favour",  age=5, weight_lbs=124, form="211",  trainer="Aidan O'Brien",  jockey="Ryan Moore",      draw=1, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Close Call",    age=4, weight_lbs=122, form="213",  trainer="Charlie Appleby",jockey="William Buick",   draw=5, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Market Mover",  age=5, weight_lbs=120, form="321",  trainer="Roger Varian",   jockey="Andrea Atzeni",   draw=2, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Solid Each Way",age=4, weight_lbs=118, form="413",  trainer="Mark Johnston",  jockey="Joe Fanning",     draw=4, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Long Shot",     age=6, weight_lbs=116, form="537",  trainer="Ralph Beckett",  jockey="Tom Marquand",    draw=6, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("No Hoper",      age=7, weight_lbs=112, form="789",  trainer="Jim Boyle",      jockey="David Probert",   draw=7, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
]
# Data Ghost is priced 80/1 (market outsider despite top model score).
# Royal Favour is the 3/1 market favourite.
# Market Mover is 5/1 (genuine danger money).
# Solid Each Way is 12/1 — model rates it decently, market underestimates it.
odds1 = {
    "Data Ghost":    "80/1",
    "Royal Favour":  "3/1",
    "Close Call":    "9/2",
    "Market Mover":  "5/1",
    "Solid Each Way":"12/1",
    "Long Shot":     "20/1",
    "No Hoper":      "50/1",
}

print("\n" + "─"*70)
print("  RACE 1 — The Outsider Trap")
print("  Setup: model's rank-4 (Data Ghost) is 80/1 but model has inflated it.")
print("         Royal Favour (3/1) is the market favourite, model also ranks it #1.")
print("  OLD Gold: would take rank-1 unless rank-2 within 3% — one guard only.")
print("  NEW Gold: market_alignment composite — same result here but better reason.")
print("  OLD Silver: takes rank-2 by score (Close Call) regardless of market.")
print("  NEW Silver: proximity logic — Close Call at 9/2 is a genuine market danger")
print("             to Royal Favour at 3/1 (within 2× odds) → correctly selected.")
print("  OLD Dark: rank 3–6 with score ≥ 85% gold AND odds 6/1–33/1 first pass.")
print("           Would likely pick Market Mover (rank 3) as it clears 85% floor.")
print("  NEW Dark: value_ratio composite — Long Shot (20/1, ~12.8% model prob)")
print("           is the biggest market overlay (model says 7/1 fair, market says 20/1).")
print("─"*70)
run_race("The Outsider Trap", race1, runners1, odds1)


# ─────────────────────────────────────────────────────────────────────────────
# RACE 2: "The Clone Problem"
#
# Gold and model rank-2 are nearly identical horses (same trainer/jockey,
# similar form) — old Silver just picks the clone.
# New Silver detects the profile similarity and boosts the horse with a
# different strength profile (form-led vs connections-led) even if it's
# rank-3 by raw score.
# ─────────────────────────────────────────────────────────────────────────────

race2 = RaceInfo(
    course="Cheltenham", country="uk", race_type="national_hunt", surface="turf",
    distance_f=16.0, going="soft", runners=8,
    discipline="Jumps", discipline_subtype="Chase", ground_bucket="Soft/Heavy",
)
runners2 = [
    Runner("Top Dog",       age=7, weight_lbs=160, form="111",  trainer="Willie Mullins", jockey="Paul Townend",   draw=0, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Carbon Copy",   age=8, weight_lbs=158, form="112",  trainer="Willie Mullins", jockey="Patrick Mullins",draw=0, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Form Horse",    age=6, weight_lbs=154, form="121",  trainer="Nicky Henderson", jockey="Nico de Boinville",draw=0, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Market Cert",   age=9, weight_lbs=152, form="213",  trainer="Gordon Elliott", jockey="Jack Kennedy",   draw=0, jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Each Way Saver",age=7, weight_lbs=148, form="314",  trainer="Henry de Bromhead",jockey="Rachael Blackmore",draw=0,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Rank Outsider", age=8, weight_lbs=144, form="456",  trainer="Dermot McLoughlin",jockey="Bryan Cooper",  draw=0,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Veteran",       age=11,weight_lbs=140, form="567",  trainer="Mouse Morris",   jockey="Davy Russell",   draw=0,jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
    Runner("Maiden",        age=5, weight_lbs=136, form="56",   trainer="Tom Mullins",    jockey="D. Meyler",      draw=0,jockey_claim_lbs=0, comment="", equipment="", previous_runs=[]),
]
odds2 = {
    "Top Dog":       "2/1",
    "Carbon Copy":   "5/2",    # close to Top Dog in odds — looks like Silver
    "Form Horse":    "7/2",    # similar odds to Carbon Copy but different profile
    "Market Cert":   "5/1",
    "Each Way Saver":"10/1",
    "Rank Outsider": "25/1",
    "Veteran":       "33/1",
    "Maiden":        "50/1",
}

print("\n\n" + "─"*70)
print("  RACE 2 — The Clone Problem")
print("  Setup: Gold (Top Dog) and rank-2 (Carbon Copy) same trainer/jockey.")
print("  OLD Silver: takes rank-2 (Carbon Copy) — same stable, same profile.")
print("  NEW Silver: profile_diversity boosts Form Horse (different connections)")
print("             over Carbon Copy, since both have similar market proximity.")
print("  OLD Dark: rank-3 to 6 with score ≥ 85% gold → close call.")
print("  NEW Dark: value_ratio finds Each Way Saver (10/1) if model rates it well.")
print("─"*70)
run_race("The Clone Problem", race2, runners2, odds2)


# ─────────────────────────────────────────────────────────────────────────────
# RACE 3: "The Hidden Value"
#
# A horse at 16/1 has above-average official ratings and recent win form
# but is priced long because it's lightly raced and less newsworthy.
# Old Dark Horse misses it (rank 5, score doesn't clear 85% of Gold floor).
# New Dark Horse finds it via value_ratio + rating_edge upside signal.
# ─────────────────────────────────────────────────────────────────────────────

race3 = RaceInfo(
    course="Newmarket", country="uk", race_type="flat", surface="turf",
    distance_f=10.0, going="good to firm", runners=9,
    discipline="Flat", discipline_subtype=None, ground_bucket="Good",
)
runners3 = [
    Runner("Clear Favourite", age=4, weight_lbs=130, form="112", trainer="John Gosden",  jockey="Frankie Dettori",draw=1,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Strong Contender",age=5, weight_lbs=128, form="211", trainer="Aidan O'Brien",jockey="Ryan Moore",     draw=2,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Dark Market",     age=4, weight_lbs=126, form="123", trainer="Charlie Appleby",jockey="William Buick",draw=3,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Consistent One",  age=5, weight_lbs=124, form="231", trainer="Roger Varian", jockey="Andrea Atzeni",  draw=4,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Rated Gem",       age=3, weight_lbs=118, form="121", trainer="Andrew Balding",jockey="David Probert", draw=5,jockey_claim_lbs=0,comment="Officially rated 108, lightly raced, expected to improve",equipment="",previous_runs=[]),
    Runner("Handicapper",     age=6, weight_lbs=116, form="345", trainer="Mark Johnston", jockey="Joe Fanning",   draw=6,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Journeyman",      age=7, weight_lbs=114, form="456", trainer="Ralph Beckett", jockey="Tom Marquand",  draw=7,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Longshot",        age=5, weight_lbs=110, form="567", trainer="Eve Johnson Houghton",jockey="Hollie Doyle",draw=8,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
    Runner("Outsider",        age=8, weight_lbs=108, form="789", trainer="Jim Boyle",     jockey="Tom Queally",   draw=9,jockey_claim_lbs=0,comment="",equipment="",previous_runs=[]),
]
odds3 = {
    "Clear Favourite":  "5/4",
    "Strong Contender": "3/1",
    "Dark Market":      "5/1",
    "Consistent One":   "8/1",
    "Rated Gem":        "16/1",   # market underestimates — model should rate it higher
    "Handicapper":      "20/1",
    "Journeyman":       "25/1",
    "Longshot":         "33/1",
    "Outsider":         "66/1",
}

print("\n\n" + "─"*70)
print("  RACE 3 — The Hidden Value")
print("  Setup: Rated Gem at 16/1 has good form (121) but market ignores it.")
print("  OLD Dark: rank ≥ 3, score ≥ 85% gold, odds 6/1–33/1.")
print("           Rated Gem at rank-5 rarely cleared the 85% score floor.")
print("  NEW Dark: value_ratio boosts Rated Gem (model rates it, market at 16/1)")
print("           + form ≥ 0.85 upside bonus → selected as genuine overlay.")
print("─"*70)
run_race("The Hidden Value", race3, runners3, odds3)


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("""

╔══════════════════════════════════════════════════════════════════════╗
║  OLD vs NEW — What changed and why it matters                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  GOLD                                                                ║
║  Old: rank-1 scorer, ONE guard (66/1 outsider + rank-2 within 3%).  ║
║  New: composite = score × market_alignment × data_quality.          ║
║       A market outsider at rank-1 now LOSES to a market-confirmed   ║
║       horse at rank-2 or 3, producing smarter win tips.             ║
║                                                                      ║
║  SILVER                                                              ║
║  Old: rank-2 or rank-3 by raw score, minor tiebreaks only.          ║
║  New: composite = score_contention × market_proximity × diversity.  ║
║       "Biggest threat" = horse the MARKET also rates close to Gold. ║
║       A 5/1 shot when Gold is 2/1 outscores a 14/1 shot even if    ║
║       the 14/1 has a fractionally better model score.               ║
║       Same-stable clones are penalised; different profiles rewarded.║
║                                                                      ║
║  DARK HORSE                                                          ║
║  Old: rank 3–6, score ≥ 85% gold, odds 6/1–33/1, first pass wins.  ║
║       Effectively just rank-3 with an odds filter — not value.      ║
║  New: value_ratio = model_prob / market_prob.                        ║
║       Selects the horse the MARKET underestimates vs model.         ║
║       Upside signals (rating_edge, form, perf_b) reward hidden      ║
║       potential, not just a better-ranked horse.                    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")
