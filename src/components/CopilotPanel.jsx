import { useState } from 'react'
import { Sparkles, Loader2, Volume2, ListChecks, Lightbulb, MessageSquareText, AlertCircle } from 'lucide-react'
import { apiFetch } from '../api.js'
import { LANGUAGES } from './LanguageSelect.jsx'
import ComplexitySelect from './ComplexitySelect.jsx'

export default function CopilotPanel() {
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('mr')
  const [complexity, setComplexity] = useState('simple')
  const [result, setResult] = useState(null)
  const [editedReply, setEditedReply] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const askCopilot = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const res = await apiFetch('/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, language, complexity }),
      })
      if (!res.ok) throw new Error('Copilot request failed')
      const data = await res.json()
      setResult(data)
      setEditedReply(data.suggested_reply_local)
    } catch (err) {
      setError('Could not reach the AI copilot. Check your connection and API key.')
    } finally {
      setBusy(false)
    }
  }

  const speakReply = async () => {
    if (!editedReply.trim()) return
    const form = new FormData()
    form.append('text', editedReply)
    form.append('language', language)
    const res = await apiFetch('/speak', { method: 'POST', body: form })
    if (res.ok) {
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      new Audio(url).play().catch(() => {})
    }
  }

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      {/* Left: query form */}
      <div className="lg:col-span-2">
        <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-7 lg:sticky lg:top-28">
          <h3 className="flex items-center gap-2 text-xl font-display font-bold text-charcoal mb-1">
            <Sparkles className="h-5 w-5 text-primary-500" />
            AI Employee Copilot
          </h3>
          <p className="text-sm text-charcoal/60 mb-5">
            Type what the customer asked (or paraphrase it). The copilot briefs
            you and drafts a reply — nothing is sent until you approve it.
          </p>

          <form onSubmit={askCopilot} className="space-y-5">
            <div>
              <label className="block text-base font-semibold text-charcoal mb-1.5">
                Customer's question
              </label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={4}
                placeholder="e.g. Customer wants to know how to open a savings account for their mother"
                className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base
                  focus:border-primary-500 outline-none transition-colors resize-none"
              />
            </div>

            <div>
              <label className="block text-base font-semibold text-charcoal mb-1.5">
                Reply language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base
                  focus:border-primary-500 outline-none transition-colors"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.english} ({l.label})</option>
                ))}
              </select>
            </div>

            <ComplexitySelect value={complexity} onChange={setComplexity} />

            <button
              type="submit"
              disabled={busy}
              className="w-full py-3.5 rounded-2xl bg-primary-500 text-white font-display font-semibold text-lg
                hover:bg-primary-600 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
              {busy ? 'Thinking…' : 'Ask copilot'}
            </button>

            {error && (
              <div className="flex items-center gap-2 text-warn-600 bg-warn-100 rounded-xl px-4 py-3 text-base">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}
          </form>
        </div>
      </div>

      {/* Right: briefing + draft reply */}
      <div className="lg:col-span-3 space-y-5">
        {!result && !busy && (
          <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-10 text-center text-charcoal/50">
            The copilot's briefing and drafted reply will appear here.
          </div>
        )}

        {result && (
          <>
            <InfoCard
              icon={ListChecks}
              title="What the customer wants"
              body={result.understood_summary}
            />
            <InfoCard
              icon={Lightbulb}
              title="Relevant policy info"
              body={result.relevant_info}
              multiline
            />
            <InfoCard
              icon={ListChecks}
              title="Suggested next action"
              body={result.suggested_action}
              accent
            />

            <div className="bg-white rounded-3xl shadow-card border border-secondary-400/50 p-7">
              <h4 className="flex items-center gap-2 text-lg font-display font-bold text-charcoal mb-1">
                <MessageSquareText className="h-5 w-5 text-secondary-600" />
                Drafted reply — review before sending
              </h4>
              <p className="text-sm text-charcoal/60 mb-4">
                Edit as needed. Nothing is spoken to the customer until you click "Speak to customer."
              </p>
              <textarea
                value={editedReply}
                onChange={(e) => setEditedReply(e.target.value)}
                rows={4}
                className="w-full border-2 border-secondary-400/60 rounded-xl px-4 py-3 text-base
                  focus:border-primary-500 outline-none transition-colors resize-none bg-secondary-50"
              />
              {result.suggested_reply_english && (
                <p className="text-sm text-charcoal/50 italic mt-2">
                  English: {result.suggested_reply_english}
                </p>
              )}
              <button
                onClick={speakReply}
                className="mt-4 px-6 py-3 rounded-2xl bg-secondary-500 text-charcoal font-display font-semibold
                  hover:bg-secondary-600 transition-colors flex items-center gap-2"
              >
                <Volume2 className="h-5 w-5" />
                Speak to customer
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function InfoCard({ icon: Icon, title, body, multiline, accent }) {
  return (
    <div className={`bg-white rounded-2xl shadow-card border p-6 ${accent ? 'border-primary-400/50' : 'border-primary-100'}`}>
      <h4 className="flex items-center gap-2 text-base font-display font-bold text-charcoal mb-2">
        <Icon className={`h-4 w-4 ${accent ? 'text-primary-600' : 'text-primary-500'}`} />
        {title}
      </h4>
      {multiline ? (
        <ul className="space-y-1">
          {(body || '').split('\n').filter(Boolean).map((line, i) => (
            <li key={i} className="text-base text-charcoal flex gap-2">
              <span className="text-primary-500 mt-1">•</span>
              <span>{line.replace(/^[-•]\s*/, '')}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-base text-charcoal">{body}</p>
      )}
    </div>
  )
}
