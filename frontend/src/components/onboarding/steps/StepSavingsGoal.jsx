import { GoalOptionCard } from './GoalOptionCard'
import { GoalDetailForm } from './GoalDetailForm'
import { GOALS } from './goalOptions'


export function StepSavingsGoal({ goals, onToggleGoal, onPriorityChange, onAmountChange, onAmountClear, onCustomNameChange, onSavedAmountChange, onDeadlineChange, disabledGoalIds = [] }) {
  return (
    <div className="step-content">
      <h4 className="question-title">Yığım məqsədiniz nədir?</h4>
      <div className="savings-goals-grid">
        {GOALS.map((goal) => (
          <GoalOptionCard
            key={goal.id}
            icon={goal.icon}
            label={goal.label}
            selected={goals.some((selectedGoal) => selectedGoal.id === goal.id)}
            disabled={disabledGoalIds.includes(goal.id)}
            hint={disabledGoalIds.includes(goal.id) ? 'Bu məqsəd artıq planınızda var' : undefined}
            onClick={() => onToggleGoal(goal)}
          />
        ))}
      </div>

      <div className="goal-details-list">
        {goals.map((goal) => (
          <GoalDetailForm
            key={goal.id}
            goal={{ ...goal, label: GOALS.find((option) => option.id === goal.id)?.label || goal.label || goal.id }}
            onPriorityChange={(priority) => onPriorityChange(goal.id, priority)}
            onAmountChange={(amount) => onAmountChange(goal.id, amount)}
            onAmountClear={() => onAmountClear(goal.id)}
            onCustomNameChange={(name) => onCustomNameChange(goal.id, name)}
            onSavedAmountChange={onSavedAmountChange && ((value) => onSavedAmountChange(goal.id, value))}
            onDeadlineChange={onDeadlineChange && ((value) => onDeadlineChange(goal.id, value))}
          />
        ))}
      </div>
    </div>
  )
}
