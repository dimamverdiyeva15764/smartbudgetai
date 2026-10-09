import { OptionButton } from '../../common/OptionButton'
import { CustomInput } from '../../common/CustomInput'

export function StepExtraIncome({
  hasExtraIncome,
  extraIncome,
  onSelectOption,
  onAmountChange,
  onAmountClear
}) {
  return (
    <div className="step-content">
      <h4 className="question-title">Əlavə gəliriniz var mı?</h4>

      <div className="option-buttons-row">
        <OptionButton
          label="Bəli"
          selected={hasExtraIncome === 'Bəli'}
          onClick={() => onSelectOption('Bəli')}
        />
        <OptionButton
          label="Xeyr"
          selected={hasExtraIncome === 'Xeyr'}
          onClick={() => onSelectOption('Xeyr')}
        />
      </div>

      {hasExtraIncome === 'Bəli' && (
        <div className="conditional-input-container">
          <label htmlFor="extra-income-input" className="sub-label">
            Məbləği daxil edin:
          </label>
          <CustomInput
            id="extra-income-input"
            value={extraIncome}
            onChange={onAmountChange}
            onClear={onAmountClear}
            placeholder="0"
          />
        </div>
      )}
    </div>
  )
}
