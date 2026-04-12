import { useState } from "react";

const PICK_CONFIG = {
  GOLD: {
    emoji: "\u{1F947}",
    label: "Gold Pick",
    border: "border-gold/60",
    bg: "bg-gold/10",
    text: "text-gold",
  },
  SILVER: {
    emoji: "\u{1F948}",
    label: "Silver Pick",
    border: "border-gray-400/60",
    bg: "bg-gray-400/10",
    text: "text-gray-300",
  },
  "DARK HORSE": {
    emoji: "\u{1F40E}",
    label: "Dark Horse",
    border: "border-purple-400/60",
    bg: "bg-purple-400/10",
    text: "text-purple-300",
  },
};

export default function ResultsPanel({ result, silverEnabled = false, darkHorseEnabled = false }) {
  const [excludeSilver, setExcludeSilver] = useState(false);
  const [excludeDark, setExcludeDark] = useState(false);

  if (!result) return null;

  // Map backend shape → UI shape
  const goldName   = result.gold_pick?.name;
  const silverName = result.silver_pick?.name;
  const darkName   = result.dark_horse?.name;

  // Silver is shown only when the user asked for it AND the engine returned one.
  const showSilver = silverEnabled && !!result.silver_pick;
  // Dark horse: user asked AND engine returned one. Dedup against Silver only if
  // Silver is actually being rendered, so the same horse doesn't appear twice.
  const showDark =
    darkHorseEnabled &&
    !!result.dark_horse &&
    !(showSilver && darkName === silverName);

  // When a toggle is on but no pick came back, show a subtle message instead of hiding the slot.
  const silverMissing = silverEnabled && !result.silver_pick;
  const darkMissing =
    darkHorseEnabled &&
    (!result.dark_horse || (showSilver && darkName === silverName));

  const allPicks = [
    result.gold_pick && { pick: "GOLD", name: goldName, model_alignment: result.gold_pick.confidence, why: result.gold_pick.label, writeup: result.gold_pick.writeup, market_flag: result.gold_pick.market_flag },
    showSilver && { pick: "SILVER", name: silverName, model_alignment: result.silver_pick.confidence, why: result.silver_pick.label, writeup: result.silver_pick.writeup, market_flag: result.silver_pick.market_flag },
    showDark && { pick: "DARK HORSE", name: darkName, model_alignment: result.dark_horse.confidence, why: result.dark_horse.label, writeup: result.dark_horse.writeup },
  ].filter(Boolean);

  // Display-only exclusion — does NOT affect rankings or scores
  const picks = allPicks.filter((p) => {
    if (p.pick === "SILVER" && excludeSilver) return false;
    if (p.pick === "DARK HORSE" && excludeDark) return false;
    return true;
  });

  const engine_version = "PeakPace v1 [build:7748e38]";
  const note = "Scores are model estimates — always verify with your own analysis.";
  const raceConf = result.race_confidence || null;
  const confStyle = raceConf === "HIGH"
    ? "bg-green-500/20 text-green-300 border-green-500/40"
    : raceConf === "MEDIUM"
    ? "bg-gold/20 text-gold border-gold/40"
    : "bg-gray-500/20 text-gray-300 border-gray-500/40";

  const hasSilver = showSilver;
  const hasDark   = showDark;

  // Exclude controls block — reused below in Jumps section or standalone
  const ExcludeControls = (hasSilver || hasDark) ? (
    <div className="flex flex-wrap gap-3 items-center">
      <span className="text-xs text-text-dim uppercase tracking-wider">Manual exclude:</span>
      {hasSilver && (
        <button
          onClick={() => setExcludeSilver((v) => !v)}
          className={`text-xs px-3 py-1 rounded border transition-colors ${
            excludeSilver
              ? "border-red-500/60 bg-red-500/20 text-red-300"
              : "border-gray-400/40 bg-gray-400/10 text-gray-300 hover:border-red-400/50 hover:bg-red-400/10 hover:text-red-300"
          }`}
        >
          {excludeSilver ? "✕ Silver excluded" : "✕ Exclude Silver"}
        </button>
      )}
      {hasDark && (
        <button
          onClick={() => setExcludeDark((v) => !v)}
          className={`text-xs px-3 py-1 rounded border transition-colors ${
            excludeDark
              ? "border-red-500/60 bg-red-500/20 text-red-300"
              : "border-purple-400/40 bg-purple-400/10 text-purple-300 hover:border-red-400/50 hover:bg-red-400/10 hover:text-red-300"
          }`}
        >
          {excludeDark ? "✕ Dark Horse excluded" : "✕ Exclude Dark Horse"}
        </button>
      )}
      {(excludeSilver || excludeDark) && (
        <span className="text-xs text-text-dim italic opacity-60">
          Display only — model scores unchanged
        </span>
      )}
    </div>
  ) : null;

  return (
    <section className="bg-surface rounded-xl border border-border p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-gold">
          Analysis Results
        </h2>
        {raceConf && (
          <span className={`text-xs font-bold uppercase tracking-wider px-2 py-1 rounded border ${confStyle}`}>
            {raceConf} Confidence
          </span>
        )}
      </div>

      {/* Manual exclude controls */}
      {ExcludeControls}

      {/* Top Picks */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {(picks || []).map((p) => {
          const cfg = PICK_CONFIG[p.pick] || PICK_CONFIG["DARK HORSE"];
          return (
            <div
              key={p.pick}
              className={`rounded-lg border ${cfg.border} ${cfg.bg} p-4`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{cfg.emoji}</span>
                <span
                  className={`text-xs font-bold uppercase tracking-wider ${cfg.text}`}
                >
                  {cfg.label}
                </span>
              </div>
              <p className="text-lg font-semibold">{p.name}</p>
              <p className="text-gold text-sm font-medium mt-1">
                {p.model_alignment} confidence
              </p>
              {p.writeup && (
                <p className="text-text-dim text-xs mt-2 leading-relaxed italic border-t border-border/30 pt-2">
                  {p.writeup}
                </p>
              )}
              {p.market_flag && (
                <p className={`text-xs mt-1 font-medium ${
                  p.market_flag === "market_confirms" ? "text-green-400"
                  : p.market_flag === "market_near_agreement" ? "text-gold"
                  : "text-red-400"
                }`}>
                  {p.market_flag === "market_confirms" && "Market agrees"}
                  {p.market_flag === "market_near_agreement" && "Market near-agreement"}
                  {p.market_flag === "model_vs_market" && "Market disagrees — long price"}
                </p>
              )}
              {p.why && (
                <p className="text-text-dim text-xs mt-1 opacity-60">
                  {p.why}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Subtle empty-state messages — toggle was on but no pick returned */}
      {(silverMissing || darkMissing) && (
        <div className="flex flex-col gap-1 text-xs text-text-dim italic opacity-70">
          {silverMissing && <p>No Silver pick for this race</p>}
          {darkMissing && <p>No Dark Horse pick for this race</p>}
        </div>
      )}

      {/* Footer */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pt-2 border-t border-border/50">
        <p className="text-xs text-text-dim italic">{note}</p>
        <p className="text-xs text-text-dim">Engine: {engine_version}</p>
      </div>
    </section>
  );
}
