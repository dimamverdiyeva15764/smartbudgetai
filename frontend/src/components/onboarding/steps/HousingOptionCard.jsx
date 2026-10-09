/**
 * HousingOptionCard – single-select card for housing type (Step 3).
 * Props:
 *   icon     – SVG element or react-icons component
 *   label    – string displayed under the icon
 *   selected – boolean, true when this option is active
 *   onClick  – callback
 */
export function HousingOptionCard({ icon, label, selected, onClick }) {
  return (
    <button
      type="button"
      id={`housing-option-${label.replace(/\s+/g, '-').toLowerCase()}`}
      className={`housing-option-card${selected ? ' is-selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span className="housing-card-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="housing-card-label">{label}</span>
    </button>
  )
}
