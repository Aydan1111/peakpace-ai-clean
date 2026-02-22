const PICK_CONFIG = {
  GOLD: {
    emoji: "\u{1F947}",
    label: "Gold Pick",
    border: "border-yellow-500/60",
    bg: "bg-yellow-500/10",
    text: "text-yellow-400",
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

export default function ResultsPanel({ result }) {
  if (!result) return null;

  // Map backend shape → UI shape
  const goldName = result.gold_pick?.name;
  const silverName = result.silver_pick?.name;
  const darkName = result.dark_horse?.name;

  const picks = [
    result.gold_pick && { pick: "GOLD", name: goldName, model_alignment: result.gold_pick.confidence, why: result.gold_pick.label },
    result.silver_pick && { pick: "SILVER", name: silverName, model_alignment: result.silver_pick.confidence, why: result.silver_pick.label },
    result.dark_horse && darkName !== silverName && { pick: "DARK HORSE", name: darkName, model_alignment: result.dark_horse.confidence, why: result.dark_horse.label },
  ].filter(Boolean);

  const predictions_table = (result.full_rankings || []).map((r) => {
    let pick = null;
    if (r.name === goldName) pick = "GOLD";
    else if (r.name === silverName) pick = "SILVER";
    else if (r.name === darkName) pick = "DARK HORSE";
    return {
      name: r.name,
      total_score: r.score,
      model_alignment: r.confidence,
      form: r.form || 0,
      connections: r.connections || 0,
      structural: r.structural || 0,
      fitness: r.fitness || 0,
      pick,
    };
  });

  const engine_version = "PeakPace v1";
  const note = "Scores are model estimates — always verify with your own analysis.";
  const raceConf = result.race_confidence || null;
  const confStyle = raceConf === "HIGH"
    ? "bg-green-500/20 text-green-300 border-green-500/40"
    : raceConf === "MEDIUM"
    ? "bg-yellow-500/20 text-yellow-300 border-yellow-500/40"
    : "bg-gray-500/20 text-gray-300 border-gray-500/40";

  return (
    <section className="bg-surface rounded-xl border border-border p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-gold">Analysis Results</h2>
        {raceConf && (
          <span className={`text-xs font-bold uppercase tracking-wider px-2 py-1 rounded border ${confStyle}`}>
            {raceConf} Confidence
          </span>
        )}
      </div>

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
                {p.model_alignment} alignment
              </p>
              {p.why && (
                <p className="text-text-dim text-xs mt-2 leading-relaxed">
                  {p.why}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Full Rankings Table */}
      <div>
        <h3 className="text-sm font-semibold text-text-dim uppercase tracking-wide mb-3">
          Full Rankings
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-text-dim border-b border-border">
                <th className="pb-2 pr-3">Rank</th>
                <th className="pb-2 pr-3">Horse</th>
                <th className="pb-2 pr-3">Score</th>
                <th className="pb-2 pr-3">Alignment</th>
                <th className="pb-2 pr-3">Form</th>
                <th className="pb-2 pr-3">Connections</th>
                <th className="pb-2 pr-3">Structural</th>
                <th className="pb-2 pr-3">Fitness</th>
                <th className="pb-2">Pick</th>
              </tr>
            </thead>
            <tbody>
              {(predictions_table || []).map((row, i) => (
                <tr
                  key={row.name}
                  className="border-b border-border/30 hover:bg-surface-light transition-colors"
                >
                  <td className="py-2.5 pr-3 text-text-dim">{i + 1}</td>
                  <td className="py-2.5 pr-3 font-medium">{row.name}</td>
                  <td className="py-2.5 pr-3 font-mono">
                    {row.total_score.toFixed(2)}
                  </td>
                  <td className="py-2.5 pr-3">
                    <AlignmentBadge value={row.model_alignment} />
                  </td>
                  <td className="py-2.5 pr-3 font-mono">
                    {row.form.toFixed(1)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono">
                    {row.connections.toFixed(1)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono">
                    {row.structural.toFixed(1)}
                  </td>
                  <td className="py-2.5 pr-3 font-mono">
                    {row.fitness.toFixed(1)}
                  </td>
                  <td className="py-2.5">
                    <PickBadge pick={row.pick} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footer */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pt-2 border-t border-border/50">
        <p className="text-xs text-text-dim italic">{note}</p>
        <p className="text-xs text-text-dim">Engine: {engine_version}</p>
      </div>
    </section>
  );
}

function AlignmentBadge({ value }) {
  const v = Math.round(value);
  let color = "text-text-dim";
  if (v >= 85) color = "text-green-400";
  else if (v >= 78) color = "text-yellow-400";

  return (
    <span className={`font-mono font-semibold ${color}`}>{v}%</span>
  );
}

function PickBadge({ pick }) {
  if (!pick) return <span className="text-text-dim">-</span>;
  const cfg = PICK_CONFIG[pick];
  if (!cfg) return <span>{pick}</span>;
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-bold ${cfg.text}`}
    >
      {cfg.emoji} {pick}
    </span>
  );
}
