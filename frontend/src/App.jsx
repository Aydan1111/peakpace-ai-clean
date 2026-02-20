import { useState } from "react";
import ModeToggle from "./components/ModeToggle";
import RaceForm from "./components/RaceForm";
import RunnerTable from "./components/RunnerTable";
import PasteInput from "./components/PasteInput";
import ResultsPanel from "./components/ResultsPanel";
import Spinner from "./components/Spinner";

/*
  CLEAN PRODUCTION API SETUP
  --------------------------
  1️⃣ Uses Vercel env variable if set
  2️⃣ Falls back to your current backend
*/
const API_BASE =
  (import.meta.env.VITE_API_BASE_URL ||
    "https://peakpace-ai.onrender.com"
  ).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Turn any backend error response body into a human-readable string.
 * Handles FastAPI's {detail: [...]} arrays, plain strings, and objects.
 */
function extractErrorMsg(rawText, status) {
  if (!rawText) return `Server error (${status})`;
  try {
    const parsed = JSON.parse(rawText);
    const d = parsed.detail;
    if (Array.isArray(d)) {
      // FastAPI validation errors: [{msg, loc, type}, ...]
      return d.map((e) => e.msg || JSON.stringify(e)).join("; ");
    }
    if (d && typeof d === "object") return d.msg || JSON.stringify(d);
    if (typeof d === "string") return d;
    const fallback = parsed.error || parsed.message;
    if (typeof fallback === "string") return fallback;
    return JSON.stringify(parsed);
  } catch {
    return rawText;
  }
}

/**
 * Forgiving weight parser — accepts:
 *   "9-4"  → 9st 4lb = 130 lbs
 *   "9 4"  → same
 *   "9/4"  → same
 *   "130"  → raw lbs (>50 treated as lbs, ≤50 treated as stone)
 */
function parseWeightSt(str) {
  const s = (str || "").trim();
  // st-lb with any separator: dash, slash, or space
  const stLb = /^(\d+)[\s\-\/](\d+)$/.exec(s);
  if (stLb) return parseInt(stLb[1], 10) * 14 + parseInt(stLb[2], 10);
  // Single number: >50 → raw lbs, ≤50 → treat as stone only
  const n = parseInt(s, 10);
  if (!isNaN(n)) return n > 50 ? n : n * 14;
  return 130; // safe fallback
}

/**
 * Forgiving distance parser — accepts:
 *   "7f"   → 7
 *   "1m"   → 8
 *   "1m4f" → 12
 *   "2m4f" → 20
 *   "2m 4f"→ 20  (spaces stripped)
 *   "12"   → 12  (raw furlongs)
 */
function parseDistanceStr(str) {
  // Strip all spaces so "2m 4f" → "2m4f"
  const s = (str || "").trim().toLowerCase().replace(/\s+/g, "");
  const mf = /^(\d+)m(\d+)f$/.exec(s);
  if (mf) return parseInt(mf[1], 10) * 8 + parseInt(mf[2], 10);
  const m = /^(\d+)m$/.exec(s);
  if (m) return parseInt(m[1], 10) * 8;
  const f = /^(\d+)f$/.exec(s);
  if (f) return parseInt(f[1], 10);
  const n = parseFloat(s);
  return isNaN(n) ? 8 : n;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_RACE = {
  course: "",
  race_type: "flat",
  surface: "aw",
  distance_str: "1m",
  going: "standard",
};

const DEFAULT_RUNNERS = [
  { name: "", age: 4, weight_st: "9-4", form: "", trainer: "", jockey: "" },
  { name: "", age: 4, weight_st: "9-4", form: "", trainer: "", jockey: "" },
  { name: "", age: 4, weight_st: "9-4", form: "", trainer: "", jockey: "" },
];

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [inputMode, setInputMode] = useState("manual");
  const [race, setRace] = useState(DEFAULT_RACE);
  const [runners, setRunners] = useState(DEFAULT_RUNNERS);
  const [pasteText, setPasteText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Only require: horse name present + at least 2 runners.
  // Course, form, weight etc. are all optional — backend handles defaults.
  const canSubmitManual =
    !loading &&
    runners.length >= 2 &&
    runners.every((r) => r.name.trim() !== "");

  const canSubmitPaste = !loading && pasteText.trim().length > 0;
  const canSubmit = inputMode === "manual" ? canSubmitManual : canSubmitPaste;

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const url =
        inputMode === "paste"
          ? `${API_BASE}/analyze-text`
          : `${API_BASE}/analyze`;

      const options =
        inputMode === "paste"
          ? {
              method: "POST",
              headers: { "Content-Type": "text/plain" },
              body: pasteText,
            }
          : {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                race: {
                  course: race.course || "",
                  race_type: race.race_type,
                  surface: race.surface,
                  distance_f: parseDistanceStr(race.distance_str),
                  going: race.going,
                  country: "UK",
                  runners: runners.length,
                  track_config: "standard",
                },
                runners: runners.map((r) => ({
                  name: r.name,
                  age: r.age || null,
                  weight_lbs: parseWeightSt(r.weight_st),
                  form: r.form.trim() || "0",   // blank form → safe default
                  trainer: r.trainer || "",
                  jockey: r.jockey || "",
                  flags: [],
                  headgear: [],
                  jockey_claim_lbs: 0,
                  draw: null,
                  days_since_run: null,
                  pace_hint: null,
                })),
                mode: "standard",
              }),
            };

      const res = await fetch(url, options);

      if (!res.ok) {
        const raw = await res.text().catch(() => "");
        throw new Error(extractErrorMsg(raw, res.status));
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        setError("Cannot reach backend — check API URL or CORS.");
      } else if (inputMode === "paste") {
        // Give a helpful hint for paste-mode failures
        setError(
          `Could not fully parse racecard — ${err.message || "check formatting."}`
        );
      } else {
        setError(err.message || "Request failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto space-y-6">

        <header className="text-center mb-2">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
            <span className="text-gold">PeakPace</span>{" "}
            <span className="text-text-dim font-light">AI</span>
          </h1>
          <p className="text-text-dim text-sm mt-1">
            Racing intelligence for UK &amp; Irish horse racing
          </p>
        </header>

        <ModeToggle mode={inputMode} onChange={setInputMode} />

        {inputMode === "manual" ? (
          <>
            <RaceForm race={race} onChange={setRace} />
            <RunnerTable runners={runners} onChange={setRunners} />
          </>
        ) : (
          <PasteInput value={pasteText} onChange={setPasteText} />
        )}

        <div className="flex justify-center">
          <button
            type="button"
            disabled={!canSubmit}
            onClick={analyze}
            className="btn-primary text-base px-10 py-3"
          >
            {loading ? "Analyzing…" : "Analyze Race"}
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 text-red-400 text-sm text-center">
            {error}
          </div>
        )}

        {loading && <Spinner />}

        <ResultsPanel result={result} />
      </div>
    </div>
  );
}
