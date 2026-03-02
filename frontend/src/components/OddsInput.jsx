import { useState } from "react";

/**
 * Odds input panel — shown when runner names are available.
 * Collapsed by default; user can expand to enter market odds.
 */
export default function OddsInput({ runnerNames = [], odds, onChange }) {
  const [open, setOpen] = useState(false);

  if (runnerNames.length === 0) return null;

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
            Market odds let the AI flag any disagreements with its analysis.
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
