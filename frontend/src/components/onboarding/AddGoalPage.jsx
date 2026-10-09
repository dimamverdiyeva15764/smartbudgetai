import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from './Header'
import { FormNavigation } from './FormNavigation'
import { StepSavingsGoal } from './steps/StepSavingsGoal'
import { GOALS } from './steps/goalOptions'
import { getGoalsError } from '../../hooks/useOnboardingForm'
import { addSavingsGoals, getOnboardingAnswers } from '../../services/api'

const money = (value) => `${(Number(value) || 0).toLocaleString('az-AZ', { maximumFractionDigits: 2 })} AZN`

/**
 * "Yeni plan əlavə et": adds another savings goal to the EXISTING plan.
 * Only Question 5 is shown (no Questions 1–4). Existing goals stay untouched;
 * after confirming, the one shared 12-month plan is recalculated.
 */
export function AddGoalPage() {
  const navigate = useNavigate()
  const [existingGoals, setExistingGoals] = useState([])
  const [newGoals, setNewGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    getOnboardingAnswers()
      .then((data) => active && setExistingGoals(data.answers?.savingsGoals || []))
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  const existingIds = existingGoals.map((goal) => goal.id)
  const labelOf = (id) => GOALS.find((goal) => goal.id === id)?.label || id

  const toggleGoal = (goal) => {
    if (existingIds.includes(goal.id)) return
    setError(null)
    setNewGoals((current) => (current.some((g) => g.id === goal.id)
      ? current.filter((g) => g.id !== goal.id)
      : [...current, { id: goal.id, label: goal.label, priority: 'Orta prioritet', amount: '', customName: '', savedAmount: '', deadlineMonths: '' }]))
  }

  const updateGoal = (field) => (goalId, value) => {
    setError(null)
    setNewGoals((current) => current.map((g) => (g.id === goalId ? { ...g, [field]: value } : g)))
  }

  const handleConfirm = async () => {
    const validationError = newGoals.length ? getGoalsError(newGoals) : 'Əlavə etmək üçün yeni məqsəd seçin.'
    if (validationError) {
      setError(validationError)
      return
    }
    setSaving(true)
    try {
      await addSavingsGoals(newGoals)
      // Recalculate the one shared plan with all goals (processing screen).
      navigate('/processing', { replace: true, state: { action: 'recalculate', adjustments: [] } })
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <div className="onboarding-page-wrapper">
      <Header />
      <main className="onboarding-main-container">
        <div className="question-card-container">
          <div className="question-card-header">
            <div className="header-text-block">
              <h3 className="user-greeting">Yeni məqsəd əlavə et</h3>
              <p className="subtitle-text">Mövcud planınız və məqsədləriniz saxlanılır — yeni məqsəd eyni büdcəyə əlavə olunur.</p>
            </div>
          </div>

          <div className="question-card-body">
            {loading ? (
              <p className="subtitle-text" role="status">Məqsədləriniz yüklənir...</p>
            ) : (
              <>
                {existingGoals.length > 0 && (
                  <div className="existing-goals-list" aria-label="Mövcud məqsədlər">
                    <p className="existing-goals-title">Mövcud məqsədləriniz:</p>
                    <ul>
                      {existingGoals.map((goal) => (
                        <li key={goal.id}>
                          <strong>{goal.id === 'other' && goal.customName ? goal.customName : labelOf(goal.id)}</strong>
                          {' — '}{money(goal.savedAmount)} / {money(goal.amount)}
                          {' · '}{goal.deadlineMonths} ay · {goal.priority}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <StepSavingsGoal
                  goals={newGoals}
                  disabledGoalIds={existingIds}
                  onToggleGoal={toggleGoal}
                  onPriorityChange={updateGoal('priority')}
                  onAmountChange={updateGoal('amount')}
                  onAmountClear={(goalId) => updateGoal('amount')(goalId, '')}
                  onCustomNameChange={updateGoal('customName')}
                  onSavedAmountChange={updateGoal('savedAmount')}
                  onDeadlineChange={updateGoal('deadlineMonths')}
                />
              </>
            )}
            {error && <p className="error-text" role="alert">{error}</p>}
          </div>

          <div className="question-card-footer">
            <FormNavigation
              onNext={handleConfirm}
              onPrev={() => navigate(-1)}
              showBack
              disableNext={loading || saving}
              nextLabel="Təsdiqlə"
              isSubmitting={saving}
            />
          </div>
        </div>
      </main>
    </div>
  )
}

export default AddGoalPage
