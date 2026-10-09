import { useEffect, useState } from 'react'
import {
  getOnboardingAnswers,
  updateSalary,
  updateExtraIncome,
  updateHousing,
  updateHasCredit,
  syncCredits,
  updateSavingsGoals,
  updateMonthlyExpenses,
  updateRecurringExpenses,
  updateFinancialAssessment,
  updateMonthlySavingsAbility
} from '../services/api'

export const ONBOARDING_STORAGE_KEY = 'smartbudget-onboarding-state'
export const ONBOARDING_ACTIVE_KEY = 'smartbudget-onboarding-active'
export const ACCOUNT_STORAGE_KEY = 'smartbudget-account-state'
export const BUDGET_MONTHS_STORAGE_KEY = 'smartbudget-budget-plan-months'

export function clearSavedOnboardingProgress() {
  const keys = [
    ONBOARDING_STORAGE_KEY,
    ONBOARDING_ACTIVE_KEY,
    BUDGET_MONTHS_STORAGE_KEY,
    'budgetModifiedFields',
    'onboardingStep',
    'currentStep'
  ]
  for (const storage of [window.localStorage, window.sessionStorage]) {
    keys.forEach((key) => storage.removeItem(key))
  }
}

const EMPTY_CREDIT = () => ({ monthly: '', remaining: '', rate: '', months: '' })
const DEFAULT_GOAL_PRIORITY = 'Orta prioritet'
const TOTAL_STEPS = 10

const createInitialFormData = () => ({
  salary: '',
  hasExtraIncome: null,
  extraIncome: '',
  housingType: null,
  housingAmount: '',
  hasCredit: null,
  credits: [EMPTY_CREDIT()],
  monthlyExpenses: {
    market: '',
    utilities: '',
    transport: '',
    restaurant: '',
    clothing: '',
    entertainment: '',
    onlineShopping: '',
    other: ''
  },
  recurringExpenses: [],
  savingsGoals: [],
  financialAssessment: '',
  monthlySavingsAbility: '',
  annualBudgetPriority: ''
})

// Step 6: a zero amount is shown as an empty field with the gray "0"
// placeholder (empty is still saved and calculated as 0).
const zeroToEmpty = (expenses = {}) => Object.fromEntries(
  Object.entries(expenses).map(([key, value]) => [key, value !== '' && value !== null && Number(value) === 0 ? '' : value])
)

const mergeFormData = (data = {}) => {
  const initial = createInitialFormData()
  return {
    ...initial,
    ...data,
    credits: Array.isArray(data.credits) && data.credits.length ? data.credits : initial.credits,
    monthlyExpenses: { ...initial.monthlyExpenses, ...zeroToEmpty(data.monthlyExpenses) },
    recurringExpenses: Array.isArray(data.recurringExpenses) ? data.recurringExpenses : [],
    savingsGoals: Array.isArray(data.savingsGoals) ? data.savingsGoals : []
  }
}

const getSavedState = (userEmail) => {
  if (!userEmail) return null
  try {
    const savedState = window.localStorage.getItem(ONBOARDING_STORAGE_KEY)
    if (!savedState) return null
    const parsedState = JSON.parse(savedState)
    const savedStep = Number(parsedState.currentStep)
    const savedEmail = String(parsedState.userEmail || '').trim().toLowerCase()
    if (savedEmail !== userEmail || !Number.isInteger(savedStep) || savedStep < 1 || savedStep > TOTAL_STEPS) {
      return null
    }
    return parsedState
  } catch {
    return null
  }
}

// --- validation (US-02 … US-11) -------------------------------------------

const isBlank = (value) => value === '' || value === null || value === undefined
const toNumber = (value) => (isBlank(value) ? NaN : Number(value))
const isPositive = (value) => Number.isFinite(toNumber(value)) && toNumber(value) > 0

/** Validation of savings goals (Step 5 and "Yeni plan əlavə et"). */
export function getGoalsError(goals) {
  if (!goals.length) return 'Ən azı bir yığım məqsədi seçin.'
  for (const goal of goals) {
    const label = goal.label || 'Məqsəd'
    if (goal.id === 'other' && !(goal.customName || '').trim()) return '“Digər” məqsədinin adını daxil edin.'
    if (!isPositive(goal.amount)) return `${label}: hədəf məbləği 0-dan böyük olmalıdır.`
    if (!isBlank(goal.savedAmount) && Number(goal.savedAmount) > Number(goal.amount)) {
      return `${label}: artıq yığılmış məbləğ hədəfdən çox ola bilməz.`
    }
    if (!isBlank(goal.deadlineMonths)) {
      const months = Number(goal.deadlineMonths)
      if (!Number.isInteger(months) || months < 1 || months > 600) return `${label}: müddət 1–600 ay arasında olmalıdır.`
    }
  }
  return null
}

