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


def _parse_odds(raw: str) -> Optional[float]:
    """Convert fractional or decimal odds string to a decimal float.

    "9/1"  → 10.0  |  "6/4"  → 2.5  |  "evs" → 2.0  |  "10.0" → 10.0
    Returns None if the string cannot be parsed.
    """
    s = str(raw).strip().lower()
    if s in ("evs", "evens", "1/1"):
        return 2.0
    if "/" in s:
        parts = s.split("/")
        try:
            num, den = float(parts[0]), float(parts[1])
            return round(num / den + 1, 4) if den != 0 else None
        except ValueError:
            return None
    try:
        val = float(s)
        return val if val >= 1.01 else None
    except ValueError:
        return None


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

# Going conditions considered testing (used for going confidence penalty)
_TESTING_GOING = frozenset({"heavy", "soft", "good to soft"})

# Matches country suffixes appended to horse names on racecards, e.g. (IRE), (GB)
_COUNTRY_SUFFIX_RE = re.compile(
    r"\s*\((?:ire|gb|fr|usa|ger|nz|aus|can|spa|ity|por)\)\s*$",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """Normalize a horse name for dictionary lookups.

    Strips country suffixes like (IRE), (GB), (FR) that appear on racecards
    but are absent from the stats/ratings files, then lowercases and trims.
    """
    n = _COUNTRY_SUFFIX_RE.sub("", name).strip().lower()
    return n


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
    "Irish Trainers Stats Flat 2024 and 2025 and 2026.txt",
)
_TRAINER_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "Irish Trainers Stats National Hunt (Jumps) 2024 and 2025 and 2026.txt",
)

_JOCKEY_DATA_FLAT: Dict[str, float] = _build_people_multipliers(
    "Irish Jockeys Stats Flat 2024 and 2025.txt",
)
_JOCKEY_DATA_NH: Dict[str, float] = _build_people_multipliers(
    "Irish Jockeys Stats National Hunt 2024 and 2025 and 2026.txt",
)

_HORSE_RATINGS_FLAT: Dict[str, int] = _parse_ratings_file(
    "Irish Horse Ratings For Flat Racing - Engine Format.txt"
)
_HORSE_RATINGS_NH: Dict[str, int] = _parse_ratings_file(
    "Irish Horse Ratings For National Hunt Racing (Jumps) - Engine Format.txt"
)

