# ============================================================
# PEAKPACE AI — RACING CORE (DATA-DRIVEN VERSION)
# ============================================================

import os
import re
from dataclasses import dataclass
from typing import List, Dict, Optional
import statistics


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class RaceInfo:
    course: str
    country: str
    race_type: str
    surface: str
    distance_f: int
    going: str
    runners: int


@dataclass
class Runner:
    name: str
    age: int
    weight_lbs: int
    form: str
    trainer: str
    jockey: str
    draw: int = None
    jockey_claim_lbs: int = 0


# ============================================================
# DATA LOADING — parse all 8 Irish racing data files
# ============================================================

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _parse_stats_file(filename: str) -> Dict[str, dict]:
    """Parse trainer/jockey/horse stats files.

    Format: Name — Runs (N) | 1st (N) | 2nd (N) | ... | Total Prize Money (€N)
    Returns dict: lowercase name → {runs, wins, prize}
    """
    result = {}
    filepath = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(filepath):
        return result

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "—" not in line:
                continue
            try:
                name_part, stats_part = line.split("—", 1)
                name = name_part.strip().lower()

                runs_m = re.search(r"Runs \((\d+)\)", stats_part)
                wins_m = re.search(r"1st \((\d+)\)", stats_part)
                prize_m = re.search(r"Total Prize Money \(€([\d,]+)\)", stats_part)

                if runs_m and wins_m:
                    runs = int(runs_m.group(1))
                    wins = int(wins_m.group(1))
                    prize = int(prize_m.group(1).replace(",", "")) if prize_m else 0
                    if runs > 0:
                        result[name] = {"runs": runs, "wins": wins, "prize": prize}
            except Exception:
                continue
    return result


def _parse_ratings_file(filename: str) -> Dict[str, int]:
    """Parse horse ratings files.

    Format: Name — Rating (N) | Trainer (Name)
    Returns dict: lowercase name → rating (int)
    """
    result = {}
    filepath = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(filepath):
        return result

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "—" not in line:
                continue
            try:
                name_part, rest = line.split("—", 1)
                name = name_part.strip().lower()
                rating_m = re.search(r"Rating \((\d+)\)", rest)
                if rating_m:
                    result[name] = int(rating_m.group(1))
            except Exception:
                continue
    return result


def _win_rate_to_multiplier(wins: int, runs: int) -> float:
    """Convert wins/runs to a score multiplier.

    Baseline win rate ~10%. Each +10% above baseline adds +0.045.
    Capped at 1.12. Sample-size penalty for fewer than 20 runs.
    """
    if runs == 0:
        return 1.0
    win_rate = wins / runs
    raw = 1.0 + min(max(win_rate - 0.10, 0.0), 0.30) * 0.45

    # Discount tiny samples
    if runs < 10:
        raw = 1.0 + (raw - 1.0) * 0.4
    elif runs < 20:
        raw = 1.0 + (raw - 1.0) * 0.7

    return round(min(raw, 1.12), 4)


def _build_people_multipliers(filename: str) -> Dict[str, float]:
    """Build a name→multiplier dict from a single stats file."""
    combined = {}
    data = _parse_stats_file(filename)
    for name, d in data.items():
        m = _win_rate_to_multiplier(d["wins"], d["runs"])
        combined[name] = max(combined.get(name, 1.0), m)
    return combined


# ============================================================
# RACE-TYPE CLASSIFIER — used by all lookup methods
# ============================================================

_NH_KEYWORDS = ("hurdle", "chase", "nh", "national hunt", "national_hunt",
                "jump", "bumper", "steeplechase", "hunter chase",
                "cross country", "point-to-point")


def _is_nh(race_type: str) -> bool:
    """Return True when race_type indicates National Hunt / Jumps."""
    if not race_type:
        return False
    rt = race_type.lower()
    return any(k in rt for k in _NH_KEYWORDS)


# ============================================================
# DATA LOADING — explicit Flat vs National Hunt separation
# ============================================================

# ---------- IRISH ----------
_TRAINER_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "Irish Trainers Stats Flat 2025 and 2026.txt",
)
_TRAINER_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "Irish Trainers Stats National Hunt 2025 and 2026.txt",
)

_JOCKEY_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "Irish Jockeys Stats Flat 2025.txt",
)
_JOCKEY_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "Irish Jockeys Stats National Hunt 2025 and 2026.txt",
)

_HORSE_RATINGS_FLAT: Dict[str, int] = _parse_ratings_file(
    "Irish Horses Flat Ratings - Engine Format.txt"
)
_HORSE_RATINGS_NH: Dict[str, int] = _parse_ratings_file(
    "Irish Horses National Hunt Ratings - Engine Format.txt"
)

