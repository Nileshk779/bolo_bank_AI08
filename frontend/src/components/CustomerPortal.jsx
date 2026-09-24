import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Headphones, HelpCircle, Landmark, Loader2, PlusCircle, ShieldCheck, Sparkles, UserRound, Volume2, X } from 'lucide-react'
import MicButton from './MicButton.jsx'
import VisualDataCard from './VisualDataCard.jsx'
import LoanEligibility from './LoanEligibility.jsx'
import NewSchemesNotice, { NewSchemesBell, getSeenSchemes, markSchemesSeen } from './NewSchemesNotice.jsx'
import { LANGUAGES, t } from '../i18n.js'
import { customerFetch, clearCustomerSession, setCustomerSession } from '../api.js'

export default function CustomerPortal({ onBack }) {
  const [language, setLanguage] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [statusKey, setStatusKey] = useState('')
  const [elderlyMode, setElderlyMode] = useState(true)
  const [ended, setEnded] = useState(false)
  const [showEligibility, setShowEligibility] = useState(false)
  // Explanation level: starts Simple and adapts when the customer says "I
  // didn't understand" / "tell me more" (backend/services/clarification_service.py).
  const [level, setLevel] = useState('simple')
  const audioRef = useRef(null)
  const lastSpokenRef = useRef('')

  const tr = (key) => t(language || 'en', key)

  // "New schemes at the bank" — staff-approved schemes from the daily
  // update, in the customer's language. Never shown automatically: the voice
  // assistant stays the main screen, and the list opens only from the
  // header button, whose badge counts schemes this browser hasn't opened yet.
  const [newSchemes, setNewSchemes] = useState([])
  const [noticeOpen, setNoticeOpen] = useState(false)
  const [unseenCount, setUnseenCount] = useState(0)
  useEffect(() => {
    if (!language) return
    let cancelled = false
    fetch(`/api/customer/new-schemes?language=${language}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => {
        if (cancelled) return
        setNewSchemes(list)
        const seen = getSeenSchemes()
        setUnseenCount(list.filter((s) => !seen.includes(s.scheme_id)).length)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [language])
  const openNotice = () => { markSchemesSeen(newSchemes.map((s) => s.scheme_id)); setUnseenCount(0); setNoticeOpen(true) }
  const hideNotice = () => setNoticeOpen(false)
  const openChecker = async () => {
    if (!sessionId && !(await startSession())) return
    setNoticeOpen(false)
    setShowEligibility(true)
  }

  const startSession = async () => {
    setBusy(true)
    try {
      const res = await fetch('/api/customer/session/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ language })
      })
      if (!res.ok) throw new Error('session')
      const data = await res.json()
      setCustomerSession(data.customer_token)
      setSessionId(data.session_id)
      setEnded(false)
      return true
    } catch {
      setMessages([{ role: 'system', text: tr('aiFailed') }])
      return false
    } finally { setBusy(false) }
  }

  const playAudio = async (text) => {
    if (!text) return
    lastSpokenRef.current = text
    const form = new FormData()
    form.append('text', text); form.append('language', language); form.append('elderly_mode', elderlyMode ? 'true' : 'false')
    const res = await customerFetch('/customer/speak', { method: 'POST', body: form })
    if (res.ok) {
      const blob = await res.blob(); const url = URL.createObjectURL(blob)
      if (audioRef.current) { audioRef.current.src = url; audioRef.current.play().catch(() => {}) }
    }
  }

  const processText = async (text) => {
    setMessages((m) => [...m, { role: 'customer', text }]); setStatusKey('thinking')
    try {
      const res = await customerFetch('/customer/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, text, language, complexity: level, elderly_mode: elderlyMode })
      })
      if (!res.ok) throw new Error('chat')
      const data = await res.json()
      if (data.complexity_used) setLevel(data.complexity_used)
      const noteKey = { simpler: 'noteSimpler', reexplain: 'noteReexplain', more_detail: 'noteMore' }[data.level_change]
      setMessages((m) => [...m, { role: 'assistant', text: data.reply_local, visualData: data.visual_data, uiAction: data.ui_action, note: noteKey ? tr(noteKey) : null }])
      setStatusKey('speaking'); await playAudio(data.spoken_response); setStatusKey('')
    } catch { setStatusKey(''); setMessages((m) => [...m, { role: 'system', text: tr('aiFailed') }]) }
  }

  const handleRecording = async (blob) => {
    setBusy(true); setStatusKey('transcribing')
    try {
      const form = new FormData(); form.append('audio', blob, 'speech.webm'); form.append('language', language)
      const res = await customerFetch('/customer/transcribe', { method: 'POST', body: form })
      if (!res.ok) throw new Error('stt')
      const data = await res.json(); await processText(data.text)
    } catch { setStatusKey(''); setMessages((m) => [...m, { role: 'system', text: tr('recordingFailed') }]) }
    finally { setBusy(false) }
  }

  const endSession = () => { clearCustomerSession(); setEnded(true); setSessionId(null); setStatusKey(''); setShowEligibility(false) }
  const reset = () => { clearCustomerSession(); setLanguage(null); setSessionId(null); setMessages([]); setEnded(false); setStatusKey(''); setShowEligibility(false); setLevel('simple') }
  const hasAnswer = messages.some((m) => m.role === 'assistant')

  if (!language) return <LanguageGate onBack={onBack} onChoose={setLanguage} />
  if (ended) return (
    <CustomerShell language={language} onBack={onBack} onChangeLanguage={reset}>
      <div className="max-w-2xl mx-auto premium-card p-9 sm:p-12 text-center">
        <div className="h-20 w-20 mx-auto rounded-full bg-secondary-100 flex items-center justify-center mb-5"><Check className="h-10 w-10 text-secondary-600" /></div>
        <h1 className="text-3xl font-display font-bold text-primary-900">{tr('sessionEnded')}</h1>
        <p className="mt-3 text-lg text-charcoal/65">{tr('thankYou')}</p>
        <button onClick={() => { setEnded(false); setMessages([]) }} className="mt-8 w-full py-4 rounded-2xl bg-primary-500 text-white font-semibold text-lg">{tr('newSession')}</button>
      </div>
    </CustomerShell>
  )

  return (
    <CustomerShell language={language} onBack={onBack} onChangeLanguage={reset} bell={<NewSchemesBell language={language} total={newSchemes.length} unseen={unseenCount} onClick={openNotice} />}>
      {noticeOpen && (
        <NewSchemesNotice language={language} schemes={newSchemes} big={elderlyMode} onCheck={openChecker} onHide={hideNotice} onSpeak={sessionId ? playAudio : undefined} />
      )}
      {!sessionId ? (
        <div className="max-w-3xl mx-auto text-center">
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-secondary-50 border border-secondary-400/40 text-secondary-600 font-semibold"><Sparkles className="h-4 w-4" />{tr('customerSubtitle')}</span>
          <h1 className="mt-5 text-4xl sm:text-5xl font-display font-semibold text-primary-900">{tr('welcome')}</h1>
          <p className="mt-4 text-xl text-charcoal/65">{tr('welcomeText')}</p>
          <div className="premium-card p-7 sm:p-9 mt-9 text-left">
            <div className="flex items-center justify-between gap-4 mb-6">
              <div><p className="font-semibold text-lg text-charcoal">{tr('elderlyMode')}</p><p className="text-sm text-charcoal/55">{tr('privacy')}</p></div>
              <button onClick={() => setElderlyMode(v => !v)} className={`px-5 py-3 rounded-full font-bold ${elderlyMode ? 'bg-secondary-500 text-charcoal' : 'bg-primary-50 text-primary-700'}`}>{elderlyMode ? tr('on') : tr('off')}</button>
            </div>
            <button disabled={busy} onClick={startSession} className="w-full py-5 rounded-2xl bg-primary-500 text-white font-display font-semibold text-xl flex items-center justify-center gap-2 disabled:opacity-50">{tr('startSession')}<ArrowRight className="h-6 w-6" /></button>
          </div>
        </div>
      ) : showEligibility ? (
        <>
          <LoanEligibility
            language={language}
            sessionId={sessionId}
            big={elderlyMode}
            onSpeak={playAudio}
            onClose={() => setShowEligibility(false)}
            onTalkToStaff={() => { setShowEligibility(false); processText(tr('requestHelp')) }}
          />
          <audio ref={audioRef} className="hidden" />
        </>
      ) : (
        <div className="max-w-5xl mx-auto grid lg:grid-cols-[1.1fr_.9fr] gap-6 items-start">
          <div className="premium-card p-6 sm:p-8 flex flex-col items-center text-center">
            <div className="w-full flex items-center justify-between gap-3 mb-3"><span className="text-sm font-bold text-primary-700 uppercase tracking-wide">{tr('customerPortal')}</span><button onClick={() => setElderlyMode(v=>!v)} className={`px-3 py-2 rounded-full text-sm font-semibold ${elderlyMode ? 'bg-secondary-500' : 'bg-primary-50'}`}>{tr('elderlyMode')} · {elderlyMode ? tr('on') : tr('off')}</button></div>
            <MicButton onRecordingComplete={handleRecording} disabled={busy} big={elderlyMode} labels={{ hold: tr('holdToSpeak'), listening: tr('listening'), microphoneBlocked: tr('microphoneBlocked') }} />
            {statusKey && <p className="mt-4 flex items-center gap-2 text-primary-700 font-semibold"><Loader2 className="h-5 w-5 animate-spin" />{tr(statusKey)}</p>}
            {lastSpokenRef.current && <button onClick={() => playAudio(lastSpokenRef.current)} className="mt-5 inline-flex items-center gap-2 px-5 py-3 rounded-full bg-secondary-100 text-charcoal font-semibold"><Volume2 className="h-5 w-5" />{tr('listenAgain')}</button>}
            {elderlyMode && <div className="grid grid-cols-2 gap-3 w-full mt-6"><button disabled={busy} onClick={() => processText(tr('yes'))} className="py-4 rounded-2xl bg-primary-500 text-white text-xl font-bold flex items-center justify-center gap-2"><Check />{tr('yes')}</button><button disabled={busy} onClick={() => processText(tr('no'))} className="py-4 rounded-2xl bg-offwhite border border-primary-100 text-charcoal text-xl font-bold flex items-center justify-center gap-2"><X />{tr('no')}</button></div>}
            {hasAnswer && (
              <div className="grid grid-cols-2 gap-3 w-full mt-3">
                <button disabled={busy} onClick={() => processText(tr('btnNotUnderstood'))} className={`rounded-2xl border-2 border-primary-400 bg-white text-primary-700 font-bold flex items-center justify-center gap-2 disabled:opacity-50 ${elderlyMode ? 'py-4 text-lg' : 'py-3'}`}><HelpCircle className="h-5 w-5 shrink-0" />{tr('btnNotUnderstood')}</button>
                <button disabled={busy} onClick={() => processText(tr('btnTellMore'))} className={`rounded-2xl border-2 border-secondary-500 bg-white text-secondary-600 font-bold flex items-center justify-center gap-2 disabled:opacity-50 ${elderlyMode ? 'py-4 text-lg' : 'py-3'}`}><PlusCircle className="h-5 w-5 shrink-0" />{tr('btnTellMore')}</button>
              </div>
            )}
            {(() => { const last=[...messages].reverse().find(m=>m.role==='assistant'); return last?.visualData ? <div className="mt-6 w-full"><VisualDataCard data={last.visualData} big={elderlyMode} labels={{ secureScreen: tr('secureScreen'), dataLabel: tr('secureValue'), hideDescription: language !== 'en' }} /></div> : null })()}
            <audio ref={audioRef} className="hidden" />
          </div>

          <div className="space-y-6">
            <div className="premium-card p-6 sm:p-7">
              <h2 className="font-display font-bold text-xl text-charcoal mb-4">{tr('yourConversation')}</h2>
              <div className="space-y-3 max-h-[28rem] overflow-y-auto pr-1">
                {messages.length===0 && <p className="text-charcoal/45">{tr('noConversation')}</p>}
                {messages.map((m,i)=><CustomerBubble key={i} m={m} tr={tr} onOpenEligibility={() => setShowEligibility(true)} />)}
              </div>
            </div>
            <div className="premium-card p-6">
              <div className="flex items-start gap-3"><Landmark className="h-6 w-6 text-primary-600 shrink-0" /><div><h3 className="font-bold text-charcoal">{tr('eligCardTitle')}</h3><p className="text-sm text-charcoal/60 mt-1">{tr('eligCardDesc')}</p></div></div>
              <button onClick={() => setShowEligibility(true)} disabled={busy} className="mt-4 w-full py-3 rounded-xl bg-primary-500 text-white font-semibold">{tr('eligStart')}</button>
            </div>
            <div className="premium-card p-6 border-secondary-100">
              <div className="flex items-start gap-3"><UserRound className="h-6 w-6 text-secondary-600 shrink-0" /><div><h3 className="font-bold text-charcoal">{tr('helpStaff')}</h3><p className="text-sm text-charcoal/60 mt-1">{tr('helpStaffDesc')}</p></div></div>
              <button onClick={() => processText(tr('requestHelp'))} disabled={busy} className="mt-4 w-full py-3 rounded-xl bg-secondary-100 text-charcoal font-semibold">{tr('requestHelp')}</button>
            </div>
            <button onClick={endSession} className="w-full py-4 rounded-2xl border-2 border-warn-400 text-warn-600 font-bold">{tr('endSession')}</button>
          </div>
        </div>
      )}
    </CustomerShell>
  )
}

function LanguageGate({ onBack, onChoose }) {
  const [selected, setSelected] = useState('mr')
  return <div className="min-h-screen"><div className="max-w-5xl mx-auto px-5 py-8"><button onClick={onBack} className="inline-flex items-center gap-2 text-charcoal/60 font-semibold"><ArrowLeft className="h-4 w-4" />Back</button><div className="max-w-3xl mx-auto mt-14 premium-card p-8 sm:p-10"><div className="text-center mb-8"><h1 className="text-3xl sm:text-4xl font-display font-bold text-primary-900">Choose your preferred language</h1><p className="mt-2 text-charcoal/55">भाषा निवडा · भाषा चुनें · ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ · భాషను ఎంచుకోండి</p></div><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{LANGUAGES.map(l=><button key={l.code} onClick={()=>setSelected(l.code)} className={`p-5 rounded-2xl border-2 text-left ${selected===l.code?'border-primary-500 bg-primary-50':'border-primary-100 bg-white'}`}><span className="text-xl font-bold text-charcoal">{l.label}</span><span className="block text-sm text-charcoal/45 mt-1">{l.english}</span></button>)}</div><button onClick={()=>onChoose(selected)} className="mt-7 w-full py-4 rounded-2xl bg-primary-500 text-white font-bold text-lg flex items-center justify-center gap-2">{t(selected,'continue')}<ArrowRight className="h-5 w-5" /></button></div></div></div>
}

function CustomerShell({ language, onBack, onChangeLanguage, bell, children }) {
  return <div className="min-h-screen"><header className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-primary-100"><div className="max-w-7xl mx-auto px-5 py-3.5 flex items-center justify-between gap-3"><div className="flex items-center gap-3"><div className="h-10 w-10 rounded-full bg-primary-500 flex items-center justify-center"><Headphones className="h-5 w-5 text-white" /></div><div><p className="font-display font-bold text-primary-900">{t(language,'appName')}</p><p className="text-xs text-charcoal/45">{t(language,'customerPortal')}</p></div></div><div className="flex items-center gap-2">{bell}<button onClick={onChangeLanguage} className="px-3 py-2 rounded-full bg-primary-50 text-primary-700 text-sm font-semibold">{t(language,'changeLanguage')}</button><button onClick={onBack} className="p-2 rounded-full hover:bg-primary-50" aria-label={t(language,'back')}><ArrowLeft className="h-5 w-5" /></button></div></div></header><main className="max-w-7xl mx-auto px-5 sm:px-7 py-8">{children}</main><footer className="max-w-7xl mx-auto px-6 pb-8 text-center text-sm text-charcoal/45 flex items-center justify-center gap-2"><ShieldCheck className="h-4 w-4" />{t(language,'privacy')}</footer></div>
}

function CustomerBubble({ m, tr, onOpenEligibility }) {
  if (m.role==='system') return <div className="rounded-2xl bg-warn-100/60 px-4 py-3 text-warn-600">{m.text}</div>
  const mine=m.role==='customer'
  return <div className={`flex ${mine?'justify-end':'justify-start'}`}><div className={`max-w-[88%] rounded-2xl px-4 py-3 ${mine?'bg-primary-500 text-white':'bg-primary-50 text-charcoal border border-primary-100'}`}><p className="text-xs font-bold opacity-70 mb-1">{mine?tr('you'):tr('assistant')}</p>{m.note && <p className="text-sm font-semibold text-primary-700 mb-1">{m.note}</p>}<p>{m.text}</p>{m.uiAction==='open_eligibility' && <button onClick={onOpenEligibility} className="mt-3 w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary-500 text-white font-semibold"><Landmark className="h-4 w-4" />{tr('eligOffer')}</button>}</div></div>
}
