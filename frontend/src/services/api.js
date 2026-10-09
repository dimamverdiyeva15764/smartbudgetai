import { API_BASE_URL } from '../config'

// --- TOKENS -----------------------------------------------------------------
// Older builds stored the JWT under several keys; read all of them, write one set.
const ACCESS_KEYS = ['accessToken', 'token', 'access_token']
const REFRESH_KEYS = ['refreshToken', 'refresh_token']

export function getAccessToken() {
  for (const key of ACCESS_KEYS) {
    const value = localStorage.getItem(key)
    if (value) return value
  }
  return null
}

function getRefreshToken() {
  for (const key of REFRESH_KEYS) {
    const value = localStorage.getItem(key)
    if (value) return value
  }
  return null
}

function setTokens(access, refresh) {
  if (access) ACCESS_KEYS.forEach((key) => localStorage.setItem(key, access))
  if (refresh) REFRESH_KEYS.forEach((key) => localStorage.setItem(key, refresh))
}

export function clearTokens() {
  ;[...ACCESS_KEYS, ...REFRESH_KEYS].forEach((key) => localStorage.removeItem(key))
}

// --- ERRORS -----------------------------------------------------------------

export class ApiError extends Error {
  constructor(message, { status = 0, data = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

const NETWORK_ERROR = 'Serverlə əlaqə qurula bilmədi. İnternet bağlantınızı yoxlayıb yenidən cəhd edin.'

function firstErrorMessage(errors) {
  if (!errors) return null
  if (typeof errors === 'string') return errors
  if (Array.isArray(errors)) return firstErrorMessage(errors[0])
  if (typeof errors === 'object') {
    for (const value of Object.values(errors)) {
      const message = firstErrorMessage(value)
      if (message) return message
    }
  }
  return null
}

async function parseJsonResponse(response) {
  const contentType = response.headers.get('content-type') || ''

  if (!contentType.toLowerCase().includes('json')) {
    // Technical details go to the console; the user gets a readable message.
    console.error(`[API] ${response.url} returned ${contentType || 'no content type'} (HTTP ${response.status}) instead of JSON. Check VITE_API_BASE_URL and the backend deployment.`)
    throw new ApiError(
      response.status >= 500
        ? 'Serverdə xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.'
        : 'Serverdən gözlənilməz cavab alındı.',
      { status: response.status }
    )
  }

  try {
    return await response.json()
  } catch (error) {
    console.error(`[API] Invalid JSON (HTTP ${response.status}) from ${response.url}`, error)
    throw new ApiError('Serverdən gözlənilməz cavab alındı.', { status: response.status })
  }
}

function errorFromResponse(response, data, fallback) {
  const message = data?.message || data?.error || firstErrorMessage(data?.errors) || fallback
  return new ApiError(message, { status: response.status, data })
}

// --- REQUESTS ----------------------------------------------------------------

async function refreshAccessToken() {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null

  try {
    const response = await fetch(`${API_BASE_URL}/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken })
    })
    if (!response.ok) return null
    const data = await parseJsonResponse(response)
    setTokens(data.access, data.refresh)
    return data.access
  } catch {
    return null
  }
}

function redirectToLogin() {
  clearTokens()
  if (window.location.pathname !== '/login') window.location.assign('/login')
}

/** Authenticated fetch. Refreshes an expired token once; returns the raw Response. */
async function authorizedFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`
  const build = (token) => ({
    cache: 'no-store',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  })

  let response
  try {
    response = await fetch(url, build(getAccessToken()))
    if (response.status === 401) {
      const newToken = await refreshAccessToken()
      if (!newToken) {
        redirectToLogin()
        throw new ApiError('Sessiyanın vaxtı bitib. Zəhmət olmasa yenidən daxil olun.', { status: 401 })
      }
      response = await fetch(url, build(newToken))
    }
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(NETWORK_ERROR, { cause: error })
  }
  return response
}

/** JSON request that throws ApiError for every non-2xx response. */
// Performance: GET requests started early (e.g. while the "registered"
// message is shown). The page that needs the data takes the already running
// request once instead of starting a new one. Same request, same result.
const prefetched = new Map()
const PREFETCH_MAX_AGE_MS = 15000

export function prefetchApi(path) {
  const promise = apiRequest(path)
  promise.catch(() => {}) // errors are reported when the page uses the data
  prefetched.set(path, { promise, at: Date.now(), token: getAccessToken() })
}

export async function apiRequest(path, options = {}, fallbackMessage = 'Sorğu uğursuz oldu.') {
  const early = !options.method && prefetched.get(path)
  if (early) {
    prefetched.delete(path)
    // Only reuse it for the same signed-in user and only while it is fresh.
    if (Date.now() - early.at < PREFETCH_MAX_AGE_MS && early.token === getAccessToken()) return early.promise
  }
  const response = await authorizedFetch(path, options)
  const data = await parseJsonResponse(response)
  if (!response.ok) throw errorFromResponse(response, data, fallbackMessage)
  return data
}

const json = (method, body) => ({ method, body: JSON.stringify(body ?? {}) })

// --- AUTH ------------------------------------------------------------------

export async function registerUser({ fullName, email, password }) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fullName, email, password })
    })
  } catch (networkErr) {
    throw new ApiError(NETWORK_ERROR, { cause: networkErr })
  }

  const data = await parseJsonResponse(response)
  if (!response.ok) throw errorFromResponse(response, data, 'Qeydiyyat uğursuz oldu.')

  if (!data.tokens?.access) throw new ApiError('Serverdən giriş tokeni alınmadı.')
  setTokens(data.tokens.access, data.tokens.refresh)
  return data
}

