// force rebuild

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

const DEFAULT_RACE = {
  course: "",
  race_type: "flat",
  surface: "aw",
  distance_f: 8,
  race_class: 4,
  going: "standard",
};

const DEFAULT_RUNNERS = [
  { name: "", age: 4, weight_lbs: 130, form: "", trainer: "", jockey: "" },
  { name: "", age: 4, weight_lbs: 130, form: "", trainer: "", jockey: "" },
  { name: "", age: 4, weight_lbs: 130, form: "", trainer: "", jockey: "" },
];

export default function App() {
  const [inputMode, setInputMode] = useState("manual");
  const [race, setRace] = useState(DEFAULT_RACE);
  const [runners, setRunners] = useState(DEFAULT_RUNNERS);
  const [pasteText, setPasteText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const canSubmitManual =
    !loading &&
    race.course.trim() !== "" &&
    runners.length >= 2 &&
    runners.every((r) => r.name.trim() !== "" && r.form.trim() !== "");

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
                  ...race,
                  country: "UK",
                  runners: runners.length,
                  track_config: "standard",
                },
                runners: runners.map((r) => ({
                  ...r,
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
        let msg = `Server error (${res.status})`;

        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            msg = parsed.detail || parsed.error || parsed.message || raw;
          } catch {
            msg = raw;
          }
        }

        throw new Error(msg);
      }

      const data = await res.json();
      setResult(data);
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
