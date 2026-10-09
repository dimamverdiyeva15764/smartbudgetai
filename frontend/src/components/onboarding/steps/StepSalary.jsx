import { CustomInput } from '../../common/CustomInput'

export function StepSalary({ salary, onChange, onClear }) {
  return (
    <div className="step-content">
      <h4 className="question-title">Aylıq əmək haqqınız nə qədərdir?</h4>
      <div className="step-input-block">
        <CustomInput
          id="salary-input"
          value={salary}
          onChange={onChange}
          onClear={onClear}
          placeholder="0"
        />
      </div>
    </div>
  )
}
