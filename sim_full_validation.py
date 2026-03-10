"""
sim_full_validation.py
======================
Comprehensive 4-context, 400-race validation of the PeakPace AI tipster logic.

Contexts (100 races each):
  1. Flat / Dry   — firm/good/good-to-firm ground, UK/Irish flat distances
  2. Flat / Wet   — soft/heavy/good-to-soft ground, UK/Irish flat distances
  3. Jumps / Dry  — good/good-to-soft/good-to-firm ground, 2m–3m2f NH distances
  4. Jumps / Wet  — soft/heavy/yielding/very-soft ground, 2m–3m2f NH distances

Real names loaded from historical datasets (horses, trainers, jockeys).

Reports per context:
  • Parser / engine health
  • Confidence distribution (deductions histogram)
  • Gold behaviour  (fav match, top-3 rate, outsider top-1 rate)
  • Silver behaviour (contender rate, market-backed rate)
  • Dark Horse frequency and clash checks
  • Tipster-logic impact vs raw-rank baseline
      — how often Gold changed due to outsider bypass
      — how often Silver changed due to new contender logic
  • Wet/Dry leakage verification (Wet Jumps mode only fires in Wet Jumps context)

Run as: python sim_full_validation.py
"""

import sys
import re
import os
import random
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

sys.path.insert(0, "/home/user/peakpace-ai-clean")

