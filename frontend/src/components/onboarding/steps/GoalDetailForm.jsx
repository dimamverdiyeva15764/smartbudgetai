import { CustomInput } from '../../common/CustomInput'

const PRIORITIES = [
  'Aşağı prioritet',
  'Orta prioritet',
  'Yuxarı prioritet'
]

export function GoalDetailForm({ goal, onPriorityChange, onAmountChange, onAmountClear, onCustomNameChange, onSavedAmountChange, onDeadlineChange }) {
  return (
    <section className="goal-detail-form" aria-labelledby={`goal-detail-${goal.id}`}>
      <h5 id={`goal-detail-${goal.id}`} className="goal-detail-title">{goal.label}</h5>

      {goal.id === 'other' && (
      <CustomInput
        id={`goal-custom-name-${goal.id}`}
        label="Məqsədin adı"
        value={goal.customName || ''}
        onChange={onCustomNameChange}
        onClear={() => onCustomNameChange('')}
        placeholder="Məsələn: Yeni notbuk"
        type="text"
      />
      )}

      <fieldset className="priority-fieldset">
        <legend>Prioritet növü</legend>
        <div className="priority-options">
          {PRIORITIES.map((priority) => (
            <label key={priority} className="priority-option">
              <input
                type="radio"
                name={`priority-${goal.id}`}
                value={priority}
                checked={goal.priority === priority}
                onChange={() => onPriorityChange(priority)}
              />
              <span>{priority}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <CustomInput
        id={`goal-amount-${goal.id}`}
        label="Yığım məbləğini daxil edin"
        value={goal.amount}
        onChange={onAmountChange}
        onClear={onAmountClear}
        placeholder="0"
      />
      {onSavedAmountChange && (
        <CustomInput
          id={`goal-saved-${goal.id}`}
          label="Artıq yığılmış məbləğ (varsa)"
          value={goal.savedAmount ?? ''}
          onChange={onSavedAmountChange}
          onClear={() => onSavedAmountChange('')}
          placeholder="0"
        />
      )}
      {onDeadlineChange && (
        <CustomInput
          id={`goal-deadline-${goal.id}`}
          label="Neçə aya yığmaq istəyirsiniz?"
          value={goal.deadlineMonths ?? ''}
          onChange={onDeadlineChange}
          onClear={() => onDeadlineChange('')}
          placeholder="12"
          unit="ay"
          integer
        />
      )}
    </section>
  )
}
