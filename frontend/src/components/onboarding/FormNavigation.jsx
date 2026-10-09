import { LuChevronLeft, LuChevronRight } from 'react-icons/lu'

export function FormNavigation({
  onNext,
  onComplete,
  onPrev,
  showBack = true,
  disableNext = false,
  nextLabel = 'Növbəti',
  isSubmitting = false
}) {
  const handleClick = (e) => {
    e.preventDefault()
    if (disableNext) return
    if (onComplete) {
      onComplete(e)
    } else {
      onNext(e)
    }
  }

  return (
    <div className="form-navigation-container">
      <div className="nav-left">
        {showBack && (
          <button type="button" className="btn-back" onClick={onPrev} disabled={isSubmitting}>
            <LuChevronLeft size={18} />
            <span>Geri</span>
          </button>
        )}
      </div>
      <div className="nav-right">
        <button
          type="button"
          className="btn-next"
          onClick={handleClick}
          disabled={disableNext}
        >
          <span>{isSubmitting ? 'Gözləyin...' : nextLabel}</span>
          {!isSubmitting && <LuChevronRight size={18} />}
        </button>
      </div>
    </div>
  )
}
