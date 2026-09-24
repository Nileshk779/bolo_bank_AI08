import { useState } from 'react'
import { LayoutDashboard, Mic, Users, FileText, Sparkles, Circle, ArrowRight, LogOut } from 'lucide-react'
import LoginPage from './components/LoginPage.jsx'
import LanguageSelect from './components/LanguageSelect.jsx'
import CustomerPanel from './components/CustomerPanel.jsx'
import CopilotPanel from './components/CopilotPanel.jsx'
import SessionSummary from './components/SessionSummary.jsx'
import QueuePanel from './components/QueuePanel.jsx'
import { apiFetch, getToken, getStaffName, clearSession } from './api.js'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'customer', label: 'Customer', icon: Mic },
  { id: 'copilot', label: 'Copilot', icon: Sparkles },
  { id: 'queue', label: 'Queue', icon: Users },
  { id: 'summary', label: 'Summary', icon: FileText },
]

export default function App() {
  const [staffName, setStaffName] = useState(getToken() ? getStaffName() : null)
  const [tab, setTab] = useState('dashboard')
  const [language, setLanguage] = useState('mr')
  const [sessionId, setSessionId] = useState(null)
  const [summary, setSummary] = useState(null)

  if (!staffName) {
    return <LoginPage onLoggedIn={(name) => setStaffName(name || 'Staff')} />
  }

  const logout = () => {
    clearSession()
    setStaffName(null)
    setSessionId(null)
    setSummary(null)
    setTab('dashboard')
  }

  const startSession = async () => {
    const form = new FormData()
    form.append('language', language)
    const res = await apiFetch('/sessions/start', { method: 'POST', body: form })
    const data = await res.json()
    setSessionId(data.session_id)
    setTab('customer')
  }

  const endSession = async () => {
    const res = await apiFetch(`/sessions/${sessionId}/summary`)
    if (res.ok) setSummary(await res.json())
    setTab('summary')
  }

  return (
    <div className="min-h-screen">
      <Header tab={tab} setTab={setTab} sessionActive={!!sessionId} staffName={staffName} onLogout={logout} />

      <main className="max-w-6xl mx-auto px-6 py-10 animate-fadeUp">
        {tab === 'dashboard' && (
          <Dashboard language={language} setLanguage={setLanguage} onStart={startSession} sessionId={sessionId} />
        )}
        {tab === 'customer' && sessionId && (
          <CustomerPanel sessionId={sessionId} language={language} onEndSession={endSession} />
        )}
        {tab === 'customer' && !sessionId && (
          <EmptyState message="Start a session from the Dashboard tab first." icon={Mic} />
        )}
        {tab === 'copilot' && <CopilotPanel />}
        {tab === 'queue' && <QueuePanel />}
        {tab === 'summary' && (
          summary
            ? <SessionSummary summary={summary} onStartNew={() => { setSessionId(null); setSummary(null); setTab('dashboard') }} />
            : <EmptyState message="End a session to see its summary here." icon={FileText} />
        )}
      </main>

      <footer className="max-w-6xl mx-auto px-6 pb-8 pt-4 text-center text-sm text-charcoal/40">
        BoloBank — built for accessible, multilingual banking
      </footer>
    </div>
  )
}

