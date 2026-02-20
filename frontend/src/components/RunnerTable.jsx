const EMPTY_RUNNER = {
  name: "",
  age: 4,
  weight_lbs: 130,
  form: "",
  trainer: "",
  jockey: "",
};

export default function RunnerTable({ runners, onChange }) {
  const update = (idx, field, value) => {
    const next = runners.map((r, i) =>
      i === idx ? { ...r, [field]: value } : r
    );
    onChange(next);
  };

  const addRunner = () => onChange([...runners, { ...EMPTY_RUNNER }]);

  const removeRunner = (idx) => {
    if (runners.length <= 2) return;
    onChange(runners.filter((_, i) => i !== idx));
  };

  return (
    <section className="bg-surface rounded-xl border border-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gold">
          Runners ({runners.length})
        </h2>
        <button
          type="button"
          onClick={addRunner}
          className="btn-secondary text-sm"
        >
          + Add Runner
        </button>
      </div>

      {/* Desktop table */}
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
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {runners.map((r, i) => (
              <tr key={i} className="border-b border-border/50">
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
                    type="number"
                    min={100}
                    max={180}
                    value={r.weight_lbs}
                    onChange={(e) =>
                      update(i, "weight_lbs", Number(e.target.value))
                    }
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
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
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
                <input
                  type="text"
                  value={r.name}
                  onChange={(e) => update(i, "name", e.target.value)}
                  placeholder="Horse name"
                  className="input"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Age</span>
                <input
                  type="number"
                  min={2}
                  max={14}
                  value={r.age}
                  onChange={(e) => update(i, "age", Number(e.target.value))}
                  className="input"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Weight (lbs)</span>
                <input
                  type="number"
                  min={100}
                  max={180}
                  value={r.weight_lbs}
                  onChange={(e) =>
                    update(i, "weight_lbs", Number(e.target.value))
                  }
                  className="input"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Form</span>
                <input
                  type="text"
                  value={r.form}
                  onChange={(e) => update(i, "form", e.target.value)}
                  placeholder="e.g. 1231"
                  className="input"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-text-dim">Trainer</span>
                <input
                  type="text"
                  value={r.trainer}
                  onChange={(e) => update(i, "trainer", e.target.value)}
                  className="input"
                />
              </label>
              <label className="col-span-2 flex flex-col gap-1">
                <span className="text-xs text-text-dim">Jockey</span>
                <input
                  type="text"
                  value={r.jockey}
                  onChange={(e) => update(i, "jockey", e.target.value)}
                  className="input"
                />
              </label>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
