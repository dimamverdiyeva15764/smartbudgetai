import { LuPlus } from 'react-icons/lu'
import { OptionButton } from '../../common/OptionButton'
import { CreditFormGroup } from './CreditFormGroup'

/**
 * Step 4 – Credit payment status.
 * Props:
 *   hasCredit      – 'Bəli' | 'Xeyr' | null
 *   credits        – array of credit objects
 *   onSelectOption – (value: 'Bəli' | 'Xeyr') => void
 *   onUpdateCredit – (index, field, value) => void
 *   onClearCredit  – (index, field) => void
 *   onRemoveCredit – (index) => void
 *   onAddCredit    – () => void
 */
export function StepCredit({
  hasCredit,
  credits,
  onSelectOption,
  onUpdateCredit,
  onClearCredit,
  onRemoveCredit,
  onAddCredit
}) {
  return (
    <div className="step-content">
      <h4 className="question-title">Kredit ödənişiniz varmı?</h4>

      <div className="option-buttons-row">
        <OptionButton
          label="Bəli"
          selected={hasCredit === 'Bəli'}
          onClick={() => onSelectOption('Bəli')}
        />
        <OptionButton
          label="Xeyr"
          selected={hasCredit === 'Xeyr'}
          onClick={() => onSelectOption('Xeyr')}
        />
      </div>

      {hasCredit === 'Bəli' && (
        <div className="credit-list" aria-live="polite">
          {credits.map((credit, index) => (
            <CreditFormGroup
              key={index}
              index={index}
              canRemove={credits.length > 1}
              credit={credit}
              onChange={(field, value) => onUpdateCredit(index, field, value)}
              onClear={(field) => onClearCredit(index, field)}
              onRemove={() => onRemoveCredit(index)}
            />
          ))}

          <button
            type="button"
            id="add-credit-btn"
            className="add-credit-btn"
            onClick={onAddCredit}
          >
            <LuPlus size={16} />
            <span>Kredit əlavə edin</span>
          </button>
        </div>
      )}
    </div>
  )
}
