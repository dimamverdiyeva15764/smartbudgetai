import { Suspense, lazy, useEffect, useState } from 'react'
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LuShieldCheck } from 'react-icons/lu'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ACCOUNT_STORAGE_KEY, ONBOARDING_ACTIVE_KEY, ONBOARDING_STORAGE_KEY, clearSavedOnboardingProgress } from './hooks/useOnboardingForm'
import { prefetchApi, registerUser } from './services/api'
import './App.css'

// Performance: the login page is the first screen, so the other pages are
// split into separate files. They are downloaded in the background right after
// the first page has rendered, so navigating to them stays instant.
const loadOnboarding = () => import('./components/onboarding/OnboardingLayout')
const loadResults = () => import('./components/onboarding/BudgetPlanResults')
const loadProcessing = () => import('./components/onboarding/ProcessingPage')
const loadAddGoal = () => import('./components/onboarding/AddGoalPage')
const OnboardingLayout = lazy(() => loadOnboarding().then((m) => ({ default: m.OnboardingLayout })))
const BudgetPlanResults = lazy(() => loadResults().then((m) => ({ default: m.BudgetPlanResults })))
const ProcessingPage = lazy(() => loadProcessing().then((m) => ({ default: m.ProcessingPage })))
const AddGoalPage = lazy(() => loadAddGoal().then((m) => ({ default: m.AddGoalPage })))

const preloadPages = () => {
  const run = () => [loadOnboarding, loadResults, loadProcessing, loadAddGoal].forEach((load) => load().catch(() => {}))
  if ('requestIdleCallback' in window) window.requestIdleCallback(run, { timeout: 2000 })
  else window.setTimeout(run, 300)
}

