import { useState } from "react";
import ModeToggle from "./components/ModeToggle";
import RaceForm from "./components/RaceForm";
import RunnerTable from "./components/RunnerTable";
import PasteInput from "./components/PasteInput";
import ResultsPanel from "./components/ResultsPanel";
import Spinner from "./components/Spinner";
import RacePreCheck from "./components/RacePreCheck";
import JumpsCheckFilter from "./components/JumpsCheckFilter";

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
// Guided Entry — inline fallback template (used if /canonical-template fails)
// ---------------------------------------------------------------------------
const GUIDED_TEMPLATE_FALLBACK = `COURSE:
RACE:
TYPE:
DISTANCE:
RUNNERS:
CLASS:
GOING / GROUND:
GROUND:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:

HORSE:
JOCKEY:
TRAINER:
FORM:
AGE:
WEIGHT:
OR:
RPR:
TS:
ODDS:
EQUIPMENT:
COMMENT:

RECENT RUNS:
`;

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

/**
 * Convert a distance string ("2m4f", "1m", "8f", "2m 4f 29y") to furlongs.
 * Used when building previous_runs for the engine.
 */
function distToFurlongs(str) {
  const s = (str || "").toLowerCase();
  const mMatch = s.match(/(\d+)\s*m/);
  const fMatch = s.match(/(\d+)\s*f/);
  const yMatch = s.match(/(\d+)\s*y/);
  const miles    = mMatch ? parseInt(mMatch[1]) : 0;
  const furlongs = fMatch ? parseInt(fMatch[1]) : 0;
  const yards    = yMatch ? parseInt(yMatch[1]) : 0;
  return miles * 8 + furlongs + yards / 220;
}

/**
 * Convert the UI previous_runs array (strings) into the engine format
 * ({distance_f, going, pos, field_size, discipline}).
 * Rows missing pos or field_size are dropped.
 */
