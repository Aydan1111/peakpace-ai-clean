export default function PasteInput({ value, onChange }) {
  return (
    <section className="bg-surface rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold text-gold mb-1">Paste Race Card</h2>
      <p className="text-text-dim text-xs mb-4">
        Paste the full race card text below — the AI will extract runners, form,
        trainers, jockeys, and race details automatically.
      </p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={"Paste race card text here…\n\ne.g. from Racing Post, Timeform, or At The Races"}
        rows={14}
        className="input resize-y min-h-[200px] font-mono text-sm leading-relaxed"
      />
    </section>
  );
}
