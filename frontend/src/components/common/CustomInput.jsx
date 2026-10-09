import { LuX } from 'react-icons/lu'

/**
 * Amount input (FE-03). In numeric mode it accepts only digits with up to two
 * decimals (no minus sign, so negative amounts cannot be entered) and shows
 * the currency/unit (AZN by default).
 */
export function CustomInput({
  value,
  onChange,
  onClear,
  placeholder = '0',
  id,
  label,
  type = 'number',
  unit = 'AZN',
  integer = false
}) {
  const isText = type === 'text'
  const pattern = integer ? /^\d*$/ : /^\d*([.,]\d{0,2})?$/

  const handleInputChange = (e) => {
    const val = e.target.value
    if (isText) {
      onChange(val)
      return
    }
    if (val === '' || pattern.test(val)) {
      onChange(val.replace(',', '.'))
    }
  }

  const hasValue = value !== undefined && value !== null && value !== ''

  return (
    <div className="custom-input-wrapper">
      {label && <label htmlFor={id} className="custom-input-label">{label}</label>}
      <div className={`input-with-clear${!isText && unit ? ' has-unit' : ''}`}>
        <input
          id={id}
          type="text"
          inputMode={isText ? 'text' : integer ? 'numeric' : 'decimal'}
          className="custom-input-field"
          value={value ?? ''}
          onChange={handleInputChange}
          placeholder={placeholder}
          autoComplete="off"
        />
        {!isText && unit && <span className="input-unit" aria-hidden="true">{unit}</span>}
        {hasValue && (
          <button
            type="button"
            className="clear-input-btn"
            onClick={onClear}
            aria-label="Təmizlə"
            title="Təmizlə"
          >
            <LuX size={16} />
          </button>
        )}
      </div>
    </div>
  )
}
