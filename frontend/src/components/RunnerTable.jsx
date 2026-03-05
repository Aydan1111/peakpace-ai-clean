import { useState, Fragment } from "react";

const EMPTY_RUNNER = {
  name: "",
  age: 4,
  weight_st: "9-4",
  form: "",
  trainer: "",
  jockey: "",
  odds: "",
  equipment: "",
  comment: "",
  previous_runs: [],
};

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
          Runners ({runners.length})
        </h2>
        <button type="button" onClick={addRunner} className="btn-secondary text-sm">
          + Add Runner
        </button>
      </div>

      {/* ── Desktop table ─────────────────────────────────────────────────── */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-text-dim border-b border-border">
              <th className="pb-2 pr-2">#</th>
              <th className="pb-2 pr-2">Name</th>
              <th className="pb-2 pr-2">Age</th>
              <th className="pb-2 pr-2">Weight</th>
              <th className="pb-2 pr-2">Form</th>
              <th className="pb-2 pr-2">Trainer</th>
              <th className="pb-2 pr-2">Jockey</th>
              <th className="pb-2 pr-2">Odds</th>
              <th className="pb-2 pr-2">Equipment</th>
              <th className="pb-2 pr-2"></th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {runners.map((r, i) => (
              <Fragment key={i}>
                {/* Main row */}
                <tr className={expanded[i] ? "" : "border-b border-border/50"}>
                  <td className="py-2 pr-2 text-text-dim">{i + 1}</td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.name}
                      onChange={(e) => update(i, "name", e.target.value)}
                      placeholder="Horse name"
                      className="input-compact"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="number"
                      min={2}
                      max={14}
                      value={r.age}
                      onChange={(e) => update(i, "age", Number(e.target.value))}
                      className="input-compact w-16"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.weight_st}
                      onChange={(e) => update(i, "weight_st", e.target.value)}
                      placeholder="9-0"
                      className="input-compact w-20"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.form}
                      onChange={(e) => update(i, "form", e.target.value)}
                      placeholder="e.g. 1231"
                      className="input-compact w-24"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.trainer}
                      onChange={(e) => update(i, "trainer", e.target.value)}
                      placeholder="Trainer"
                      className="input-compact"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.jockey}
                      onChange={(e) => update(i, "jockey", e.target.value)}
                      placeholder="Jockey"
                      className="input-compact"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.odds || ""}
                      onChange={(e) => update(i, "odds", e.target.value)}
                      placeholder="e.g. 9/1"
                      className="input-compact w-20"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="text"
                      value={r.equipment || ""}
                      onChange={(e) => update(i, "equipment", e.target.value)}
                      placeholder="hood, cheekpieces…"
                      className="input-compact w-32"
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <button
                      type="button"
                      onClick={() => toggleExpand(i)}
                      className={`text-xs px-2 py-1 rounded border transition-colors whitespace-nowrap ${
                        expanded[i]
                          ? "border-gold/60 text-gold bg-gold/10"
                          : "border-border text-text-dim hover:border-gold/40 hover:text-gold/70"
                      }`}
                    >
                      {expanded[i] ? "▴ Details" : "▾ Details"}
                    </button>
                  </td>
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() => removeRunner(i)}
                      disabled={runners.length <= 2}
                      className="text-text-dim hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors px-1"
                      title="Remove runner"
                    >
                      &times;
                    </button>
                  </td>
                </tr>

                {/* Details panel row */}
                {expanded[i] && (
                  <tr className="border-b border-border/50">
                    <td colSpan={10} className="pb-4 pt-1 pl-6 pr-2">
                      <DetailsPanel
                        runner={r}
                        onUpdateComment={(v) => update(i, "comment", v)}
                        onAddPrevRun={() => addPrevRun(i)}
                        onRemovePrevRun={(ri) => removePrevRun(i, ri)}
                        onUpdatePrevRun={(ri, f, v) => updatePrevRun(i, ri, f, v)}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Mobile cards ──────────────────────────────────────────────────── */}
      <div className="md:hidden flex flex-col gap-4">
        {runners.map((r, i) => (
          <div
            key={i}
            className="bg-surface-light rounded-lg border border-border/50 p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-text-dim">
                Runner {i + 1}
              </span>
              <button
                type="button"
                onClick={() => removeRunner(i)}
                disabled={runners.length <= 2}
                className="text-xs text-text-dim hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Remove
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="col-span-2 flex flex-col gap-1">
                <span className="text-xs text-text-dim">Name</span>
                <input type="text" value={r.name}
                  onChange={(e) => update(i, "name", e.target.value)}
                  placeholder="Horse name" className="input" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Age</span>
                <input type="number" min={2} max={14} value={r.age}
                  onChange={(e) => update(i, "age", Number(e.target.value))}
                  className="input" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Weight (st-lb)</span>
                <input type="text" value={r.weight_st}
                  onChange={(e) => update(i, "weight_st", e.target.value)}
                  placeholder="9-0" className="input" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Form</span>
                <input type="text" value={r.form}
                  onChange={(e) => update(i, "form", e.target.value)}
                  placeholder="e.g. 1231" className="input" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Trainer</span>
                <input type="text" value={r.trainer}
                  onChange={(e) => update(i, "trainer", e.target.value)}
                  className="input" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Jockey</span>
                <input type="text" value={r.jockey}
                  onChange={(e) => update(i, "jockey", e.target.value)}
                  className="input" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Odds (optional)</span>
                <input type="text" value={r.odds || ""}
                  onChange={(e) => update(i, "odds", e.target.value)}
                  placeholder="e.g. 9/1" className="input" />
              </label>
              <label className="col-span-2 flex flex-col gap-1">
                <span className="text-xs text-text-dim">Equipment (optional)</span>
                <input type="text" value={r.equipment || ""}
                  onChange={(e) => update(i, "equipment", e.target.value)}
                  placeholder="hood, cheekpieces, tongue strap…" className="input" />
              </label>
            </div>

            {/* Expandable detail section on mobile */}
            <div className="mt-3 pt-3 border-t border-border/30">
              <button
                type="button"
                onClick={() => toggleExpand(i)}
                className={`text-xs font-medium transition-colors ${
                  expanded[i] ? "text-gold" : "text-text-dim"
                }`}
              >
                {expanded[i]
                  ? "▴ Hide comment & previous runs"
                  : "▾ Add comment & previous runs"}
              </button>
              {expanded[i] && (
                <div className="mt-3">
                  <DetailsPanel
                    runner={r}
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

// ── Details panel (comment + previous runs mini-table) ──────────────────────

function DetailsPanel({ runner, onUpdateComment, onAddPrevRun, onRemovePrevRun, onUpdatePrevRun }) {
  const prevRuns = runner.previous_runs || [];

  return (
    <div className="space-y-4">

      {/* Analyst comment */}
      <label className="flex flex-col gap-1">
        <span className="text-xs text-text-dim uppercase tracking-wide">
          Analyst Comment
        </span>
        <textarea
          value={runner.comment || ""}
          onChange={(e) => onUpdateComment(e.target.value)}
          placeholder="e.g. Progressive type, well suited to this trip and ground…"
          rows={2}
          className="input text-sm resize-none"
        />
      </label>

      {/* Previous runs */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-text-dim uppercase tracking-wide">
            Previous Runs
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
            No previous runs — click &quot;+ Add Run&quot; to add entries
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