_HORSE_STATS_FLAT: Dict[str, dict] = _parse_stats_file(
    "Irish Horses Flat 2024 and 2025 - Engine Format.txt"
)
_HORSE_STATS_NH: Dict[str, dict] = _parse_stats_file(
    "Irish Horses National Hunt (Jumps) 2024 and 2025 and 2026 - Engine Format.txt"
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
        name = _normalize_name(horse_name)
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
        name = _normalize_name(horse_name)
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
        # In racing form strings, 0 means finished 10th or worse (unplaced).
        # Treat it as 10 so bad form doesn't score better than a 1st.
        digits = [10 if c == "0" else int(c) for c in form if c.isdigit()]
        if not digits:
            return 0.5

        avg = statistics.mean(digits)
        score = max(0.3, 1.2 - (avg * 0.12))

        # Improving trend bonus — only when last run is genuinely better
        if len(digits) >= 2 and digits[-1] < digits[-2]:
            score *= 1.05

        return score

    # --------------------------------------------------------
    # WEIGHT SCORE
    # --------------------------------------------------------
    def weight_score(self, runner: Runner) -> float:
        net_weight = runner.weight_lbs - runner.jockey_claim_lbs
        # Cap at 1.12 so a very light weight cannot inflate the score
        # beyond a realistic +12% advantage.
        return min(1.12, max(0.75, 1.2 - ((net_weight - 126) * 0.01)))

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
        The deduction also drives adaptive racecard weighting and a direct
        score penalty in analyze(), so unknown horses rank lower and are
        deprioritised for Gold/Silver picks.
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
        name = _normalize_name(horse_name)
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
    def _build_writeup(
        form: float,
        trainer_b: float, jockey_b: float, combo_b: float,
        structural: float, fitness: float,
        rating_boost: float, perf_boost: float,
        conf_deduction: int = 0,
        going_penalty: int = 0,
        rating_edge: float = 0.0,
    ) -> str:
        """Generate a 1–2 sentence Racing Post-style writeup from scoring factors.

        Sentence 1 — strongest positive reasons (up to 2 factors).
        Sentence 2 — uncertainty caveat when confidence was reduced.
        Score and ranking are never referenced; only analytical factors.
        """
        strengths = []

        # Form
        if form >= 0.95:
            strengths.append("strong recent form")
        elif form >= 0.75:
            strengths.append("solid form figures")

        # Official rating
        if rating_boost >= 1.05:
            strengths.append("high official rating")
        elif rating_boost >= 1.02:
            strengths.append("solid official rating")

        # Connections — most specific descriptor first
        if combo_b > 1.0:
            strengths.append("proven trainer/jockey partnership")
        elif trainer_b >= 1.07:
            strengths.append("in-form training operation")
        elif jockey_b >= 1.06:
            strengths.append("top jockey booking")
        elif trainer_b >= 1.04 or jockey_b >= 1.04:
            strengths.append("positive connections")

        # Historical performance
        if perf_boost >= 1.05:
            strengths.append("strong winning record")
        elif perf_boost >= 1.02:
            strengths.append("decent win rate")

        # Weight / structural
        if structural >= 1.08:
            strengths.append("favourable weight")

        # Age / fitness
        if fitness >= 1.04:
            strengths.append("prime age profile")

        # Fallback concerns (used only when no strengths)
        weight_concern = structural <= 0.82
        form_concern = form < 0.50

        # --- Sentence 1: primary assessment ---
        if strengths:
            top = strengths[:2]
            if len(top) == 1:
                sentence1 = top[0].capitalize() + "."
            else:
                sentence1 = (top[0].capitalize() + " alongside "
                             + top[1] + ".")
        elif weight_concern:
            sentence1 = "Carries a significant weight burden."
        elif form_concern:
            sentence1 = "Recent form figures are a concern."
        else:
            sentence1 = "Limited historical data available for assessment."

        # --- Sentence 2: uncertainty caveats ---
        unc_parts = []
        if conf_deduction >= 5:
            unc_parts.append("Confidence notably reduced due to limited profile data")
        elif conf_deduction >= 2:
            unc_parts.append("Confidence slightly reduced due to limited profile data")
        if going_penalty > 0:
            unc_parts.append("testing ground adds further uncertainty")

        if unc_parts:
            unc = unc_parts[0]
            if len(unc_parts) > 1:
                unc += "; " + unc_parts[1]
            return sentence1 + " " + unc + "."

        # Field-strength context phrase (only when no uncertainty sentence)
        if rating_edge >= 5:
            return sentence1 + " Holds a clear ratings edge over this field."
        if rating_edge <= -5:
            return sentence1 + " Faces stronger opposition on ratings."

        # Minor concern note when no other second sentence
        if weight_concern and strengths:
            return sentence1 + " Weight burden may be a factor."
        if form_concern and strengths:
            return sentence1 + " Form is worth monitoring."

        return sentence1

    # --------------------------------------------------------
    # GOING / GROUND CONFIDENCE PENALTY
    # --------------------------------------------------------
    def _going_penalty(self, runner: Runner, going: str,
                       race_type: str = "", country: str = "") -> int:
        """Confidence deduction when going is testing (soft/heavy/good-to-soft).

        Also applies a small score reduction in the caller.
        Deductions (max combined 5):
          +2  horse has fewer than 10 career runs (inexperience on testing ground)
               OR has no historical stats at all
          +3  horse carries more than 135 lbs net (heavy burden harder on soft)
        """
        if going.lower().strip() not in _TESTING_GOING:
            return 0

        penalty = 0
        name = _normalize_name(runner.name)
        uk = _is_uk(country)
        is_nh_flag = _is_nh(race_type)

        # Look up career run count from stats files
        if uk:
            stats = (_UK_HORSE_STATS_NH if is_nh_flag
                     else _UK_HORSE_STATS_FLAT).get(name)
        else:
            stats = (_HORSE_STATS_NH if is_nh_flag
                     else _HORSE_STATS_FLAT).get(name)

        # No data at all, or fewer than 10 career runs → uncertain on testing ground
        if stats is None or stats["runs"] < 10:
            penalty += 2

        # High net weight is a greater physical burden on soft/heavy ground
        net_weight = runner.weight_lbs - runner.jockey_claim_lbs
        if net_weight > 135:
            penalty += 3

        return min(penalty, 5)

    # --------------------------------------------------------
    # RAW RATING LOOKUP (for field-context calculation)
    # --------------------------------------------------------
    def _get_horse_rating(self, horse_name: str, race_type: str,
                          country: str = "") -> Optional[int]:
        """Return the raw official rating integer for a horse, or None.

        Reuses the same rating dicts as horse_rating_boost() — no new data.
        Used only for the field-average context layer; never alters scoring.
        """
        name = _normalize_name(horse_name)
        uk = _is_uk(country)
        if uk:
            return (_UK_HORSE_RATINGS_NH if _is_nh(race_type)
                    else _UK_HORSE_RATINGS_FLAT).get(name)
        return (_HORSE_RATINGS_NH if _is_nh(race_type)
                else _HORSE_RATINGS_FLAT).get(name)

    # --------------------------------------------------------
    # RACE QUALITY CHECK  (pre-analysis, multi-signal)
    # --------------------------------------------------------
    def race_quality_check(self, race: RaceInfo,
                           runners: List[Runner]) -> dict:
        """Five-signal pre-analysis quality gate.

        Each signal scores 0–3.  Total 0–15:
          HIGH   = 11+   well-documented, analysable race
          MEDIUM = 7–10  enough signal, some gaps
          LOW    = 0–6   limited data, treat picks with caution

        Signals
        -------
        data_coverage   % of field with trainer + jockey in our data
        form_quality    % of field with ≥2 recorded form results
        field_size      sweet spot is 6–12 runners
        race_type       flat > NH for modelling confidence
        field_richness  runners with at least one traceable signal
                        (trainer OR jockey known) AND ≥1 form digit
        """
        n = len(runners)
        if n == 0:
            return {
                "level": "LOW",
                "headline": "No runners found.",
                "total_score": 0,
                "signals": {},
            }

        # ── Signal 1: Data coverage ──────────────────────────────────
        # Partial credit (0.5) for runners missing only one source.
        known: float = 0.0
        for r in runners:
            ded = self._confidence_deduction(
                r.trainer, r.jockey, r.name, race.race_type, race.country)
            if ded == 0:
                known += 1.0
            elif ded <= 2:
                known += 0.5
        cov_pct = known / n
        if cov_pct >= 0.80:
            data_s, data_l = 3, "Strong data coverage across the field"
        elif cov_pct >= 0.55:
            data_s, data_l = 2, "Decent coverage — a few runners untracked"
        elif cov_pct >= 0.35:
            data_s, data_l = 1, "Patchy data — several runners untracked"
        else:
            data_s, data_l = 0, "Limited data across most of the field"

        # ── Signal 2: Form quality ────────────────────────────────────
        form_rich = sum(
            1 for r in runners
            if len([c for c in (r.form or "") if c.isdigit()]) >= 2
        )
        form_pct = form_rich / n
        if form_pct >= 0.70:
            form_s, form_l = 3, "Good form figures available across the field"
        elif form_pct >= 0.50:
            form_s, form_l = 2, "Reasonable form data for most runners"
        elif form_pct >= 0.30:
            form_s, form_l = 1, "Thin form — limited runs to compare"
        else:
            form_s, form_l = 0, "Very sparse form — most runners unraced or unknown"

        # ── Signal 3: Field size ──────────────────────────────────────
        if 6 <= n <= 12:
            size_s, size_l = 3, f"Good field size ({n} runners)"
        elif 4 <= n <= 5 or 13 <= n <= 16:
            size_s, size_l = 2, f"Workable field size ({n} runners)"
        elif 2 <= n <= 3 or 17 <= n <= 20:
            size_s, size_l = 1, f"Edge-case field size ({n} runners)"
        else:
            size_s, size_l = 0, f"Very large field ({n} runners) — difficult to model"

        # ── Signal 4: Race type ───────────────────────────────────────
        is_nh = _is_nh(race.race_type)
        if not is_nh:
            type_s, type_l = 3, "Flat race — well-structured for modelling"
        elif _is_uk(race.country):
            type_s, type_l = 2, "National Hunt — solid UK data available"
        else:
            type_s, type_l = 1, "National Hunt — more variance than flat"

        # ── Signal 5: Mixed signal richness ──────────────────────────
        # Runners where at least trainer/jockey is known AND form exists.
        rich = sum(
            1 for r in runners
            if (
                self._confidence_deduction(
                    r.trainer, r.jockey, r.name,
                    race.race_type, race.country) < 5
                and len([c for c in (r.form or "") if c.isdigit()]) >= 1
            )
        )
        rich_pct = rich / n
        if rich_pct >= 0.65:
            rich_s, rich_l = 3, "Most runners have traceable signals"
        elif rich_pct >= 0.40:
            rich_s, rich_l = 2, "A core group of runners have enough signal"
        elif rich_pct >= 0.20:
            rich_s, rich_l = 1, "Only a handful of runners have usable signal"
        else:
            rich_s, rich_l = 0, "Very few runners have any traceable signal"

        total = data_s + form_s + size_s + type_s + rich_s

        if total >= 11:
            level = "HIGH"
            headline = "This looks like a well-documented, analysable race."
        elif total >= 7:
            level = "MEDIUM"
            headline = "Enough signal to analyse, but some gaps in the data."
        else:
            level = "LOW"
            headline = "Limited data across this field — treat picks with caution."

        return {
            "level":       level,
            "headline":    headline,
            "total_score": total,
            "signals": {
                "data_coverage":  {"score": data_s, "label": data_l},
                "form_quality":   {"score": form_s, "label": form_l},
                "field_size":     {"score": size_s, "label": size_l},
                "race_type":      {"score": type_s, "label": type_l},
                "field_richness": {"score": rich_s, "label": rich_l},
            },
        }

    # --------------------------------------------------------
    # MAIN ANALYSIS
    # --------------------------------------------------------
    def analyze(self, race: RaceInfo, runners: List[Runner],
                odds: Optional[Dict[str, str]] = None):

        scored = []

        for r in runners:

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

            # Data quality check done early so it drives both weighting and
            # the score penalty below.
            conf_deduction = self._confidence_deduction(
                r.trainer, r.jockey, r.name, race.race_type, race.country)

            # Option 3 — Form quality: how many numeric results are in the string.
            # A horse with no or single-run form gets reduced weight on that
            # factor; the surplus is redistributed to structural/fitness so a
            # blank form string can't pad the score for an unknown horse.
            _form_digits = [c for c in (r.form or "") if c.isdigit()]
            form_quality = min(1.0, len(_form_digits) / 2)  # 0=none 0.5=1-run 1=2+

            # Adaptive racecard weights: when historical data is sparse, shift
            # weight toward observable racecard factors (form, age, weight).
            # Full data → standard split.  Partial gap → moderate shift.
            # Severely limited → maximise racecard factor influence.
            if conf_deduction >= 5:
                w_base, w_form, w_age, w_wt = 0.05, 0.50, 0.23, 0.22
            elif conf_deduction >= 2:
                w_base, w_form, w_age, w_wt = 0.15, 0.42, 0.22, 0.21
            else:
                w_base, w_form, w_age, w_wt = 0.25, 0.35, 0.20, 0.20

            # Thin form: redistribute unused form weight to structural factors.
            if form_quality < 1.0:
                _surplus = w_form * (1.0 - form_quality)
                w_form -= _surplus
                w_wt   += _surplus * 0.55
                w_age  += _surplus * 0.45

            final_score = (
                1.0    * w_base +
                form   * w_form +
                age    * w_age +
                weight * w_wt
            )

            final_score *= trainer
            final_score *= jockey
            final_score *= combo
            final_score *= rating
            final_score *= perf

            # Score penalty for missing data: pushes unknown horses down the
            # ranking so well-documented runners are preferred for top picks.
            # 1.5% per deduction point, floor at 0.88 (~12% max reduction).
            if conf_deduction > 0:
                final_score *= max(0.88, 1.0 - conf_deduction * 0.015)

            going_pen = self._going_penalty(r, race.going, race.race_type,
                                            race.country)
            # Score reduction for testing ground: 1% per penalty point,
            # floor at 0.95 (~5% max reduction on score).
            if going_pen > 0:
                final_score *= max(0.95, 1.0 - going_pen * 0.01)
            confidence = min(95, max(70, int(final_score * 80)
                                     - conf_deduction - going_pen))

            conn = round(trainer * jockey * combo, 3)
            raw_rating = self._get_horse_rating(r.name, race.race_type,
                                                race.country)
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
                "_trainer_b":  trainer,
                "_jockey_b":   jockey,
                "_combo_b":    combo,
                "_conf_ded":   conf_deduction,
                "_going_pen":  going_pen,
                "_raw_rating": raw_rating,   # raw int or None
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # ── Odds corroboration ───────────────────────────────────────────────
        # When odds are provided (low-confidence races), the market acts as a
        # second opinion.  Odds never change final_score or sort order — they
        # only adjust displayed confidence and attach a market_flag so the
        # writeup can reference agreement or disagreement.
        odds_decimal: dict = {}
        if odds:
            for _oname, _oraw in odds.items():
                _dec = _parse_odds(_oraw)
                if _dec is not None:
                    odds_decimal[_oname.lower().strip()] = _dec

        if odds_decimal:
            _mkt_sorted = sorted(
                scored,
                key=lambda h: odds_decimal.get(h["name"].lower().strip(), 9999.0),
            )
            _mkt_rank = {h["name"]: i for i, h in enumerate(_mkt_sorted)}
            for _mrank, _horse in enumerate(scored):
                _dec = odds_decimal.get(_horse["name"].lower().strip())
                if _dec is None:
                    continue
                _mpos = _mkt_rank.get(_horse["name"], len(scored))
                if _mrank == 0:
                    if _dec > 51.0:           # 50/1+ — market strongly disagrees
                        _horse["confidence"] = max(70, _horse["confidence"] - 5)
                        _horse["market_flag"] = "model_vs_market"
                    elif _mpos == 0:          # also market favourite — agree
                        _horse["confidence"] = min(95, _horse["confidence"] + 3)
                        _horse["market_flag"] = "market_confirms"
                    elif _mpos <= 2:          # near-agreement
                        _horse["confidence"] = min(95, _horse["confidence"] + 1)
                        _horse["market_flag"] = "market_near_agreement"
                elif _mrank == 1 and _dec > 51.0:
                    _horse["confidence"] = max(70, _horse["confidence"] - 3)
                    _horse["market_flag"] = "model_vs_market"

        # Field-strength context — confidence ±1 when a horse is clearly
        # above or below the field average on official ratings.
        # Score and sort order are never touched.
        raw_ratings = [e["_raw_rating"] for e in scored
                       if e["_raw_rating"] is not None]
        field_avg = (sum(raw_ratings) / len(raw_ratings)
                     if raw_ratings else None)
        for entry in scored:
            raw_r = entry["_raw_rating"]
            if field_avg is not None and raw_r is not None:
                edge = raw_r - field_avg
                if edge >= 5:
                    entry["confidence"] = min(95, entry["confidence"] + 1)
                elif edge <= -5:
                    entry["confidence"] = max(70, entry["confidence"] - 1)
                entry["_rating_edge"] = round(edge, 1)
            else:
                entry["_rating_edge"] = 0.0

        # Race-level confidence based on percentage lead of top horse over second.
        # Using a relative spread avoids penalising races where absolute scores
        # are compressed (e.g. large, evenly-matched fields).
        race_confidence = "LOW"
        if len(scored) >= 2:
            spread_pct = (
                (scored[0]["score"] - scored[1]["score"]) / scored[1]["score"]
                if scored[1]["score"] > 0 else 0.0
            )
            if spread_pct >= 0.04:      # top horse ≥4% clear → HIGH
                race_confidence = "HIGH"
            elif spread_pct >= 0.012:   # top horse ≥1.2% clear → MEDIUM
                race_confidence = "MEDIUM"
        elif len(scored) == 1:
            race_confidence = "MEDIUM"

        # Helper to build a writeup from a scored entry
        def _wp(entry):
            return self._build_writeup(
                entry["form"],
                entry["_trainer_b"], entry["_jockey_b"], entry["_combo_b"],
                entry["structural"], entry["fitness"],
                entry["_rating_b"], entry["_perf_b"],
                entry["_conf_ded"], entry["_going_pen"],
                entry["_rating_edge"],
            )

        # Picks — prefer horses with sufficient data (conf_deduction < 5).
        # A deduction of 5+ means at least two data sources are missing
        # (e.g. trainer + horse, or trainer + jockey), making the pick
        # little better than a guess.  Falls back to the full sorted list
        # if every runner in the field has limited data.
        _PICK_DED_LIMIT = 5

        def _best_pick(ranked, exclude_names):
            pool = [h for h in ranked if h["name"] not in exclude_names]
            qualified = [h for h in pool if h["_conf_ded"] < _PICK_DED_LIMIT]
            return (qualified or pool or [None])[0]

        gold_entry   = _best_pick(scored, set())
        gold_exclude = {gold_entry["name"]} if gold_entry else set()
        silver_entry = _best_pick(scored, gold_exclude)

        gold   = ({**gold_entry,   "label": "Good E/W Bet",
                   "writeup": _wp(gold_entry)}   if gold_entry   else None)
        silver = ({**silver_entry, "label": "Good Place Bet",
                   "writeup": _wp(silver_entry)} if silver_entry else None)

        gold_name   = gold_entry["name"]   if gold_entry   else None
        silver_name = silver_entry["name"] if silver_entry else None

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
        # Strip all temporary writeup-helper fields from every entry.
        _temp = ("_rating_b", "_perf_b", "_trainer_b", "_jockey_b",
                 "_combo_b", "_conf_ded", "_going_pen",
                 "_raw_rating", "_rating_edge")
        for i, entry in enumerate(scored):
            for f in _temp:
                entry.pop(f, None)
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
                for f in _temp:
                    pick.pop(f, None)

        return {
            "gold_pick":       gold,
            "silver_pick":     silver,
            "dark_horse":      dark,
            "race_confidence": race_confidence,
            "full_rankings":   scored,
        }
