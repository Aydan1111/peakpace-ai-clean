// Values must match backend normalize_going() exactly (lowercase, spaces not underscores).
// "not_specified" is handled specially — backend treats it as no detailed going.
const GOING_OPTIONS = [
  { value: "not_specified", label: "Not Specified" },
  { value: "heavy", label: "Heavy" },
  { value: "soft", label: "Soft" },
  { value: "good to soft", label: "Good to Soft" },
  { value: "good", label: "Good" },
  { value: "good to firm", label: "Good to Firm" },
  { value: "firm", label: "Firm" },
  { value: "standard", label: "Standard" },
];

// Simple 2-way ground bucket — optional, inferred from Going when left blank.
// When Going is "Not Specified", Auto leaves ground_bucket unknown; user can
// manually choose Wet or Dry to still provide ground context.
const GROUND_BUCKET_OPTIONS = [
  { value: "", label: "Auto (from Going/Ground)" },
  { value: "Wet", label: "Wet" },
  { value: "Dry", label: "Dry" },
];

const RACE_TYPE_OPTIONS = ["flat", "jumps"];
const SURFACE_OPTIONS = [
  { value: "aw", label: "All Weather" },
  { value: "grass", label: "Grass" },
];

export default function RaceForm({ race, onChange }) {
  const set = (field, value) => onChange({ ...race, [field]: value });

  return (
    <section className="bg-surface rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold text-gold mb-4">Race Information</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Field label="Course">
          <input
            type="text"
            value={race.course}
            onChange={(e) => set("course", e.target.value)}
            placeholder="e.g. Ascot"
            className="input"
          />
        </Field>

        <Field label="Distance (e.g. 1m4f, 7f, 2m)">
          <input
            type="text"
            value={race.distance_str}
            onChange={(e) => set("distance_str", e.target.value)}
            placeholder="e.g. 1m4f"
            className="input"
          />
        </Field>

        <Field label="Race Type">
          <select
            value={race.race_type}
            onChange={(e) => set("race_type", e.target.value)}
            className="input"
          >
            {RACE_TYPE_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {o.charAt(0).toUpperCase() + o.slice(1)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Going / Ground">
          <select
            value={race.going}
            onChange={(e) => set("going", e.target.value)}
            className="input"
          >
            {GOING_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Ground Bucket">
          <select
            value={race.ground_bucket || ""}
            onChange={(e) => set("ground_bucket", e.target.value || null)}
            className="input"
          >
            {GROUND_BUCKET_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Surface">
          <select
            value={race.surface}
            onChange={(e) => set("surface", e.target.value)}
            className="input"
          >
            {SURFACE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
    </section>
  );
}

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-text-dim">
        {label}
      </span>
      {children}
    </label>
  );
}
