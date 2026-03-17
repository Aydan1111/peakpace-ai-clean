import { useRef } from "react";

/**
 * RacePreCheck — screenshot-based broad triage tool.
 *
 * Requires TWO screenshots before the Run Pre-Check button is enabled:
 *   1. Main Race Screenshot  (market shape, prices, field size, race structure)
 *   2. ATR Draw/Pace Screenshot  (draw and pace setup)
 *
 * Props:
 *   mainShot       – { file, preview, mediaType } | null
 *   drawShot       – { file, preview, mediaType } | null
 *   onMainChange   – (shotObj | null) => void
 *   onDrawChange   – (shotObj | null) => void
 *   onRun          – () => void
 *   loading        – bool
 *   result         – { precheck_confidence, short_reason } | null
 *   error          – string | null
 */
export default function RacePreCheck({
  mainShot,
  drawShot,
  onMainChange,
  onDrawChange,
  onRun,
  loading,
  result,
  error,
}) {
  const mainRef = useRef(null);
  const drawRef = useRef(null);

  const bothPresent = !!mainShot && !!drawShot;
  const canRun = bothPresent && !loading;

  const handleFile = (e, setter) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setter({ file, preview: ev.target.result, mediaType: file.type || "image/png" });
    };
    reader.readAsDataURL(file);
    // Reset input so same file can be re-selected
    e.target.value = "";
  };

  const clearShot = (setter, inputRef) => {
    setter(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  // Waiting message shown when only one screenshot is uploaded
  let waitingMsg = null;
  if (!mainShot && !drawShot) {
    waitingMsg = null; // show nothing — user hasn't started yet
  } else if (!mainShot && drawShot) {
    waitingMsg = "Waiting for main race screenshot";
  } else if (mainShot && !drawShot) {
    waitingMsg = "Waiting for ATR draw/pace screenshot";
  }

  return (
    <div className="space-y-6">

      {/* ── Upload Areas ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <UploadArea
          label="Main Race Screenshot"
          hint="Market odds · field size · race type · race structure"
          shot={mainShot}
          inputRef={mainRef}
          onSelect={(e) => handleFile(e, onMainChange)}
          onClear={() => clearShot(onMainChange, mainRef)}
        />
        <UploadArea
          label="ATR Draw / Pace Screenshot"
          hint="Draw setup · pace setup"
          shot={drawShot}
          inputRef={drawRef}
          onSelect={(e) => handleFile(e, onDrawChange)}
          onClear={() => clearShot(onDrawChange, drawRef)}
        />
      </div>

      {/* ── Waiting Message ─────────────────────────────────────────────── */}
      {waitingMsg && (
        <p className="text-center text-sm text-text-dim italic">{waitingMsg}</p>
      )}

      {/* ── Run Button ──────────────────────────────────────────────────── */}
      <div className="flex justify-center">
        <button
          type="button"
          disabled={!canRun}
          onClick={onRun}
          className="btn-primary text-base px-10 py-3"
        >
          {loading ? "Running Pre-Check…" : "Run Pre-Check"}
        </button>
      </div>

      {/* ── Error ───────────────────────────────────────────────────────── */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 text-red-400 text-sm text-center">
          {error}
        </div>
      )}

      {/* ── Result ──────────────────────────────────────────────────────── */}
      {result && <PrecheckResult result={result} />}
    </div>
  );
}


/* ── Sub-components ──────────────────────────────────────────────────────── */

function UploadArea({ label, hint, shot, inputRef, onSelect, onClear }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <div>
        <p className="text-sm font-semibold text-text">{label}</p>
        <p className="text-xs text-text-dim mt-0.5">{hint}</p>
      </div>

      {shot ? (
        <div className="relative">
          <img
            src={shot.preview}
            alt={label}
            className="w-full rounded-lg object-contain max-h-48 border border-border"
          />
          <button
            type="button"
            onClick={onClear}
            className="absolute top-1 right-1 rounded-full bg-surface/80 border border-border px-2 py-0.5 text-xs text-text-dim hover:text-text transition-colors"
          >
            Remove
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="w-full rounded-lg border-2 border-dashed border-border hover:border-gold/60 bg-surface-light/30 hover:bg-surface-light/60 transition-colors py-8 flex flex-col items-center gap-2"
        >
          <UploadIcon />
          <span className="text-xs text-text-dim">Click to upload screenshot</span>
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onSelect}
      />
    </div>
  );
}

function UploadIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-6 w-6 text-text-dim"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
      />
    </svg>
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
