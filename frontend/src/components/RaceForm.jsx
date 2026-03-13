import { useState } from "react";

// Values must match backend normalize_going() exactly (lowercase, spaces not underscores).
const GOING_OPTIONS = [
  { value: "not_specified", label: "Not Specified" },
  { value: "heavy",         label: "Heavy" },
  { value: "soft",          label: "Soft" },
  { value: "good to soft",  label: "Good to Soft" },
  { value: "good",          label: "Good" },
  { value: "good to firm",  label: "Good to Firm" },
  { value: "firm",          label: "Firm" },
  { value: "standard",      label: "Standard" },
];

// Simple 2-way ground bucket — optional, inferred from Going when left blank.
const GROUND_OPTIONS = [
  { value: "",    label: "Auto (from Going / Ground)" },
  { value: "Wet", label: "Wet" },
  { value: "Dry", label: "Dry" },
];

// Canonical TYPE options.  "flat" maps to backend race_type=flat;
// everything else maps to national_hunt (handled in App.jsx).
const TYPE_OPTIONS = [
  { value: "flat",          label: "Flat" },
  { value: "national_hunt", label: "Jumps / National Hunt" },
  { value: "chase",         label: "Chase" },
  { value: "hurdle",        label: "Hurdle" },
  { value: "bumper",        label: "NH Flat (Bumper)" },
];

// Advanced: surface (not in canonical template, kept for All-Weather entries)
const SURFACE_OPTIONS = [
  { value: "aw",   label: "All Weather" },
  { value: "turf", label: "Turf / Grass" },
];

export default function RaceForm({ race, onChange }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const set = (field, value) => onChange({ ...race, [field]: value });

  return (
    <section className="bg-surface rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold text-gold mb-4">Race Information</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

        {/* COURSE */}
        <Field label="COURSE">
          <input
            type="text"
            value={race.course}
            onChange={(e) => set("course", e.target.value)}
            placeholder="e.g. Cheltenham"
            className="input"
          />
        </Field>

        {/* RACE */}
        <Field label="RACE">
          <input
            type="text"
            value={race.race_name || ""}
            onChange={(e) => set("race_name", e.target.value)}
            placeholder="e.g. Supreme Novices' Hurdle"
            className="input"
          />
        </Field>

        {/* TYPE */}
        <Field label="TYPE">
          <select
            value={race.race_type}
            onChange={(e) => set("race_type", e.target.value)}
            className="input"
          >
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>

        {/* DISTANCE */}
        <Field label="DISTANCE">
          <input
            type="text"
            value={race.distance_str}
            onChange={(e) => set("distance_str", e.target.value)}
            placeholder="e.g. 2m, 1m4f, 7f"
            className="input"
          />
        </Field>

        {/* RUNNERS */}
        <Field label="RUNNERS">
          <input
            type="number"
            min={2}
            max={40}
            value={race.runners_count || ""}
            onChange={(e) => set("runners_count", e.target.value)}
            placeholder="e.g. 8"
            className="input"
          />
        </Field>

        {/* CLASS */}
        <Field label="CLASS">
          <input
            type="text"
            value={race.race_class || ""}
            onChange={(e) => set("race_class", e.target.value)}
            placeholder="e.g. Class 1, Grade 1"
            className="input"
          />
        </Field>

        {/* GOING / GROUND */}
        <Field label="GOING / GROUND">
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

        {/* GROUND (bucket override) */}
        <Field label="GROUND">
          <select
            value={race.ground_bucket || ""}
            onChange={(e) => set("ground_bucket", e.target.value || null)}
            className="input"
          >
            {GROUND_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>

      </div>

      {/* Advanced toggle */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="text-xs text-text-dim hover:text-text transition-colors"
        >
          {showAdvanced ? "▴ Hide advanced" : "▾ Advanced"}
        </button>

        {showAdvanced && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
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
        )}
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