export function getStepError(step, formData) {
  switch (step) {
    case 1:
      if (isBlank(formData.salary)) return 'Aylıq əmək haqqını daxil edin.'
      if (!isPositive(formData.salary)) return 'Əmək haqqı 0-dan böyük rəqəm olmalıdır.'
      return null
    case 2:
      if (!formData.hasExtraIncome) return 'Bəli və ya Xeyr seçin.'
      if (formData.hasExtraIncome === 'Bəli' && !isPositive(formData.extraIncome)) {
        return 'Əlavə gəlir məbləği 0-dan böyük olmalıdır.'
      }
      return null
    case 3:
      if (!formData.housingType) return 'Yaşayış formasını seçin.'
      if (formData.housingType === 'Kirayədir' && !isPositive(formData.housingAmount)) return 'Aylıq kirayə məbləğini daxil edin.'
      if (formData.housingType === 'İpotekadır' && !isPositive(formData.housingAmount)) return 'Aylıq ipoteka ödənişini daxil edin.'
      return null
    case 4: {
      if (!formData.hasCredit) return 'Bəli və ya Xeyr seçin.'
      if (formData.hasCredit === 'Xeyr') return null
      if (!formData.credits.length) return 'Ən azı 1 kredit daxil edin.'
      for (const [index, credit] of formData.credits.entries()) {
        const label = `Kredit ${index + 1}:`
        if (!isPositive(credit.monthly)) return `${label} aylıq ödəniş 0-dan böyük olmalıdır.`
        if (!isPositive(credit.remaining)) return `${label} qalıq məbləğ 0-dan böyük olmalıdır.`
        const rate = toNumber(credit.rate)
        if (!Number.isFinite(rate) || rate < 0 || rate > 100) return `${label} illik faiz 0–100 arasında rəqəm olmalıdır.`
        const months = toNumber(credit.months)
        if (!Number.isInteger(months) || months <= 0) return `${label} qalan ay sayı müsbət tam ədəd olmalıdır.`
      }
      return null
    }
    case 5:
      return getGoalsError(formData.savingsGoals)
    case 6:
      // Empty fields are accepted as 0 (US-07); negative values cannot be typed.
      return null
    case 7:
      return null
    case 8:
      return formData.financialAssessment ? null : 'Maliyyə davranışınızı seçin.'
    case 9:
      return formData.monthlySavingsAbility ? null : 'Bir cavab seçin.'
    case 10:
      return formData.annualBudgetPriority ? null : 'Əsas prioritetinizi seçin.'
    default:
      return null
  }
}