_HORSE_STATS_FLAT: Dict[str, dict] = _parse_stats_file("Irish Horses Flat 2025.txt")
_HORSE_STATS_NH: Dict[str, dict] = _parse_stats_file(
    "Irish Horses National Hunt 2025 and 2026.txt"
)

# ---------- UK (loaded when files exist; empty dict otherwise) ----------
_UK_TRAINER_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "UK_Trainers_Flat_clean.txt",
)
_UK_TRAINER_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "UK_Trainers_Jumps_clean.txt",
)

_UK_JOCKEY_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "UK_Jockeys_Flat_clean.txt",
)
_UK_JOCKEY_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "UK_Jockeys_Jumps_clean.txt",
)

_UK_HORSE_RATINGS_FLAT: Dict[str, int] = _parse_ratings_file(
    "UK_Ratings_Flat_Top500.txt"
)
_UK_HORSE_RATINGS_NH: Dict[str, int] = _parse_ratings_file(
    "UK_Ratings_Jumps_Top500.txt"
)

_UK_HORSE_STATS_FLAT: Dict[str, dict] = _parse_stats_file(
    "UK_Horses_Flat_2024_2025_2026_clean.txt"
)
_UK_HORSE_STATS_NH: Dict[str, dict] = _parse_stats_file(
    "UK_Horses_Jumps_2024_2025_2026_clean.txt"
)


# ============================================================
# COUNTRY CLASSIFIER
# ============================================================

def _is_uk(country: str) -> bool:
    """Return True when the race is in the UK (not Ireland)."""
    if not country:
        return False
    c = country.lower().strip()
    if c in ("ireland", "ire", "ie", "irish"):
        return False
    # Anything else (uk, gb, england, scotland, wales, etc.) → UK
    return True


# ============================================================
# TRAINER + JOCKEY COMBO BOOSTS
# (data-backed key pairings)
# ============================================================

TRAINER_JOCKEY_COMBOS = {
    ("a.p. o'brien", "ryan moore"):           1.08,
    ("w.p. mullins", "paul townend"):          1.08,
    ("w.p. mullins", "p. townend"):            1.08,
    ("w.p. mullins", "p.w. mullins"):          1.06,
    ("gordon elliott", "jack kennedy"):        1.06,
    ("gordon elliott", "j.w. kennedy"):        1.06,
    ("dan skelton", "harry skelton"):          1.06,
    ("paul nicholls", "harry cobden"):         1.06,
    ("john & thady gosden", "william buick"): 1.05,
    ("joseph patrick o'brien", "m.p. walsh"): 1.04,
    ("henry de bromhead", "rachael blackmore"): 1.05,
}


# ============================================================
# UK TRAINER / JOCKEY HARDCODED FALLBACK
# (used for UK races only, when name is not in UK data files)
# ============================================================

_UK_TRAINER_FALLBACK: Dict[str, float] = {
    "dan skelton":           1.08,
    "paul nicholls":         1.08,
    "nicky henderson":       1.07,
    "olly murphy":           1.06,
    "ben pauling":           1.06,
    "joe tizzard":           1.05,
    "nigel twiston-davies":  1.05,
    "jamie snowden":         1.04,
    "fergal o'brien":        1.05,
    "john & thady gosden":   1.08,
    "andrew balding":        1.07,
    "richard hannon":        1.06,
    "charlie johnston":      1.05,
    "james tate":            1.05,
    "michael appleby":       1.05,
    "david o'meara":         1.04,
    "k. r. burke":           1.04,
    "richard fahey":         1.04,
    "ed walker":             1.03,
    "david simcock":         1.03,
    "jamie osborne":         1.03,
    "james fanshawe":        1.03,
    "jim goldie":            1.03,
    "archie watson":         1.04,
    "robert cowell":         1.03,
    "anthony honeyball":     1.04,
    "jonjo o'neill":         1.04,
    "harry derham":          1.04,
    "lucinda russell":       1.04,
    "gary moore":            1.03,
    "emma lavelle":          1.03,
    "donald mccain":         1.03,
    "neil mulholland":       1.03,
    "sam thomas":            1.03,
    "alan king":             1.04,
    "venetia williams":      1.04,
    "chris gordon":          1.03,
    "tom lacey":             1.03,
    "warren greatrex":       1.03,
}

