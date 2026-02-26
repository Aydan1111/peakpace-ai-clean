import { useState } from "react";

/**
 * Odds input panel — surfaces automatically when quality is LOW,
 * and is available as a collapsible option for MEDIUM races too.
 * Not shown for HIGH confidence races where it adds little value.
 */
export default function OddsInput({ quality, odds, onChange }) {
  const runnerNames = quality?.runner_names || [];
  const level = quality?.level;

  // Auto-expand for LOW races; collapsed by default otherwise
  const [open, setOpen] = useState(level === "LOW");

  if (level === "HIGH" || runnerNames.length === 0) return null;

  const handleChange = (name, val) => {
    onChange({ ...odds, [name]: val });
  };

  return (
    <div className="bg-surface rounded-xl border border-border p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">
            Add Odds{" "}
            <span className="text-text-dim font-normal text-xs">(optional)</span>
          </p>
          <p className="text-xs text-text-dim mt-0.5">
            {level === "LOW"
              ? "Limited data detected — market odds help the AI cross-check its picks."
              : "Market odds let the AI flag any disagreements with its analysis."}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-xs text-text-dim hover:text-gold transition-colors underline underline-offset-2 whitespace-nowrap"
        >
          {open ? "Hide" : "Show"}
        </button>
      </div>

      {open && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
          {runnerNames.map((name) => (
            <div key={name} className="space-y-1">
              <label className="block text-xs text-text-dim truncate" title={name}>
                {name}
              </label>
              <input
                type="text"
                value={odds[name] || ""}
                onChange={(e) => handleChange(name, e.target.value)}
                placeholder="e.g. 9/1"
                className="input-compact w-full"
              />
            </div>
          ))}
        </div>
      )}

      {open && (
        <p className="text-xs text-text-dim opacity-60">
          Fractional (9/1, 6/4) or decimal (10.0, 2.5). Leave blank to skip.
        </p>
      )}
    </div>
  );
}
