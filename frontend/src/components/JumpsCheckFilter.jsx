import { useState } from "react";

function runJumpsCheck({ numRunners, confidence, scoreGap, topOdds, profileStrength }) {
  if (numRunners < 3) {
    return { status: "OFF", reason: "Fewer than 3 runners — filter not applicable." };
  }
  if (confidence === "high") {
    return { status: "OFF", reason: "HIGH confidence race — top of market is standout enough, no warning needed." };
  }

  const signals = [];

  // Signal 1: score gap between top 2
  if (scoreGap !== "" && parseFloat(scoreGap) < 12) {
    signals.push("Score gap between top 2 is narrow (< 12%) — no clear model standout.");
  }

  // Signal 2: market dominance (top horse implied prob vs. field average)
  if (topOdds !== "" && parseFloat(topOdds) > 1) {
    const topProb = 1 / parseFloat(topOdds);
    const avgProb = 1 / numRunners;
    if (topProb < 2 * avgProb) {
      signals.push("Top market horse is not dominating — implied probability is less than 2× field average.");
    }
  }

  // Signal 3: jumps profile strength of top 2
  if (profileStrength === "weak") {
    signals.push("Neither of the top 2 market horses has a standout jumps profile.");
  }

  if (signals.length >= 2) {
    return {
      status: "ON",
      reason:
        signals.join(" ") +
        " Consider ignoring the top 2 in the market for place / value analysis.",
    };
  }

  return {
    status: "OFF",
    reason:
      signals.length === 1
        ? `One warning signal detected but not enough to trigger filter. Top of market appears broadly sufficient.`
        : "Top of market appears standout enough. No jumps filter advisory triggered.",
  };
}

export default function JumpsCheckFilter() {
  const [numRunners, setNumRunners] = useState("");
  const [confidence, setConfidence] = useState("medium");
  const [scoreGap, setScoreGap] = useState("");
  const [topOdds, setTopOdds] = useState("");
  const [profileStrength, setProfileStrength] = useState("mixed");
  const [checkResult, setCheckResult] = useState(null);

  const canRun = numRunners !== "" && parseInt(numRunners, 10) >= 2;

  const handleRun = () => {
    setCheckResult(
      runJumpsCheck({
        numRunners: parseInt(numRunners, 10) || 0,
        confidence,
        scoreGap,
        topOdds,
        profileStrength,
      })
    );
  };

  const isOn = checkResult?.status === "ON";

  return (
    <section className="bg-surface rounded-xl border border-border p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gold mb-1">Jumps Check Filter</h2>
        <p className="text-text-dim text-sm">
          Quick advisory filter for jumps races. Assess whether the top of the market is
          standout enough, or whether to consider ignoring the top 2 for place / value analysis.
          Advisory only — does not affect rankings or picks.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Number of runners */}
        <div>
          <label className="block text-xs font-medium text-text-dim uppercase tracking-wider mb-1">
            Number of Runners
          </label>
          <input
            type="number"
            min={2}
            max={40}
            placeholder="e.g. 12"
            value={numRunners}
            onChange={(e) => { setNumRunners(e.target.value); setCheckResult(null); }}
            className="w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-gold/60"
          />
        </div>

        {/* Race confidence */}
        <div>
          <label className="block text-xs font-medium text-text-dim uppercase tracking-wider mb-1">
            Your Race Confidence
          </label>
          <select
            value={confidence}
            onChange={(e) => { setConfidence(e.target.value); setCheckResult(null); }}
            className="w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-gold/60"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        {/* Score gap */}
        <div>
          <label className="block text-xs font-medium text-text-dim uppercase tracking-wider mb-1">
            Score Gap Between Top 2 (%)
          </label>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            placeholder="e.g. 8 — leave blank if unknown"
            value={scoreGap}
            onChange={(e) => { setScoreGap(e.target.value); setCheckResult(null); }}
            className="w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-gold/60"
          />
        </div>

        {/* Top horse decimal odds */}
        <div>
          <label className="block text-xs font-medium text-text-dim uppercase tracking-wider mb-1">
            Top Market Horse — Decimal Odds
          </label>
          <input
            type="number"
            min={1}
            step={0.1}
            placeholder="e.g. 3.50 — leave blank if unknown"
            value={topOdds}
            onChange={(e) => { setTopOdds(e.target.value); setCheckResult(null); }}
            className="w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-gold/60"
          />
        </div>

        {/* Jumps profile strength */}
        <div className="sm:col-span-2">
          <label className="block text-xs font-medium text-text-dim uppercase tracking-wider mb-1">
            Top 2 Horses — Jumps Profile Strength
          </label>
          <select
            value={profileStrength}
            onChange={(e) => { setProfileStrength(e.target.value); setCheckResult(null); }}
            className="w-full bg-surface-light border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-gold/60"
          >
            <option value="strong">Strong — both are proven jumps performers</option>
            <option value="mixed">Mixed — one standout, one questionable</option>
            <option value="weak">Weak — neither has a standout jumps profile</option>
          </select>
        </div>
      </div>

      {/* Run button */}
      <div className="flex justify-center">
        <button
          type="button"
          disabled={!canRun}
          onClick={handleRun}
          className="btn-primary px-8 py-2.5 text-sm"
        >
          Run Jumps Check
        </button>
      </div>

      {/* Output block */}
      {checkResult && (
        <div
          className={`rounded-xl border-2 p-4 space-y-3 ${
            isOn
              ? "border-orange-400/70 bg-orange-400/10"
              : "border-gray-600/50 bg-gray-700/20"
          }`}
        >
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-sm font-bold uppercase tracking-wider text-orange-200">
              Jumps Filter Result
            </span>
            <span
              className={`text-sm font-bold uppercase tracking-wider px-3 py-1 rounded border ${
                isOn
                  ? "border-orange-400/60 bg-orange-400/20 text-orange-300"
                  : "border-gray-500/50 bg-gray-500/10 text-gray-400"
              }`}
            >
              {checkResult.status}
            </span>
          </div>
          <p
            className={`text-xs leading-relaxed ${
              isOn ? "text-orange-200 font-medium" : "text-gray-400"
            }`}
          >
            {isOn && "⚠ "}
            {checkResult.reason}
          </p>
          {isOn && (
            <p className="text-orange-300/60 text-xs italic">
              Advisory only — use your own judgement before deciding.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
