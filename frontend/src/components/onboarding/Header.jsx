import { PiggyBank } from 'lucide-react'

export function Header() {
  return (
    <header className="onboarding-header">
      <div className="onboarding-logo-container">
        <div className="piggy-icon-box" aria-hidden="true">
          <PiggyBank className="piggy-svg" size={32} strokeWidth={2} />
        </div>
        <span className="onboarding-brand-title">SmartBudget AI</span>
      </div>
    </header>
  )
}
