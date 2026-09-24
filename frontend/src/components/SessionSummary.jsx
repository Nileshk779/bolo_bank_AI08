import { FileText, RotateCcw, User, Bot, AlertCircle, ListChecks, BookOpen, ArrowRight, HelpCircle } from 'lucide-react'

export default function SessionSummary({ summary, onStartNew }) {
  if (!summary) return null

  return (
    <div className="premium-card p-8 max-w-2xl mx-auto">
      <p className="flex items-center gap-2 text-sm uppercase tracking-wide text-charcoal/50 font-semibold mb-2">
        <FileText className="h-4 w-4" />
        Customer session summary
      </p>
      <h2 className="text-2xl font-display font-bold text-charcoal mb-6">
        {summary.language ? `Language: ${summary.language}` : 'Session record'}
      </h2>

      <div className="space-y-4 mb-6">
        <SummaryField
          icon={AlertCircle}
          label="Customer issue"
          value={summary.customer_issue}
          accent="border-primary-400/50"
        />

        {summary.important_information?.length > 0 && (
          <div className="rounded-2xl border border-primary-100 p-5">
            <p className="flex items-center gap-2 text-sm font-semibold text-primary-700 mb-2">
              <ListChecks className="h-4 w-4" />
              Important information
            </p>
            <ul className="space-y-1">
              {summary.important_information.map((item, i) => (
                <li key={i} className="text-base text-charcoal flex gap-2">
                  <span className="text-primary-500 mt-1">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {summary.relevant_policy && (
          <SummaryField icon={BookOpen} label="Relevant policy" value={summary.relevant_policy} />
        )}

        {summary.recommended_next_action && (
          <SummaryField
            icon={ArrowRight}
            label="Recommended next action"
            value={summary.recommended_next_action}
            accent="border-secondary-400/60 bg-secondary-50"
          />
        )}

        {summary.unresolved && (
          <SummaryField
            icon={HelpCircle}
            label="Unresolved"
            value={summary.unresolved}
            accent="border-warn-400/60 bg-warn-100/40"
          />
        )}
      </div>

      {summary.turns?.length > 0 && (
        <details className="mb-6">
          <summary className="cursor-pointer text-sm font-semibold text-charcoal/60 mb-3 select-none">
            View full transcript ({summary.turns.length} turns)
          </summary>
          <div className="space-y-3 max-h-80 overflow-y-auto pr-1 mt-3">
            {summary.turns.map((t, i) => (
              <div key={i} className="text-base border-l-4 border-secondary-500 pl-4 flex gap-2">
                <span className="shrink-0 mt-0.5">
                  {t.role === 'customer'
                    ? <User className="h-4 w-4 text-primary-600" />
                    : <Bot className="h-4 w-4 text-secondary-600" />}
                </span>
                <span>
                  <span className="font-semibold text-charcoal">
                    {t.role === 'customer' ? 'Customer' : 'BoloBank'}:
                  </span>{' '}
                  {t.text_local}
                  {t.text_english && (
                    <span className="block text-sm text-charcoal/60 italic">{t.text_english}</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      <button
        onClick={onStartNew}
        className="w-full py-4 rounded-2xl bg-primary-500 text-white font-display font-semibold shadow-soft hover:shadow-card text-lg
          hover:bg-primary-600 hover:-translate-y-0.5 transition-all flex items-center justify-center gap-2"
      >
        <RotateCcw className="h-5 w-5" strokeWidth={2.5} />
        Start new session
      </button>
    </div>
  )
}

function SummaryField({ icon: Icon, label, value, accent = 'border-primary-100' }) {
  if (!value) return null
  return (
    <div className={`rounded-2xl border p-5 ${accent}`}>
      <p className="flex items-center gap-2 text-sm font-semibold text-primary-700 mb-1">
        <Icon className="h-4 w-4" />
        {label}
      </p>
      <p className="text-base text-charcoal">{value}</p>
    </div>
  )
}
