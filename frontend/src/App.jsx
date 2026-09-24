import { useState } from 'react'
import LanguageSelect from './components/LanguageSelect.jsx'
import CustomerPanel from './components/CustomerPanel.jsx'
import SessionSummary from './components/SessionSummary.jsx'
import QueuePanel from './components/QueuePanel.jsx'

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'customer', label: 'Customer' },
  { id: 'queue', label: 'Queue' },
  { id: 'summary', label: 'Summary' },
]

const API_BASE = '/api'

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [language, setLanguage] = useState('mr')
  const [sessionId, setSessionId] = useState(null)
  const [summary, setSummary] = useState(null)

  const startSession = async () => {
    const form = new FormData()
    form.append('language', language)
    const res = await fetch(`${API_BASE}/sessions/start`, { method: 'POST', body: form })
    const data = await res.json()
    setSessionId(data.session_id)
    setTab('customer')
  }

  const endSession = async () => {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/summary`)
    if (res.ok) setSummary(await res.json())
    setTab('summary')
  }

  return (
    <div className="min-h-screen bg-cream">
      <Header tab={tab} setTab={setTab} sessionActive={!!sessionId} />

      <main className="max-w-5xl mx-auto px-6 py-10">
        {tab === 'dashboard' && (
          <Dashboard language={language} setLanguage={setLanguage} onStart={startSession} sessionId={sessionId} />
        )}
        {tab === 'customer' && sessionId && (
          <CustomerPanel sessionId={sessionId} language={language} onEndSession={endSession} />
        )}
        {tab === 'customer' && !sessionId && (
          <EmptyState message="Start a session from the Dashboard tab first." />
        )}
        {tab === 'queue' && <QueuePanel />}
        {tab === 'summary' && (
          summary
            ? <SessionSummary summary={summary} onStartNew={() => { setSessionId(null); setSummary(null); setTab('dashboard') }} />
            : <EmptyState message="End a session to see its summary here." />
        )}
      </main>
    </div>
  )
}

function Header({ tab, setTab, sessionActive }) {
  return (
    <header className="bg-teal-900 text-white">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <LogoMark />
          <div>
            <p className="font-display font-bold text-lg leading-tight">BoloBank</p>
            <p className="text-xs text-white/60 leading-tight">Voice banking assistant</p>
          </div>
        </div>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-full text-base font-semibold transition-colors
                ${tab === t.id ? 'bg-gold-500 text-teal-950' : 'text-white/80 hover:bg-teal-800'}`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <span
          className={`hidden sm:inline-flex items-center gap-2 text-sm font-medium px-3 py-1 rounded-full
            ${sessionActive ? 'bg-leaf/20 text-leaf' : 'bg-white/10 text-white/60'}`}
        >
          <span className={`h-2 w-2 rounded-full ${sessionActive ? 'bg-leaf' : 'bg-white/40'}`} />
          {sessionActive ? 'Session active' : 'No active session'}
        </span>
      </div>
    </header>
  )
}

function Dashboard({ language, setLanguage, onStart, sessionId }) {
  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-3xl font-display font-bold text-teal-900 mb-2">Staff dashboard</h1>
      <p className="text-charcoal/70 mb-8 text-lg">Start a new customer interaction session.</p>

      <div className="bg-white rounded-3xl shadow-sm border border-teal-100 p-8">
        <LanguageSelect value={language} onChange={setLanguage} />
        <button
          onClick={onStart}
          className="mt-8 w-full py-4 rounded-2xl bg-teal-900 text-white font-display font-semibold text-lg hover:bg-teal-800 transition-colors"
        >
          {sessionId ? 'Start new session →' : 'Start session →'}
        </button>
      </div>

      <div className="mt-6 bg-gold-100 rounded-2xl p-5 text-base text-teal-950">
        <strong className="font-display">Tip:</strong> hand the device to the customer once the
        session starts — they only need to hold the microphone button and speak.
      </div>
    </div>
  )
}

function EmptyState({ message }) {
  return (
    <div className="max-w-md mx-auto text-center py-20">
      <p className="text-charcoal/60 text-lg">{message}</p>
    </div>
  )
}

function LogoMark() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <circle cx="18" cy="18" r="18" fill="#E8A33D" />
      <path d="M18 9a6 6 0 0 0-6 6v3a6 6 0 0 0 12 0v-3a6 6 0 0 0-6-6Z" fill="#0F4C4C" />
      <path d="M11 18a1 1 0 1 0-2 0 9 9 0 0 0 8 8.94V29h-2a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.06A9 9 0 0 0 27 18a1 1 0 1 0-2 0 7 7 0 0 1-14 0Z" fill="#0F4C4C" />
    </svg>
  )
}