function AuthPage() {
  const navigate = useNavigate()

  const savedAccount = (() => {
    try {
      const value = window.localStorage.getItem(ACCOUNT_STORAGE_KEY)
      return value ? JSON.parse(value) : null
    } catch {
      return null
    }
  })()

  const [formData, setFormData] = useState({
    fullName: savedAccount?.formData?.fullName || '',
    email: savedAccount?.formData?.email || '',
    password: ''
  })

  const [touched, setTouched] = useState({
    fullName: false,
    email: false,
    password: false
  })

  const [isSubmitted, setIsSubmitted] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [apiError, setApiError] = useState(null)

  // Validation functions
  const isFullNameValid = formData.fullName.trim().length > 0

  const isEmailValid =
    formData.email.trim().includes('@') &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())

  const isPasswordValid =
    formData.password.length >= 8 &&
    /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(formData.password)

  const isFormValid = isFullNameValid && isEmailValid && isPasswordValid

  const handleChange = (e) => {
    const { name, value } = e.target
    setApiError(null)
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleBlur = (e) => {
    const { name } = e.target
    setTouched((prev) => ({ ...prev, [name]: true }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setApiError(null)
    setTouched({
      fullName: true,
      email: true,
      password: true
    })

    if (!isFormValid) return

    setIsLoading(true)

    try {
      // 1. Try to register a new account first
      const registration = await registerUser({
        fullName: formData.fullName.trim(),
        email: formData.email.trim(),
        password: formData.password
      })

      // Start from the server's saved answers; never keep the password.
      clearSavedOnboardingProgress()
      setIsSubmitted(true)
      window.localStorage.setItem(ONBOARDING_ACTIVE_KEY, 'true')
      window.localStorage.setItem(ACCOUNT_STORAGE_KEY, JSON.stringify({
        formData: {
          fullName: registration.user?.fullName || formData.fullName.trim(),
          email: registration.user?.email || formData.email.trim()
        }
      }))

      // Performance: load the next page's data during the success message.
      if (registration.isReturningUser && registration.sessionStatus === 'completed') {
        ['/summary/', '/summary/goals/', '/summary/table/', '/summary/comparison/'].forEach(prefetchApi)
      } else {
        prefetchApi('/financial-inquiry/answers/')
      }

      setTimeout(() => {
        if (registration.isReturningUser && registration.sessionStatus === 'completed') {
          navigate(`/summary/${registration.session_id}`, { replace: true })
        } else {
          navigate('/onboarding', { replace: true, state: { startAtStep: 1 } })
        }
      }, 500)

    } catch (err) {
      setApiError(err.message || 'Qeydiyyat zamanı xəta baş verdi.')
    } finally {
      setIsLoading(false)
    }
  }

  const showFullNameError = (touched.fullName || isSubmitted) && !isFullNameValid
  const showEmailError = (touched.email || isSubmitted) && !isEmailValid
  const showPasswordError = (touched.password || isSubmitted) && !isPasswordValid

  return (
    <main className="app-layout">
      {/* SOL PANEL */}
      <section className="left-panel">
        <header className="brand-container">
          <div className="brand-icon-box" aria-hidden="true">
            <svg
              className="brand-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div className="brand-text">
            <h1 className="brand-title">SmartBudget AI</h1>
            <p className="brand-subtitle">Maliyyə gələcəyini ağıllı şəkildə planlaşdır</p>
          </div>
        </header>

        <div className="hero-main-content">
          <div className="pill-badge-outline">
            <svg className="spark-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2z" />
            </svg>
            <span>Fərdiləşdirilmiş AI planı</span>
          </div>

          <h2 className="hero-heading">
            <span className="headline-dark">İllik büdcəni</span>
            <span className="headline-orange">ağıllı şəkildə planla</span>
          </h2>

          <p className="hero-body-text">
            Bir neçə sadə suala cavab verərək AI ilə gəlir və xərclərinə uyğun fərdiləşdirilmiş illik büdcə plan hazırla.
          </p>

          <div className="pill-badge-solid">
            <LuShieldCheck className="shield-icon" size={18} />
            <span>Real və balanslı plan</span>
          </div>
        </div>

        <div className="left-footer-spacer"></div>
      </section>

      {/* SAĞ PANEL */}
      <section className="right-panel">
        <div className="card-container">
          <h3 className="card-title">Başlamaq üçün məlumatlarınızı daxil edin</h3>
          <p className="card-desc">Cavablarınız və planınız hesabınızda təhlükəsiz saxlanılır.</p>

          {apiError && (
            <div className="error-banner" role="alert" style={{ color: '#ef4444', marginBottom: '1rem' }}>
              <span>{apiError}</span>
            </div>
          )}

          {isSubmitted && isFormValid && !apiError && (
            <div className="success-banner" role="alert">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 10 1 1-5.93-9.14" strokeLinecap="round" strokeLinejoin="round"/>
                <polyline points="22 4 12 14.01 9 11.01" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span>Uğurla qeydiyyatdan keçdiniz!</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-field">
              <label htmlFor="fullName" className="field-label">Ad və soyad</label>
              <input
                id="fullName"
                name="fullName"
                type="text"
                className={`field-input ${showFullNameError ? 'has-error' : ''}`}
                value={formData.fullName}
                onChange={handleChange}
                onBlur={handleBlur}
                aria-invalid={showFullNameError}
                disabled={isLoading}
              />
              {showFullNameError && <p className="error-text">Ad və soyad hissəsini doldurun.</p>}
            </div>

            <div className="form-field">
              <label htmlFor="email" className="field-label">Email</label>
              <input
                id="email"
                name="email"
                type="email"
                className={`field-input ${showEmailError ? 'has-error' : ''}`}
                value={formData.email}
                onChange={handleChange}
                onBlur={handleBlur}
                aria-invalid={showEmailError}
                disabled={isLoading}
              />
              {showEmailError && <p className="error-text">Düzgün email ünvanı daxil edin ('@' işarəsi mütləqdir).</p>}
            </div>

            <div className="form-field">
              <label htmlFor="password" className="field-label">Şifrə</label>
              <input
                id="password"
                name="password"
                type="password"
                className={`field-input ${showPasswordError ? 'has-error' : ''}`}
                value={formData.password}
                onChange={handleChange}
                onBlur={handleBlur}
                aria-invalid={showPasswordError}
                disabled={isLoading}
              />
              {showPasswordError && <p className="error-text">Şifrə ən azı 8 simvol olmalı və xüsusi simvol ehtiva etməlidir.</p>}
            </div>

            <button
              type="submit"
              className="btn-submit"
              disabled={isLoading}
            >
              <span>{isLoading ? 'Gözləyin...' : 'Planlamaya başla'}</span>
              <svg className="btn-arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          </form>
        </div>
      </section>
    </main>
  )
}

function OnboardingWrapper() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialStep = location.state?.startAtStep
  const reloadAnswers = location.state?.reloadAnswers

  if (reloadAnswers) {
    // "Cavabı dəyiş": load the answers saved on the server, not an old local copy.
    window.localStorage.removeItem(ONBOARDING_STORAGE_KEY)
  }

  useEffect(() => {
    if (initialStep) {
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [initialStep, location.pathname, navigate])

  const savedAccount = (() => {
    try {
      const value = window.localStorage.getItem(ACCOUNT_STORAGE_KEY)
      return value ? JSON.parse(value) : null
    } catch {
      return null
    }
  })()
  const displayName = savedAccount?.formData?.fullName?.trim().split(' ')[0] || 'User'
  const userEmail = savedAccount?.formData?.email || ''
  return <OnboardingLayout key={reloadAnswers ? 'reload' : 'default'} userName={displayName} userEmail={userEmail} initialStep={initialStep} />
}

export function App() {
  useEffect(preloadPages, [])

  return (
    <Suspense fallback={null}>
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<OnboardingWrapper />} />
        <Route path="/onboarding" element={<OnboardingWrapper />} />
        <Route path="/processing" element={<ProcessingPage />} />
        <Route path="/goals/new" element={<AddGoalPage />} />
        <Route path="/results/:sessionId" element={<BudgetPlanResults />} />
        <Route path="/summary/:sessionId" element={<BudgetPlanResults />} />
      </Route>
      
      {/* Fallback to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
    </Suspense>
  )
}

export default App