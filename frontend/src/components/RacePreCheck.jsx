import { useState } from "react";

// ---------------------------------------------------------------------------
// Local scoring — no API, no external model, fully offline
// ---------------------------------------------------------------------------

function computePrecheck(form) {
  let score = 0;
  const runners = parseInt(form.runners, 10) || 10;
  const isFlat = form.discipline === "Flat";
  const isJumps = form.discipline === "Jumps";

  // Discipline: Flat is generally clearer
  if (isFlat) score += 1;

  // Runners: fewer = clearer
  if (runners <= 7)       score += 2;
  else if (runners <= 12) score += 1;
  else if (runners <= 16) score += 0;
  else                    score -= 1;  // 17+ runners: very negative

  // Going / Ground
  const goingScore = {
    Firm:              1,
    Good:              1,
    "Good to Soft":    0,
    Soft:              isJumps ? -1 : 0,
    Heavy:            -1,
    Standard:          1,
    "Standard to Slow": 0,
    Unknown:          -1,
  };
  score += goingScore[form.going] ?? 0;

  // Handicap: yes = more volatile
  if (form.handicap === "Yes") score -= 1;
  else score += 1;

  // Market shape
  if (form.marketShape === "Clear favourite") score += 2;
  else if (form.marketShape === "Very open")  score -= 2;
  // "Fairly open" = 0

  // Pace shape
  if (form.paceShape === "Clear leader") score += 1;
  else if (form.paceShape === "Weak pace")  score -= 1;
  else if (form.paceShape === "Unknown")    score -= 1;
  // "Some pace" = 0

  // Draw influence — only meaningful on Flat; unknown = slight negative
  if (form.drawInfluence === "Strong" && isFlat) score += 1;
  else if (form.drawInfluence === "Unknown")      score -= 1;
  // Moderate / Neutral = 0

  // Composite penalty: soft/heavy + Jumps + big field
  if ((form.going === "Soft" || form.going === "Heavy") && isJumps && runners > 14) {
    score -= 1;
  }

  if (score >= 4) return "HIGH";
  if (score >= 1) return "MEDIUM";
  return "LOW";
}

function buildReason(form, confidence) {
  const runners = parseInt(form.runners, 10) || 10;
  if (confidence === "HIGH") {
    return "Clear enough race shape and market structure for deeper analysis.";
  }
  if (confidence === "LOW") {
    if (runners > 16) return "Very large field makes this race too open to justify full entry.";
    if (form.marketShape === "Very open") return "Too open a market to justify full entry.";
    if (form.going === "Heavy") return "Heavy ground with limited clarity — too messy to justify full entry.";
    return "Too open or messy to justify full entry.";
  }
  // MEDIUM
  if (form.handicap === "Yes" && form.marketShape !== "Clear favourite") {
    return "Handicap with no clear market leader — borderline, use judgement.";
  }
  if (form.paceShape === "Weak pace" || form.paceShape === "Unknown") {
    return "Weak or unknown pace scenario limits clarity — borderline.";
  }
  return "Some structure, but not especially clear.";
}

// ---------------------------------------------------------------------------
// Default form state
// ---------------------------------------------------------------------------

const DEFAULT_FORM = {
  discipline:    "Flat",
  runners:       "",
  distance:      "",
  going:         "Good",
  handicap:      "No",
  marketShape:   "Fairly open",
  paceShape:     "Some pace",
  drawInfluence: "Neutral",
};

// ---------------------------------------------------------------------------
// Main component — self-contained, no external calls
// ---------------------------------------------------------------------------

