import { useState } from "react";

const EMPTY_RUNNER = {
  name: "",
  jockey: "",
  trainer: "",
  form: "",
  age: 4,
  weight_st: "9-4",
  draw: "",
  pace: "",
  odds: "",
  equipment: "",
  comment: "",
  previous_runs: [],
  or_rating: "",
  rpr: "",
  top_speed: "",
};

const PACE_OPTIONS = [
  { value: "",          label: "— select —" },
  { value: "HOLD_UP",   label: "Hold Up" },
  { value: "MIDFIELD",  label: "Midfield" },
  { value: "PROMINENT", label: "Prominent" },
  { value: "LEADER",    label: "Leader" },
];

const EMPTY_PREV_RUN = {
  distance: "",
  going: "",
  pos: "",
  field_size: "",
  discipline: "flat",
};

export default function RunnerTable({ runners, onChange }) {
  const [expanded, setExpanded] = useState({});

  const update = (idx, field, value) =>
    onChange(runners.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));

  const toggleExpand = (idx) =>
    setExpanded((e) => ({ ...e, [idx]: !e[idx] }));

  const addRunner = () =>
    onChange([...runners, { ...EMPTY_RUNNER, previous_runs: [] }]);

  const removeRunner = (idx) => {
    if (runners.length <= 2) return;
    onChange(runners.filter((_, i) => i !== idx));
    setExpanded((e) => { const n = { ...e }; delete n[idx]; return n; });
  };

  const addPrevRun = (idx) =>
    update(idx, "previous_runs", [
      ...(runners[idx].previous_runs || []),
      { ...EMPTY_PREV_RUN },
    ]);

  const removePrevRun = (rIdx, prIdx) =>
    update(rIdx, "previous_runs",
      (runners[rIdx].previous_runs || []).filter((_, i) => i !== prIdx));

  const updatePrevRun = (rIdx, prIdx, field, value) =>
    update(rIdx, "previous_runs",
      (runners[rIdx].previous_runs || []).map((pr, i) =>
        i === prIdx ? { ...pr, [field]: value } : pr));

  return (
    <section className="bg-surface rounded-xl border border-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gold">
          Horses ({runners.length})
        </h2>
        <button type="button" onClick={addRunner} className="btn-secondary text-sm">
          + Add Horse
        </button>
      </div>

      <div className="flex flex-col gap-4">
        {runners.map((r, i) => (
          <div
            key={i}
            className="bg-surface-light rounded-lg border border-border/50 p-4"
          >
            {/* Card header */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-gold uppercase tracking-wide">
                Horse {i + 1}
              </span>
              <button
                type="button"
                onClick={() => removeRunner(i)}
                disabled={runners.length <= 2}
                className="text-xs text-text-dim hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Remove
              </button>
            </div>

            {/* Main fields grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">

              <CardField label="HORSE" className="col-span-2 sm:col-span-2 lg:col-span-2">
                <input
                  type="text"
                  value={r.name}
                  onChange={(e) => update(i, "name", e.target.value)}
                  placeholder="Horse name"
                  className="input"
                />
              </CardField>

              <CardField label="JOCKEY">
                <input
                  type="text"
                  value={r.jockey}
                  onChange={(e) => update(i, "jockey", e.target.value)}
                  className="input"
                />
              </CardField>

              <CardField label="TRAINER">
                <input
                  type="text"
                  value={r.trainer}
                  onChange={(e) => update(i, "trainer", e.target.value)}
                  className="input"
                />
              </CardField>

              <CardField label="FORM">
                <input
                  type="text"
                  value={r.form}
                  onChange={(e) => update(i, "form", e.target.value)}
                  placeholder="e.g. 1231"
                  className="input"
                />
              </CardField>

              <CardField label="AGE">
                <input
                  type="number"
                  min={2}
                  max={14}
                  value={r.age}
                  onChange={(e) => update(i, "age", Number(e.target.value))}
                  className="input"
                />
              </CardField>

              <CardField label="WEIGHT (st-lb)">
                <input
                  type="text"
                  value={r.weight_st}
                  onChange={(e) => update(i, "weight_st", e.target.value)}
                  placeholder="9-0"
                  className="input"
                />
              </CardField>

              <CardField label="DRAW">
                <input
                  type="number"
                  min={1}
                  value={r.draw || ""}
                  onChange={(e) => update(i, "draw", e.target.value)}
                  placeholder="—"
                  className="input"
                />
              </CardField>

              <CardField label="PACE">
                <select
                  value={r.pace || ""}
                  onChange={(e) => update(i, "pace", e.target.value)}
                  className="input"
                >
                  {PACE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </CardField>

              <CardField label="ODDS">
                <input
                  type="text"
                  value={r.odds || ""}
                  onChange={(e) => update(i, "odds", e.target.value)}
                  placeholder="e.g. 9/1"
                  className="input"
                />
              </CardField>

              <CardField label="EQUIPMENT" className="col-span-2">
                <input
                  type="text"
                  value={r.equipment || ""}
                  onChange={(e) => update(i, "equipment", e.target.value)}
                  placeholder="hood, cheekpieces, tongue strap…"
                  className="input"
                />
              </CardField>

            </div>

            {/* Comment & Recent Runs (expandable) */}
            <div className="mt-3 pt-3 border-t border-border/30">
              <button
                type="button"
                onClick={() => toggleExpand(i)}
                className={`text-xs font-medium transition-colors ${
                  expanded[i] ? "text-gold" : "text-text-dim"
                }`}
              >
                {expanded[i]
                  ? "▴ Hide ratings, comment & recent runs"
                  : "▾ Add ratings (OR/RPR/TS), comment & recent runs"}
              </button>
              {expanded[i] && (
                <div className="mt-3">
                  <DetailsPanel
                    runner={r}
                    onUpdateField={(f, v) => update(i, f, v)}
                    onUpdateComment={(v) => update(i, "comment", v)}
                    onAddPrevRun={() => addPrevRun(i)}
                    onRemovePrevRun={(ri) => removePrevRun(i, ri)}
                    onUpdatePrevRun={(ri, f, v) => updatePrevRun(i, ri, f, v)}
                  />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function CardField({ label, children, className = "" }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="text-xs font-medium uppercase tracking-wide text-text-dim">
        {label}
      </span>
      {children}
    </label>
  );
}

// ── Details panel (COMMENT + RECENT RUNS) ────────────────────────────────────

function DetailsPanel({ runner, onUpdateField, onUpdateComment, onAddPrevRun, onRemovePrevRun, onUpdatePrevRun }) {
  const prevRuns = runner.previous_runs || [];

  return (
    <div className="space-y-4">

      {/* RATINGS (optional — OR / RPR / TS) */}
      <div>
        <span className="text-xs text-text-dim uppercase tracking-wide">
          RATINGS (OPTIONAL)
        </span>
        <div className="grid grid-cols-3 gap-2 mt-1">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-text-dim uppercase tracking-wide">OR</span>
            <input
              type="number"
              min={0}
              value={runner.or_rating ?? ""}
              onChange={(e) => onUpdateField("or_rating", e.target.value)}
              placeholder="—"
              className="input text-sm"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-text-dim uppercase tracking-wide">RPR</span>
            <input
              type="number"
              min={0}
              value={runner.rpr ?? ""}
              onChange={(e) => onUpdateField("rpr", e.target.value)}
              placeholder="—"
              className="input text-sm"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-text-dim uppercase tracking-wide">TS</span>
            <input
              type="number"
              min={0}
              value={runner.top_speed ?? ""}
              onChange={(e) => onUpdateField("top_speed", e.target.value)}
              placeholder="—"
              className="input text-sm"
            />
          </label>
        </div>
      </div>

      {/* COMMENT */}
      <label className="flex flex-col gap-1">
        <span className="text-xs text-text-dim uppercase tracking-wide">
          COMMENT
        </span>
        <textarea
          value={runner.comment || ""}
          onChange={(e) => onUpdateComment(e.target.value)}
          placeholder="e.g. Progressive type, well suited to this trip and ground…"
          rows={2}
          className="input text-sm resize-none"
        />
      </label>

      {/* RECENT RUNS */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-text-dim uppercase tracking-wide">
            RECENT RUNS
          </span>
          <button
            type="button"
            onClick={onAddPrevRun}
            className="text-xs text-gold/80 hover:text-gold transition-colors"
          >
            + Add Run
          </button>
        </div>

        {prevRuns.length === 0 ? (
          <p className="text-xs text-text-dim italic opacity-60">
            No recent runs — click &quot;+ Add Run&quot; to add entries
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-text-dim border-b border-border/30">
                  <th className="pb-1 pr-2">Distance</th>
                  <th className="pb-1 pr-2">Going</th>
                  <th className="pb-1 pr-2">Pos</th>
                  <th className="pb-1 pr-2">Field</th>
                  <th className="pb-1 pr-2">Type</th>
                  <th className="pb-1"></th>
                </tr>
              </thead>
              <tbody>
                {prevRuns.map((pr, ri) => (
                  <tr key={ri} className="border-b border-border/20">
                    <td className="py-1.5 pr-2">
                      <input
                        type="text"
                        value={pr.distance || ""}
                        onChange={(e) => onUpdatePrevRun(ri, "distance", e.target.value)}
                        placeholder="2m4f"
                        className="input-compact w-16"
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <input
                        type="text"
                        value={pr.going || ""}
                        onChange={(e) => onUpdatePrevRun(ri, "going", e.target.value)}
                        placeholder="good"
                        className="input-compact w-24"
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <input
                        type="number"
                        min={1}
                        value={pr.pos || ""}
                        onChange={(e) => onUpdatePrevRun(ri, "pos", e.target.value)}
                        placeholder="3"
                        className="input-compact w-12"
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <input
                        type="number"
                        min={2}
                        value={pr.field_size || ""}
                        onChange={(e) => onUpdatePrevRun(ri, "field_size", e.target.value)}
                        placeholder="10"
                        className="input-compact w-12"
                      />
                    </td>
                    <td className="py-1.5 pr-2">
                      <select
                        value={pr.discipline || "flat"}
                        onChange={(e) => onUpdatePrevRun(ri, "discipline", e.target.value)}
                        className="input-compact"
                      >
                        <option value="flat">Flat</option>
                        <option value="hurdle">Hurdle</option>
                        <option value="chase">Chase</option>
                        <option value="bumper">Bumper</option>
                        <option value="nh_flat">NH Flat</option>
                      </select>
                    </td>
                    <td className="py-1.5">
                      <button
                        type="button"
                        onClick={() => onRemovePrevRun(ri)}
                        className="text-text-dim hover:text-red-400 transition-colors px-1"
                        title="Remove run"
                      >
                        &times;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
