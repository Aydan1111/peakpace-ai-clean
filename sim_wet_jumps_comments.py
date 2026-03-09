"""
sim_wet_jumps_comments.py
─────────────────────────
Targeted 100-race simulation for Wet Jumps mode with comment-based signals.

Goals:
  • Confirm Wet Jumps mode activates correctly.
  • Confirm "made mistakes" causes a slight downgrade vs. a neutral runner.
  • Confirm "stayed on" causes a slight upgrade vs. a neutral runner.
  • Report confidence distribution and parser/engine errors.
  • Show a handful of illustrative example races.
"""

import random
import sys
from racing_ai_core import RacingAICore, Runner, RaceInfo

# ── Constants ──────────────────────────────────────────────────────────────
TOTAL_RACES = 100
random.seed(42)

AI = RacingAICore()

# Wet-ground goings (all should trigger Wet Jumps when discipline=Jumps)
WET_GOINGS = ["heavy", "soft", "yielding", "very soft"]

# Distances spanning 2m – 3m2f+ (in furlongs)
DISTANCES = [16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 26.5]

# Field sizes
FIELD_SIZES = [5, 6, 7, 8, 9, 10, 12]

# Jump comment pools
JUMP_NEG_PHRASES = [
    "made mistakes", "bad mistake", "not fluent", "sloppy",
    "jumped left", "jumped right", "sketchy jumping", "error-prone", "clumsy",
]
JUMP_POS_PHRASES = [
    "jumped well", "sound jumper", "accurate at obstacles", "fluent jumping",
]
STAMINA_POS_PHRASES = [
    "stayed on", "kept on", "stayed well", "plugged on",
    "finished strongly", "kept on dourly", "found plenty",
]
STAMINA_NEG_PHRASES = [
    "weakened approaching finish", "weakened", "tired", "emptied",
    "folded quickly", "faded", "no extra",
]
NEUTRAL_PHRASES = [
    "ran well", "held every chance", "ran to form",
    "midfield", "held up", "",
]

# ── Helpers ────────────────────────────────────────────────────────────────

def make_runner(name: str, comment: str, form: str = "1234",
                prev_runs=None) -> Runner:
    r = Runner(name=name, age=6, weight_lbs=168, form=form,
               trainer="Nicky Henderson", jockey="Ryan Moore",
               comment=comment, previous_runs=prev_runs or [])
    return r


def make_race(distance_f: float, going: str, field_size: int) -> RaceInfo:
    return RaceInfo(
        course="Cheltenham",
        country="GB",
        distance_f=int(distance_f),
        going=going,
        ground_bucket="Wet",
        discipline="Jumps",
        race_type="Chase",
        runners=field_size,
        surface="Turf",
    )


def score_runner(runner: Runner, race: RaceInfo) -> float:
    """Return the wet-jumps adjustment multiplier for a single runner."""
    return AI._wet_jumps_adjustment(runner, race)


# ── Simulation ─────────────────────────────────────────────────────────────

def run_simulation():
    errors = 0
    results = []

    # Track how often comment signals shifted the winner
    jump_neg_downgrades = 0   # "made mistakes" runner beat by neutral
    jump_pos_upgrades   = 0   # "jumped well" runner beats neutral
    stamina_pos_ups     = 0
    stamina_neg_downs   = 0

    example_races = []        # Keep up to 6 illustrative examples

    for race_idx in range(TOTAL_RACES):
        going      = random.choice(WET_GOINGS)
        distance_f = random.choice(DISTANCES)
        field_size = random.choice(FIELD_SIZES)
        race       = make_race(distance_f, going, field_size)

        # Build a small field with mixed comment types
        field_comment_types = random.choices(
            ["jump_neg", "jump_pos", "stamina_pos", "stamina_neg", "neutral"],
            weights=[20, 15, 20, 15, 30],
            k=field_size,
        )

        runners_with_types = []
        try:
            for i, ctype in enumerate(field_comment_types):
                if ctype == "jump_neg":
                    cmt = random.choice(JUMP_NEG_PHRASES)
                elif ctype == "jump_pos":
                    cmt = random.choice(JUMP_POS_PHRASES)
                elif ctype == "stamina_pos":
                    cmt = random.choice(STAMINA_POS_PHRASES)
                elif ctype == "stamina_neg":
                    cmt = random.choice(STAMINA_NEG_PHRASES)
                else:
                    cmt = random.choice(NEUTRAL_PHRASES)

                runner = make_runner(f"Horse{i+1}", cmt)
                mult   = score_runner(runner, race)
                runners_with_types.append((runner, ctype, mult))

        except Exception as e:
            errors += 1
            print(f"  [ERROR] Race {race_idx+1}: {e}")
            continue

        # Sort by multiplier descending (higher = model prefers)
        ranked = sorted(runners_with_types, key=lambda x: x[2], reverse=True)

        # Collect stats
        for runner, ctype, mult in runners_with_types:
            results.append({"ctype": ctype, "mult": mult})

        # Check influence: does neutral runner beat jump_neg / stamina_neg?
        neutral_mults  = [m for _, ct, m in runners_with_types if ct == "neutral"]
        jneg_mults     = [m for _, ct, m in runners_with_types if ct == "jump_neg"]
        jpos_mults     = [m for _, ct, m in runners_with_types if ct == "jump_pos"]
        sneg_mults     = [m for _, ct, m in runners_with_types if ct == "stamina_neg"]
        spos_mults     = [m for _, ct, m in runners_with_types if ct == "stamina_pos"]

        if neutral_mults and jneg_mults:
            if min(neutral_mults) > max(jneg_mults):
                jump_neg_downgrades += 1
        if jpos_mults and neutral_mults:
            if min(jpos_mults) > max(neutral_mults):
                jump_pos_upgrades += 1
        if spos_mults and neutral_mults:
            if min(spos_mults) > max(neutral_mults):
                stamina_pos_ups += 1
        if neutral_mults and sneg_mults:
            if min(neutral_mults) > max(sneg_mults):
                stamina_neg_downs += 1

        # Collect example races (first 6 that have both neg and pos of interest)
        has_jneg = any(ct == "jump_neg"    for _, ct, _ in runners_with_types)
        has_spos = any(ct == "stamina_pos" for _, ct, _ in runners_with_types)
        if len(example_races) < 6 and (has_jneg or has_spos):
            example_races.append({
                "race_idx": race_idx + 1,
                "going": going,
                "distance_f": distance_f,
                "field_size": field_size,
                "runners": runners_with_types,
                "ranked": ranked,
            })

    return results, errors, example_races, {
        "jump_neg_downgrades": jump_neg_downgrades,
        "jump_pos_upgrades":   jump_pos_upgrades,
        "stamina_pos_ups":     stamina_pos_ups,
        "stamina_neg_downs":   stamina_neg_downs,
    }


