import { useRef, useState } from 'react'
import { Loader2, LogOut, MessageCircleWarning, User, Bot, Sparkles, Volume2, Check, X, ShieldAlert } from 'lucide-react'
import MicButton from './MicButton.jsx'
import ComplexitySelect from './ComplexitySelect.jsx'
import VisualDataCard from './VisualDataCard.jsx'
import { LANGUAGES } from './LanguageSelect.jsx'
import { apiFetch } from '../api.js'

export default function CustomerPanel({ sessionId, language, onEndSession }) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [complexity, setComplexity] = useState('simple')
  // Elderly Voice Mode: voice-first, large controls, minimal text, forced
  // simple language, and a slower/clearer speaking pace — designed so a
  // customer can complete a common interaction without reading much at all.
  const [elderlyMode, setElderlyMode] = useState(false)
  const audioRef = useRef(null)
  const lastSpokenRef = useRef('')

  const langLabel = LANGUAGES.find((l) => l.code === language)?.label ?? language
  const effectiveComplexity = elderlyMode ? 'simple' : complexity

  const playAudio = async (spokenText) => {
    lastSpokenRef.current = spokenText
    const speakForm = new FormData()
    speakForm.append('text', spokenText)
    speakForm.append('language', language)
    speakForm.append('elderly_mode', elderlyMode ? 'true' : 'false')
    // Note: /api/speak re-checks this text for sensitive content itself,
    // unconditionally, regardless of what's sent — see backend/api/voice.py.
    // We already send the privacy-safe `spoken_response` here, never the
    // raw reply text, as the normal (non-bypassable) path.
    const speakRes = await apiFetch('/speak', { method: 'POST', body: speakForm })
    if (speakRes.ok) {
      const audioBlob = await speakRes.blob()
      const url = URL.createObjectURL(audioBlob)
      if (audioRef.current) {
        audioRef.current.src = url
        audioRef.current.play().catch(() => {})
      }
    }
  }

  const processCustomerText = async (text) => {
    setMessages((m) => [...m, { role: 'customer', text }])
    setStatusText('Thinking…')
    try {
      const chatRes = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          text,
          language,
          complexity: effectiveComplexity,
          elderly_mode: elderlyMode,
        }),
      })
      if (!chatRes.ok) throw new Error('chat-failed')
      const { reply_local, reply_english, spoken_response, visual_data, sensitive } = await chatRes.json()

      setMessages((m) => [
        ...m,
        { role: 'assistant', text: reply_local, textEnglish: reply_english, visualData: visual_data, sensitive },
      ])
      setStatusText('Speaking reply…')

      // Always speak spoken_response, never reply_local directly — for a
      // sensitive answer these differ (spoken_response is the generic
      // "shown on screen" phrase; the real value lives only in visual_data
      // and is rendered by VisualDataCard, never passed to TTS).
      await playAudio(spoken_response)
      setStatusText('')
    } catch (err) {
      setStatusText('')
      setMessages((m) => [
        ...m,
        {
          role: 'system',
          text: 'Something went wrong reaching the AI service. Please check your API keys / connection and try again.',
        },
      ])
    }
  }

  const handleRecording = async (blob) => {
    setBusy(true)
    setStatusText('Transcribing…')
    try {
      const form = new FormData()
      form.append('audio', blob, 'speech.webm')
      form.append('language', language)
      const transcribeRes = await apiFetch('/transcribe', { method: 'POST', body: form })
      if (!transcribeRes.ok) throw new Error('transcribe-failed')
      const { text } = await transcribeRes.json()
      await processCustomerText(text)
    } catch (err) {
      setStatusText('')
      setMessages((m) => [
        ...m,
        { role: 'system', text: 'Could not understand the recording. Please try again.' },
      ])
    } finally {
      setBusy(false)
    }
  }

  const handleQuickReply = async (text) => {
    if (busy) return
    setBusy(true)
    await processCustomerText(text)
    setBusy(false)
  }

  const repeatLast = () => {
    if (lastSpokenRef.current) playAudio(lastSpokenRef.current)
  }

  const hasAssistantReply = messages.some((m) => m.role === 'assistant')

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Customer side */}
      <div className={`premium-card flex flex-col items-center
        ${elderlyMode ? 'p-6' : 'p-8'}`}>
        <div className="w-full flex items-center justify-between mb-1">
          <p className="text-sm uppercase tracking-wide text-charcoal/50 font-semibold">Customer panel</p>
          <button
            type="button"
            onClick={() => setElderlyMode((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full font-semibold text-xs border transition-colors
              ${elderlyMode
                ? 'bg-secondary-500 text-white border-secondary-500'
                : 'bg-white text-charcoal/60 border-primary-200 hover:border-secondary-300'}`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Elderly Voice Mode {elderlyMode ? 'On' : 'Off'}
          </button>
        </div>

        <p className={`font-display font-semibold text-charcoal ${elderlyMode ? 'text-2xl mb-6' : 'text-lg mb-6'}`}>
          {elderlyMode ? `🌐 ${langLabel}` : `Language: ${langLabel}`}
        </p>

        <MicButton onRecordingComplete={handleRecording} disabled={busy} big={elderlyMode} />

        {statusText && (
          <p className={`mt-4 flex items-center gap-2 text-primary-600 font-medium ${elderlyMode ? 'text-xl' : 'text-base'}`}>
            <Loader2 className={elderlyMode ? 'h-6 w-6 animate-spin' : 'h-4 w-4 animate-spin'} />
            {statusText}
          </p>
        )}

        {elderlyMode ? (
          <div className="mt-8 w-full flex flex-col items-center gap-4">
            {hasAssistantReply && (
              <button
                type="button"
                onClick={repeatLast}
                disabled={busy}
                className="w-full flex items-center justify-center gap-3 py-5 rounded-2xl bg-secondary-500 text-white
                  font-display font-bold text-2xl shadow-card hover:bg-secondary-600 transition-colors disabled:opacity-50"
              >
                <Volume2 className="h-8 w-8" strokeWidth={2.5} />
                LISTEN AGAIN
              </button>
            )}
            <div className="grid grid-cols-2 gap-4 w-full">
              <button
                type="button"
                onClick={() => handleQuickReply('Yes')}
                disabled={busy}
                className="flex items-center justify-center gap-2 py-5 rounded-2xl bg-primary-500 text-white
                  font-display font-bold text-2xl shadow-card hover:bg-primary-600 hover:-translate-y-0.5 transition-all disabled:opacity-50"
              >
                <Check className="h-8 w-8" strokeWidth={3} />
                YES
              </button>
              <button
                type="button"
                onClick={() => handleQuickReply('No')}
                disabled={busy}
                className="flex items-center justify-center gap-2 py-5 rounded-2xl bg-warn-500 text-white
                  font-display font-bold text-2xl shadow-card hover:bg-warn-600 transition-colors disabled:opacity-50"
              >
                <X className="h-8 w-8" strokeWidth={3} />
                NO
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-8 w-full flex justify-center">
            <ComplexitySelect value={complexity} onChange={setComplexity} />
          </div>
        )}

        {/* The customer's own screen shows the latest sensitive visual_data
            prominently — this is the "screen only" half of the privacy
            guarantee, right where the customer can see it. */}
        {(() => {
          const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
          return lastAssistant?.visualData ? (
            <div className="mt-6 w-full">
              <VisualDataCard data={lastAssistant.visualData} big={elderlyMode} />
            </div>
          ) : null
        })()}

        <audio ref={audioRef} className="hidden" />
      </div>

      {/* Staff side — bilingual transcript (always full detail, for staff use) */}
      <div className="premium-card p-8 flex flex-col">
        <p className="text-sm uppercase tracking-wide text-charcoal/50 font-semibold mb-4">
          Staff panel — live transcript
        </p>
        <div className="flex-1 space-y-4 overflow-y-auto max-h-96 pr-1">
          {messages.length === 0 && (
            <p className="text-charcoal/40 text-base">
              The conversation will appear here as the customer speaks.
            </p>
          )}
          {messages.map((m, i) => (
            <Bubble key={i} message={m} />
          ))}
        </div>
        <button
          onClick={() => onEndSession(messages)}
          className="mt-6 w-full py-4 rounded-2xl bg-warn-500 text-white font-display font-semibold text-lg
            hover:bg-warn-600 transition-colors flex items-center justify-center gap-2"
        >
          <LogOut className="h-5 w-5" strokeWidth={2.5} />
          End session &amp; generate summary
        </button>
      </div>
    </div>
  )
}

function Bubble({ message }) {
  if (message.role === 'system') {
    return (
      <div className="bg-warn-100 text-warn-600 rounded-xl px-4 py-3 text-base flex items-start gap-2 animate-fadeUp">
        <MessageCircleWarning className="h-5 w-5 shrink-0 mt-0.5" />
        {message.text}
      </div>
    )
  }
  const isCustomer = message.role === 'customer'
  return (
    <div className={`flex gap-2.5 items-start animate-fadeUp ${isCustomer ? '' : 'flex-row-reverse'}`}>
      <div className={`shrink-0 h-8 w-8 rounded-full flex items-center justify-center
        ${isCustomer ? 'bg-primary-100 text-primary-600' : 'bg-secondary-100 text-secondary-600'}`}>
        {isCustomer ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={`rounded-2xl px-5 py-3 max-w-[85%] ${isCustomer ? 'bg-primary-50' : 'bg-secondary-50'}`}>
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal/50 mb-1 flex items-center gap-1.5">
          {isCustomer ? 'Customer' : 'BoloBank'}
          {message.sensitive && (
            <span
              className="inline-flex items-center gap-1 text-warn-600 normal-case font-medium"
              title="Sensitive info — shown on screen only, never spoken aloud"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              on-screen only
            </span>
          )}
        </p>
        <p className="text-base text-charcoal">{message.text}</p>
        {message.textEnglish && (
          <p className="text-sm text-charcoal/60 mt-1 italic">{message.textEnglish}</p>
        )}
        {message.visualData && (
          <div className="mt-2">
            <VisualDataCard data={message.visualData} />
          </div>
        )}
      </div>
    </div>
  )
}
