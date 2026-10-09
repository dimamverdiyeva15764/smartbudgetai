import { PiggyBank } from 'lucide-react'

const ASSESSMENTS = [
  { value: 'Pulumu yaxşı idarə edə bilirəm', icon: <PiggyBank size={16} strokeWidth={2} />, label: 'Pulumu yaxşı idarə edə bilirəm' },
  { value: 'Bəzən planı poza bilirəm', icon: '👤', label: 'Bəzən planı poza bilirəm' },
  { value: 'Ay sonuna pul qalmır', icon: '✂️', label: 'Ay sonuna pul qalmır' }
]

export function StepFinancialAssessment({ value, onChange }) {
  return (
    <div className="step-content">
      <h4 className="question-title">Siz özünüzü necə qiymətləndirirsiniz?</h4>
      <div className="assessment-options-grid">
        {ASSESSMENTS.map((assessment) => (
          <button
            key={assessment.value}
            type="button"
            className={`assessment-option${value === assessment.value ? ' is-selected' : ''}`}
            onClick={() => onChange(assessment.value)}
            aria-pressed={value === assessment.value}
          >
            <span aria-hidden="true">{assessment.icon}</span>
            <span>{assessment.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
