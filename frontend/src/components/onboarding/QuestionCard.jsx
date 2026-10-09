import { ProgressBar } from './ProgressBar'
import { FormNavigation } from './FormNavigation'
import { StepSalary } from './steps/StepSalary'
import { StepExtraIncome } from './steps/StepExtraIncome'
import { StepHousing } from './steps/StepHousing'
import { StepCredit } from './steps/StepCredit'
import { StepMonthlyExpenses } from './steps/StepMonthlyExpenses'
import { StepRecurringExpenses } from './steps/StepRecurringExpenses'
import { StepSavingsGoal } from './steps/StepSavingsGoal'
import { StepSummary } from './steps/StepSummary'
import { StepFinancialAssessment } from './steps/StepFinancialAssessment'
import { StepMonthlySavingsAbility } from './steps/StepMonthlySavingsAbility'
import { StepAnnualBudgetPriority } from './steps/StepAnnualBudgetPriority'

export function QuestionCard({ onboarding, submittedFormData, onComplete, isSubmitting = false }) {
  const {
    currentStep,
    totalSteps,
    userName,
    formData,
    stepError,
    updateField,
    clearField,
    addCredit,
    updateCredit,
    clearCredit,
    removeCredit,
    updateMonthlyExpense,
    clearMonthlyExpense,
    toggleRecurringExpense,
    toggleSavingsGoal,
    updateSavingsGoal,
    nextStep,
    prevStep,
    resetOnboarding,
    isSaving,
    isHydrating
  } = onboarding

  const isCompleted = currentStep > totalSteps

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <StepSalary
            salary={formData.salary}
            onChange={(val) => updateField('salary', val)}
            onClear={() => clearField('salary')}
          />
        )

      case 2:
        return (
          <StepExtraIncome
            hasExtraIncome={formData.hasExtraIncome}
            extraIncome={formData.extraIncome}
            onSelectOption={(option) => updateField('hasExtraIncome', option)}
            onAmountChange={(val) => updateField('extraIncome', val)}
            onAmountClear={() => clearField('extraIncome')}
          />
        )

      case 3:
        return (
          <StepHousing
            housingType={formData.housingType}
            housingAmount={formData.housingAmount}
            onSelect={(val) => updateField('housingType', val)}
            onAmountChange={(val) => updateField('housingAmount', val)}
            onAmountClear={() => clearField('housingAmount')}
          />
        )

      case 4:
        return (
          <StepCredit
            hasCredit={formData.hasCredit}
            credits={formData.credits}
            onSelectOption={(val) => updateField('hasCredit', val)}
            onUpdateCredit={updateCredit}
            onClearCredit={clearCredit}
            onRemoveCredit={removeCredit}
            onAddCredit={addCredit}
          />
        )

      case 5:
        return (
          <StepSavingsGoal
            goals={formData.savingsGoals}
            onToggleGoal={toggleSavingsGoal}
            onPriorityChange={(goalId, priority) => updateSavingsGoal(goalId, 'priority', priority)}
            onAmountChange={(goalId, amount) => updateSavingsGoal(goalId, 'amount', amount)}
            onAmountClear={(goalId) => updateSavingsGoal(goalId, 'amount', '')}
            onCustomNameChange={(goalId, name) => updateSavingsGoal(goalId, 'customName', name)}
            onSavedAmountChange={(goalId, value) => updateSavingsGoal(goalId, 'savedAmount', value)}
            onDeadlineChange={(goalId, value) => updateSavingsGoal(goalId, 'deadlineMonths', value)}
          />
        )

      case 6:
        return (
          <StepMonthlyExpenses
            values={formData.monthlyExpenses}
            onChange={updateMonthlyExpense}
            onClear={clearMonthlyExpense}
          />
        )

      case 7:
        return (
          <StepRecurringExpenses
            selectedExpenses={formData.recurringExpenses}
            onToggle={toggleRecurringExpense}
          />
        )

      case 8:
        return (
          <StepFinancialAssessment
            value={formData.financialAssessment}
            onChange={(value) => updateField('financialAssessment', value)}
          />
        )

      case 9:
        return (
          <StepMonthlySavingsAbility
            value={formData.monthlySavingsAbility}
            onChange={(value) => updateField('monthlySavingsAbility', value)}
          />
        )

      case 10:
        return (
          <StepAnnualBudgetPriority
            value={formData.annualBudgetPriority}
            onChange={(value) => updateField('annualBudgetPriority', value)}
          />
        )

      default:
        return (
          <StepSummary
            formData={submittedFormData || formData}
            userName={userName}
            onReset={() => {
              resetOnboarding()
              window.location.reload()
            }}
          />
        )
    }
  }

  return (
    <div className="question-card-container">
      {!isCompleted && (
        <div className="question-card-header">
          <div className="header-text-block">
            <h3 className="user-greeting">Salam, {userName}!</h3>
            <p className="subtitle-text">10 suala cavab ver, planınızı başlayaq.</p>
          </div>
          <ProgressBar currentStep={currentStep} totalSteps={totalSteps} />
        </div>
      )}

      <div className="question-card-body">
        {isHydrating ? (
          <p className="subtitle-text" role="status">Cavablarınız yüklənir...</p>
        ) : renderStepContent()}
        {stepError && <p className="error-text" role="alert">{stepError}</p>}
      </div>

      {!isCompleted && (
        <div className="question-card-footer">
          <FormNavigation
            onNext={nextStep}
            onComplete={currentStep === totalSteps ? () => onComplete(formData) : undefined}
            onPrev={prevStep}
            showBack={currentStep > 1}
            disableNext={isSubmitting || isSaving || isHydrating}
            nextLabel={currentStep === totalSteps ? 'Təsdiqlə' : 'Növbəti'}
            isSubmitting={isSubmitting || isSaving}
          />
        </div>
      )}
    </div>
  )
}