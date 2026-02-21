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
 * Handles FastAPI detail arrays [{msg,loc,type}], plain strings, objects.
 */
function extractErrorMsg(rawText, status) {
  if (!rawText) return `Server error (${status})`;
  try {
    const parsed = JSON.parse(rawText);
    const d = parsed.detail;
    if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join("; ");
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
 * Normalize any weight input into the "stone-lbs" string the backend expects.
 *   "9-4"  → "9-4"   (dash separator — passthrough)
 *   "9 4"  → "9-4"   (space separator)
 *   "9/4"  → "9-4"   (slash separator)
 *   "130"  → "9-4"   (raw lbs → convert back to stone-lbs)
 */
function normalizeWeight(str) {
  const s = (str || "").trim();
  const stLb = /^(\d+)[\s\-\/](\d+)$/.exec(s);
  if (stLb) return `${stLb[1]}-${stLb[2]}`;
  const n = parseInt(s, 10);
  if (!isNaN(n)) {
    const totalLbs = n > 50 ? n : n * 14;
    return `${Math.floor(totalLbs / 14)}-${totalLbs % 14}`;
  }
  return "9-4"; // safe fallback
}

/**
 * Normalize distance string for the backend.
 *   "7f"    → "7f"
 *   "1m"    → "1m"
 *   "1m4f"  → "1m4f"
 *   "2m 4f" → "2m4f"  (spaces stripped)
 *   "12"    → "12f"   (plain number → append f)
 */
function normalizeDistance(str) {
  const s = (str || "").trim().toLowerCase().replace(/\s+/g, "");
  if (!s) return "8f";
  if (/\d+[mf]/.test(s)) return s;
  const n = parseInt(s, 10);
  return isNaN(n) ? "8f" : `${n}f`;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_RACE = {
  course: "",
  race_type: "flat",
  surface: "aw",
  distance_str: "1m",
  going: "good",
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

  // Only require horse name + at least 2 runners for manual mode.
  const canSubmitManual =
    !loading &&
    runners.length >= 2 &&
    runners.every((r) => r.name.trim() !== "");

  const canSubmitPaste = !loading && pasteText.trim().length > 0;

  const canSubmit =
    inputMode === "manual" ? canSubmitManual : canSubmitPaste;

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const url =
        inputMode === "paste" ? `${API_BASE}/analyze-text` : `${API_BASE}/analyze`;

      // -----------------------------------------------------------------
      // JSON MODES — paste and manual
      // -----------------------------------------------------------------
      let payload;

      if (inputMode === "paste") {
        // /analyze-text expects { race_info: {...}, racecard_text: "..." }
        payload = {
          race_info: {
            course:    race.course || "Unknown",
            country:   "UK",
            race_type: race.race_type,
            surface:   race.surface,
            distance:  normalizeDistance(race.distance_str),
            going:     race.going,
          },
          racecard_text: pasteText,
        };
      } else {
        // /analyze expects flat AnalyzeRequest
        // weight → "stone-lbs" string  |  distance → "1m4f" string
        payload = {
          course:    race.course || "Unknown",
          country:   "UK",
          race_type: race.race_type,
          surface:   race.surface,
          distance:  normalizeDistance(race.distance_str),
          going:     race.going,
          runners: runners.map((r) => ({
            name:            r.name,
            age:             r.age || 4,
            weight:          normalizeWeight(r.weight_st),
            form:            r.form.trim() || "",
            trainer:         r.trainer || "",
            jockey:          r.jockey || "",
            draw:            null,
            jockey_claim_lbs: 0,
          })),
        };
      }

      console.log("FINAL PAYLOAD", JSON.stringify(payload, null, 2));

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const raw = await res.text().catch(() => "");
        throw new Error(extractErrorMsg(raw, res.status));
      }

      setResult(await res.json());
    } catch (err) {
      if (err instanceof TypeError && err.message === "Failed to fetch") {
        setError("Cannot reach backend — check API URL or CORS.");
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
