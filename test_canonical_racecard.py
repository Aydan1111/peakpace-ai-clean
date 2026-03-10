"""
test_canonical_racecard.py
===========================
Parse-and-engine smoke-test for the canonical paste format.

canonical_racecard_paste_example.txt is the reference format for racecard
paste input.  This test locks in parser compatibility so changes elsewhere
never silently break it.

Checks:
  1. All 12 runners are extracted with correct names, odds, form.
  2. All runners have previous_runs populated (DD Mon YY date format).
  3. Talk The Talk's N/A finish is handled gracefully (no crash, other
     runs from that entry still parsed).
  4. Engine runs without error and returns Gold, Silver, and Dark Horse.
  5. Gold and Silver are distinct.
  6. Silver is market-backed (≤33/1) — not a dark-horse/outsider pick.
  7. Race confidence is MEDIUM or HIGH (not LOW) for a well-populated field.
  8. Dark Horse is not Gold or Silver.

Run as: python test_canonical_racecard.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import parse_racecard_text, parse_racecard_header, parse_distance_to_furlongs
from racing_ai_core import RacingAICore, RaceInfo, Runner, _parse_odds

_CANONICAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "canonical_racecard_paste_example.txt")

PASS = "PASS"
FAIL = "FAIL"

_results = []


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    _results.append((label, status, detail))
    marker = "✓" if condition else "✗"
    print(f"  {marker} {label}", end="")
    if detail:
        print(f"  [{detail}]", end="")
    print()
    return condition


def main():
    print("\n" + "=" * 62)
    print("  Canonical Racecard Format — Parse + Engine Smoke Test")
    print("=" * 62)

    if not os.path.isfile(_CANONICAL):
        print(f"\n  ERROR: canonical file not found: {_CANONICAL}")
        sys.exit(1)

    with open(_CANONICAL, encoding="utf-8") as f:
        text = f.read()

    # ── 1. Header ────────────────────────────────────────────────────
    print("\n  [Header]")
    header = parse_racecard_header(text)
    check("Course parsed",   header.get("course") == "Cheltenham",
          f"got {header.get('course')!r}")
    check("Distance parsed", header.get("distance") == "2m",
          f"got {header.get('distance')!r}")
    check("Race type",       header.get("race_type") == "Jumps",
          f"got {header.get('race_type')!r}")
    check("Ground bucket",   header.get("ground_bucket") == "Dry",
          f"got {header.get('ground_bucket')!r}")

    # ── 2. Runner count and core fields ──────────────────────────────
    print("\n  [Runners]")
    runners = parse_racecard_text(text)
    check("Runner count = 12", len(runners) == 12, f"got {len(runners)}")

    expected_names = [
        "Old Park Star", "Talk The Talk", "Mighty Park", "Mydaddypaddy",
        "El Cairos", "Leader Dallier", "Sober Glory", "Baron Noir",
        "Too Bossy For Us", "Koktail Brut", "Eachtotheirown", "Sageborough",
    ]
    names_ok = [r["name"] for r in runners] == expected_names
    check("All names in order", names_ok,
          "" if names_ok else f"got {[r['name'] for r in runners]}")

    # Spot-check odds
    odds_ok = all(r.get("odds") for r in runners)
    check("All runners have odds", odds_ok)

    fav = next((r for r in runners if r["name"] == "Old Park Star"), None)
    check("Old Park Star odds = 2/1", fav and fav.get("odds") == "2/1",
          f"got {fav.get('odds') if fav else 'missing'!r}")

    ext = next((r for r in runners if r["name"] == "Sageborough"), None)
    check("Sageborough odds = 80/1", ext and ext.get("odds") == "80/1",
          f"got {ext.get('odds') if ext else 'missing'!r}")

    # ── 3. Previous runs (DD Mon YY format) ─────────────────────────
    print("\n  [Previous runs — DD Mon YY date format]")
    all_have_prev = all((r.get("previous_runs") or []) for r in runners)
    check("All runners have ≥1 prev run", all_have_prev)

    ops = next((r for r in runners if r["name"] == "Old Park Star"), None)
    ops_runs = ops.get("previous_runs") or [] if ops else []
    check("Old Park Star has 5 prev runs", len(ops_runs) == 5,
          f"got {len(ops_runs)}")
    if ops_runs:
        first = ops_runs[0]
        check("First prev run has going",      "going" in first,     f"{first}")
        check("First prev run has distance_f", "distance_f" in first, f"{first}")
        check("First prev run has pos",        "pos" in first,        f"{first}")

    # N/A fall in Talk The Talk
    ttk = next((r for r in runners if r["name"] == "Talk The Talk"), None)
    ttk_runs = ttk.get("previous_runs") or [] if ttk else []
    check("Talk The Talk has 5 prev runs", len(ttk_runs) == 5,
          f"got {len(ttk_runs)}")
    # The N/A run should have distance_f + going but no pos
    na_run = next((p for p in ttk_runs if "pos" not in p), None)
    check("N/A run parsed (no pos, has going)",
          na_run is not None and "going" in na_run,
          f"{na_run!r}" if na_run else "no N/A run found")

    # ── 4. Engine run ─────────────────────────────────────────────────
    print("\n  [Engine output]")
    engine = RacingAICore()
    engine.dark_horse_enabled = True

    race = RaceInfo(
        course=header.get("course", ""),
        country="uk",
        race_type="national_hunt",
        surface="Turf",
        distance_f=int(parse_distance_to_furlongs(header.get("distance", "2m"))),
        going="good to soft",
        runners=len(runners),
        ground_bucket=header.get("ground_bucket", "Dry"),
        discipline="Jumps",
    )

    runner_objs = []
    odds_map = {}
    for r in runners:
        runner_objs.append(Runner(
            name=r["name"], age=r["age"],
            weight_lbs=120,
            form=r.get("form", ""),
            trainer=r.get("trainer", ""),
            jockey=r.get("jockey", ""),
            comment=r.get("comment", ""),
            previous_runs=r.get("previous_runs"),
        ))
        if r.get("odds"):
            odds_map[r["name"]] = r["odds"]

    try:
        result = engine.analyze(race, runner_objs, odds=odds_map)
        check("Engine ran without error", True)
    except Exception as e:
        check("Engine ran without error", False, str(e))
        print("\n  FAIL: engine crashed — aborting remaining checks.")
        _summarise()
        sys.exit(1)

    gold   = result.get("gold_pick")
    silver = result.get("silver_pick")
    dark   = result.get("dark_horse")
    conf   = result.get("race_confidence", "")

    check("Gold pick returned",   gold   is not None)
    check("Silver pick returned", silver is not None)
    check("Dark horse returned",  dark   is not None)

    # ── 5. Gold ≠ Silver ──────────────────────────────────────────────
    if gold and silver:
        check("Gold ≠ Silver", gold["name"] != silver["name"],
              f"both = {gold['name']!r}")

    # ── 6. Silver is market-backed (not a dark-horse/outsider) ────────
    if silver:
        sil_dec = _parse_odds(odds_map.get(silver["name"], ""))
        sil_mkt = sil_dec is not None and sil_dec <= 35.0   # ≤33/1
        check("Silver is market-backed (≤33/1)",
              sil_mkt,
              f"{silver['name']} at {odds_map.get(silver['name'],'?')} = {sil_dec}")

    # ── 7. Confidence is not LOW ───────────────────────────────────────
    check("Race confidence not LOW", conf in ("MEDIUM", "HIGH"),
          f"got {conf!r}")

    # ── 8. Dark ≠ Gold and Dark ≠ Silver ─────────────────────────────
    if dark and gold and silver:
        check("Dark ≠ Gold",   dark["name"] != gold["name"],
              f"dark={dark['name']!r}")
        check("Dark ≠ Silver", dark["name"] != silver["name"],
              f"dark={dark['name']!r}")

    print(f"\n  Gold   : {gold['name']} ({odds_map.get(gold['name'],'?')}) "
          f"score={gold['score']:.4f}" if gold else "  Gold  : None")
    print(f"  Silver : {silver['name']} ({odds_map.get(silver['name'],'?')}) "
          f"score={silver['score']:.4f}" if silver else "  Silver: None")
    if dark:
        print(f"  Dark   : {dark['name']} ({odds_map.get(dark['name'],'?')}) "
              f"score={dark['score']:.4f}")
    print(f"  Confidence: {conf}")

    _summarise()


def _summarise():
    passed = sum(1 for _, s, _ in _results if s == PASS)
    total  = len(_results)
    fails  = [label for label, s, _ in _results if s == FAIL]
    print(f"\n{'='*62}")
    print(f"  Result: {passed}/{total} checks passed")
    if fails:
        print(f"  FAILED checks:")
        for f in fails:
            print(f"    • {f}")
        print(f"{'='*62}\n")
        sys.exit(1)
    else:
        print(f"  ALL CHECKS PASS ✓")
        print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
