"""
test_prediction_sanity.py
─────────────────────────
Simulates 100 synthetic races to sanity-check the prediction engine.

Each race includes one deliberately "strong" horse (good form, high rating,
reasonable weight).  The script records how often the model picks that horse
in the top 1 and top 3 positions, and reports the overall confidence
distribution.

Run with:
    python test_prediction_sanity.py
"""

import random
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from racing_ai_core import RacingAICore, RaceInfo, Runner  # noqa: E402

# ── Constants ──────────────────────────────────────────────────────────────

TOTAL_RACES = 100
RUNNERS_MIN = 8
RUNNERS_MAX = 12

COURSES = ["Newmarket", "Ascot", "Sandown", "Kempton", "York",
           "Cheltenham", "Haydock", "Goodwood", "Lingfield", "Chester"]

# UK trainer names drawn from typical flat racecard data
TRAINERS = [
    "John Gosden", "Aidan O'Brien", "Charlie Appleby",
    "Roger Varian", "Mark Johnston", "William Haggas",
    "Richard Fahey", "Andrew Balding", "Hugo Palmer",
    "Sir Michael Stoute", "Ralph Beckett", "Ed Walker",
]

# UK jockey names
JOCKEYS = [
    "Frankie Dettori", "Ryan Moore", "William Buick",
    "Oisin Murphy", "Tom Marquand", "James Doyle",
    "Robert Havlin", "Andrea Atzeni", "Kieran Shoemark",
    "Adam Kirby", "Hollie Doyle", "David Egan",
]

# ── Helpers ────────────────────────────────────────────────────────────────

def _random_weight_lbs() -> int:
    """Return a plausible race weight in lbs (9st–11st 10lb = 126–164 lbs)."""
    return random.randint(126, 164)


def _random_form(quality: str = "normal") -> str:
    """Generate a synthetic form string appropriate to the quality tier."""
    if quality == "strong":
        # Recent winner / placed consistently
        options = ["1213", "2112", "1121", "11231", "21213", "12112"]
        return random.choice(options)
    if quality == "poor":
        # Lots of zeros (unplaced) and high positions
        options = ["56000", "60340", "00056", "45600", "06050", "00034"]
        return random.choice(options)
    # Normal: mixed bag of positions including the occasional 0
    pool = "11223345670"
    length = random.randint(3, 6)
    return "".join(random.choices(pool, k=length))


def _make_runner(name: str, quality: str = "normal") -> Runner:
    weight = _random_weight_lbs()
    if quality == "strong":
        weight = random.randint(126, 138)   # reasonable burden for strong horse
    return Runner(
        name=name,
        age=random.randint(3, 8),
        weight_lbs=weight,
        form=_random_form(quality),
        trainer=random.choice(TRAINERS),
        jockey=random.choice(JOCKEYS),
        draw=None,
        jockey_claim_lbs=0,
    )


# ── Engine ─────────────────────────────────────────────────────────────────

engine = RacingAICore()


# ── Simulation ─────────────────────────────────────────────────────────────

def run_simulation() -> None:
    strong_top1 = 0
    strong_top3 = 0
    confidence_dist: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    surprising: list[dict] = []

    for race_idx in range(TOTAL_RACES):
        n_runners = random.randint(RUNNERS_MIN, RUNNERS_MAX)
        strong_name = f"Strong Horse {race_idx}"

        # Build field — n-1 normal runners + 1 strong horse at a random slot
        field = [_make_runner(f"Runner {race_idx}_{j}") for j in range(n_runners - 1)]
        strong_runner = _make_runner(strong_name, quality="strong")
        field.insert(random.randint(0, len(field)), strong_runner)

        race = RaceInfo(
            course=random.choice(COURSES),
            country="UK",
            race_type="flat",
            surface="turf",
            distance_f=8.0,
            going="good",
            runners=len(field),
        )

        result = engine.analyze(race, field)

        race_conf = result.get("race_confidence", "LOW")
        confidence_dist[race_conf] = confidence_dist.get(race_conf, 0) + 1

        rankings = result.get("full_rankings", [])
        ranked_names = [entry["name"] for entry in rankings]

        if strong_name in ranked_names:
            pos = ranked_names.index(strong_name) + 1  # 1-based
        else:
            pos = n_runners   # fell off the rankings entirely

        if pos == 1:
            strong_top1 += 1
        if pos <= 3:
            strong_top3 += 1

        # Flag races where the strong horse missed the top 3
        if pos > 3:
            top_pick = ranked_names[0] if ranked_names else "N/A"
            top_score = round(rankings[0]["score"], 4) if rankings else 0.0
            strong_score = next(
                (round(e["score"], 4) for e in rankings if e["name"] == strong_name),
                None,
            )
            surprising.append({
                "race":         race_idx,
                "strong_pos":   pos,
                "strong_score": strong_score,
                "top_pick":     top_pick,
                "top_score":    top_score,
                "confidence":   race_conf,
            })

    # ── Summary ────────────────────────────────────────────────────────────

    top1_pct  = round(strong_top1 / TOTAL_RACES * 100, 1)
    top3_pct  = round(strong_top3 / TOTAL_RACES * 100, 1)

    print("=" * 60)
    print("PeakPace AI — Prediction Sanity Check")
    print("=" * 60)
    print(f"Total races simulated : {TOTAL_RACES}")
    print(f"Runners per race      : {RUNNERS_MIN}–{RUNNERS_MAX}")
    print()
    print("Strong horse placement:")
    print(f"  Top 1 : {strong_top1:>3} races  ({top1_pct}%)")
    print(f"  Top 3 : {strong_top3:>3} races  ({top3_pct}%)")
    print()
    print("Race confidence distribution:")
    for level in ("HIGH", "MEDIUM", "LOW"):
        count = confidence_dist.get(level, 0)
        bar = "█" * count
        print(f"  {level:<7}: {count:>3}  {bar}")
    print()

    if surprising:
        print(f"Unexpected selections (strong horse outside top 3): "
              f"{len(surprising)} / {TOTAL_RACES}")
        print("First 5 examples:")
        for r in surprising[:5]:
            print(
                f"  Race {r['race']:>3}: strong pos={r['strong_pos']}, "
                f"strong score={r['strong_score']}, "
                f"top pick='{r['top_pick']}' (score={r['top_score']}), "
                f"confidence={r['confidence']}"
            )
    else:
        print("No unexpected selections — strong horse always finished top 3.")

    print("=" * 60)

    # ── Basic assertions ───────────────────────────────────────────────────
    # The strong horse should finish top 3 in the vast majority of races.
    # If it doesn't, something is wrong with the scoring logic.
    assert top3_pct >= 60, (
        f"FAIL: strong horse only made top 3 in {top3_pct}% of races "
        f"(expected ≥60%)"
    )
    print(f"PASS: strong horse top-3 rate = {top3_pct}%  (threshold ≥60%)")

    # Confidence should not be overwhelmingly LOW
    low_pct = round(confidence_dist["LOW"] / TOTAL_RACES * 100, 1)
    assert low_pct <= 60, (
        f"FAIL: {low_pct}% of races returned LOW confidence (expected ≤60%)"
    )
    print(f"PASS: LOW confidence rate = {low_pct}%  (threshold ≤60%)")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation()