function Header({ tab, setTab, sessionActive, staffName, onLogout }) {
  return (
    <header className="sticky top-0 z-30 bg-primary-900 border-b border-primary-700">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <LogoMark />
          <div>
            <p className="font-display font-bold text-lg leading-tight text-white">BoloBank</p>
            <p className="text-xs text-white/70 leading-tight">Voice banking assistant</p>
          </div>
        </div>

        <nav className="hidden lg:flex gap-1 bg-white/10 rounded-full p-1">
          {TABS.map((t) => {
            const Icon = t.icon
            const active = tab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-base font-semibold transition-colors
                  ${active ? 'bg-secondary-500 text-charcoal' : 'text-white/85 hover:bg-white/10'}`}
              >
                <Icon className="h-4 w-4" strokeWidth={2.5} />
                {t.label}
              </button>
            )
          })}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 text-sm font-semibold px-3 py-1.5 rounded-full border
              ${sessionActive
                ? 'bg-secondary-500/20 text-secondary-100 border-secondary-500/40'
                : 'bg-white/5 text-white/60 border-white/15'}`}
          >
            <Circle className={`h-2 w-2 ${sessionActive ? 'fill-secondary-400 text-secondary-400' : 'fill-white/40 text-white/40'}`} />
            {sessionActive ? 'Session active' : 'No active session'}
          </span>
          <span className="text-sm text-white/70">Hi, {staffName}</span>
          <button
            onClick={onLogout}
            aria-label="Log out"
            title="Log out"
            className="p-2 rounded-full text-white/70 hover:bg-white/10 hover:text-white transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* compact nav for small screens */}
      <nav className="lg:hidden flex gap-1 px-4 pb-3 overflow-x-auto">
        {TABS.map((t) => {
          const Icon = t.icon
          const active = tab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-semibold whitespace-nowrap transition-colors
                ${active ? 'bg-secondary-500 text-charcoal' : 'text-white/80 bg-white/5'}`}
            >
              <Icon className="h-3.5 w-3.5" strokeWidth={2.5} />
              {t.label}
            </button>
          )
        })}
        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-semibold whitespace-nowrap bg-white/5 text-white/80"
        >
          <LogOut className="h-3.5 w-3.5" />
          Log out
        </button>
      </nav>
    </header>
  )
}

function Dashboard({ language, setLanguage, onStart, sessionId }) {
  return (
    <div className="grid lg:grid-cols-5 gap-8 items-start">
      <div className="lg:col-span-2 lg:sticky lg:top-28">
        <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-primary-700 bg-primary-100 px-3 py-1.5 rounded-full mb-4">
          <Sparkles className="h-3.5 w-3.5" />
          AI-powered · 5 languages
        </span>
        <h1 className="text-4xl font-display font-bold text-charcoal mb-3 leading-tight">
          Staff dashboard
        </h1>
        <p className="text-charcoal/70 text-lg mb-8">
          Start a new customer interaction session — hand the device over and
          let the customer speak naturally in their own language.
        </p>

        <div className="grid grid-cols-3 gap-3">
          <StatChip value="5+" label="Languages" />
          <StatChip value="24/7" label="Available" />
          <StatChip value="~2s" label="Response" />
        </div>
      </div>

      <div className="lg:col-span-3">
        <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-8">
          <LanguageSelect value={language} onChange={setLanguage} />
          <button
            onClick={onStart}
            className="mt-8 w-full py-4 rounded-2xl bg-primary-500 text-white font-display font-semibold text-lg
              hover:bg-primary-600 transition-colors flex items-center justify-center gap-2"
          >
            {sessionId ? 'Start new session' : 'Start session'}
            <ArrowRight className="h-5 w-5" strokeWidth={2.5} />
          </button>
        </div>

        <div className="mt-6 bg-secondary-50 border border-secondary-400/40 rounded-2xl p-5 text-base text-charcoal flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-secondary-600 shrink-0 mt-0.5" />
          <p>
            <strong className="font-display">Tip:</strong> hand the device to the customer once the
            session starts — they only need to hold the microphone button and speak. Use the
            <strong> Copilot</strong> tab if you'd rather type the question yourself.
          </p>
        </div>
      </div>
    </div>
  )
}

function StatChip({ value, label }) {
  return (
    <div className="bg-white border border-primary-100 rounded-2xl px-3 py-4 text-center shadow-soft">
      <p className="text-2xl font-display font-bold text-charcoal">{value}</p>
      <p className="text-xs font-semibold text-charcoal/50 uppercase tracking-wide mt-0.5">{label}</p>
    </div>
  )
}

function EmptyState({ message, icon: Icon }) {
  return (
    <div className="max-w-md mx-auto text-center py-24">
      {Icon && (
        <div className="mx-auto mb-5 h-16 w-16 rounded-2xl bg-primary-100 flex items-center justify-center">
          <Icon className="h-7 w-7 text-primary-600" strokeWidth={2} />
        </div>
      )}
      <p className="text-charcoal/60 text-lg">{message}</p>
    </div>
  )
}

function LogoMark() {
  return (
    <svg width="40" height="40" viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <circle cx="18" cy="18" r="18" fill="#5B9BD5" />
      <path d="M18 9a6 6 0 0 0-6 6v3a6 6 0 0 0 12 0v-3a6 6 0 0 0-6-6Z" fill="#FFFFFF" />
      <path d="M11 18a1 1 0 1 0-2 0 9 9 0 0 0 8 8.94V29h-2a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.06A9 9 0 0 0 27 18a1 1 0 1 0-2 0 7 7 0 0 1-14 0Z" fill="#FFFFFF" />
    </svg>
  )
}
