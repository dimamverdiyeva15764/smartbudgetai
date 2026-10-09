import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Download,
  FilePenLine,
  LineChart,
  PiggyBank,
  Plus,
  Printer,
  RefreshCw,
  RotateCcw,
  TrendingUp
} from 'lucide-react'
import {
  ONBOARDING_ACTIVE_KEY,
  ONBOARDING_STORAGE_KEY,
  ACCOUNT_STORAGE_KEY,
  BUDGET_MONTHS_STORAGE_KEY
} from '../../hooks/useOnboardingForm'
import {
  downloadExcelReport,
  getBudgetComparison,
  getFinancialSummary,
  getMonthlyBudgetTable,
  getSavingsGoalsProgress,
  recalculatePlan
} from '../../services/api'
import { Header } from './Header'
import { LoadingPlan } from './LoadingPlan'
import { GoalCard } from './GoalCard'

const MONTHS = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'İyn', 'İyl', 'Avq', 'Sen', 'Okt', 'Noy', 'Dek']

// Columns required by the specification (§4 / §28) and US-15.
const TABLE_COLUMNS = [
  { key: 'income', label: 'Gəlir', editable: false },
  { key: 'housing', label: 'Kirayə', editable: false },
  { key: 'restaurant', label: 'Restoran' },
  { key: 'entertainment', label: 'Əyləncə' },
  { key: 'food', label: 'Qida' },
  { key: 'utilities', label: 'Kommunal' },
  { key: 'transport', label: 'Nəqliyyat' },
  { key: 'credit', label: 'Kredit', editable: false },
  { key: 'other', label: 'Digər' },
  { key: 'savings', label: 'Yığım', editable: false },
  { key: 'balance', label: 'Qalıq', editable: false }
]
const OTHER_PARTS = ['clothing', 'online_shopping', 'other_misc']
// Values sent to the server after a manual edit ("Digər" is sent as its parts).
const ADJUSTABLE_COLUMNS = ['restaurant', 'entertainment', 'food', 'utilities', 'transport', ...OTHER_PARTS, 'savings']
const EXPENSE_KEYS = ['housing', 'restaurant', 'entertainment', 'food', 'utilities', 'transport', 'credit', 'other']
// Editable recommended amounts → monthly field they change. Rent and credit
// are fixed obligations from the answers ("Cavabı dəyiş").
const COMPARISON_TO_COLUMN = {
  food: 'food',
  restaurant: 'restaurant',
  entertainment: 'entertainment',
  utilities: 'utilities',
  transport: 'transport',
  clothing: 'clothing',
  online_shopping: 'online_shopping',
  other_misc: 'other_misc',
  savings: 'savings'
}
const AUTO_RECALC_DELAY_MS = 800

const STATUS_TONE = {
  'Prioritet ödəniş': 'priority',
  'Diqqət': 'attention',
  'Uyğundur': 'good',
  'Yüksək xərc': 'high',
  'Qənaətlidir': 'savings'
}

const numberValue = (value) => Number(value) || 0
const round2 = (value) => Math.round(value * 100) / 100
const money = (value) => `${numberValue(value).toLocaleString('az-AZ', { maximumFractionDigits: 2 })} AZN`

/**
 * Instant preview of a dashboard edit. Qalıq is the leftover: Income − expenses −
 * planned Savings; Savings are reduced only when the leftover would be negative.
 * The server then recalculates automatically (Yığım, Qalıq, goal split).
 */
const withOtherTotal = (month) => ({
  ...month,
  other: OTHER_PARTS.reduce((total, key) => total + numberValue(month[key]), 0)
})

const rebalanceMonth = (month, plannedSavings = 0) => {
  const expenses = EXPENSE_KEYS.reduce((total, key) => total + numberValue(month[key]), 0)
  const free = round2(numberValue(month.income) - expenses)
  const savings = Math.max(0, Math.min(numberValue(plannedSavings), free))
  return { ...month, savings: round2(savings), balance: round2(free - savings) }
}

