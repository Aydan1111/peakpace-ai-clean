export default function Spinner() {
  return (
    <div className="flex items-center justify-center gap-3 py-8">
      <div className="h-6 w-6 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
      <span className="text-text-dim text-sm">Analyzing race&hellip;</span>
    </div>
  );
}
