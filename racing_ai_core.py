# ============================================================
# PEAKPACE AI — RACING CORE (FULL UPDATED VERSION)
# ============================================================

from dataclasses import dataclass
from typing import List, Dict
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
# TRAINER STRENGTH DATABASE
# (Irish + UK Flat + Jump trainers from your tables)
# ============================================================

TRAINER_STRENGTH = {

    # ===== IRISH ELITE =====
    "w.p. mullins": 1.08,
    "gordon elliott": 1.08,
    "a.p. o'brien": 1.08,
    "joseph patrick o'brien": 1.07,

    # ===== IRISH STRONG =====
    "henry de bromhead": 1.06,
    "gavin cromwell": 1.06,
    "noel meade": 1.05,
    "emmet mullins": 1.05,
    "john c. mcconnell": 1.05,
    "andrew slattery": 1.05,
    "paul w. flynn": 1.04,
    "adrian mcguinness": 1.04,
    "daniel james murphy": 1.04,
    "ross o'sullivan": 1.04,

    # ===== UK JUMPS ELITE =====
    "dan skelton": 1.08,
    "paul nicholls": 1.08,
    "nicky henderson": 1.07,
    "olly murphy": 1.06,
    "ben pauling": 1.06,
    "joe tizzard": 1.05,
    "nigel twiston-davies": 1.05,
    "jamie snowden": 1.04,
    "fergal o'brien": 1.05,

    # ===== UK FLAT ELITE =====
    "john & thady gosden": 1.08,
    "andrew balding": 1.07,
    "richard hannon": 1.06,
    "charlie johnston": 1.05,
    "james tate": 1.05,
    "michael appleby": 1.05,

    # ===== UK FLAT STRONG =====
    "david o'meara": 1.04,
    "k. r. burke": 1.04,
    "richard fahey": 1.04,
    "ed walker": 1.03,
    "david simcock": 1.03,
    "jamie osborne": 1.03,
    "james fanshawe": 1.03,
    "jim goldie": 1.03,
    "archie watson": 1.04,
    "robert cowell": 1.03,

    # ===== UK JUMPS STRONG =====
    "anthony honeyball": 1.04,
    "jonjo o'neill": 1.04,
    "harry derham": 1.04,
    "lucinda russell": 1.04,
    "gary moore": 1.03,
    "emma lavelle": 1.03,
    "donald mccain": 1.03,
    "neil mulholland": 1.03,
    "sam thomas": 1.03,
    "alan king": 1.04,
    "venetia williams": 1.04,
    "chris gordon": 1.03,
    "tom lacey": 1.03,
    "warren greatrex": 1.03,
}


# ============================================================
# TRAINER + JOCKEY COMBO BOOSTS
# ============================================================

TRAINER_JOCKEY_COMBOS = {
    ("a.p. o'brien", "ryan moore"): 1.08,
    ("w.p. mullins", "paul townend"): 1.08,
    ("gordon elliott", "jack kennedy"): 1.06,
    ("dan skelton", "harry skelton"): 1.06,
    ("paul nicholls", "harry cobden"): 1.06,
    ("john & thady gosden", "william buick"): 1.05,
}


# ============================================================
# CORE ENGINE
# ============================================================

class RacingAICore:

    # --------------------------------------------------------
    # TRAINER POWER
    # --------------------------------------------------------
    def trainer_style_boost(self, trainer: str) -> float:
        t = trainer.lower().strip()

        if t in TRAINER_STRENGTH:
            return TRAINER_STRENGTH[t]

        for name, boost in TRAINER_STRENGTH.items():
            if name in t or t in name:
                return boost

        return 1.0

    # --------------------------------------------------------
    # JOCKEY STRENGTH
    # --------------------------------------------------------
    def jockey_boost(self, jockey: str) -> float:
        j = jockey.lower()

        elite = ["ryan moore", "william buick", "dettori", "rachel blackmore"]
        strong = ["james doyle", "tom marquand", "danny tudhope", "hollie doyle"]

        if any(x in j for x in elite):
            return 1.06
        if any(x in j for x in strong):
            return 1.03

        return 1.0

    # --------------------------------------------------------
    # TRAINER + JOCKEY CHEMISTRY
    # --------------------------------------------------------
    def combo_boost(self, trainer, jockey):
        t = trainer.lower().strip()
        j = jockey.lower().strip()

        for (tt, jj), boost in TRAINER_JOCKEY_COMBOS.items():
            if tt in t and jj in j:
                return boost

        return 1.0

    # --------------------------------------------------------
    # FORM SCORE
    # --------------------------------------------------------
    def form_score(self, form: str) -> float:
        digits = [int(c) for c in form if c.isdigit()]
        if not digits:
            return 0.5

        avg = statistics.mean(digits)
        score = max(0.3, 1.2 - (avg * 0.12))

        # improving trend
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
    # MAIN ANALYSIS
    # --------------------------------------------------------
    def analyze(self, race: RaceInfo, runners: List[Runner]):

        scored = []

        for r in runners:

            base = 1.0

            form = self.form_score(r.form)
            weight = self.weight_score(r)
            age = self.age_score(r.age)

            trainer = self.trainer_style_boost(r.trainer)
            jockey = self.jockey_boost(r.jockey)
            combo = self.combo_boost(r.trainer, r.jockey)

            final_score = (
                base * 0.25 +
                form * 0.35 +
                age * 0.20 +
                weight * 0.20
            )

            final_score *= trainer
            final_score *= jockey
            final_score *= combo

            confidence = min(95, int(final_score * 12))

            scored.append({
                "name": r.name,
                "score": round(final_score, 3),
                "confidence": confidence,
                "form": round(form, 3),
                "connections": round(trainer * jockey * combo, 3),
                "structural": round(weight, 3),
                "fitness": round(age, 3),
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        return {
            "gold_pick": scored[0],
            "silver_pick": scored[1] if len(scored) > 1 else None,
            "dark_horse": scored[-1],
            "full_rankings": scored
        }