export function BudgetPlanResults() {
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [summary, setSummary] = useState(null)
  const [goals, setGoals] = useState([])
  const [planMonths, setPlanMonths] = useState([]) // as calculated by the server
  const [months, setMonths] = useState([]) // incl. local what-if edits
  const [comparison, setComparison] = useState([])

  const [showAllGoals, setShowAllGoals] = useState(false)
  const [showNotes, setShowNotes] = useState(false)
  const [showRecalcModal, setShowRecalcModal] = useState(false)
  const [download, setDownload] = useState({ type: null, error: null })
  const [drafts, setDrafts] = useState({}) // raw text while an input is being edited
  const [sync, setSync] = useState({ state: 'idle', error: null }) // idle | saving | saved | error

  const monthsRef = useRef([])
  const timerRef = useRef(null)
  const editSeq = useRef(0)
  const dirtyRef = useRef(new Set()) // "monthIndex:key" cells the user really edited
  const requestSeq = useRef(0)
  useEffect(() => { monthsRef.current = months }, [months])
  useEffect(() => () => window.clearTimeout(timerRef.current), [])

  const loadPlanData = useCallback(() => Promise.all([
    getFinancialSummary(),
    getSavingsGoalsProgress(),
    getMonthlyBudgetTable(),
    getBudgetComparison()
  ]), [])

  const applyPlanData = ([summaryRes, goalsRes, tableRes, comparisonRes]) => {
    setSummary(summaryRes.data)
    setGoals(goalsRes.data || [])
    setPlanMonths(tableRes.monthly_table || [])
    setMonths(tableRes.monthly_table || [])
    setComparison(comparisonRes.budget_comparison || [])
    setLoading(false)
  }

  useEffect(() => {
    // Old builds kept table edits in localStorage, which showed stale numbers.
    window.localStorage.removeItem('budgetModifiedFields')
    window.localStorage.removeItem(BUDGET_MONTHS_STORAGE_KEY)

    let active = true
    loadPlanData()
      .then((data) => active && applyPlanData(data))
      .catch((err) => {
        if (!active) return
        if (err.status === 409) {
          // Plan is not Ready (pending / processing / failed) → processing screen.
          navigate('/processing', { replace: true })
          return
        }
        setError(err.message || 'Plan məlumatlarını yükləmək mümkün olmadı.')
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [loadPlanData, navigate])

  const isEdited = useMemo(
    () => JSON.stringify(months) !== JSON.stringify(planMonths),
    [months, planMonths]
  )

  const totals = useMemo(() => TABLE_COLUMNS.reduce((result, column) => ({
    ...result,
    [column.key]: round2(months.reduce((total, month) => total + numberValue(month[column.key]), 0))
  }), {}), [months])

  const comparisonRows = useMemo(() => {
    if (!isEdited) return comparison
    const income = numberValue(summary?.reliable_monthly_income)
    return comparison.map((row) => {
      const column = COMPARISON_TO_COLUMN[row.category_key]
      if (!column) return row
      const annual = round2(months.reduce((total, month) => total + numberValue(month[column]), 0))
      const recommended = round2(annual / 12)
      return {
        ...row,
        recommended_monthly_amount: recommended,
        annual_amount: annual,
        percentage: income ? round2((recommended / income) * 100) : 0
      }
    })
  }, [comparison, isEdited, months, summary])

  const userName = (() => {
    try {
      const stored = window.localStorage.getItem(ACCOUNT_STORAGE_KEY)
      const parsed = stored ? JSON.parse(stored) : null
      return parsed?.formData?.fullName?.trim().split(' ')[0] || 'İstifadəçi'
    } catch {
      return 'İstifadəçi'
    }
  })()

  // Only the cells the user edited are sent (preview values such as the
  // recalculated Yığım are never sent as manual values).
  const collectAdjustments = (current, dirty) => [...dirty].map((cell) => {
    const [index, key] = cell.split(':')
    return { month_index: Number(index) + 1, category: key, value: numberValue(current[Number(index)]?.[key]) }
  }).filter((item) => ADJUSTABLE_COLUMNS.includes(item.category))

  const markDirty = (index, key) => {
    const keys = key === 'other' ? OTHER_PARTS : [key]
    keys.forEach((k) => dirtyRef.current.add(`${index}:${k}`))
  }

  // Manual edits are recalculated automatically on the server (no button):
  // the edited value is kept and Yığım, Qalıq and the goal split are updated.
  const autoRecalculate = async () => {
    const dirty = new Set(dirtyRef.current)
    const adjustments = collectAdjustments(monthsRef.current, dirty)
    if (!adjustments.length) return
    dirtyRef.current = new Set()
    const seq = ++requestSeq.current
    const sentAtEdit = editSeq.current
    setSync({ state: 'saving', error: null })
    try {
      await recalculatePlan(adjustments)
      const [summaryRes, goalsRes, tableRes, comparisonRes] = await loadPlanData()
      if (seq !== requestSeq.current) return // a newer recalculation is running
      setSummary(summaryRes.data)
      setGoals(goalsRes.data || [])
      setPlanMonths(tableRes.monthly_table || [])
      setComparison(comparisonRes.budget_comparison || [])
      // keep any newer local edits; they are sent with the next recalculation
      if (editSeq.current === sentAtEdit) setMonths(tableRes.monthly_table || [])
      setSync({ state: 'saved', error: null })
    } catch (err) {
      dirty.forEach((cell) => dirtyRef.current.add(cell)) // try again with the next edit
      if (seq === requestSeq.current) setSync({ state: 'error', error: err.message || 'Plan yenilənmədi.' })
    }
  }

  const scheduleAutoRecalculate = () => {
    editSeq.current += 1
    window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(autoRecalculate, AUTO_RECALC_DELAY_MS)
  }

  const setDraft = (id, value) => setDrafts((current) => ({ ...current, [id]: value }))
  const clearDraft = (id) => setDrafts((current) => {
    const next = { ...current }
    delete next[id]
    return next
  })

  // Editing one month cell. An empty field counts as 0 but stays empty while typing.
  const updateCell = (monthIndex, key, value) => {
    setDraft(`m:${monthIndex}:${key}`, value)
    markDirty(monthIndex, key)
    const newValue = value === '' ? 0 : Math.max(0, numberValue(value))
    setMonths((current) => current.map((month, index) => {
      if (index !== monthIndex) return month
      let next = { ...month, [key]: newValue }
      if (key === 'other') {
        // spread the new "Digər" total over its parts in the current proportion
        const partsTotal = OTHER_PARTS.reduce((total, part) => total + numberValue(month[part]), 0)
        let assigned = 0
        OTHER_PARTS.forEach((part, partIndex) => {
          const share = partIndex === OTHER_PARTS.length - 1
            ? newValue - assigned
            : (partsTotal > 0 ? Math.round(newValue * numberValue(month[part]) / partsTotal) : 0)
          next[part] = Math.max(0, share)
          assigned += next[part]
        })
        next = withOtherTotal(next)
      }
      return rebalanceMonth(next, planMonths[index]?.savings)
    }))
    scheduleAutoRecalculate()
  }

  // Editing a recommended monthly amount scales that category in every month,
  // keeping the seasonal pattern instead of copying one value into 12 months.
  const updateComparisonCell = (row, value) => {
    const column = COMPARISON_TO_COLUMN[row.category_key]
    if (!column) return
    setDraft(`c:${row.category_key}`, value)
    for (let index = 0; index < 12; index += 1) markDirty(index, column)
    const target = value === '' ? 0 : Math.max(0, numberValue(value))
    const planAverage = planMonths.reduce((total, month) => total + numberValue(month[column]), 0) / 12
    setMonths((current) => current.map((month, index) => {
      const base = numberValue(planMonths[index]?.[column])
      const nextValue = planAverage > 0 ? Math.round(base * (target / planAverage)) : Math.round(target)
      const next = withOtherTotal({ ...month, [column]: nextValue })
      return rebalanceMonth(next, column === 'savings' ? nextValue : planMonths[index]?.savings)
    }))
    scheduleAutoRecalculate()
  }

  const resetEdits = () => {
    window.clearTimeout(timerRef.current)
    dirtyRef.current = new Set()
    setDrafts({})
    setMonths(planMonths)
  }

  const handleEdit = () => {
    window.localStorage.removeItem(ONBOARDING_STORAGE_KEY)
    window.localStorage.setItem(ONBOARDING_ACTIVE_KEY, 'true')
    navigate('/onboarding', { state: { startAtStep: 1, reloadAnswers: true } })
  }

  // "Planı yenilə": always a genuinely new alternative plan (new variant),
  // also after manual edits; not-yet-sent edits are included.
  const handleRecalculate = () => {
    setShowRecalcModal(false)
    window.clearTimeout(timerRef.current)
    const adjustments = collectAdjustments(months, dirtyRef.current)
    dirtyRef.current = new Set()
    navigate('/processing', { state: { action: 'recalculate', adjustments, regenerate: true } })
  }

  const handleDownload = async (type) => {
    setDownload({ type, error: null })
    try {
      await downloadExcelReport()
      setDownload({ type: null, error: null })
    } catch (err) {
      setDownload({ type: null, error: err.message || 'Fayl yüklənə bilmədi.' })
    }
  }

  const visibleGoals = showAllGoals ? goals : goals.slice(0, 3)

  if (loading) {
    return (
      <div className="results-page-wrapper">
        <Header />
        <main className="results-main-container results-loading-container">
          <LoadingPlan phase={2} />
        </main>
      </div>
    )
  }

  if (error) {
    return (
      <div className="results-page-wrapper">
        <Header />
        <main className="results-main-container results-error-container">
          <p role="alert">{error}</p>
          <button type="button" className="btn-restart" onClick={() => window.location.reload()}>Yenidən cəhd et</button>
        </main>
      </div>
    )
  }

  const editedNote = (isEdited || sync.state !== 'idle') && (
    <p className={sync.state === 'error' ? 'processing-error-text' : 'results-what-if-note'} role="status">
      {sync.state === 'error'
        ? sync.error
        : sync.state === 'saving' || isEdited
          ? 'Dəyişiklik avtomatik hesablanır: Yığım, Qalıq və məqsəd bölgüsü yenilənir...'
          : 'Dəyişiklik tətbiq olundu: Yığım, Qalıq və məqsəd bölgüsü yeniləndi.'}{' '}
      {isEdited && (
        <button type="button" className="results-link-button" onClick={resetEdits}>
          <RotateCcw size={12} /> AI planına qaytar
        </button>
      )}
    </p>
  )

  return (
    <div className="results-page-wrapper">
      <Header />
      <main className="results-main-container">
      <div className="budget-results" id="budget-plan-results">
      <div className="results-heading">
        <div>
          <h1>{userName}, illik büdcə planınız hazırdır</h1>
          <p>{summary?.monthly_budget_plan || 'Cavablarınıza əsaslanan fərdiləşdirilmiş illik plan'}</p>
        </div>
        <button type="button" className="results-action results-action-primary" onClick={() => window.print()}>
          <Printer size={15} /> Çap/PDF
        </button>
      </div>

      <section className="results-summary-grid" aria-label="Büdcə xülasəsi">
        <div className="results-summary-card">
          <div className="results-summary-copy">
            <span>Tövsiyə olunan aylıq yığım</span>
            <strong>{money(summary?.recommended_monthly_savings)}</strong>
          </div>
          <span className="results-summary-icon"><PiggyBank size={20} strokeWidth={2} /></span>
        </div>
        <div className="results-summary-card">
          <div className="results-summary-copy">
            <span>Tövsiyə olunan illik yığım</span>
            <strong>{money(summary?.recommended_annual_savings)}</strong>
          </div>
          <span className="results-summary-icon"><TrendingUp size={20} strokeWidth={2} /></span>
        </div>
        <div className="results-summary-card results-summary-card-accent" title={summary?.financial_status_description || ''}>
          <div className="results-summary-copy">
            <span>Maliyyə vəziyyəti</span>
            <strong>{summary?.financial_status || 'Naməlum'}</strong>
          </div>
          <span className="results-summary-icon"><LineChart size={20} strokeWidth={2} /></span>
        </div>
      </section>
      {summary?.financial_status_description && (
        <p className="results-what-if-note">{summary.financial_status_description}</p>
      )}
      {summary && summary.is_feasible === false && (
        <div className="results-warning-banner" role="alert">
          <strong>Diqqət: büdcə maliyyə baxımından mümkün deyil.</strong>{' '}
          Məcburi ödənişlər (kirayə, kredit) və minimum vacib xərclər gəliri aşır — qırmızı “Qalıq” aylıq kəsiri göstərir.
          Gəliri artırmaq və ya öhdəlikləri azaltmaq lazımdır.
        </div>
      )}
      {summary?.goal_warnings?.length > 0 && (
        <div className="results-warning-banner results-warning-soft" role="status">
          <strong>Bəzi məqsədlərə istənilən müddətdə çatmaq mümkün deyil:</strong>
          <ul>{summary.goal_warnings.map((text, index) => <li key={index}>{text}</li>)}</ul>
        </div>
      )}

      <section className="goals-section">
        <div className="results-section-heading">
          <h2>Yığım məqsədləri</h2>
          {goals.length > 3 && (
            <button type="button" className="results-link-button" onClick={() => setShowAllGoals((current) => !current)}>
              <span>{showAllGoals ? 'Gizlət' : 'Hamısına bax'}</span>
              {showAllGoals ? <ChevronUp className="results-link-icon" /> : <ChevronRight className="results-link-icon" />}
            </button>
          )}
        </div>
        {goals.length > 0 ? (
          <div className="results-goals-grid">
            {visibleGoals.map((goal, idx) => (
              <GoalCard key={goal.goal_id || idx} goal={goal} />
            ))}
          </div>
        ) : <div className="results-empty-state">Hələ yığım məqsədi seçilməyib.</div>}
        {goals.length > 0 && planMonths.some((month) => Array.isArray(month.goal_contributions)) && (
          <div className="results-panel goal-split-panel">
            <p className="goal-split-title">Aylıq “Yığım” məbləğinin məqsədlər üzrə bölgüsü</p>
            <div className="results-table-scroll">
              <table className="annual-plan-table goal-split-table">
                <thead>
                  <tr>
                    <th>Məqsəd</th>
                    {planMonths.map((month, index) => <th key={month.month_name}>{MONTHS[index] || month.month_name}</th>)}
                    <th>Cəmi</th>
                  </tr>
                </thead>
                <tbody>
                  {goals.map((goal, goalIndex) => (
                    <tr key={goal.goal_id || goalIndex}>
                      <th>{goal.goal_name}</th>
                      {planMonths.map((month) => <td key={month.month_name}>{money(month.goal_contributions?.[goalIndex])}</td>)}
                      <td><strong>{money(goal.planned_contribution_12m)}</strong></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th>Yığım</th>
                    {planMonths.map((month) => <th key={month.month_name}>{money(month.savings)}</th>)}
                    <th>{money(planMonths.reduce((total, month) => total + numberValue(month.savings), 0))}</th>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}
      </section>

      <section className="annual-plan-section results-panel">
        <div className="results-section-heading plan-heading">
          <div>
            <h2>AI tərəfindən hazırlanmış 12 aylıq plan</h2>
            <p>Hər ay ayrıca hesablanır: mövsüm, bayramlar və sizin cavablarınız nəzərə alınır. Yığım — məqsədlərinizə ayrılan pul, Qalıq — xərclər və yığımdan sonra sərbəst qalan pul.</p>
            {summary?.plan_version ? <p className="results-what-if-note">Plan versiyası: {summary.plan_version}</p> : null}
          </div>
          <div className="results-actions">
            <button type="button" className="results-action" onClick={handleEdit}><FilePenLine size={14} /> Cavabı dəyiş</button>
            <button type="button" className="results-action" onClick={() => setShowRecalcModal(true)}>
              <RefreshCw size={14} /> Planı yenilə
            </button>
            <button type="button" className="results-action" onClick={() => navigate('/goals/new')}><Plus size={14} /> Yeni plan əlavə et</button>
          </div>
        </div>
        {editedNote}
        <div className="results-table-scroll">
          <table className="annual-plan-table">
            <thead>
              <tr>
                <th>Ay</th>
                {TABLE_COLUMNS.map((column) => <th key={column.key}>{column.label}</th>)}
              </tr>
            </thead>
            <tbody>{months.map((month, monthIndex) => (
              <tr key={month.month_name || monthIndex}>
                <th><span className="month-pill" title={month.note || ''}>{MONTHS[monthIndex] || month.month_name}</span></th>
                {TABLE_COLUMNS.map((column) => (
                  <td key={column.key}>
                    {column.editable === false
                      ? <strong className={column.key === 'balance' && numberValue(month.balance) < 0 ? 'negative-value' : ''}>{money(month[column.key])}</strong>
                      : <input
                          aria-label={`${month.month_name} ${column.label}`}
                          type="number"
                          min="0"
                          value={drafts[`m:${monthIndex}:${column.key}`] ?? month[column.key] ?? ''}
                          placeholder="0"
                          onChange={(event) => updateCell(monthIndex, column.key, event.target.value)}
                          onBlur={() => clearDraft(`m:${monthIndex}:${column.key}`)}
                        />}
                  </td>
                ))}
              </tr>
            ))}</tbody>
            <tfoot>
              <tr>
                <th>İllik cəmi</th>
                {TABLE_COLUMNS.map((column) => (
                  <th key={column.key} className={column.key === 'balance' && totals.balance < 0 ? 'negative-value' : ''}>{money(totals[column.key])}</th>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
        {months.some((month) => numberValue(month.balance) < 0) && (
          <p className="processing-error-text" role="alert">
            Qırmızı qalıq: həmin aylarda məcburi ödənişlər və minimum vacib xərclər gəliri aşır — büdcə mümkün deyil.
          </p>
        )}
        <button type="button" className="results-link-button" onClick={() => setShowNotes((value) => !value)}>
          {showNotes ? <ChevronUp className="results-link-icon" /> : <ChevronDown className="results-link-icon" />}
          <span>Aylar üzrə AI izahı</span>
        </button>
        {showNotes && (
          <ul className="results-month-notes">
            {planMonths.map((month) => (
              <li key={month.month_name}><strong>{month.month_name}:</strong> {month.note}</li>
            ))}
          </ul>
        )}
        <div className="results-panel-footer">
          {download.error && <p className="processing-error-text" role="alert">{download.error}</p>}
          <div className="results-actions">
            <button type="button" className="results-action results-action-primary" onClick={() => handleDownload('excel')} disabled={download.type !== null}>
              <Download size={14} /> {download.type === 'excel' ? 'Yüklənir...' : 'Excel yüklə'}
            </button>
          </div>
        </div>
      </section>

      <section className="distribution-section results-panel">
        <div className="results-section-heading"><div><h2>Tövsiyə olunan büdcə bölgüsü</h2><p>Tövsiyə olunan aylıq məbləğləri dəyişə bilərsiniz. Yığım və qalıq avtomatik yenidən hesablanacaq.</p></div></div>
        <div className="results-table-scroll">
          <table className="distribution-table">
            <thead><tr><th>Kateqoriya</th><th>%</th><th>Hazırkı aylıq</th><th>Tövsiyə olunan aylıq</th><th>İllik</th><th>Status</th><th>AI tövsiyəsi</th></tr></thead>
            <tbody>{comparisonRows.map((row) => (
              <tr key={row.category_key || row.category_name}>
                <th><span>{row.category_name}</span></th>
                <td>{row.percentage}%</td>
                <td>{money(row.current_monthly_amount)}</td>
                <td>
                  {COMPARISON_TO_COLUMN[row.category_key]
                    ? <input
                        type="number"
                        min="0"
                        className="distribution-input"
                        aria-label={`${row.category_name} tövsiyə olunan aylıq`}
                        value={drafts[`c:${row.category_key}`] ?? row.recommended_monthly_amount ?? ''}
                        onChange={(event) => updateComparisonCell(row, event.target.value)}
                        onBlur={() => clearDraft(`c:${row.category_key}`)}
                      />
                    : <strong>{money(row.recommended_monthly_amount)}</strong>}
                </td>
                <td>{money(row.annual_amount)}</td>
                <td><span className={`budget-tag ${STATUS_TONE[row.status] || 'good'}`}>{row.status}</span></td>
                <td>{row.ai_recommendation}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        {editedNote}
      </section>

      {showRecalcModal && (
        <div className="results-modal-backdrop" role="presentation" onClick={() => setShowRecalcModal(false)}>
          <div className="results-modal" role="dialog" aria-modal="true" aria-labelledby="recalc-title" onClick={(event) => event.stopPropagation()}>
            <h2 id="recalc-title">Plan yenidən hesablansın?</h2>
            <p>Bütün 12 aylıq plan ən son cavablarınız və cədvəldə dəyişdiyiniz məbləğlər əsasında yenidən hesablanacaq, yadda saxlanılacaq və əvvəlki planı əvəz edəcək. Gəlir, kirayə və ya kredit kimi cavabları dəyişmək üçün “Cavabı dəyiş” düyməsindən istifadə edin.</p>
            <div className="results-modal-actions">
              <button type="button" className="results-action" onClick={() => setShowRecalcModal(false)}>Ləğv et</button>
              <button type="button" className="results-action results-action-primary" onClick={handleRecalculate}>Yenidən hesabla</button>
            </div>
          </div>
        </div>
      )}

      </div>
      </main>
    </div>
  )
}

export default BudgetPlanResults
