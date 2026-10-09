export function GoalOptionCard({ icon, label, selected, onClick, disabled = false, hint }) {
  return (
    <button
      type="button"
      className={`savings-goal-card${selected ? ' is-selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
      disabled={disabled}
      title={hint}
    >
      <span className="savings-goal-icon" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </button>
  )
}
