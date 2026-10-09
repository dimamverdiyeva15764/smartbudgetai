export function LoadingPlan({ phase }) {
  const subtitle = phase === 1
    ? 'AI planınızı hazırlayır - Məlumatlar analiz edilir...'
    : 'AI planınızı hazırlayır - Xərclər hesablanır...'

  return (
    <div className="loading-screen-container">
      <div className="question-card-container loading-plan-card" role="status" aria-live="polite">
        <div className="loading-plan-content">
          <span className="loading-plan-spinner" aria-hidden="true" />
          <h2 className="loading-plan-title">SmartBudget AI işləyir</h2>
          <p className="loading-plan-subtitle">{subtitle}</p>
        </div>
      </div>
    </div>
  )
}
