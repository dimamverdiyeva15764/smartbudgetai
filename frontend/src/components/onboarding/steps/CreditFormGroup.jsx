import { LuTrash2 } from 'react-icons/lu'
import { CustomInput } from '../../common/CustomInput'

/**
 * CreditFormGroup – 2×2 grid of inputs for a single credit/loan entry.
 * Props:
 *   index        – number, position in the credits array
 *   credit       – { monthly, remaining, rate, months }
 *   onChange     – (field, value) => void
 *   onClear      – (field) => void
 *   onRemove     – () => void  (only shown when index > 0)
 */
export function CreditFormGroup({ index, credit, onChange, onClear, onRemove, canRemove = index > 0 }) {
  return (
    <div className="credit-entry">
      {canRemove && (
        <div className="credit-entry-header">
          <span className="credit-entry-label">Kredit {index + 1}</span>
          <button
            type="button"
            className="credit-remove-btn"
            onClick={onRemove}
            aria-label={`Kredit ${index + 1} sil`}
          >
            <LuTrash2 size={15} />
          </button>
        </div>
      )}

      <div className="credit-fields-grid">
        {/* Aylıq kredit ödənişi */}
        <CustomInput
          id={`credit-${index}-monthly`}
          label="Aylıq kredit ödənişi"
          value={credit.monthly}
          onChange={(val) => onChange('monthly', val)}
          onClear={() => onClear('monthly')}
          placeholder="0"
        />

        {/* Qalıq məbləğ */}
        <CustomInput
          id={`credit-${index}-remaining`}
          label="Qalıq məbləğ"
          value={credit.remaining}
          onChange={(val) => onChange('remaining', val)}
          onClear={() => onClear('remaining')}
          placeholder="0"
        />

        {/* İllik faiz(%) */}
        <CustomInput
          id={`credit-${index}-rate`}
          label="İllik faiz(%)"
          unit="%"
          value={credit.rate}
          onChange={(val) => onChange('rate', val)}
          onClear={() => onClear('rate')}
          placeholder="0"
        />

        {/* Qalan ay */}
        <CustomInput
          id={`credit-${index}-months`}
          label="Qalan ay"
          unit="ay"
          integer
          value={credit.months}
          onChange={(val) => onChange('months', val)}
          onClear={() => onClear('months')}
          placeholder="0"
        />
      </div>
    </div>
  )
}
