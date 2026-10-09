import { PiggyBank } from 'lucide-react'

const PRIORITIES = [
  { value: 'Daha çox qənaət etmək', icon: '👤', label: 'Daha çox qənaət etmək' },
  { value: 'Xərclərə nəzarət etmək', icon: '🚚', label: 'Xərclərə nəzarət etmək' },
  { value: 'Borcları azaltmaq', icon: '💲', label: 'Borcları azaltmaq' },
  { value: 'Gəliri daha düzgün bölüşdürmək', icon: '🪪', label: 'Gəliri daha düzgün bölüşdürmək' },
  { value: 'Gözlənilməz xərclərə hazır olmaq', icon: '📈', label: 'Gözlənilməz xərclərə hazır olmaq' },
  { value: 'Gələcək üçün pul toplamaq', icon: <PiggyBank size={16} strokeWidth={2} />, label: 'Gələcək üçün pul toplamaq' }
]

export function StepAnnualBudgetPriority({ value, onChange }) {
  return (
    <div className="step-content">
      <h4 className="question-title">İllik büdcə planı hazırlayarkən sizin üçün əsas vacib olan nədir?</h4>
      <div className="annual-priority-grid">
        {PRIORITIES.map((priority) => (
          <button
            key={priority.value}
            type="button"
            className={`annual-priority-option${value === priority.value ? ' is-selected' : ''}`}
            onClick={() => onChange(priority.value)}
            aria-pressed={value === priority.value}
          >
            <span aria-hidden="true">{priority.icon}</span>
            <span>{priority.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
