export default function SessionSummary({ summary, onStartNew }) {
  if (!summary) return null

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-teal-100 p-8 max-w-2xl mx-auto">
      <p className="text-sm uppercase tracking-wide text-teal-900/60 font-semibold mb-2">
        Session summary
      </p>
      <h2 className="text-2xl font-display font-bold text-teal-900 mb-6">
        Bilingual interaction record
      </h2>

      <div className="bg-teal-50 rounded-2xl p-5 mb-6">
        <p className="text-sm font-semibold text-teal-900/70 mb-1">Summary (English)</p>
        <p className="text-base text-charcoal">{summary.summary_english}</p>
      </div>

      {summary.turns?.length > 0 && (
        <div className="space-y-3 mb-6 max-h-80 overflow-y-auto pr-1">
          {summary.turns.map((t, i) => (
            <div key={i} className="text-base border-l-4 border-gold-500 pl-4">
              <span className="font-semibold text-teal-900">
                {t.role === 'customer' ? 'Customer' : 'BoloBank'}:
              </span>{' '}
              {t.text_local}
              {t.text_english && (
                <span className="block text-sm text-charcoal/60 italic">{t.text_english}</span>
              )}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onStartNew}
        className="w-full py-4 rounded-2xl bg-teal-900 text-white font-display font-semibold text-lg hover:bg-teal-800 transition-colors"
      >
        Start new session
      </button>
    </div>
  )
}
