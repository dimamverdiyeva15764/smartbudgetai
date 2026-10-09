import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Header } from './Header'
import { LoadingPlan } from './LoadingPlan'
import {
  completeOnboarding,
  getInquiryStatus,
  recalculatePlan,
  retryPlanGeneration
} from '../../services/api'

const POLL_INTERVAL_MS = 2000
const MAX_NETWORK_ERRORS = 5

/**
 * AI processing screen (US-12).
 * - submits the questionnaire / recalculation when opened with an action;
 * - polls GET /financial-inquiry/status/ (Pending → Processing → Ready / Error);
 * - redirects to the dashboard automatically when the plan is ready;
 * - shows an error with "Yenidən cəhd et" when generation fails;
 * - survives a page refresh because the status lives on the server.
 */
export function ProcessingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [startAction] = useState(() => location.state || null)
  const [phase, setPhase] = useState(1)
  const [view, setView] = useState('loading') // loading | failed | pending | incomplete
  const [message, setMessage] = useState('')
  const requestInFlight = useRef(false)
  const pollTimer = useRef(null)
  const networkErrors = useRef(0)
  const mounted = useRef(true)
  const pollRef = useRef(() => {})

  const goToResults = useCallback((sessionId) => {
    navigate(`/summary/${sessionId || 'me'}`, { replace: true })
  }, [navigate])

  const handleStatus = useCallback((data) => {
    if (!mounted.current || requestInFlight.current) return // our own request reports the result
    if (data.status === 'completed') {
      goToResults(data.session_id)
      return
    }
    if (data.status === 'failed') {
      setView('failed')
      setMessage(data.message)
    } else if (data.status === 'pending') {
      setView('pending')
      setMessage(data.message)
    } else if (data.status === 'processing' && data.isStale) {
      setView('failed')
      setMessage('Plan hazırlanması gözləniləndən uzun çəkdi. Yenidən cəhd edin.')
    }
  }, [goToResults])

  const poll = useCallback(async () => {
    window.clearTimeout(pollTimer.current)
    try {
      const data = await getInquiryStatus()
      networkErrors.current = 0
      handleStatus(data)
      if (!mounted.current || data.status === 'completed') return
      if (data.status === 'processing' || requestInFlight.current) {
        pollTimer.current = window.setTimeout(() => pollRef.current(), POLL_INTERVAL_MS)
      }
    } catch (error) {
      if (!mounted.current) return
      networkErrors.current += 1
      if (networkErrors.current >= MAX_NETWORK_ERRORS) {
        setView('failed')
        setMessage(error.message)
        return
      }
      pollTimer.current = window.setTimeout(() => pollRef.current(), POLL_INTERVAL_MS * 1.5)
    }
  }, [handleStatus])

  useEffect(() => {
    pollRef.current = poll
  }, [poll])

  const runAction = useCallback(async (action) => {
    requestInFlight.current = true
    setView('loading')
    setMessage('')
    setPhase(1)
    pollTimer.current = window.setTimeout(poll, POLL_INTERVAL_MS)
    try {
      let result
      if (action.action === 'complete') {
        result = await completeOnboarding({
          annualBudgetPriority: action.annualBudgetPriority,
          monthlySavingsAbility: action.monthlySavingsAbility
        })
      } else if (action.action === 'recalculate') {
        result = await recalculatePlan(action.adjustments || [], { regenerate: Boolean(action.regenerate) })
      } else {
        result = await retryPlanGeneration()
      }
      requestInFlight.current = false
      if (result?.status === 'completed') {
        goToResults(result.session_id)
      } else {
        poll()
      }
    } catch (error) {
      requestInFlight.current = false
      if (!mounted.current) return
      window.clearTimeout(pollTimer.current)
      if (error.status === 409 || error.data?.code === 'PLAN_ALREADY_PROCESSING') {
        poll()
        return
      }
      if (error.data?.code === 'ANSWERS_INCOMPLETE') {
        setView('incomplete')
      } else {
        setView('failed')
      }
      setMessage(error.message)
    }
  }, [goToResults, poll])

  useEffect(() => {
    mounted.current = true
    if (startAction?.action) {
      // Drop the action from history so a refresh only polls, never re-submits.
      navigate(location.pathname, { replace: true, state: null })
    }
    const startTimer = window.setTimeout(() => {
      if (startAction?.action) runAction(startAction)
      else poll()
    }, 0)
    const phaseTimer = window.setTimeout(() => setPhase(2), 1800)
    return () => {
      mounted.current = false
      window.clearTimeout(pollTimer.current)
      window.clearTimeout(phaseTimer)
      window.clearTimeout(startTimer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const editAnswers = () => {
    navigate('/onboarding', { state: { startAtStep: 1, reloadAnswers: true } })
  }

  return (
    <div className="results-page-wrapper">
      <Header />
      <main className="results-main-container results-loading-container">
        {view === 'loading' ? (
          <LoadingPlan phase={phase} />
        ) : (
          <div className="loading-screen-container">
            <div className="question-card-container loading-plan-card" role="alert">
              <div className="loading-plan-content">
                <h2 className="loading-plan-title">
                  {view === 'pending' ? 'Plan hələ hazır deyil' : view === 'incomplete' ? 'Cavablar tamamlanmayıb' : 'Plan hazırlana bilmədi'}
                </h2>
                <p className="processing-error-text">{message}</p>
                <div className="processing-actions">
                  {view !== 'incomplete' && (
                    <button type="button" className="btn-restart" onClick={() => runAction({ action: 'retry' })}>
                      {view === 'pending' ? 'Planı hazırla' : 'Yenidən cəhd et'}
                    </button>
                  )}
                  <button type="button" className="btn-secondary-outline" onClick={editAnswers}>
                    Cavablara qayıt
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default ProcessingPage
