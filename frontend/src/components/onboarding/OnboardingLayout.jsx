import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from './Header'
import { QuestionCard } from './QuestionCard'
import { BUDGET_MONTHS_STORAGE_KEY, useOnboardingForm } from '../../hooks/useOnboardingForm'

export function OnboardingLayout({ userName = 'User', userEmail = '', initialStep }) {
  const onboarding = useOnboardingForm(userName, userEmail, initialStep)
  const navigate = useNavigate()
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Step 10 "Təsdiqlə": validate every answer, then open the processing screen,
  // which submits the questionnaire and follows the plan status (US-11/US-12).
  const handleComplete = (formData) => {
    if (isSubmitting) return
    if (!onboarding.validateAll()) return
    setIsSubmitting(true)
    window.localStorage.removeItem(BUDGET_MONTHS_STORAGE_KEY)
    onboarding.finishOnboarding()
    navigate('/processing', {
      state: {
        action: 'complete',
        annualBudgetPriority: formData.annualBudgetPriority,
        monthlySavingsAbility: formData.monthlySavingsAbility
      }
    })
  }

  return (
    <div className="onboarding-page-wrapper">
      <Header />
      <main className="onboarding-main-container">
        <QuestionCard
          onboarding={onboarding}
          submittedFormData={null}
          onComplete={handleComplete}
          isSubmitting={isSubmitting}
        />
      </main>
    </div>
  )
}
