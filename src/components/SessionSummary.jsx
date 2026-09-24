import { FileText, RotateCcw, User, Bot } from 'lucide-react'

export default function SessionSummary({ summary, onStartNew }) {
  if (!summary) return null

  return (
    <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-8 max-w-2xl mx-auto">
      <p className="flex items-center gap-2 text-sm uppercase tracking-wide text-charcoal/50 font-semibold mb-2">
        <FileText className="h-4 w-4" />
        Session summary
      </p>
      <h2 className="text-2xl font-display font-bold text-charcoal mb-6">
        Bilingual interaction record
      </h2>

      <div className="bg-primary-50 rounded-2xl p-5 mb-6 border border-primary-100">
        <p className="text-sm font-semibold text-primary-700 mb-1">Summary (English)</p>
        <p className="text-base text-charcoal">{summary.summary_english}</p>
      </div>

      {summary.turns?.length > 0 && (
        <div className="space-y-3 mb-6 max-h-80 overflow-y-auto pr-1">
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
      )}

      <button
        onClick={onStartNew}
        className="w-full py-4 rounded-2xl bg-primary-500 text-white font-display font-semibold text-lg
          hover:bg-primary-600 transition-colors flex items-center justify-center gap-2"
      >
        <RotateCcw className="h-5 w-5" strokeWidth={2.5} />
        Start new session
      </button>
    </div>
  )
}
