import { LuUser, LuUsers, LuHouse } from 'react-icons/lu'
import { HousingOptionCard } from './HousingOptionCard'
import { CustomInput } from '../../common/CustomInput'

const HOUSING_OPTIONS = [
  {
    value: 'Özümündür',
    label: 'Özümündür',
    icon: <LuUser size={20} />
  },
  {
    value: 'Kirayədir',
    label: 'Kirayədir',
    icon: <LuUsers size={20} />
  },
  {
    value: 'İpotekadır',
    label: 'İpotekadır',
    icon: <LuHouse size={20} />
  }
]

/**
 * Step 3 – Housing status selection.
 * Props:
 *   housingType – current selected value (string | null)
 *   onSelect    – (value: string) => void
 */
export function StepHousing({ housingType, housingAmount, onSelect, onAmountChange, onAmountClear }) {
  const amountLabel = housingType === 'Kirayədir'
    ? 'Aylıq kirayə ödənişiniz nə qədərdir?'
    : 'Aylıq ipoteka ödənişiniz nə qədərdir?'

  return (
    <div className="step-content">
      <h4 className="question-title">Yaşadığınız ev?</h4>

      <div className="housing-options-row">
        {HOUSING_OPTIONS.map((opt) => (
          <HousingOptionCard
            key={opt.value}
            icon={opt.icon}
            label={opt.label}
            selected={housingType === opt.value}
            onClick={() => onSelect(opt.value)}
          />
        ))}
      </div>

      {housingType && housingType !== 'Özümündür' && (
        <CustomInput
          id="housing-amount-input"
          label={amountLabel}
          value={housingAmount}
          onChange={onAmountChange}
          onClear={onAmountClear}
          placeholder="0"
        />
      )}
    </div>
  )
}
