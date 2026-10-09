import { ExpenseSelectCard } from './ExpenseSelectCard'

const RECURRING_EXPENSES = [
  { id: 'market', icon: '🛒', label: 'Market' },
  { id: 'clothing', icon: '👗', label: 'Geyim' },
  { id: 'restaurant', icon: '🍽️', label: 'Restoran və Kafe' },
  { id: 'entertainment', icon: '🎮', label: 'Əyləncə' },
  { id: 'transport', icon: '🚗', label: 'Nəqliyyat' },
  { id: 'onlineShopping', icon: '🛍️', label: 'Onlayn alış-veriş' },
  { id: 'utilities', icon: '💰', label: 'Kommunal ödənişlər' },
  { id: 'other', icon: '🎯', label: 'Digər' }
]

export function StepRecurringExpenses({ selectedExpenses, onToggle }) {
  return (
    <div className="step-content">
      <div className="recurring-expenses-heading">
        <span className="recurring-expenses-icon" aria-hidden="true">🛒</span>
        <h4 className="question-title">Mütəmadi xərcləriniz hansılardır?</h4>
      </div>
      <div className="recurring-expenses-grid">
        {RECURRING_EXPENSES.map((expense) => (
          <ExpenseSelectCard
            key={expense.id}
            icon={expense.icon}
            label={expense.label}
            selected={selectedExpenses.includes(expense.id)}
            onClick={() => onToggle(expense.id)}
          />
        ))}
      </div>
    </div>
  )
}
