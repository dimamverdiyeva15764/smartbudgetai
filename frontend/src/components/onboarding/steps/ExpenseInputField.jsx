import { CustomInput } from '../../common/CustomInput'

export function ExpenseInputField({ id, icon, label, value, onChange, onClear }) {
  return (
    <div className="expense-input-item">
      <label htmlFor={id} className="expense-input-label">
        <span aria-hidden="true">{icon}</span>
        <span>{label}</span>
      </label>
      <CustomInput
        id={id}
        value={value}
        onChange={onChange}
        onClear={onClear}
        placeholder="0"
      />
    </div>
  )
}
