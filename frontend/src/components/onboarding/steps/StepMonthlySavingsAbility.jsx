const SAVINGS_OPTIONS = [
  { id: 'can_save', label: 'Bəli, müntəzəm' },
  { id: 'sometimes', label: 'Bəzən' },
  { id: 'cannot_save', label: 'Xeyr' }
]

export function StepMonthlySavingsAbility({ value, onChange }) {
  return (
    <div className="step-content">
      <h4 className="question-title">Hər ay pul yığa bilirsiniz?</h4>
      <div className="savings-ability-options">
        {SAVINGS_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={`savings-ability-option${value === option.id ? ' is-selected' : ''}`}
            onClick={() => onChange(option.id)}
            aria-pressed={value === option.id}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}