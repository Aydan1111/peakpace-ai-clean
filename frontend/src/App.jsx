import { useState } from "react";
import ModeToggle from "./components/ModeToggle";
import RaceForm from "./components/RaceForm";
import RunnerTable from "./components/RunnerTable";
import PasteInput from "./components/PasteInput";
import ResultsPanel from "./components/ResultsPanel";
import RaceQualityBadge from "./components/RaceQualityBadge";
import OddsInput from "./components/OddsInput";
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

  // Race quality check state
  const [quality, setQuality] = useState(null);       // quality check result
  const [checkingQuality, setCheckingQuality] = useState(false);
  const [qualityError, setQualityError] = useState(null);

  // Odds — keyed by runner name, values are strings ("9/1", "evs", etc.)
  const [odds, setOdds] = useState({});

  // Reset quality + odds when the racecard changes
  const handlePasteChange = (val) => {
    setPasteText(val);
    setQuality(null);
    setOdds({});
  };
  const handleRaceChange = (val) => {
    setRace(val);
    setQuality(null);
    setOdds({});
  };
  const handleRunnersChange = (val) => {
    setRunners(val);
    setQuality(null);
    setOdds({});
  };

  // Only require horse name + at least 2 runners for manual mode.
  const canSubmitManual =
    !loading &&
    runners.length >= 2 &&
    runners.every((r) => r.name.trim() !== "");

  const canSubmitPaste = !loading && pasteText.trim().length > 0;

  const canSubmit =
    inputMode === "manual" ? canSubmitManual : canSubmitPaste;

  // ── Race quality check ─────────────────────────────────────────────────
  const checkQuality = async () => {
    setCheckingQuality(true);
    setQualityError(null);
    setQuality(null);
    setOdds({});

    try {
      const url =
        inputMode === "paste"
          ? `${API_BASE}/race-quality-text`
          : `${API_BASE}/race-quality`;

      let payload;
      if (inputMode === "paste") {
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
        payload = {
          course:    race.course || "Unknown",
          country:   "UK",
          race_type: race.race_type,
          surface:   race.surface,
          distance:  normalizeDistance(race.distance_str),
          going:     race.going,
          runners: runners.map((r) => ({
            name:             r.name,
            age:              r.age || 4,
            weight:           normalizeWeight(r.weight_st),
            form:             r.form.trim() || "",
            trainer:          r.trainer || "",
            jockey:           r.jockey || "",
            draw:             null,
            jockey_claim_lbs: 0,
          })),
        };
      }

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const raw = await res.text().catch(() => "");
        throw new Error(extractErrorMsg(raw, res.status));
      }
      const data = await res.json();
      setQuality(data);
      // Pre-seed odds keys from returned runner names
      if (data.runner_names) {
        const seed = {};
        data.runner_names.forEach((n) => { seed[n] = ""; });
        setOdds(seed);
      }
    } catch (err) {
      setQualityError(err.message || "Quality check failed");
    } finally {
      setCheckingQuality(false);
    }
  };

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

      // Strip empty odds values before sending
      const activeOdds = Object.fromEntries(
        Object.entries(odds).filter(([, v]) => v.trim() !== "")
      );
      const oddsPayload = Object.keys(activeOdds).length > 0 ? activeOdds : undefined;

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
          odds: oddsPayload,
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
          odds: oddsPayload,
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
        console.error("RESPONSE ERROR", res.status, raw);
        throw new Error(extractErrorMsg(raw, res.status));
      }

      const data = await res.json();
      console.log("RESPONSE OK", JSON.stringify(data, null, 2));
      if (!data || (!data.gold_pick && !data.full_rankings)) {
        throw new Error("Analysis failed \u2013 check backend response");
      }
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
    <div className="min-h-screen">

      {/* ── Hero Section ─────────────────────────────────────────────────── */}
      <div
        className="hero-section"
        style={{ backgroundImage: "url('/images/hero-bg.jpg')" }}
      >
        <div className="hero-gradient" aria-hidden="true" />
        <div className="hero-content">
          <img
            src="/images/hero-bg.jpg"
            alt="Horse head sculpture"
            className="hero-horse-img"
          />
          <h1 className="hero-title">
            <span className="text-gold">PeakPace</span>{" "}
            <span className="hero-title-ai">AI</span>
          </h1>
          <p className="hero-subtitle">
            Racing intelligence for UK &amp; Irish horse racing
          </p>
        </div>
      </div>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="px-4 py-8 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto space-y-6">

          <ModeToggle mode={inputMode} onChange={setInputMode} />

          {inputMode === "manual" ? (
            <>
              <RaceForm race={race} onChange={handleRaceChange} />
              <RunnerTable runners={runners} onChange={handleRunnersChange} />
            </>
          ) : (
            <PasteInput value={pasteText} onChange={handlePasteChange} />
          )}

          {/* Race quality badge + odds panel */}
          {quality && (
            <RaceQualityBadge quality={quality} />
          )}
          {quality && (
            <OddsInput
              quality={quality}
              odds={odds}
              onChange={setOdds}
            />
          )}

          {qualityError && (
            <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-red-400 text-sm text-center">
              {qualityError}
            </div>
          )}

          <div className="flex justify-center gap-3">
            <button
              type="button"
              disabled={!canSubmit || checkingQuality}
              onClick={checkQuality}
              className="btn-secondary text-sm px-6 py-3"
            >
              {checkingQuality ? "Checking…" : "Check Race"}
            </button>
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
    </div>
  );
}