export default function RacePreCheck() {
  const [form, setForm]     = useState(DEFAULT_FORM);
  const [result, setResult] = useState(null);

  const set = (key, val) => {
    setForm((prev) => ({ ...prev, [key]: val }));
    setResult(null); // clear result on any change
  };

  const runPrecheck = () => {
    const confidence = computePrecheck(form);
    const short_reason = buildReason(form, confidence);
    setResult({ precheck_confidence: confidence, short_reason });
  };

  const canRun = form.runners !== "" && parseInt(form.runners, 10) > 0;

  return (
    <div className="space-y-6">

      {/* ── Form ────────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-surface p-5 space-y-5">

        <p className="text-xs font-semibold uppercase tracking-widest text-text-dim text-center">
          Is this race worth betting on?
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

          {/* 1. Discipline */}
          <FormRow label="Discipline">
            <RadioGroup
              options={["Flat", "Jumps"]}
              value={form.discipline}
              onChange={(v) => set("discipline", v)}
            />
          </FormRow>

          {/* 2. Runners */}
          <FormRow label="Runners">
            <input
              type="number"
              min="1"
              max="40"
              placeholder="e.g. 12"
              value={form.runners}
              onChange={(e) => set("runners", e.target.value)}
              className="field-input w-full"
            />
          </FormRow>

          {/* 3. Distance */}
          <FormRow label="Distance">
            <input
              type="text"
              placeholder="e.g. 1m4f, 2m, 7f"
              value={form.distance}
              onChange={(e) => set("distance", e.target.value)}
              className="field-input w-full"
            />
          </FormRow>

          {/* 4. Going / Ground */}
          <FormRow label="Going / Ground">
            <Select
              value={form.going}
              onChange={(v) => set("going", v)}
              options={["Firm", "Good", "Good to Soft", "Soft", "Heavy", "Standard", "Standard to Slow", "Unknown"]}
            />
          </FormRow>

          {/* 5. Handicap */}
          <FormRow label="Handicap?">
            <RadioGroup
              options={["Yes", "No"]}
              value={form.handicap}
              onChange={(v) => set("handicap", v)}
            />
          </FormRow>

          {/* 6. Market Shape */}
          <FormRow label="Market Shape">
            <Select
              value={form.marketShape}
              onChange={(v) => set("marketShape", v)}
              options={["Clear favourite", "Fairly open", "Very open"]}
            />
          </FormRow>

          {/* 7. Pace Shape */}
          <FormRow label="Pace Shape">
            <Select
              value={form.paceShape}
              onChange={(v) => set("paceShape", v)}
              options={["Clear leader", "Some pace", "Weak pace", "Unknown"]}
            />
          </FormRow>

          {/* 8. Draw Influence */}
          <FormRow label="Draw Influence">
            <Select
              value={form.drawInfluence}
              onChange={(v) => set("drawInfluence", v)}
              options={["Strong", "Moderate", "Neutral", "Unknown"]}
            />
          </FormRow>

        </div>
      </div>

      {/* ── Run Button ──────────────────────────────────────────────────── */}
      <div className="flex justify-center">
        <button
          type="button"
          disabled={!canRun}
          onClick={runPrecheck}
          className="btn-primary text-base px-10 py-3"
        >
          Run Pre-Check
        </button>
      </div>

      {/* ── Result ──────────────────────────────────────────────────────── */}
      {result && <PrecheckResult result={result} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FormRow({ label, children }) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-semibold text-text-dim uppercase tracking-wide">
        {label}
      </label>
      {children}
    </div>
  );
}

function RadioGroup({ options, value, onChange }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
            value === opt
              ? "bg-gold/20 border-gold/60 text-gold"
              : "bg-surface-light/30 border-border text-text-dim hover:text-text hover:border-border/80"
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="field-input w-full"
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>{opt}</option>
      ))}
    </select>
  );
}

function PrecheckResult({ result }) {
  const { precheck_confidence, short_reason } = result;

  const colorMap = {
    HIGH:   { badge: "bg-emerald-500/20 border-emerald-500/40 text-emerald-300", dot: "bg-emerald-400" },
    MEDIUM: { badge: "bg-amber-500/20 border-amber-500/40 text-amber-300",       dot: "bg-amber-400"   },
    LOW:    { badge: "bg-red-500/20 border-red-500/40 text-red-300",             dot: "bg-red-400"     },
  };
  const style = colorMap[precheck_confidence] ?? colorMap.MEDIUM;

  const labelMap = {
    HIGH:   "Worth deeper analysis",
    MEDIUM: "Borderline — use judgement",
    LOW:    "Probably not worth full entry",
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-6 space-y-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-text-dim text-center">
        Race Pre-Check Result
      </p>

      <div className="flex flex-col items-center gap-2">
        <span className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full border text-sm font-bold ${style.badge}`}>
          <span className={`h-2 w-2 rounded-full ${style.dot}`} />
          {precheck_confidence}
        </span>
        <p className="text-xs text-text-dim">{labelMap[precheck_confidence] ?? ""}</p>
      </div>

      <p className="text-sm text-text text-center leading-relaxed">{short_reason}</p>

      <p className="text-xs text-text-dim text-center italic">
        Pre-check only — not a race prediction or winner selection
      </p>
    </div>
  );
}
