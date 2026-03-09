import { useState } from "react";

const LEVEL_STYLE = {
  HIGH:   { badge: "bg-green-500/20 text-green-300 border-green-500/40",  dot: "bg-green-400" },
  MEDIUM: { badge: "bg-gold/20 text-gold border-gold/40", dot: "bg-gold" },
  LOW:    { badge: "bg-red-500/20 text-red-300 border-red-500/40",         dot: "bg-red-400" },
};

const SIGNAL_LABELS = {
  data_coverage:  "Data Coverage",
  form_quality:   "Form Quality",
  field_size:     "Field Size",
  race_type:      "Race Type",
  field_richness: "Signal Richness",
};

function ScoreDots({ score }) {
  return (
    <span className="flex gap-0.5 items-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`inline-block w-2 h-2 rounded-full ${
            i < score ? "bg-gold" : "bg-surface-lighter"
          }`}
        />
      ))}
    </span>
  );
}

export default function RaceQualityBadge({ quality }) {
  const [expanded, setExpanded] = useState(false);
  const style = LEVEL_STYLE[quality.level] || LEVEL_STYLE.LOW;

  return (
    <div className="bg-surface rounded-xl border border-border p-4 space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <span
            className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded border ${style.badge}`}
          >
            {quality.level} Confidence
          </span>
          <p className="text-sm text-text-dim">{quality.headline}</p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-text-dim hover:text-gold transition-colors underline underline-offset-2"
        >
          {expanded ? "Hide breakdown" : "Show breakdown"}
        </button>
      </div>

      {expanded && quality.signals && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
          {Object.entries(quality.signals).map(([key, sig]) => (
            <div
              key={key}
              className="flex items-center justify-between gap-2 bg-surface-light rounded-lg px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <ScoreDots score={sig.score} />
                <span className="text-xs font-medium text-text-dim whitespace-nowrap">
                  {SIGNAL_LABELS[key] || key}
                </span>
              </div>
              <span className="text-xs text-text-dim text-right leading-tight">
                {sig.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
