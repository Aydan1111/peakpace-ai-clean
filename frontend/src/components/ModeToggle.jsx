export default function ModeToggle({ mode, onChange }) {
  return (
    <div className="flex justify-center">
      <div className="inline-flex rounded-lg border border-border bg-surface p-1 gap-1">
        <ToggleButton
          active={mode === "precheck"}
          onClick={() => onChange("precheck")}
        >
          Race Pre-Check
        </ToggleButton>
        <ToggleButton
          active={mode === "manual"}
          onClick={() => onChange("manual")}
        >
          Form Entry
        </ToggleButton>
        <ToggleButton
          active={mode === "guided"}
          onClick={() => onChange("guided")}
        >
          Guided Entry
        </ToggleButton>
      </div>
    </div>
  );
}

function ToggleButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active
          ? "bg-gold text-[#111] shadow-sm"
          : "text-text-dim hover:text-text"
      }`}
    >
      {children}
    </button>
  );
}