from main import parse_distance_to_furlongs
from racing_ai_core import (
    RacingAICore, RaceInfo, Runner,
    _normalize_name, _parse_odds, _is_wet_jumps,
    classify_wet_dry,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
RACES_PER_CONTEXT = 100
RNG = random.Random(20260310)   # fixed seed for reproducibility

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_RUNS_PAT   = r'^([A-Za-z].+?) \(Runs:'
_SEASON_PAT = r'^([A-Za-z].+?) \(Season:'


def _load_names(filename: str, pattern: str) -> list:
    names = []
    path = os.path.join(_DATA_DIR, filename)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(pattern, line.strip())
                if m:
                    names.append(m.group(1).strip())
    except OSError:
        pass
    return names


def _dedup(lst):
    return list(dict.fromkeys(x for x in lst if x))


def _strip_country(name: str) -> str:
    return re.sub(r'\s*\([A-Z]{2,3}\)\s*$', '', name).strip()


# Jumps datasets
_HORSES_JUMP = _dedup(
    [_strip_country(h) for h in
     _load_names("Irish Horses National Hunt (Jumps) 2024 and 2025 and 2026 - Engine Format.txt", _RUNS_PAT) +
     _load_names("UK_Horses_Jumps_2024_2025_2026_clean.txt", _SEASON_PAT)]
)
_TRAINERS_JUMP = _dedup(
    _load_names("Irish Trainers Stats National Hunt (Jumps) 2024 and 2025 and 2026.txt", _RUNS_PAT) +
    _load_names("UK_Trainers_Jumps_clean.txt", _SEASON_PAT)
)
_JOCKEYS_JUMP = _dedup(
    _load_names("Irish Jockeys Stats National Hunt 2024 and 2025 and 2026.txt", _RUNS_PAT) +
    _load_names("UK_Jockeys_Jumps_clean.txt", _SEASON_PAT)
)

# Flat datasets
_HORSES_FLAT = _dedup(
    [_strip_country(h) for h in
     _load_names("Irish Horses Flat 2024 and 2025 - Engine Format.txt", _RUNS_PAT) +
     _load_names("UK_Horses_Flat_2024_2025_2026_clean.txt", _SEASON_PAT)]
)
_TRAINERS_FLAT = _dedup(
    _load_names("Irish Trainers Stats Flat 2024 and 2025 and 2026.txt", _RUNS_PAT) +
    _load_names("UK_Trainers_Flat_clean.txt", _SEASON_PAT)
)
_JOCKEYS_FLAT = _dedup(
    _load_names("Irish Jockeys Stats Flat 2024 and 2025.txt", _RUNS_PAT) +
    _load_names("UK_Jockeys_Flat_clean.txt", _SEASON_PAT)
)

# Fallbacks (in case files are missing)
_FB_TRAINERS_JUMP = [
    "Willie Mullins", "Gordon Elliott", "Nicky Henderson", "Paul Nicholls",
    "Dan Skelton", "Henry de Bromhead", "Ben Pauling", "Olly Murphy",
    "Gavin Cromwell", "Alan King",
]
_FB_JOCKEYS_JUMP = [
    "Paul Townend", "Rachael Blackmore", "Harry Cobden", "Nico de Boinville",
    "Danny Mullins", "Sean Bowen", "Harry Skelton", "Aidan Coleman",
]
_FB_TRAINERS_FLAT = [
    "John Gosden", "Aidan O'Brien", "Charlie Appleby", "William Haggas",
    "Roger Varian", "Mark Johnston", "Andrew Balding", "Richard Hannon",
]
_FB_JOCKEYS_FLAT = [
    "Ryan Moore", "Oisin Murphy", "Frankie Dettori", "James Doyle",
    "William Buick", "Tom Marquand", "Hollie Doyle", "Jim Crowley",
]

_TRAINERS_JUMP = _TRAINERS_JUMP or _FB_TRAINERS_JUMP
_JOCKEYS_JUMP  = _JOCKEYS_JUMP  or _FB_JOCKEYS_JUMP
_TRAINERS_FLAT = _TRAINERS_FLAT or _FB_TRAINERS_FLAT
_JOCKEYS_FLAT  = _JOCKEYS_FLAT  or _FB_JOCKEYS_FLAT

# ─────────────────────────────────────────────────────────────────────────────
# GOING / DISTANCE POOLS
# ─────────────────────────────────────────────────────────────────────────────
_WET_JUMP_GOINGS = ["soft", "heavy", "yielding", "very soft"]
_DRY_JUMP_GOINGS = ["good", "good to soft", "good to firm"]
_WET_FLAT_GOINGS = ["soft", "heavy", "good to soft"]
_DRY_FLAT_GOINGS = ["good", "good to firm", "firm"]

_JUMP_DISTS = ["2m", "2m4f", "2m5f", "3m", "3m1f", "3m2f"]
_FLAT_DISTS = ["6f", "7f", "1m", "1m2f", "1m4f", "1m6f"]

# ─────────────────────────────────────────────────────────────────────────────
# ODDS POOLS
# ─────────────────────────────────────────────────────────────────────────────
_FAV_ODDS  = ["2/1", "5/2", "3/1", "7/2", "4/1", "9/2"]
_MID_ODDS  = ["6/1", "8/1", "10/1", "12/1"]
_OUT_ODDS  = ["14/1", "16/1", "20/1", "25/1", "33/1"]
_EXTR_ODDS = ["66/1", "80/1", "100/1"]

_FORM_CHARS_JUMP = "123456780PFU"
_FORM_CHARS_FLAT = "1234567890"

# Jump comment pools (for Wet Jumps signal testing)
_JUMP_NEG_CMT    = ["made mistakes", "bad mistake", "not fluent", "jumped left"]
_JUMP_POS_CMT    = ["jumped well", "sound jumper", "accurate at obstacles"]
_STAMINA_POS_CMT = ["stayed on", "kept on well", "finished strongly"]
_STAMINA_NEG_CMT = ["weakened", "tired", "faded", "no extra"]
_NEUTRAL_CMT     = ["ran well", "held every chance", ""]

# ─────────────────────────────────────────────────────────────────────────────
# FIELD GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _make_odds_list(n: int, include_extreme: bool) -> list:
    odds = []
    # 1–2 favourites
    for _ in range(RNG.randint(1, 2)):
        odds.append(RNG.choice(_FAV_ODDS))
    # 2–3 mid-field
    for _ in range(min(RNG.randint(2, 3), n - len(odds))):
        odds.append(RNG.choice(_MID_ODDS))
    # fill remainder with outsiders
    while len(odds) < n:
        odds.append(RNG.choice(_OUT_ODDS))
    RNG.shuffle(odds)
    if include_extreme:
        odds[0] = RNG.choice(_EXTR_ODDS)
    return odds


def _make_form(discipl: str) -> str:
    chars = _FORM_CHARS_JUMP if discipl == "Jumps" else _FORM_CHARS_FLAT
    return "".join(RNG.choice(chars) for _ in range(RNG.randint(3, 8)))


def _make_weight(discipl: str) -> int:
    s = RNG.randint(10, 12) if discipl == "Jumps" else RNG.randint(8, 10)
    p = RNG.randint(0, 13)
    return s * 14 + p


def _pick_comment(discipl: str) -> str:
    """For Jumps races, randomly assign a comment with realistic distribution."""
    if discipl != "Jumps":
        return ""
    ctype = RNG.choices(
        ["jump_neg", "jump_pos", "stamina_pos", "stamina_neg", "neutral"],
        weights=[15, 10, 15, 10, 50],
    )[0]
    if ctype == "jump_neg":
        return RNG.choice(_JUMP_NEG_CMT)
    if ctype == "jump_pos":
        return RNG.choice(_JUMP_POS_CMT)
    if ctype == "stamina_pos":
        return RNG.choice(_STAMINA_POS_CMT)
    if ctype == "stamina_neg":
        return RNG.choice(_STAMINA_NEG_CMT)
    return RNG.choice(_NEUTRAL_CMT)


def _make_field(n: int, discipl: str, horse_pool: list, trainer_pool: list,
                jockey_pool: list, include_extreme: bool):
    odds_list = _make_odds_list(n, include_extreme)
    # Sample unique horse names; fall back to sequential if pool too small
    if len(horse_pool) >= n:
        names = RNG.sample(horse_pool, n)
    else:
        names = [f"Horse{i+1}" for i in range(n)]

    runners = []
    for i in range(n):
        runners.append(Runner(
            name=names[i],
            age=(RNG.randint(4, 10) if discipl == "Jumps" else RNG.randint(2, 5)),
            weight_lbs=_make_weight(discipl),
            form=_make_form(discipl),
            trainer=RNG.choice(trainer_pool),
            jockey=RNG.choice(jockey_pool),
            comment=_pick_comment(discipl),
            previous_runs=[],
        ))
    return runners, odds_list


def _make_race(discipl: str, going: str, dist_str: str, n: int) -> RaceInfo:
    bucket = classify_wet_dry(going)
    dist_f = parse_distance_to_furlongs(dist_str)
    rt = "national_hunt" if discipl == "Jumps" else "flat"
    course = "Cheltenham" if discipl == "Jumps" else "Newmarket"
    return RaceInfo(
        course=course,
        country="uk",
        race_type=rt,
        surface="Turf",
        distance_f=int(dist_f),
        going=going,
        runners=n,
        ground_bucket=bucket,
        discipline=discipl,
    )


# ─────────────────────────────────────────────────────────────────────────────
# INLINE OLD RAW-RANK BASELINE (reproduces pre-tipster behaviour)
# ─────────────────────────────────────────────────────────────────────────────
# The old _best_pick selected rank-1 as Gold, rank-2 as Silver, with only the
# data-quality gate (_conf_ded < 5). No outsider bypass, no 80% ratio gate.

def _old_gold_silver(full_rankings: list):
    """Simulate old raw-rank selection (rank-1 = gold, rank-2 = silver)."""
    _DED_LIMIT = 5
    qualified = [h for h in full_rankings if h.get("_conf_ded", 0) < _DED_LIMIT]
    pool = qualified if qualified else full_rankings
    if not pool:
        return None, None
    old_gold   = pool[0]["name"]
    old_silver = pool[1]["name"] if len(pool) >= 2 else None
    return old_gold, old_silver


# ─────────────────────────────────────────────────────────────────────────────
# PER-CONTEXT METRICS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CtxMetrics:
    label: str
    # Health
    total:   int = 0
    errors:  int = 0

    # Wet Jumps activation (Jumps contexts only)
    wet_jmp_active: int = 0

    # Confidence distribution (counts by deduction bucket)
    ded_buckets: Dict[str, int] = field(default_factory=lambda: Counter())

    # Gold behaviour
    gold_none:      int = 0    # no gold selected
    gold_is_fav:    int = 0    # gold odds in FAV_ODDS range (≤9/2 decimal ~5.5)
    gold_top3:      int = 0    # gold is in top-3 by model rank
    gold_outsider:  int = 0    # gold odds >10/1 (11.0+ decimal)

    # Silver behaviour
    silver_none:       int = 0
    silver_contender:  int = 0   # silver score ≥ 80% of gold
    silver_mkt_backed: int = 0   # silver odds ≤ 33/1

    # Dark Horse
    dark_none:  int = 0
    dark_clash: int = 0   # dark == gold or silver — MUST be 0

    # Hard invariants
    gold_silver_same: int = 0   # MUST be 0

    # Tipster-logic impact vs raw-rank baseline
    gold_changed:          int = 0   # new gold != old raw gold
    silver_changed:        int = 0   # new silver != old raw silver
    bypass_triggered:      int = 0   # extreme bypass fired
    bypass_to_mkt_backed:  int = 0   # bypass picked a market-backed horse
    silver_ratio_improved: int = 0   # new silver ratio > old silver ratio


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_context(label: str, discipl: str, going_pool: list, dist_pool: list,
                horse_pool: list, trainer_pool: list, jockey_pool: list,
                engine: RacingAICore) -> CtxMetrics:
    m = CtxMetrics(label=label)

    for _ in range(RACES_PER_CONTEXT):
        going  = RNG.choice(going_pool)
        dist   = RNG.choice(dist_pool)
        n      = RNG.randint(5, 14)
        # 12% chance of an extreme outsider in the field
        use_extreme = RNG.random() < 0.12

        runners, odds_list = _make_field(
            n, discipl, horse_pool, trainer_pool, jockey_pool, use_extreme
        )
        race     = _make_race(discipl, going, dist, n)
        odds_map = {r.name: odds_list[i] for i, r in enumerate(runners)}

        engine.dark_horse_enabled = True
        try:
            result = engine.analyze(race, runners, odds=odds_map)
        except Exception:
            m.errors += 1
            continue

        m.total += 1

        # ── Wet Jumps activation ──────────────────────────────────────────
        if _is_wet_jumps(race):
            m.wet_jmp_active += 1

        # ── Extract picks ─────────────────────────────────────────────────
        gold   = result.get("gold_pick")
        silver = result.get("silver_pick")
        dark   = result.get("dark_horse")
        ranks  = result.get("full_rankings", [])

        gold_name   = gold["name"]   if gold   else None
        silver_name = silver["name"] if silver else None
        dark_name   = dark["name"]   if dark   else None

        # ── Confidence distribution ───────────────────────────────────────
        for h in ranks:
            ded = h.get("_conf_ded", 0)
            if ded == 0:
                m.ded_buckets["0"] += 1
            elif ded < 3:
                m.ded_buckets["1-2"] += 1
            elif ded < 5:
                m.ded_buckets["3-4"] += 1
            elif ded < 8:
                m.ded_buckets["5-7"] += 1
            else:
                m.ded_buckets["8+"] += 1

        # ── Gold behaviour ────────────────────────────────────────────────
        if not gold:
            m.gold_none += 1
        else:
            gold_dec = _parse_odds(odds_map.get(gold_name, ""))
            if gold_dec is not None and gold_dec <= 5.5:
                m.gold_is_fav += 1
            if gold_dec is not None and gold_dec > 11.0:
                m.gold_outsider += 1
            # is gold in top-3 model rank?
            top3 = [h["name"] for h in ranks[:3]]
            if gold_name in top3:
                m.gold_top3 += 1

        # ── Silver behaviour ──────────────────────────────────────────────
        if not silver:
            m.silver_none += 1
        else:
            if gold and ranks:
                gold_sc   = next((h["score"] for h in ranks
                                  if h["name"] == gold_name), 0.0)
                silver_sc = silver["score"]
                if gold_sc > 0 and silver_sc / gold_sc >= 0.80:
                    m.silver_contender += 1
            sil_dec = _parse_odds(odds_map.get(silver_name, ""))
            if sil_dec is None or sil_dec <= 34.0:
                m.silver_mkt_backed += 1

        # ── Dark Horse ────────────────────────────────────────────────────
        if not dark:
            m.dark_none += 1
        else:
            if gold_name and dark_name == gold_name:
                m.dark_clash += 1
            if silver_name and dark_name == silver_name:
                m.dark_clash += 1

        # ── Hard invariant: Gold ≠ Silver ─────────────────────────────────
        if gold_name and silver_name and gold_name == silver_name:
            m.gold_silver_same += 1

        # ── Tipster-logic impact vs raw-rank baseline ─────────────────────
        if ranks:
            old_gold_name, old_silver_name = _old_gold_silver(ranks)

            # Gold change
            if gold_name != old_gold_name:
                m.gold_changed += 1
                # Check if bypass fired: old rank-1 was extreme outsider,
                # new gold is market-backed
                if old_gold_name:
                    og_dec = _parse_odds(odds_map.get(old_gold_name, ""))
                    if og_dec is not None and og_dec >= 67.0:
                        m.bypass_triggered += 1
                        if gold:
                            ng_dec = _parse_odds(odds_map.get(gold_name, ""))
                            if ng_dec is None or ng_dec < 67.0:
                                m.bypass_to_mkt_backed += 1

            # Silver change
            if silver_name != old_silver_name:
                m.silver_changed += 1
                # Check if new selection has a better ratio than old
                if gold_name and silver and old_silver_name:
                    gold_sc   = next((h["score"] for h in ranks
                                      if h["name"] == gold_name), 0.0)
                    new_sc    = silver["score"]
                    old_entry = next((h for h in ranks
                                      if h["name"] == old_silver_name), None)
                    if old_entry and gold_sc > 0:
                        new_ratio = new_sc / gold_sc
                        old_ratio = old_entry["score"] / gold_sc
                        if new_ratio >= old_ratio:
                            m.silver_ratio_improved += 1

    return m


# ─────────────────────────────────────────────────────────────────────────────
# LEAKAGE VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def leakage_check(engine: RacingAICore) -> bool:
    """
    Verify that Wet Jumps mode never fires for Flat or Dry-ground races.
    Returns True if no leakage detected.
    """
    from racing_ai_core import _is_wet_jumps, classify_wet_dry

    cases = [
        # (description, discipline, going, expected_wet_jumps)
        ("Flat + soft",         "Flat",  "soft",         False),
        ("Flat + heavy",        "Flat",  "heavy",        False),
        ("Flat + good",         "Flat",  "good",         False),
        ("Jumps + good",        "Jumps", "good",         False),
        ("Jumps + good to firm","Jumps", "good to firm", False),
        ("Jumps + soft",        "Jumps", "soft",         True),
        ("Jumps + heavy",       "Jumps", "heavy",        True),
        ("Jumps + yielding",    "Jumps", "yielding",     True),
        ("Jumps + very soft",   "Jumps", "very soft",    True),
    ]

    all_ok = True
    rows = []
    for desc, discipl, going, expected in cases:
        bucket = classify_wet_dry(going)
        race = RaceInfo(
            course="Cheltenham", country="uk",
            race_type=("national_hunt" if discipl == "Jumps" else "flat"),
            surface="Turf", distance_f=16, going=going,
            runners=8, ground_bucket=bucket, discipline=discipl,
        )
        actual = _is_wet_jumps(race)
        ok = actual == expected
        if not ok:
            all_ok = False
        rows.append((desc, expected, actual, "✓" if ok else "⚠ FAIL"))

    print("\n  ── Wet Jumps leakage check ───────────────────────────────────────")
    print(f"  {'Scenario':<28} {'Expected':<8} {'Got':<8} {'Status'}")
    print(f"  {'-'*28} {'-'*8} {'-'*8} {'-'*6}")
    for desc, exp, got, status in rows:
        print(f"  {desc:<28} {str(exp):<8} {str(got):<8} {status}")
    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def _pct(n, d):
    return f"{100*n/d:.1f}%" if d else "n/a"


def print_ctx(m: CtxMetrics) -> bool:
    v = m.total
    print(f"\n  {'─'*62}")
    print(f"  Context: {m.label}")
    print(f"  {'─'*62}")

    # Health
    print(f"    Races completed      : {v}  (errors: {m.errors})")

    # Wet Jumps activation (only meaningful for Jumps contexts)
    if "Jumps" in m.label:
        wj_pct = _pct(m.wet_jmp_active, v)
        print(f"    Wet Jumps activated  : {m.wet_jmp_active}/{v}  ({wj_pct})")
        if "Wet" in m.label:
            activated_ok = m.wet_jmp_active == v
            suffix = "  ✓ all races" if activated_ok else "  ⚠ should be 100%"
            print(f"      → expected 100% for Wet Jumps context{suffix}")
        else:
            leaked = m.wet_jmp_active > 0
            suffix = "  ⚠ LEAKAGE DETECTED" if leaked else "  ✓ no leakage"
            print(f"      → expected 0 for Dry Jumps context{suffix}")

    # Confidence distribution
    buckets = ["0", "1-2", "3-4", "5-7", "8+"]
    total_ded = sum(m.ded_buckets.values())
    print(f"    Confidence dist (ded): ", end="")
    parts = [f"[{b}]={_pct(m.ded_buckets.get(b, 0), total_ded)}"
             for b in buckets if m.ded_buckets.get(b, 0) > 0]
    print("  ".join(parts) if parts else "n/a")

    # Gold behaviour
    print(f"    Gold selected        : {v - m.gold_none}/{v}  ({_pct(v-m.gold_none, v)})")
    gold_races = v - m.gold_none
    if gold_races:
        print(f"      is favourite (≤9/2)  : {m.gold_is_fav}/{gold_races}  ({_pct(m.gold_is_fav, gold_races)})")
        print(f"      in top-3 model rank  : {m.gold_top3}/{gold_races}  ({_pct(m.gold_top3, gold_races)})")
        print(f"      is outsider (>10/1)  : {m.gold_outsider}/{gold_races}  ({_pct(m.gold_outsider, gold_races)})")

    # Silver behaviour
    sil_races = v - m.silver_none
    print(f"    Silver selected      : {sil_races}/{v}  ({_pct(sil_races, v)})")
    if sil_races:
        print(f"      contender (≥80% Gold): {m.silver_contender}/{sil_races}  ({_pct(m.silver_contender, sil_races)})")
        print(f"      market-backed (≤33/1): {m.silver_mkt_backed}/{sil_races}  ({_pct(m.silver_mkt_backed, sil_races)})")

    # Dark Horse
    dark_races = v - m.dark_none
    ok = "✓" if m.dark_clash == 0 else "⚠"
    print(f"    Dark Horse selected  : {dark_races}/{v}  — clashes: {ok} {m.dark_clash}")

    # Hard invariants
    ok = "✓" if m.gold_silver_same == 0 else "⚠"
    print(f"    Gold ≠ Silver        : {ok} ({m.gold_silver_same} violations / {v})")

    # Tipster-logic impact
    print(f"    Tipster-logic impact vs raw-rank baseline:")
    print(f"      Gold changed       : {m.gold_changed}/{v}  ({_pct(m.gold_changed, v)})")
    if m.bypass_triggered:
        print(f"        Outsider bypass  : fired {m.bypass_triggered}x  →  "
              f"picked mkt-backed {m.bypass_to_mkt_backed}x "
              f"({_pct(m.bypass_to_mkt_backed, m.bypass_triggered)})")
    print(f"      Silver changed     : {m.silver_changed}/{v}  ({_pct(m.silver_changed, v)})")
    if m.silver_changed:
        print(f"        Ratio improved   : {m.silver_ratio_improved}/{m.silver_changed}  "
              f"({_pct(m.silver_ratio_improved, m.silver_changed)})")

    # Pass/fail
    hard_ok = (m.errors == 0 and m.gold_silver_same == 0 and m.dark_clash == 0)
    print(f"    → {'ALL HARD CHECKS PASS ✓' if hard_ok else 'ISSUES DETECTED ⚠ — see above'}")
    return hard_ok


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    engine = RacingAICore()

    print(f"\n{'='*66}")
    print(f"  PeakPace AI — Full 4-Context Validation  ({RACES_PER_CONTEXT} races each)")
    print(f"{'='*66}")

    # Dataset sizes
    print(f"\n  Dataset sizes loaded:")
    print(f"    Jumps horses   : {len(_HORSES_JUMP)}")
    print(f"    Jumps trainers : {len(_TRAINERS_JUMP)}")
    print(f"    Jumps jockeys  : {len(_JOCKEYS_JUMP)}")
    print(f"    Flat horses    : {len(_HORSES_FLAT)}")
    print(f"    Flat trainers  : {len(_TRAINERS_FLAT)}")
    print(f"    Flat jockeys   : {len(_JOCKEYS_FLAT)}")

    contexts = [
        ("Flat / Dry",  "Flat",  _DRY_FLAT_GOINGS, _FLAT_DISTS,
         _HORSES_FLAT, _TRAINERS_FLAT, _JOCKEYS_FLAT),
        ("Flat / Wet",  "Flat",  _WET_FLAT_GOINGS, _FLAT_DISTS,
         _HORSES_FLAT, _TRAINERS_FLAT, _JOCKEYS_FLAT),
        ("Jumps / Dry", "Jumps", _DRY_JUMP_GOINGS, _JUMP_DISTS,
         _HORSES_JUMP, _TRAINERS_JUMP, _JOCKEYS_JUMP),
        ("Jumps / Wet", "Jumps", _WET_JUMP_GOINGS, _JUMP_DISTS,
         _HORSES_JUMP, _TRAINERS_JUMP, _JOCKEYS_JUMP),
    ]

    results = []
    for label, discipl, going_pool, dist_pool, horses, trainers, jockeys in contexts:
        print(f"\n  Running: {label} ...", end="", flush=True)
        m = run_context(label, discipl, going_pool, dist_pool,
                        horses, trainers, jockeys, engine)
        results.append(m)
        print(f"  done ({m.total} races, {m.errors} errors)")

    # Per-context detailed report
    all_pass = True
    for m in results:
        ok = print_ctx(m)
        all_pass = all_pass and ok

    # Leakage verification
    leakage_ok = leakage_check(engine)
    all_pass = all_pass and leakage_ok

    # Overall summary
    print(f"\n{'='*66}")
    print(f"  OVERALL: {'ALL CHECKS PASS ✓' if all_pass else 'ISSUES DETECTED ⚠'}")
    total_races = sum(m.total for m in results)
    total_errors = sum(m.errors for m in results)
    print(f"  Total races: {total_races}  |  Total errors: {total_errors}")
    print(f"{'='*66}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
