export function ProgressBar({ currentStep, totalSteps }) {
  const percentage = Math.min(100, Math.max(0, (currentStep / totalSteps) * 100))

  return (
    <div className="progress-bar-container">
      <div className="progress-header">
        <span className="step-counter">{currentStep}/{totalSteps}</span>
      </div>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${percentage}%` }}
          aria-valuenow={currentStep}
          aria-valuemin={1}
          aria-valuemax={totalSteps}
          role="progressbar"
        />
      </div>
    </div>
  )
}