_UK_JOCKEY_FALLBACK: Dict[str, float] = {
    "ryan moore":            1.08,
    "william buick":         1.06,
    "dettori":               1.06,
    "james doyle":           1.04,
    "tom marquand":          1.03,
    "danny tudhope":         1.03,
    "hollie doyle":          1.03,
    "harry cobden":          1.05,
    "harry skelton":         1.05,
    "nico de boinville":     1.04,
    "aidan coleman":         1.03,
    "sam twiston-davies":    1.03,
    "rachael blackmore":     1.06,
    "paul townend":          1.07,
    "jack kennedy":          1.06,
    "davy russell":          1.04,
}


# ============================================================
# CORE ENGINE
# ============================================================

class RacingAICore:

    # --------------------------------------------------------
    # TRAINER POWER
    # --------------------------------------------------------
    def trainer_style_boost(self, trainer: str, race_type: str = "",
                            country: str = "") -> float:
        t = trainer.lower().strip()
        uk = _is_uk(country)

        # Select primary dataset by country + race type
        if uk:
            data = _UK_TRAINER_DATA_NH if _is_nh(race_type) else _UK_TRAINER_DATA_FLAT
        else:
            data = _TRAINER_DATA_NH if _is_nh(race_type) else _TRAINER_DATA_FLAT

        # 1. Exact match
        if t in data:
            return data[t]

        # 2. Partial match
        for name, boost in data.items():
            if name in t or t in name:
                return boost

        # 3. UK hardcoded fallback (UK races only)
        if uk:
            if t in _UK_TRAINER_FALLBACK:
                return _UK_TRAINER_FALLBACK[t]
            for name, boost in _UK_TRAINER_FALLBACK.items():
                if name in t or t in name:
                    return boost

        return 1.0

    # --------------------------------------------------------
    # JOCKEY STRENGTH
    # --------------------------------------------------------
    def jockey_boost(self, jockey: str, race_type: str = "",
                     country: str = "") -> float:
        j = jockey.lower().strip()
        uk = _is_uk(country)

        if uk:
            data = _UK_JOCKEY_DATA_NH if _is_nh(race_type) else _UK_JOCKEY_DATA_FLAT
        else:
            data = _JOCKEY_DATA_NH if _is_nh(race_type) else _JOCKEY_DATA_FLAT

        # 1. Exact match
        if j in data:
            return data[j]

        # 2. Partial match
        for name, boost in data.items():
            if name in j or j in name:
                return boost

        # 3. UK hardcoded fallback (UK races only)
        if uk:
            for name, boost in _UK_JOCKEY_FALLBACK.items():
                if name in j:
                    return boost

        return 1.0

    # --------------------------------------------------------
    # TRAINER + JOCKEY CHEMISTRY
    # --------------------------------------------------------
    def combo_boost(self, trainer: str, jockey: str) -> float:
        t = trainer.lower().strip()
        j = jockey.lower().strip()

        for (tt, jj), boost in TRAINER_JOCKEY_COMBOS.items():
            if tt in t and jj in j:
                return boost

        return 1.0

    # --------------------------------------------------------
    # HORSE RATING BOOST
    # --------------------------------------------------------
    def horse_rating_boost(self, horse_name: str, race_type: str,
                           country: str = "") -> float:
        """Look up official rating and convert to a score multiplier.

        Flat ratings (100-126): max +8%.
        NH ratings (140-164): max +8%.
        Uses only the dataset that matches the country + race type.
        """
        name = horse_name.lower().strip()
        uk = _is_uk(country)

        if uk:
            rating = (_UK_HORSE_RATINGS_NH if _is_nh(race_type)
                      else _UK_HORSE_RATINGS_FLAT).get(name)
        else:
            rating = (_HORSE_RATINGS_NH if _is_nh(race_type)
                      else _HORSE_RATINGS_FLAT).get(name)

        if rating is None:
            return 1.0

        if rating <= 130:
            # Flat scale: 100 → 0%, 126 → +8%
            boost = (rating - 100) / 26.0 * 0.08
        else:
            # NH scale: 140 → 0%, 164 → +8%
            boost = (rating - 140) / 24.0 * 0.08

        return round(1.0 + max(0.0, boost), 4)

    # --------------------------------------------------------
    # HORSE PERFORMANCE BOOST
    # --------------------------------------------------------
    def horse_performance_boost(self, horse_name: str, race_type: str = "",
                                country: str = "") -> float:
        """Derive a multiplier from the horse's own win-rate in stats files."""
        name = horse_name.lower().strip()
        uk = _is_uk(country)

        if uk:
            stats = (_UK_HORSE_STATS_NH if _is_nh(race_type)
                     else _UK_HORSE_STATS_FLAT).get(name)
        else:
            stats = (_HORSE_STATS_NH if _is_nh(race_type)
                     else _HORSE_STATS_FLAT).get(name)

        if not stats:
            return 1.0
        return _win_rate_to_multiplier(stats["wins"], stats["runs"])

    # --------------------------------------------------------
    # FORM SCORE
    # --------------------------------------------------------
    def form_score(self, form: str) -> float:
        digits = [int(c) for c in form if c.isdigit()]
        if not digits:
            return 0.5

        avg = statistics.mean(digits)
        score = max(0.3, 1.2 - (avg * 0.12))

        # Improving trend bonus
        if len(digits) >= 2 and digits[-1] < digits[-2]:
            score *= 1.05

        return score

    # --------------------------------------------------------
    # WEIGHT SCORE
    # --------------------------------------------------------
    def weight_score(self, runner: Runner) -> float:
        net_weight = runner.weight_lbs - runner.jockey_claim_lbs
        return max(0.75, 1.2 - ((net_weight - 126) * 0.01))

    # --------------------------------------------------------
    # AGE SCORE
    # --------------------------------------------------------
    def age_score(self, age: int) -> float:
        if 4 <= age <= 6:
            return 1.05
        if age >= 9:
            return 0.95
        return 1.0

    # --------------------------------------------------------
    # CONFIDENCE DEDUCTION FOR MISSING DATA
    # --------------------------------------------------------
    def _confidence_deduction(self, trainer: str, jockey: str,
                              horse_name: str, race_type: str = "",
                              country: str = "") -> int:
        """Return confidence points to deduct when historical data is absent.

        Missing trainer in all sources  → -3 points
        Missing jockey in all sources   → -3 points
        Horse absent from the country/type-
          specific rating AND stats file → -2 points

        Maximum total deduction: 8 points.
        The score itself is never altered; only confidence is reduced.
        """
        deduction = 0
        is_nh = _is_nh(race_type)
        uk = _is_uk(country)

        # Trainer check — country-specific data + UK fallback for UK races
        if uk:
            td = _UK_TRAINER_DATA_NH if is_nh else _UK_TRAINER_DATA_FLAT
        else:
            td = _TRAINER_DATA_NH if is_nh else _TRAINER_DATA_FLAT
        t = trainer.lower().strip()
        trainer_found = (
            t in td
            or any(n in t or t in n for n in td)
        )
        if not trainer_found and uk:
            trainer_found = (
                t in _UK_TRAINER_FALLBACK
                or any(n in t or t in n for n in _UK_TRAINER_FALLBACK)
            )
        if not trainer_found:
            deduction += 3

        # Jockey check
        if uk:
            jd = _UK_JOCKEY_DATA_NH if is_nh else _UK_JOCKEY_DATA_FLAT
        else:
            jd = _JOCKEY_DATA_NH if is_nh else _JOCKEY_DATA_FLAT
        j = jockey.lower().strip()
        jockey_found = (
            j in jd
            or any(n in j or j in n for n in jd)
        )
        if not jockey_found and uk:
            jockey_found = any(n in j for n in _UK_JOCKEY_FALLBACK)
        if not jockey_found:
            deduction += 3

        # Horse check
        name = horse_name.lower().strip()
        if uk:
            rats = _UK_HORSE_RATINGS_NH if is_nh else _UK_HORSE_RATINGS_FLAT
            stats = _UK_HORSE_STATS_NH if is_nh else _UK_HORSE_STATS_FLAT
        else:
            rats = _HORSE_RATINGS_NH if is_nh else _HORSE_RATINGS_FLAT
            stats = _HORSE_STATS_NH if is_nh else _HORSE_STATS_FLAT
        horse_has_data = (
            rats.get(name) is not None
            or stats.get(name) is not None
        )
        if not horse_has_data:
            deduction += 2

        return deduction

    # --------------------------------------------------------
    # AI PICK WRITEUP
    # --------------------------------------------------------
    @staticmethod
    def _build_writeup(form: float, connections: float,
                       structural: float, fitness: float,
                       rating_boost: float, perf_boost: float) -> str:
        """Generate a brief Racing Post-style writeup from scoring factors."""
        parts = []

        if form >= 0.95:
            parts.append("strong recent form")
        elif form >= 0.75:
            parts.append("solid form figures")
        elif form < 0.55:
            parts.append("form is a concern")

        if rating_boost >= 1.04:
            parts.append("high official rating")
        elif rating_boost >= 1.02:
            parts.append("solid rating")

        if connections >= 1.06:
            parts.append("top trainer/jockey combination")
        elif connections >= 1.03:
            parts.append("positive connections")

        if perf_boost >= 1.04:
            parts.append("proven track record")
        elif perf_boost >= 1.02:
            parts.append("decent win record")

        if structural >= 1.05:
            parts.append("weight advantage")
        elif structural <= 0.82:
            parts.append("burdened by weight")

        if fitness >= 1.04:
            parts.append("prime age profile")

        if not parts:
            return "Limited historical data available for assessment."

        if len(parts) == 1:
            return parts[0].capitalize() + "."
        if len(parts) == 2:
            return parts[0].capitalize() + " and " + parts[1] + "."
        return (parts[0].capitalize() + " with " + parts[1]
                + " and " + parts[2] + ".")

    # --------------------------------------------------------
    # MAIN ANALYSIS
    # --------------------------------------------------------
    def analyze(self, race: RaceInfo, runners: List[Runner]):

        scored = []

        for r in runners:

            base = 1.0

            form    = self.form_score(r.form)
            weight  = self.weight_score(r)
            age     = self.age_score(r.age)

            trainer = self.trainer_style_boost(r.trainer, race.race_type,
                                                race.country)
            jockey  = self.jockey_boost(r.jockey, race.race_type,
                                        race.country)
            combo   = self.combo_boost(r.trainer, r.jockey)
            rating  = self.horse_rating_boost(r.name, race.race_type,
                                              race.country)
            perf    = self.horse_performance_boost(r.name, race.race_type,
                                                   race.country)

            final_score = (
                base   * 0.25 +
                form   * 0.35 +
                age    * 0.20 +
                weight * 0.20
            )

            final_score *= trainer
            final_score *= jockey
            final_score *= combo
            final_score *= rating
            final_score *= perf

            # Clamp confidence to 70–95%.
            # Reduce slightly when trainer, jockey, or horse data is absent —
            # the score is unchanged; we simply lower certainty.
            conf_deduction = self._confidence_deduction(
                r.trainer, r.jockey, r.name, race.race_type, race.country)
            confidence = min(95, max(70, int(final_score * 80) - conf_deduction))

            conn = round(trainer * jockey * combo, 3)
            scored.append({
                "name":        r.name,
                "score":       round(final_score, 3),
                "confidence":  confidence,
                "form":        round(form, 3),
                "connections": conn,
                "structural":  round(weight, 3),
                "fitness":     round(age, 3),
                # Temporary — used for writeups, stripped before return
                "_rating_b":   rating,
                "_perf_b":     perf,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # Race-level confidence based on spread between top two
        race_confidence = "LOW"
        if len(scored) >= 2:
            spread = scored[0]["score"] - scored[1]["score"]
            if spread >= 0.06:
                race_confidence = "HIGH"
            elif spread >= 0.02:
                race_confidence = "MEDIUM"
        elif len(scored) == 1:
            race_confidence = "MEDIUM"

        # Helper to build a writeup from a scored entry
        def _wp(entry):
            return self._build_writeup(
                entry["form"], entry["connections"], entry["structural"],
                entry["fitness"], entry["_rating_b"], entry["_perf_b"],
            )

        # Picks — strictly by ranking position (0 = gold, 1 = silver)
        gold = ({**scored[0], "label": "Good E/W Bet",
                 "writeup": _wp(scored[0])} if scored else None)
        silver = ({**scored[1], "label": "Good Place Bet",
                   "writeup": _wp(scored[1])} if len(scored) > 1 else None)

        gold_name   = scored[0]["name"] if scored else None
        silver_name = scored[1]["name"] if len(scored) > 1 else None

        # Dark horse: lowest-scored runner that is neither gold nor silver
        dark = None
        for candidate in reversed(scored):
            if candidate["name"] != gold_name and candidate["name"] != silver_name:
                dark = {**candidate, "label": "Value Play",
                        "writeup": _wp(candidate)}
                break

        dark_name = dark["name"] if dark else None

        # Embed position-based labels into full_rankings so the UI
        # can read them directly without any score-threshold logic.
        # Strip temporary writeup-helper fields from all entries.
        for i, entry in enumerate(scored):
            entry.pop("_rating_b", None)
            entry.pop("_perf_b", None)
            if i == 0:
                entry["label"] = "Good E/W Bet"
            elif i == 1:
                entry["label"] = "Good Place Bet"
            elif entry["name"] == dark_name:
                entry["label"] = "Value Play"
            else:
                entry["label"] = ""

        # Strip temp fields from picks too (they were spread-copied)
        for pick in (gold, silver, dark):
            if pick:
                pick.pop("_rating_b", None)
                pick.pop("_perf_b", None)

        return {
            "gold_pick":       gold,
            "silver_pick":     silver,
            "dark_horse":      dark,
            "race_confidence": race_confidence,
            "full_rankings":   scored,
        }