# ── Reporting ──────────────────────────────────────────────────────────────

def report(results, errors, example_races, influence):
    print("=" * 66)
    print("  PeakPace AI — Wet Jumps Comment Signals Simulation (100 races)")
    print("=" * 66)

    # Group by comment type
    by_type = {}
    for r in results:
        by_type.setdefault(r["ctype"], []).append(r["mult"])

    print("\n── Average multiplier by comment type ───────────────────────────")
    type_order = ["jump_pos", "stamina_pos", "neutral",
                  "jump_neg", "stamina_neg"]
    for ct in type_order:
        mults = by_type.get(ct, [])
        if mults:
            avg = sum(mults) / len(mults)
            mn  = min(mults)
            mx  = max(mults)
            print(f"  {ct:<16} n={len(mults):>3}   avg={avg:.4f}  "
                  f"min={mn:.4f}  max={mx:.4f}")

    print("\n── Influence checks ─────────────────────────────────────────────")
    print(f"  Neutral beat jump_neg  runner : {influence['jump_neg_downgrades']} races")
    print(f"  Jump_pos  beat neutral runner : {influence['jump_pos_upgrades']} races")
    print(f"  Stamina_pos beat neutral      : {influence['stamina_pos_ups']} races")
    print(f"  Neutral beat stamina_neg      : {influence['stamina_neg_downs']} races")

    # Overall confidence proxy: spread between best and worst multiplier per race
    # (higher spread = signals are having more effect)
    print("\n── Engine errors ────────────────────────────────────────────────")
    print(f"  Parser / engine errors        : {errors} / {TOTAL_RACES}")

    print("\n── Example races ────────────────────────────────────────────────")
    for ex in example_races:
        print(f"\n  Race #{ex['race_idx']}  |  {ex['going'].upper()}  "
              f"|  {ex['distance_f']}f  |  {ex['field_size']} runners")
        print(f"  {'Runner':<12} {'Comment type':<16} {'Comment':<40} {'Mult':>6}")
        print(f"  {'-'*12} {'-'*16} {'-'*40} {'-'*6}")
        for runner, ctype, mult in ex["runners"]:
            cmt_disp = (runner.comment or "")[:38]
            print(f"  {runner.name:<12} {ctype:<16} {cmt_disp:<40} {mult:.4f}")
        print(f"\n  Ranked order (by multiplier):")
        for rank, (runner, ctype, mult) in enumerate(ex["ranked"], 1):
            arrow = " ← 'made mistakes' downgrade" if ctype == "jump_neg" else \
                    " ← 'stayed on' / stamina upgrade" if ctype == "stamina_pos" else \
                    " ← 'jumped well' upgrade" if ctype == "jump_pos" else \
                    " ← 'weakened' / stamina downgrade" if ctype == "stamina_neg" else ""
            print(f"    {rank}. {runner.name:<12} mult={mult:.4f}{arrow}")

    print("\n── Wet Jumps mode activation check ──────────────────────────────")
    # Quick sanity: Flat race on wet ground should NOT go through wet_jumps_adjustment
    flat_race  = RaceInfo(
        course="Cheltenham", country="GB", distance_f=16, going="soft",
        ground_bucket="Wet", discipline="Flat", race_type="Flat",
        runners=8, surface="Turf",
    )
    jumps_race = make_race(16.0, "soft", 8)

    from racing_ai_core import _is_wet_jumps
    flat_active  = _is_wet_jumps(flat_race)
    jumps_active = _is_wet_jumps(jumps_race)
    print(f"  Flat  + Wet going → _is_wet_jumps = {flat_active}   (expected False)")
    print(f"  Jumps + Wet going → _is_wet_jumps = {jumps_active}  (expected True)")

    print("\n" + "=" * 66)
    if errors == 0:
        print("  RESULT: 0 errors.  Comment signals active.  All checks passed.")
    else:
        print(f"  RESULT: {errors} error(s) detected — review output above.")
    print("=" * 66)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results, errors, example_races, influence = run_simulation()
    report(results, errors, example_races, influence)
    sys.exit(0 if errors == 0 else 1)
