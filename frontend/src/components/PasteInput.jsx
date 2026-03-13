const GUIDED_HINT = `Fill in the race details and each horse's information below.
Only HORSE: is required — leave other fields blank if unknown.`;

const PASTE_HINT = `Paste the full race card text below — the AI will extract runners, form,
trainers, jockeys, and race details automatically.`;

export default function PasteInput({ value, onChange, mode = "paste" }) {
  const isGuided = mode === "guided";
  const title    = isGuided ? "Guided Racecard Entry" : "Paste Race Card";
  const hint     = isGuided ? GUIDED_HINT : PASTE_HINT;
  const placeholder = isGuided
    ? "Fill in details above each HORSE: line…"
    : "Paste race card text here…\n\ne.g. from Racing Post, Timeform, or At The Races";

  return (
    <section className="bg-surface rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold text-gold mb-1">{title}</h2>
      <p className="text-text-dim text-xs mb-4 whitespace-pre-line">{hint}</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={isGuided ? 28 : 14}
        className="input resize-y min-h-[200px] font-mono text-sm leading-relaxed"
      />
    </section>
  );
}
