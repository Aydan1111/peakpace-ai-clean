/** Minimal horse-and-jockey silhouette — premium, not cartoonish. */
function HorseIcon({ size = 18, className = "" }) {
  return (
    <svg
      viewBox="0 0 56 40"
      width={size}
      height={Math.round(size * 0.71)}
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      {/* Jockey: head */}
      <circle cx="42" cy="6" r="4.5" />
      {/* Jockey: crouched torso over horse */}
      <path d="M38 10 C32 15 30 20 36 23 C40 20 46 14 47 10 Z" />
      {/* Horse: body */}
      <path d="M8 22 C8 14 28 12 42 18 C46 20 48 24 46 28 C44 32 36 35 26 35 C14 35 8 30 8 22 Z" />
      {/* Horse: neck */}
      <path d="M40 18 C44 12 44 7 42 5 C40 6 37 10 36 14 Z" />
      {/* Horse: ear */}
      <path d="M41 5 C42 2 45 2 44 5 Z" />
      {/* Horse: tail */}
      <path d="M8 24 C2 20 0 26 4 28 C6 28 9 27 9 25 Z" />
      {/* Front legs — extended forward */}
      <rect x="37" y="33" width="3" height="7" rx="1.5" transform="rotate(12,38.5,33)" />
      <rect x="43" y="32" width="3" height="7" rx="1.5" transform="rotate(22,44.5,32)" />
      {/* Back legs — extended back */}
      <rect x="16" y="33" width="3" height="7" rx="1.5" transform="rotate(-18,17.5,33)" />
      <rect x="22" y="33" width="3" height="7" rx="1.5" transform="rotate(-6,23.5,33)" />
    </svg>
  );
}

/**
 * Large premium horse-and-jockey silhouette for the Results section background.
 * Rendered at low opacity as a decorative watermark — does not affect layout.
 */
function RacetrackWatermark() {
  return (
    <svg
      viewBox="0 0 280 175"
      aria-hidden="true"
      fill="currentColor"
      style={{
        position: "absolute",
        bottom: "-24px",
        right: "-16px",
        width: "340px",
        height: "auto",
        opacity: 0.13,
        pointerEvents: "none",
        userSelect: "none",
        color: "#d4a843",
      }}
    >
      {/* Horse body — main mass */}
      <path d="M48,105 C50,83 73,69 107,67 C141,65 186,71 208,85 C222,95 222,115 208,127 C188,141 136,145 94,139 C63,133 46,122 48,105 Z" />
      {/* Neck */}
      <path d="M205,85 C216,69 224,50 220,35 C218,25 210,23 206,30 C202,38 200,63 198,83 Z" />
      {/* Head */}
      <path d="M212,31 C218,17 238,14 244,26 C250,37 242,52 230,53 C218,53 208,43 212,31 Z" />
      {/* Ear */}
      <path d="M216,23 C218,11 226,11 224,21 Z" />
      {/* Nostril */}
      <ellipse cx="241" cy="35" rx="4" ry="3" />
      {/* Tail — flowing back */}
      <path d="M50,98 C34,87 18,87 12,98 C6,108 14,117 26,113 C38,109 46,104 50,98 Z" />
      {/* Front left leg (extended forward) */}
      <path d="M193,127 C197,141 200,157 199,171 L 193,171 C193,157 190,142 186,128 Z" />
      {/* Front right leg */}
      <path d="M175,131 C178,145 180,160 178,171 L 172,171 C173,160 172,145 169,131 Z" />
      {/* Back left leg (extended backward) */}
      <path d="M86,131 C81,145 77,160 75,171 L 69,171 C71,160 75,145 80,130 Z" />
      {/* Back right leg */}
      <path d="M104,133 C101,147 99,161 99,171 L 93,171 C93,161 95,147 98,132 Z" />
      {/* Jockey head */}
      <circle cx="224" cy="21" r="10" />
      {/* Jockey torso — crouched forward */}
      <path d="M212,29 C204,44 203,62 213,72 C221,64 232,46 234,29 Z" />
      {/* Jockey arm / whip */}
      <path d="M206,56 C200,66 198,76 201,80 C204,81 207,80 208,76 C209,70 210,62 212,54 Z" />
    </svg>
  );
}

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
    result.gold_pick && { pick: "GOLD", name: goldName, model_alignment: result.gold_pick.confidence, why: result.gold_pick.label, writeup: result.gold_pick.writeup },
    result.silver_pick && { pick: "SILVER", name: silverName, model_alignment: result.silver_pick.confidence, why: result.silver_pick.label, writeup: result.silver_pick.writeup },
    result.dark_horse && darkName !== silverName && { pick: "DARK HORSE", name: darkName, model_alignment: result.dark_horse.confidence, why: result.dark_horse.label, writeup: result.dark_horse.writeup },
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
    <section className="relative overflow-hidden bg-surface rounded-xl border border-border p-6 space-y-6">
      <RacetrackWatermark />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-gold flex items-center gap-2">
          <HorseIcon size={36} className="text-gold opacity-90" />
          Analysis Results
        </h2>
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
                <HorseIcon size={16} className={`ml-auto opacity-50 ${cfg.text}`} />
              </div>
              <p className="text-lg font-semibold">{p.name}</p>
              <p className="text-gold text-sm font-medium mt-1">
                {p.model_alignment} alignment
              </p>
              {p.writeup && (
                <p className="text-text-dim text-xs mt-2 leading-relaxed italic border-t border-border/30 pt-2">
                  {p.writeup}
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

      {/* Full Rankings Table */}
      <div>
        <h3 className="text-sm font-semibold text-text-dim uppercase tracking-wide mb-3 flex items-center gap-1.5">
          <HorseIcon size={14} className="opacity-50" />
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