function buildPrevRuns(uiRuns) {
  if (!uiRuns || uiRuns.length === 0) return null;
  const converted = uiRuns
    .filter((pr) => pr.pos && pr.field_size)
    .map((pr) => ({
      distance_f:  distToFurlongs(pr.distance),
      going:       (pr.going || "good").toLowerCase(),
      pos:         parseInt(pr.pos)        || 1,
      field_size:  parseInt(pr.field_size) || 10,
      discipline:  pr.discipline || "flat",
    }))
    .filter((pr) => pr.distance_f > 0);
  return converted.length > 0 ? converted : null;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_RACE = {
  course: "",
  race_name: "",
  race_type: "flat",
  distance_str: "1m",
  runners_count: "",
  race_class: "",
  going: "not_specified",
  ground_bucket: null,
  surface: "aw",
};

const DEFAULT_RUNNERS = [
  { name: "", age: 4, weight_st: "9-4", form: "", trainer: "", jockey: "", equipment: "", comment: "", previous_runs: [], or_rating: "", rpr: "", top_speed: "" },
  { name: "", age: 4, weight_st: "9-4", form: "", trainer: "", jockey: "", equipment: "", comment: "", previous_runs: [], or_rating: "", rpr: "", top_speed: "" },
  { name: "", age: 4, weight_st: "9-4", form: "", trainer: "", jockey: "", equipment: "", comment: "", previous_runs: [], or_rating: "", rpr: "", top_speed: "" },
];

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [inputMode, setInputMode] = useState("manual");
  const [race, setRace] = useState(DEFAULT_RACE);
  const [runners, setRunners] = useState(DEFAULT_RUNNERS);
  // guidedText is pre-populated with the canonical template on first switch to
  // guided mode and then edited freely by the user.
  const [guidedText, setGuidedText] = useState("");
  const [guidedTemplateLoaded, setGuidedTemplateLoaded] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Silver + Dark Horse toggles — both off by default; Gold always shown
  const [silverEnabled, setSilverEnabled] = useState(false);
  const [darkHorseEnabled, setDarkHorseEnabled] = useState(false);

  // When switching to guided mode for the first time, fetch and pre-populate
  // the canonical template from the backend.
  const handleModeChange = (newMode) => {
    setInputMode(newMode);
    if (newMode === "guided" && !guidedTemplateLoaded) {
      fetch(`${API_BASE}/canonical-template`)
        .then((r) => r.json())
        .then((data) => {
          if (data.template && !guidedText) {
            setGuidedText(data.template);
          }
          setGuidedTemplateLoaded(true);
        })
        .catch(() => {
          // Fallback inline template if the endpoint is unreachable
          if (!guidedText) {
            setGuidedText(GUIDED_TEMPLATE_FALLBACK);
          }
          setGuidedTemplateLoaded(true);
        });
    }
  };

  const handleGuidedChange = (val) => setGuidedText(val);
  const handleRaceChange  = (val) => setRace(val);
  const handleRunnersChange = (val) => setRunners(val);

  // Only require horse name + at least 2 runners for manual mode.
  const canSubmitManual =
    !loading &&
    runners.length >= 2 &&
    runners.every((r) => r.name.trim() !== "");

  const canSubmitGuided = !loading && guidedText.trim().length > 0;

  const canSubmit = inputMode === "manual" ? canSubmitManual : canSubmitGuided;

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const isTextMode = inputMode === "guided";
      const url = isTextMode ? `${API_BASE}/analyze-text` : `${API_BASE}/analyze`;

      // -----------------------------------------------------------------
      // JSON MODES — paste/guided and manual
      // -----------------------------------------------------------------
      let payload;

      // For manual mode, build odds dict from inline runner odds fields.
      // For paste/guided mode, odds are extracted per-runner in the backend parser
      // (ODDS: field in each racecard block); no separate odds payload needed.
      const inlineOdds = Object.fromEntries(
        runners
          .filter((r) => r.name.trim() && (r.odds || "").trim())
          .map((r) => [r.name.trim(), r.odds.trim()])
      );
      const manualOddsPayload = Object.keys(inlineOdds).length > 0 ? inlineOdds : undefined;

      // Map canonical TYPE values to backend race_type (flat vs national_hunt).
      const backendRaceType = race.race_type === "flat" ? "flat" : "national_hunt";

      if (isTextMode) {
        // /analyze-text expects { race_info: {...}, racecard_text: "..." }
        // Odds come from ODDS: fields inside the pasted/guided racecard text.
        payload = {
          race_info: {
            course:        race.course || "Unknown",
            country:       "UK",
            race_type:     backendRaceType,
            surface:       race.surface,
            distance:      normalizeDistance(race.distance_str),
            going:         race.going,
            ground_bucket: race.ground_bucket || null,
          },
          racecard_text: guidedText,
          silver_enabled: silverEnabled,
          dark_horse_enabled: darkHorseEnabled,
        };
      } else {
        // /analyze expects flat AnalyzeRequest
        // weight → "stone-lbs" string  |  distance → "1m4f" string
        payload = {
          course:        race.course || "Unknown",
          country:       "UK",
          race_type:     backendRaceType,
          surface:       race.surface,
          distance:      normalizeDistance(race.distance_str),
          going:         race.going,
          ground_bucket: race.ground_bucket || null,
          runners: runners.map((r) => {
            const paceMap = {
              "HOLD_UP":   "hold_up",
              "MIDFIELD":  "midfield",
              "PROMINENT": "prominent",
              "LEADER":    "leader",
            };
            const toIntOrNull = (v) => {
              const n = parseInt(v, 10);
              return isNaN(n) ? null : n;
            };
            return {
              name:             r.name,
              age:              r.age || 4,
              weight:           normalizeWeight(r.weight_st),
              form:             r.form.trim() || "",
              trainer:          r.trainer || "",
              jockey:           r.jockey || "",
              draw:             r.draw ? parseInt(r.draw, 10) : null,
              jockey_claim_lbs: 0,
              equipment:        r.equipment || "",
              comment:          r.comment   || "",
              previous_runs:    buildPrevRuns(r.previous_runs),
              pace_style:       paceMap[r.pace] || null,
              or_rating:        toIntOrNull(r.or_rating),
              rpr:              toIntOrNull(r.rpr),
              top_speed:        toIntOrNull(r.top_speed),
            };
          }),
          odds: manualOddsPayload,
          silver_enabled: silverEnabled,
          dark_horse_enabled: darkHorseEnabled,
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
        style={{ backgroundImage: "url('/images/PeakPace AI Horse Head.png')" }}
      >
        <div className="hero-gradient" aria-hidden="true" />
        <div className="hero-content">
          <img
            src="/images/PeakPace AI Horse Head.png"
            alt="PeakPace AI horse head"
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

          <ModeToggle mode={inputMode} onChange={handleModeChange} />

          {inputMode === "precheck" ? (
            <RacePreCheck />
          ) : inputMode === "jumps" ? (
            <JumpsCheckFilter />
          ) : inputMode === "manual" ? (
            <>
              <RaceForm race={race} onChange={handleRaceChange} />
              <RunnerTable runners={runners} onChange={handleRunnersChange} />
            </>
          ) : (
            <PasteInput
              value={guidedText}
              onChange={handleGuidedChange}
              mode="guided"
            />
          )}

          {/* Silver + Dark Horse Toggles + Analyze button — hidden in precheck and jumps modes */}
          {inputMode !== "precheck" && inputMode !== "jumps" && (
            <>
              <div className="flex flex-wrap justify-center items-center gap-x-8 gap-y-3">
                {/* Silver Pick Toggle */}
                <label className="flex items-center gap-3 cursor-pointer select-none group">
                  {/* Track */}
                  <span
                    onClick={() => setSilverEnabled((v) => !v)}
                    className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 transition-colors duration-200 ${
                      silverEnabled
                        ? "border-gray-300 bg-gray-300/30"
                        : "border-border bg-surface-light"
                    }`}
                  >
                    {/* Thumb */}
                    <span
                      className={`inline-block h-4 w-4 mt-0.5 rounded-full shadow transition-transform duration-200 ${
                        silverEnabled
                          ? "translate-x-5 bg-gray-200"
                          : "translate-x-0.5 bg-text-dim"
                      }`}
                    />
                  </span>
                  <span className={`text-sm font-medium transition-colors ${silverEnabled ? "text-gray-200" : "text-text-dim"}`}>
                    Enable Silver Pick
                  </span>
                </label>

                {/* Dark Horse Toggle */}
                <label className="flex items-center gap-3 cursor-pointer select-none group">
                  {/* Track */}
                  <span
                    onClick={() => setDarkHorseEnabled((v) => !v)}
                    className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 transition-colors duration-200 ${
                      darkHorseEnabled
                        ? "border-purple-500 bg-purple-500/30"
                        : "border-border bg-surface-light"
                    }`}
                  >
                    {/* Thumb */}
                    <span
                      className={`inline-block h-4 w-4 mt-0.5 rounded-full shadow transition-transform duration-200 ${
                        darkHorseEnabled
                          ? "translate-x-5 bg-purple-400"
                          : "translate-x-0.5 bg-text-dim"
                      }`}
                    />
                  </span>
                  <span className={`text-sm font-medium transition-colors ${darkHorseEnabled ? "text-purple-300" : "text-text-dim"}`}>
                    Enable Dark Horse Pick
                  </span>
                </label>
              </div>

              <div className="flex justify-center gap-3">
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

              <ResultsPanel
                result={result}
                silverEnabled={silverEnabled}
                darkHorseEnabled={darkHorseEnabled}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
