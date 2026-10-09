import { useEffect, useState } from 'react'
import { CheckCircle, RefreshCw, Download } from 'lucide-react'
import { GoalCard } from '../GoalCard'
import {
  completeOnboarding,
  getInquiryStatus,
  retryPlanGeneration,
  getFinancialSummary,
  getSavingsGoalsProgress,
  getMonthlyBudgetTable,
  getBudgetComparison,
  downloadExcelReport,
  downloadPdfReport
} from '../../../services/api'

export function StepSummary({ formData, userName, onReset }) {
  const [phase, setPhase] = useState('generating') // 'generating' | 'ready' | 'error'
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  const [goals, setGoals] = useState([])
  const [monthlyTable, setMonthlyTable] = useState([])
  const [annualTotals, setAnnualTotals] = useState(null)
  const [comparison, setComparison] = useState([])
  const [exportingType, setExportingType] = useState(null) // 'excel' | 'pdf' | null

  useEffect(() => {
    let cancelled = false

    async function run() {
      setPhase('generating')
      setError(null)

      try {
        const priority = formData?.annualBudgetPriority || 'balanced'
        await completeOnboarding(priority)

        // Poll status in case generation takes a moment
        let status = 'processing'
        let attempts = 0
        while (status !== 'completed' && status !== 'failed' && attempts < 30) {
          const statusData = await getInquiryStatus()
          status = statusData.status
          if (status === 'completed' || status === 'failed') break
          await new Promise((resolve) => setTimeout(resolve, 1000))
          attempts += 1
        }

        if (cancelled) return

        if (status === 'failed') {
          setPhase('error')
          setError('Plan hazırlanarkən xəta baş verdi.')
          return
        }

        const [summaryData, goalsData, tableData, comparisonData] = await Promise.all([
          getFinancialSummary(),
          getSavingsGoalsProgress(),
          getMonthlyBudgetTable(),
          getBudgetComparison()
        ])

        if (cancelled) return

        setSummary(summaryData.data)
        setGoals(goalsData.data || [])
        setMonthlyTable(tableData.monthly_table || [])
        setAnnualTotals(tableData.annual_totals || null)
        setComparison(comparisonData.budget_comparison || [])
        setPhase('ready')
      } catch (err) {
        if (cancelled) return
        setPhase('error')
        setError(err.message)
      }
    }

    run()

    return () => {
      cancelled = true
    }
  }, [formData?.annualBudgetPriority])

  const handleRetry = async () => {
    setPhase('generating')
    setError(null)
    try {
      await retryPlanGeneration()

      const [summaryData, goalsData, tableData, comparisonData] = await Promise.all([
        getFinancialSummary(),
        getSavingsGoalsProgress(),
        getMonthlyBudgetTable(),
        getBudgetComparison()
      ])

      setSummary(summaryData.data)
      setGoals(goalsData.data || [])
      setMonthlyTable(tableData.monthly_table || [])
      setAnnualTotals(tableData.annual_totals || null)
      setComparison(comparisonData.budget_comparison || [])
      setPhase('ready')
    } catch (err) {
      setPhase('error')
      setError(err.message)
    }
  }

  const handleExport = async (type) => {
    setExportingType(type)
    try {
      if (type === 'excel') {
        await downloadExcelReport()
      } else {
        await downloadPdfReport()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setExportingType(null)
    }
  }

  if (phase === 'generating') {
    return (
      <div style={{ padding: '4rem 2rem', textAlign: 'center', background: '#f8fafc', borderRadius: '16px', margin: '1rem auto', maxWidth: '800px' }}>
        <RefreshCw size={40} style={{ color: '#f97316', animation: 'spin 1s linear infinite', marginBottom: '1rem' }} />
        <p style={{ color: '#475569', fontSize: '1rem', fontWeight: '500' }}>AI maliyyə məlumatlarınızı təhlil edir və büdcə planını qurur...</p>
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div style={{ padding: '3rem 2rem', textAlign: 'center', background: '#fff', borderRadius: '16px', border: '1px solid #fee2e2', maxWidth: '600px', margin: '2rem auto' }}>
        <p style={{ color: '#dc2626', marginBottom: '1.5rem', fontWeight: '500' }}>{error || 'Plan hazırlanarkən xəta baş verdi.'}</p>
        <button type="button" onClick={handleRetry} style={{ background: '#f97316', color: '#fff', border: 'none', padding: '0.75rem 1.5rem', borderRadius: '8px', cursor: 'pointer', fontWeight: '600' }}>
          Yenidən cəhd et
        </button>
      </div>
    )
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto', background: '#f8fafc', borderRadius: '16px', fontFamily: 'Inter, sans-serif' }}>
      
      {/* Top Header & Export Badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: '#fff', padding: '0.75rem 1.25rem', borderRadius: '10px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <CheckCircle size={22} style={{ color: '#f97316' }} />
          <span style={{ fontWeight: '600', color: '#1e293b', fontSize: '0.95rem' }}>
            {userName ? `${userName}, illik büdcə planınız hazırdır` : 'Fərdiləşdirilmiş AI Planınız Hazırdır!'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            type="button" 
            onClick={() => handleExport('excel')} 
            disabled={exportingType !== null}
            style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', border: '1px solid #f97316', background: '#fff', color: '#f97316', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '500' }}
          >
            <Download size={15} /> {exportingType === 'excel' ? 'Endirilir...' : 'Excel'}
          </button>
          <button 
            type="button" 
            onClick={() => handleExport('pdf')} 
            disabled={exportingType !== null}
            style={{ padding: '0.5rem 1rem', fontSize: '0.85rem', border: 'none', background: '#f97316', color: '#fff', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '500', boxShadow: '0 2px 4px rgba(249, 115, 22, 0.2)' }}
          >
            <Download size={15} /> {exportingType === 'pdf' ? 'Endirilir...' : 'PDF'}
          </button>
        </div>
      </div>

      {/* Top 3 Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ background: '#fff', padding: '1.25rem 1.5rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ display: 'block', fontSize: '0.8rem', color: '#64748b', marginBottom: '6px', fontWeight: '500' }}>Tövsiyə olunan aylıq yığım</span>
          <strong style={{ fontSize: '1.4rem', color: '#0f172a', fontWeight: '700' }}>{summary?.recommended_monthly_savings || '0'}</strong>
        </div>
        <div style={{ background: '#fff', padding: '1.25rem 1.5rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ display: 'block', fontSize: '0.8rem', color: '#64748b', marginBottom: '6px', fontWeight: '500' }}>Tövsiyə olunan illik yığım</span>
          <strong style={{ fontSize: '1.4rem', color: '#0f172a', fontWeight: '700' }}>{summary?.recommended_annual_savings || '0'}</strong>
        </div>
        <div style={{ background: '#fff', padding: '1.25rem 1.5rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <span style={{ display: 'block', fontSize: '0.8rem', color: '#64748b', marginBottom: '6px', fontWeight: '500' }}>Maliyyə vəziyyəti</span>
          <strong style={{ fontSize: '1.4rem', color: '#f97316', fontWeight: '700' }}>{summary?.financial_status || 'Balanslı'}</strong>
        </div>
      </div>

      {/* Savings Goals Section */}
      {goals.length > 0 && (
        <div style={{ marginBottom: '2.5rem' }}>
          <h5 style={{ fontSize: '1rem', fontWeight: '600', color: '#1e293b', marginBottom: '1rem' }}>Yığım məqsədləri</h5>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            {goals.map((goal, idx) => (
              <GoalCard key={idx} goal={goal} />
            ))}
          </div>
        </div>
      )}

      {/* 12-Month Detailed Plan Table */}
      {monthlyTable.length > 0 && (
        <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '12px', border: '1px solid #e2e8f0', marginBottom: '2.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <h5 style={{ fontSize: '1rem', fontWeight: '600', color: '#1e293b', marginBottom: '1rem' }}>AI tərəfindən hazırlanmış 12 aylıq plan</h5>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'center', minWidth: '700px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', color: '#64748b', background: '#fafafa' }}>
                  <th style={{ padding: '0.75rem', fontWeight: '600' }}>Ay</th>
                  <th style={{ padding: '0.75rem', fontWeight: '600' }}>Gəlir</th>
                  <th style={{ padding: '0.75rem', fontWeight: '600' }}>Xərc</th>
                  <th style={{ padding: '0.75rem', fontWeight: '600' }}>Kredit</th>
                  <th style={{ padding: '0.75rem', fontWeight: '600' }}>Yığım</th>
                  <th style={{ padding: '0.75rem', fontWeight: '600' }}>Qalıq</th>
                </tr>
              </thead>
              <tbody>
                {monthlyTable.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '0.75rem', fontWeight: '600', color: '#334155' }}>{row.month_name}</td>
                    <td style={{ padding: '0.75rem', color: '#334155' }}>{row.income}</td>
                    <td style={{ padding: '0.75rem', color: '#64748b' }}>{row.expenses}</td>
                    <td style={{ padding: '0.75rem', color: '#64748b' }}>{row.credit}</td>
                    <td style={{ padding: '0.75rem', color: '#334155' }}>{row.savings}</td>
                    <td style={{ padding: '0.75rem', fontWeight: '700', color: row.is_negative ? '#dc2626' : '#16a34a' }}>
                      {row.balance}
                    </td>
                  </tr>
                ))}
              </tbody>
              {annualTotals && (
                <tfoot>
                  <tr style={{ background: '#fff7ed', fontWeight: '700', borderTop: '2px solid #fdba74' }}>
                    <td style={{ padding: '0.75rem', color: '#c2410c' }}>İllik cəm</td>
                    <td style={{ padding: '0.75rem' }}>{annualTotals.total_income}</td>
                    <td style={{ padding: '0.75rem' }}>{annualTotals.total_expenses}</td>
                    <td style={{ padding: '0.75rem' }}>{annualTotals.total_credit}</td>
                    <td style={{ padding: '0.75rem' }}>{annualTotals.total_savings}</td>
                    <td style={{ padding: '0.75rem', color: annualTotals.is_negative ? '#dc2626' : '#16a34a' }}>
                      {annualTotals.net_annual_balance}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      )}

      {/* Category Comparison Table */}
      {comparison.length > 0 && (
        <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '12px', border: '1px solid #e2e8f0', marginBottom: '2rem', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <h5 style={{ fontSize: '1rem', fontWeight: '600', color: '#1e293b', marginBottom: '1rem' }}>Tövsiyə olunan büdcə bölgüsü</h5>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left', minWidth: '800px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', color: '#64748b', background: '#fafafa' }}>
                  <th style={{ padding: '0.75rem' }}>Kateqoriya</th>
                  <th style={{ padding: '0.75rem' }}>%</th>
                  <th style={{ padding: '0.75rem' }}>Hazırkı aylıq</th>
                  <th style={{ padding: '0.75rem' }}>Tövsiyə olunan aylıq</th>
                  <th style={{ padding: '0.75rem' }}>İllik</th>
                  <th style={{ padding: '0.75rem' }}>Status</th>
                  <th style={{ padding: '0.75rem' }}>AI tövsiyəsi</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '0.75rem', fontWeight: '500', color: '#334155' }}>{row.category_name}</td>
                    <td style={{ padding: '0.75rem', color: '#64748b' }}>{row.percentage}</td>
                    <td style={{ padding: '0.75rem', color: '#64748b' }}>{row.current_monthly_amount}</td>
                    <td style={{ padding: '0.75rem', fontWeight: '600', color: '#0f172a' }}>{row.recommended_monthly_amount}</td>
                    <td style={{ padding: '0.75rem', color: '#64748b' }}>{row.annual_amount}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <span style={{ 
                        background: (row.status || '').toLowerCase().includes('optimal') ? '#dcfce7' : '#fef9c3', 
                        color: (row.status || '').toLowerCase().includes('optimal') ? '#15803d' : '#854d0e', 
                        padding: '0.25rem 0.6rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: '500', display: 'inline-block' 
                      }}>
                        {row.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem', color: '#64748b', fontSize: '0.75rem' }}>{row.ai_recommendation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Bottom Action Buttons */}
      <div style={{ textAlign: 'center', marginTop: '2rem' }}>
        <button type="button" onClick={onReset} style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', textDecoration: 'underline', fontSize: '0.9rem', fontWeight: '500' }}>
          Yenidən başla
        </button>
      </div>

    </div>
  )
}

export default StepSummary