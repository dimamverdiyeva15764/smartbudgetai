export function ExpenseSelectCard({ icon, label, selected, onClick }) {
  return (
    <button
      type="button"
      className={`expense-select-card${selected ? ' is-selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </button>
  )
}