export function useOnboardingForm(initialUserName = 'User', userEmail = '', initialStep) {
  const normalizedUserEmail = String(userEmail).trim().toLowerCase()
  const [savedState] = useState(() => getSavedState(normalizedUserEmail))
  const [currentStep, setCurrentStep] = useState(() => {
    const requestedStep = Number(initialStep)
    if (Number.isInteger(requestedStep) && requestedStep >= 1 && requestedStep <= TOTAL_STEPS) {
      return requestedStep
    }
    return savedState?.currentStep || 1
  })
  const [userName] = useState(initialUserName)
  const [stepError, setStepError] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  // Without a local copy, answers are loaded from the server (refresh on
  // another device, "Cavabı dəyiş" from the dashboard, cleared storage …).
  const [isHydrating, setIsHydrating] = useState(!savedState)
  const [formData, setFormData] = useState(() => mergeFormData(savedState?.formData))

  useEffect(() => {
    if (savedState) return undefined
    let cancelled = false
    getOnboardingAnswers()
      .then((data) => {
        if (cancelled || !data?.answers) return
        setFormData(mergeFormData(data.answers))
      })
      .catch((error) => {
        if (!cancelled) console.warn('Saved answers could not be loaded:', error)
      })
      .finally(() => {
        if (!cancelled) setIsHydrating(false)
      })
    return () => {
      cancelled = true
    }
  }, [savedState])

  useEffect(() => {
    if (!normalizedUserEmail || isHydrating) return
    window.localStorage.setItem(
      ONBOARDING_STORAGE_KEY,
      JSON.stringify({ currentStep, formData, userEmail: normalizedUserEmail })
    )
  }, [currentStep, formData, normalizedUserEmail, isHydrating])

  const updateFormData = (updater) => {
    setStepError(null)
    setFormData(updater)
  }

  const finishOnboarding = () => {
    window.localStorage.setItem(ONBOARDING_ACTIVE_KEY, 'true')
  }

  const resetOnboarding = () => {
    window.localStorage.removeItem(ONBOARDING_STORAGE_KEY)
    window.localStorage.removeItem(BUDGET_MONTHS_STORAGE_KEY)
    setCurrentStep(1)
    setFormData(createInitialFormData())
  }

  const fullReset = () => {
    clearSavedOnboardingProgress()
    window.localStorage.removeItem(ACCOUNT_STORAGE_KEY)
    setCurrentStep(1)
    setFormData(createInitialFormData())
  }

  const updateField = (fieldName, value) => {
    updateFormData((prev) => {
      const next = { ...prev, [fieldName]: value }
      // Switching to an option without an amount removes the old amount (US-03/04).
      if (fieldName === 'hasExtraIncome' && value === 'Xeyr') next.extraIncome = ''
      if (fieldName === 'housingType' && value !== prev.housingType) next.housingAmount = ''
      if (fieldName === 'hasCredit' && value === 'Bəli' && !prev.credits.length) next.credits = [EMPTY_CREDIT()]
      return next
    })
  }

  const updateMonthlyExpense = (expenseId, value) => {
    updateFormData((prev) => ({
      ...prev,
      monthlyExpenses: { ...prev.monthlyExpenses, [expenseId]: value }
    }))
  }

  const clearMonthlyExpense = (expenseId) => updateMonthlyExpense(expenseId, '')

  const toggleRecurringExpense = (expenseId) => {
    updateFormData((prev) => {
      const isSelected = prev.recurringExpenses.includes(expenseId)
      const recurringExpenses = isSelected
        ? prev.recurringExpenses.filter((id) => id !== expenseId)
        : [...prev.recurringExpenses, expenseId]
      return { ...prev, recurringExpenses }
    })
  }

  const clearField = (fieldName) => updateField(fieldName, '')

  const addCredit = () => {
    updateFormData((prev) => ({ ...prev, credits: [...prev.credits, EMPTY_CREDIT()] }))
  }

  const updateCredit = (index, field, value) => {
    updateFormData((prev) => ({
      ...prev,
      credits: prev.credits.map((c, i) => (i === index ? { ...c, [field]: value } : c))
    }))
  }

  const clearCredit = (index, field) => updateCredit(index, field, '')

  const removeCredit = (index) => {
    updateFormData((prev) => ({ ...prev, credits: prev.credits.filter((_, i) => i !== index) }))
  }

  const toggleSavingsGoal = (goal) => {
    updateFormData((prev) => {
      const isSelected = prev.savingsGoals.some((selectedGoal) => selectedGoal.id === goal.id)
      const savingsGoals = isSelected
        ? prev.savingsGoals.filter((selectedGoal) => selectedGoal.id !== goal.id)
        : [...prev.savingsGoals, { id: goal.id, label: goal.label, priority: DEFAULT_GOAL_PRIORITY, amount: '', customName: '', savedAmount: '', deadlineMonths: '' }]
      return { ...prev, savingsGoals }
    })
  }

  const updateSavingsGoal = (goalId, field, value) => {
    updateFormData((prev) => ({
      ...prev,
      savingsGoals: prev.savingsGoals.map((goal) => (goal.id === goalId ? { ...goal, [field]: value } : goal))
    }))
  }

  // Saves the current step on the server (intermediate saving, BE-03).
  const saveStep = async (step) => {
    switch (step) {
      case 1: return updateSalary(formData.salary)
      case 2: return updateExtraIncome({ hasExtraIncome: formData.hasExtraIncome, extraIncome: formData.extraIncome })
      case 3: return updateHousing({ housingType: formData.housingType, housingAmount: formData.housingAmount })
      case 4:
        await updateHasCredit(formData.hasCredit)
        return formData.hasCredit === 'Bəli' ? syncCredits(formData.credits) : null
      case 5: return updateSavingsGoals(formData.savingsGoals)
      case 6: return updateMonthlyExpenses(formData.monthlyExpenses)
      case 7: return updateRecurringExpenses(formData.recurringExpenses)
      case 8: return updateFinancialAssessment(formData.financialAssessment)
      case 9: return updateMonthlySavingsAbility(formData.monthlySavingsAbility)
      default: return null // step 10 is submitted by OnboardingLayout
    }
  }

  const nextStep = async () => {
    if (isSaving) return
    const validationError = getStepError(currentStep, formData)
    if (validationError) {
      setStepError(validationError)
      return
    }
    setStepError(null)
    setIsSaving(true)
    try {
      await saveStep(currentStep)
    } catch (err) {
      setStepError(err.message || 'Cavab yadda saxlanılmadı. Yenidən cəhd edin.')
      return
    } finally {
      setIsSaving(false)
    }
    if (currentStep < TOTAL_STEPS) setCurrentStep((prev) => prev + 1)
  }

  const prevStep = () => {
    setStepError(null)
    if (currentStep > 1) setCurrentStep((prev) => prev - 1)
  }

  const goToStep = (step) => {
    setStepError(null)
    setCurrentStep(Math.min(TOTAL_STEPS, Math.max(1, step)))
  }

  /** Validates every step before the final submit; jumps to the first invalid one. */
  const validateAll = () => {
    for (let step = 1; step <= TOTAL_STEPS; step += 1) {
      const error = getStepError(step, formData)
      if (error) {
        setCurrentStep(step)
        setStepError(error)
        return false
      }
    }
    return true
  }

  return {
    currentStep,
    totalSteps: TOTAL_STEPS,
    userName,
    formData,
    stepError,
    setStepError,
    isSaving,
    isHydrating,
    updateField,
    updateMonthlyExpense,
    clearMonthlyExpense,
    toggleRecurringExpense,
    clearField,
    addCredit,
    updateCredit,
    clearCredit,
    removeCredit,
    toggleSavingsGoal,
    updateSavingsGoal,
    nextStep,
    prevStep,
    goToStep,
    validateAll,
    finishOnboarding,
    resetOnboarding,
    fullReset,
    isCurrentStepValid: getStepError(currentStep, formData) === null
  }
}
