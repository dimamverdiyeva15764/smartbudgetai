export function OptionButton({ label, selected, onClick }) {
  return (
    <button
      type="button"
      className={`option-btn ${selected ? 'is-selected' : ''}`}
      onClick={onClick}
    >
      <span>{label}</span>
    </button>
  )
}