// --- ONBOARDING (intermediate saving of each step) -------------------------

export const getOnboardingAnswers = () => apiRequest('/financial-inquiry/answers/')

export const updateSalary = (salary) =>
  apiRequest('/financial-inquiry/salary/', json('PATCH', { salary: Number(salary) }))

export const updateExtraIncome = ({ hasExtraIncome, extraIncome }) => {
  const isYes = hasExtraIncome === 'Bəli' || hasExtraIncome === true
  return apiRequest('/financial-inquiry/extra-income/', json('PATCH', {
    hasExtraIncome: isYes ? 'Bəli' : 'Xeyr',
    extraIncome: isYes ? Number(extraIncome) : null
  }))
}

export const updateHousing = ({ housingType, housingAmount }) =>
  apiRequest('/financial-inquiry/housing/', json('PATCH', {
    housingType,
    housingAmount: housingType === 'Özümündür' || housingAmount === '' ? null : Number(housingAmount)
  }))

export const updateHasCredit = (hasCredit) =>
  apiRequest('/financial-inquiry/has-credit/', json('PATCH', {
    hasCredit: hasCredit === 'Bəli' || hasCredit === true ? 'Bəli' : 'Xeyr'
  }))

/** Replaces the whole credit list in one atomic request. */
export const syncCredits = (credits) =>
  apiRequest('/financial-inquiry/credits/', json('PUT', {
    credits: credits.map((c) => ({
      monthly: Number(c.monthly),
      remaining: Number(c.remaining),
      rate: Number(c.rate),
      months: Number(c.months)
    }))
  }))

const goalPayload = (g) => ({
  id: g.id,
  customName: g.id === 'other' ? (g.customName || '').trim() : '',
  priority: g.priority || 'Orta prioritet',
  amount: Number(g.amount),
  savedAmount: Number(g.savedAmount || 0),
  deadlineMonths: g.deadlineMonths === '' || g.deadlineMonths === undefined || g.deadlineMonths === null ? 12 : Number(g.deadlineMonths)
})

export const updateSavingsGoals = (goals) =>
  apiRequest('/financial-inquiry/savings-goals/', json('PATCH', { goals: goals.map(goalPayload) }))

/** "Yeni plan əlavə et": append goals to the existing ones (nothing is replaced). */
export const addSavingsGoals = (goals) =>
  apiRequest('/financial-inquiry/savings-goals/add/', json('POST', { goals: goals.map(goalPayload) }),
    'Məqsədi əlavə etmək mümkün olmadı.')

export const updateMonthlyExpenses = (e) =>
  apiRequest('/financial-inquiry/monthly-expenses/', json('PATCH', {
    market: Number(e.market || 0),
    utilities: Number(e.utilities || 0),
    transport: Number(e.transport || 0),
    restaurant: Number(e.restaurant || 0),
    clothing: Number(e.clothing || 0),
    entertainment: Number(e.entertainment || 0),
    onlineShopping: Number(e.onlineShopping || 0),
    other: Number(e.other || 0)
  }))

export const updateRecurringExpenses = (recurringExpenses) =>
  apiRequest('/financial-inquiry/recurring-expenses/', json('PATCH', { recurringExpenses }))

export const updateFinancialAssessment = (financialAssessment) =>
  apiRequest('/financial-inquiry/financial-assessment/', json('PATCH', { financialAssessment }))

export const updateMonthlySavingsAbility = (monthlySavingsAbility) =>
  apiRequest('/financial-inquiry/monthly-savings-ability/', json('PATCH', { monthlySavingsAbility }))

// --- PLAN GENERATION ---------------------------------------------------------

export const completeOnboarding = ({ annualBudgetPriority, monthlySavingsAbility }) =>
  apiRequest('/financial-inquiry/complete/', json('POST', {
    annualBudgetPriority,
    ...(monthlySavingsAbility ? { monthlySavingsAbility } : {})
  }), 'Plan hazırlanarkən xəta baş verdi.')

export const getInquiryStatus = () => apiRequest('/financial-inquiry/status/')

export const retryPlanGeneration = () =>
  apiRequest('/financial-inquiry/retry/', json('POST'), 'Planı yenidən hazırlamaq mümkün olmadı.')

export const recalculatePlan = (adjustments = [], { regenerate = false } = {}) =>
  apiRequest('/summary/recalculate/', json('PUT', { adjustments, regenerate }), 'Planı yenidən hesablamaq mümkün olmadı.')

// --- DASHBOARD -------------------------------------------------------------

export const getFinancialSummary = () => apiRequest('/summary/')
export const getSavingsGoalsProgress = () => apiRequest('/summary/goals/')
export const getMonthlyBudgetTable = () => apiRequest('/summary/table/')
export const getBudgetComparison = () => apiRequest('/summary/comparison/')

// --- EXPORTS ---------------------------------------------------------------

async function downloadAuthenticatedFile(path, fallbackFilename) {
  const response = await authorizedFetch(path)
  if (!response.ok) {
    let message = 'Fayl yüklənə bilmədi. Yenidən cəhd edin.'
    try {
      const data = await response.json()
      message = data.message || message
    } catch {
      // keep default message
    }
    throw new ApiError(message, { status: response.status })
  }

  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/)
  const filename = match ? match[1] : fallbackFilename

  const blobUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1000)
}

export const downloadExcelReport = () => downloadAuthenticatedFile('/summary/export/excel/', 'budce_plani.xlsx')
export const downloadPdfReport = () => downloadAuthenticatedFile('/summary/export/pdf/', 'budce_plani.pdf')
