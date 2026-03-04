"""
test_prediction_sanity.py
─────────────────────────
Two test suites for the prediction engine:

1. run_simulation()   — 100 synthetic races each with a "strong" horse
   (good form + reasonable weight).  Checks it ranks top 3 ≥60% of the time.

2. test_fallback_logic() — 50 races where two low-data horses compete:
   * "strong_unknown": no historical horse data, but a top-tier trainer/jockey
   * "poor_unknown":   no historical horse data AND unknown trainer/jockey
   Checks that strong_unknown outranks poor_unknown in ≥65% of races,
   verifying the coverage-based connections fallback is working.

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

# ── Fallback test constants ─────────────────────────────────────────────────

# Names in the UK fallback dictionaries (guaranteed recognised by the engine)
STRONG_TRAINER = "Nicky Henderson"   # 1.07 in _UK_TRAINER_FALLBACK
STRONG_JOCKEY  = "Ryan Moore"        # 1.08 in _UK_JOCKEY_FALLBACK

# Names that will NOT appear in any stats file → conf_deduction += 3 each
UNKNOWN_TRAINER = "Unknown Trainer XYZ"
UNKNOWN_JOCKEY  = "Unknown Jockey XYZ"

FALLBACK_RACES = 50

# ── Helpers ────────────────────────────────────────────────────────────────

# Plausible fractional odds pools by role
_FAVOURITE_ODDS   = ["2/1", "5/2", "3/1", "7/2", "4/1"]
_MID_ODDS         = ["5/1", "6/1", "7/1", "8/1", "10/1", "12/1"]
_OUTSIDER_ODDS    = ["14/1", "16/1", "20/1", "25/1", "33/1"]
_EXTREME_ODDS     = ["40/1", "50/1", "66/1", "80/1", "100/1"]


def _synthetic_odds(runners: list[Runner],
                    favourite_name: str,
                    outsider_name: str | None = None) -> dict[str, str]:
    """Build a plausible odds dict for a synthetic race.

    * favourite_name gets a short price
    * outsider_name (if given) gets an extreme price
    * remaining runners get mid-range or outsider prices
    """
    result: dict[str, str] = {}
    for r in runners:
        if r.name == favourite_name:
            result[r.name] = random.choice(_FAVOURITE_ODDS)
        elif outsider_name and r.name == outsider_name:
            result[r.name] = random.choice(_EXTREME_ODDS)
        else:
            # 60% mid, 40% outsider for the rest of the field
            pool = _MID_ODDS if random.random() < 0.6 else _OUTSIDER_ODDS
            result[r.name] = random.choice(pool)
    return result


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

        # Generate synthetic odds with the strong horse as market favourite
        race_odds = _synthetic_odds(field, strong_name)
        result = engine.analyze(race, field, odds=race_odds)

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


def test_fallback_logic() -> None:
    """Verify the coverage-based connections fallback works as intended.

    Each race contains:
      * strong_unknown — no horse history, no form, but top-tier trainer/jockey
      * poor_unknown   — no horse history, no form, completely unknown connections
      * 6–10 normal runners

    The strong_unknown should consistently outrank the poor_unknown because the
    fallback amplifies trainer/jockey signal when horse data is absent.
    """
    strong_beat_poor = 0
    strong_scores: list[float] = []
    poor_scores:   list[float] = []

    for race_idx in range(FALLBACK_RACES):
        n_normal   = random.randint(6, 10)
        su_name    = f"StrongUnknown {race_idx}"
        pu_name    = f"PoorUnknown {race_idx}"

        # Strong unknown: recognised top trainer/jockey, no horse record, no form
        strong_unknown = Runner(
            name=su_name,
            age=random.randint(3, 7),
            weight_lbs=random.randint(126, 142),
            form="",                    # deliberately empty — no history
            trainer=STRONG_TRAINER,
            jockey=STRONG_JOCKEY,
            draw=None,
            jockey_claim_lbs=0,
        )

        # Poor unknown: unknown trainer/jockey, no horse record, no form
        poor_unknown = Runner(
            name=pu_name,
            age=random.randint(3, 7),
            weight_lbs=random.randint(126, 142),
            form="",                    # deliberately empty — no history
            trainer=UNKNOWN_TRAINER,
            jockey=UNKNOWN_JOCKEY,
            draw=None,
            jockey_claim_lbs=0,
        )

        # Fill the rest of the field with normal runners
        field = [_make_runner(f"Normal {race_idx}_{j}") for j in range(n_normal)]
        field.append(strong_unknown)
        field.append(poor_unknown)
        random.shuffle(field)

        race = RaceInfo(
            course=random.choice(COURSES),
            country="UK",
            race_type="flat",
            surface="turf",
            distance_f=8.0,
            going="good",
            runners=len(field),
        )

        result  = engine.analyze(race, field)
        rankings = result.get("full_rankings", [])
        scored_map = {e["name"]: e["score"] for e in rankings}

        su_score = scored_map.get(su_name, 0.0)
        pu_score = scored_map.get(pu_name, 0.0)
        strong_scores.append(su_score)
        poor_scores.append(pu_score)

        if su_score > pu_score:
            strong_beat_poor += 1

    beat_pct = round(strong_beat_poor / FALLBACK_RACES * 100, 1)
    avg_su   = round(sum(strong_scores) / len(strong_scores), 4)
    avg_pu   = round(sum(poor_scores)   / len(poor_scores),   4)

    print()
    print("=" * 60)
    print("Fallback Logic Test — Unknown horses with/without connections")
    print("=" * 60)
    print(f"Races simulated         : {FALLBACK_RACES}")
    print(f"Strong unknown trainer  : {STRONG_TRAINER}")
    print(f"Strong unknown jockey   : {STRONG_JOCKEY}")
    print(f"Poor unknown trainer    : {UNKNOWN_TRAINER}")
    print(f"Poor unknown jockey     : {UNKNOWN_JOCKEY}")
    print()
    print(f"Strong unknown avg score : {avg_su}")
    print(f"Poor   unknown avg score : {avg_pu}")
    print(f"Score gap (su - pu)      : {round(avg_su - avg_pu, 4)}")
    print(f"Strong unknown outranked poor unknown in: "
          f"{strong_beat_poor}/{FALLBACK_RACES} races ({beat_pct}%)")
    print("=" * 60)

    assert beat_pct >= 65, (
        f"FAIL: strong_unknown only beat poor_unknown in {beat_pct}% of races "
        f"(expected ≥65%) — fallback logic may not be working"
    )
    print(f"PASS: strong_unknown beat poor_unknown {beat_pct}%  (threshold ≥65%)")
    print("=" * 60)


def test_racecard_signals() -> None:
    """Verify that racecard intelligence signals produce meaningful score differences.

    Two near-identical runners compete in 50 races:
      * enriched  — carries rich racecard data: good previous_runs (similar
                    distance/going, high field-adjusted form), positive comment,
                    and first-time equipment signal
      * plain     — identical trainer/jockey/form/weight, no racecard extras

    The enriched runner should outrank the plain one in the majority of races,
    demonstrating that racecard signals provide a useful secondary boost without
    dominating the model.
    """
    RACECARD_RACES = 50
    enriched_beat_plain = 0
    enriched_scores: list[float] = []
    plain_scores:    list[float] = []

    # Rich previous_runs: ran at 8f on good ground, consistently in top 30%
    rich_prev_runs = [
        {"going": "good", "distance_f": 8.0, "pos": 1, "field_size": 10, "discipline": "flat"},
        {"going": "good", "distance_f": 8.5, "pos": 2, "field_size": 12, "discipline": "flat"},
        {"going": "good", "distance_f": 7.0, "pos": 1, "field_size":  8, "discipline": "flat"},
        {"going": "good", "distance_f": 8.0, "pos": 3, "field_size": 11, "discipline": "flat"},
    ]

    # Shared trainer/jockey so connections are identical between the two runners
    shared_trainer = "William Haggas"
    shared_jockey  = "Oisin Murphy"
    shared_form    = "1213"
    shared_weight  = 133

    for race_idx in range(RACECARD_RACES):
        n_normal = random.randint(6, 10)
        enriched_name = f"Enriched {race_idx}"
        plain_name    = f"Plain {race_idx}"

        enriched = Runner(
            name=enriched_name,
            age=5,
            weight_lbs=shared_weight,
            form=shared_form,
            trainer=shared_trainer,
            jockey=shared_jockey,
            draw=None,
            jockey_claim_lbs=0,
            comment="Progressive type who keeps the faith with connections; lightly raced.",
            equipment="cheekpieces first time",
            previous_runs=rich_prev_runs,
        )

        plain = Runner(
            name=plain_name,
            age=5,
            weight_lbs=shared_weight,
            form=shared_form,
            trainer=shared_trainer,
            jockey=shared_jockey,
            draw=None,
            jockey_claim_lbs=0,
            # No comment, equipment, or previous_runs
        )

        field = [_make_runner(f"Normal {race_idx}_{j}") for j in range(n_normal)]
        field.append(enriched)
        field.append(plain)
        random.shuffle(field)

        race = RaceInfo(
            course=random.choice(COURSES),
            country="UK",
            race_type="flat",
            surface="turf",
            distance_f=8,
            going="good",
            runners=len(field),
        )

        result    = engine.analyze(race, field)
        rankings  = result.get("full_rankings", [])
        score_map = {e["name"]: e["score"] for e in rankings}

        es = score_map.get(enriched_name, 0.0)
        ps = score_map.get(plain_name,    0.0)
        enriched_scores.append(es)
        plain_scores.append(ps)

        if es > ps:
            enriched_beat_plain += 1

    beat_pct = round(enriched_beat_plain / RACECARD_RACES * 100, 1)
    avg_e    = round(sum(enriched_scores) / len(enriched_scores), 4)
    avg_p    = round(sum(plain_scores)    / len(plain_scores),    4)

    print()
    print("=" * 60)
    print("Racecard Signals Test — enriched vs plain runner")
    print("=" * 60)
    print(f"Races simulated             : {RACECARD_RACES}")
    print(f"Enriched runner avg score   : {avg_e}")
    print(f"Plain runner avg score      : {avg_p}")
    print(f"Score gap (enriched - plain): {round(avg_e - avg_p, 4)}")
    print(f"Enriched outranked plain in : "
          f"{enriched_beat_plain}/{RACECARD_RACES} races ({beat_pct}%)")
    print("=" * 60)

    assert beat_pct >= 70, (
        f"FAIL: enriched runner only beat plain in {beat_pct}% of races "
        f"(expected ≥70%) — racecard signals may not be registering"
    )
    print(f"PASS: enriched beat plain {beat_pct}%  (threshold ≥70%)")
    print("=" * 60)


def test_outsider_suppression() -> None:
    """Verify that extreme outsiders (40/1+) are almost never selected as top pick.

    Each race contains one runner deliberately assigned extreme odds (40–100/1)
    but with average form and connections (no other handicaps).  The model
    should rarely promote this horse to the top pick despite normal scoring.
    """
    OUTSIDER_RACES  = 50
    outsider_top1   = 0
    outsider_top3   = 0

    for race_idx in range(OUTSIDER_RACES):
        n_runners     = random.randint(8, 12)
        outsider_name = f"Outsider {race_idx}"

        # Build field — outsider has normal average form, not deliberately weak
        field = [_make_runner(f"Normal {race_idx}_{j}") for j in range(n_runners - 1)]
        outsider = _make_runner(outsider_name, quality="normal")
        field.insert(random.randint(0, len(field)), outsider)

        # Choose a random favourite (not the outsider)
        others      = [r for r in field if r.name != outsider_name]
        fav_runner  = random.choice(others)

        race = RaceInfo(
            course=random.choice(COURSES),
            country="UK",
            race_type="flat",
            surface="turf",
            distance_f=8.0,
            going="good",
            runners=len(field),
        )

        race_odds = _synthetic_odds(field, fav_runner.name, outsider_name=outsider_name)
        result    = engine.analyze(race, field, odds=race_odds)

        rankings     = result.get("full_rankings", [])
        ranked_names = [e["name"] for e in rankings]

        if ranked_names and ranked_names[0] == outsider_name:
            outsider_top1 += 1
        if outsider_name in ranked_names[:3]:
            outsider_top3 += 1

    top1_pct = round(outsider_top1 / OUTSIDER_RACES * 100, 1)
    top3_pct = round(outsider_top3 / OUTSIDER_RACES * 100, 1)

    print()
    print("=" * 60)
    print("Outsider Suppression Test — extreme odds (40/1+)")
    print("=" * 60)
    print(f"Races simulated              : {OUTSIDER_RACES}")
    print(f"Outsider selected as Top 1   : {outsider_top1} races  ({top1_pct}%)")
    print(f"Outsider in Top 3            : {outsider_top3} races  ({top3_pct}%)")
    print("=" * 60)

    assert top1_pct <= 10, (
        f"FAIL: extreme outsider was top pick in {top1_pct}% of races "
        f"(expected ≤10%) — odds suppression may not be working"
    )
    print(f"PASS: outsider top-1 rate = {top1_pct}%  (threshold ≤10%)")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation()
    test_fallback_logic()
    test_racecard_signals()
    test_outsider_suppression()
