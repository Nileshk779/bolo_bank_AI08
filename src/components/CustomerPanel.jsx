import { useRef, useState } from 'react'
import { Loader2, LogOut, MessageCircleWarning, User, Bot } from 'lucide-react'
import MicButton from './MicButton.jsx'
import ComplexitySelect from './ComplexitySelect.jsx'
import { LANGUAGES } from './LanguageSelect.jsx'
import { apiFetch } from '../api.js'

export default function CustomerPanel({ sessionId, language, onEndSession }) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [complexity, setComplexity] = useState('simple')
  const audioRef = useRef(null)

  const langLabel = LANGUAGES.find((l) => l.code === language)?.label ?? language

  const handleRecording = async (blob) => {
    setBusy(true)
    setStatusText('Transcribing…')
    try {
      // 1. Speech to text
      const form = new FormData()
      form.append('audio', blob, 'speech.webm')
      form.append('language', language)
      const transcribeRes = await apiFetch('/transcribe', { method: 'POST', body: form })
      if (!transcribeRes.ok) throw new Error('transcribe-failed')
      const { text } = await transcribeRes.json()

      setMessages((m) => [...m, { role: 'customer', text }])
      setStatusText('Thinking…')

      // 2. Ask the assistant
      const chatRes = await apiFetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, text, language, complexity }),
      })
      if (!chatRes.ok) throw new Error('chat-failed')
      const { reply_local, reply_english } = await chatRes.json()

      setMessages((m) => [
        ...m,
        { role: 'assistant', text: reply_local, textEnglish: reply_english },
      ])
      setStatusText('Speaking reply…')

      // 3. Text to speech
      const speakForm = new FormData()
      speakForm.append('text', reply_local)
      speakForm.append('language', language)
      const speakRes = await apiFetch('/speak', { method: 'POST', body: speakForm })
      if (speakRes.ok) {
        const audioBlob = await speakRes.blob()
        const url = URL.createObjectURL(audioBlob)
        if (audioRef.current) {
          audioRef.current.src = url
          audioRef.current.play().catch(() => {})
        }
      }
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
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Customer side */}
      <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-8 flex flex-col items-center">
        <p className="text-sm uppercase tracking-wide text-charcoal/50 font-semibold mb-1">
          Customer panel
        </p>
        <p className="text-lg font-display font-semibold text-charcoal mb-6">
          Language: {langLabel}
        </p>
        <MicButton onRecordingComplete={handleRecording} disabled={busy} />
        {statusText && (
          <p className="mt-4 flex items-center gap-2 text-base text-primary-600 font-medium">
            <Loader2 className="h-4 w-4 animate-spin" />
            {statusText}
          </p>
        )}
        <div className="mt-8 w-full flex justify-center">
          <ComplexitySelect value={complexity} onChange={setComplexity} />
        </div>
        <audio ref={audioRef} className="hidden" />
      </div>

      {/* Staff side — bilingual transcript */}
      <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-8 flex flex-col">
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
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal/50 mb-1">
          {isCustomer ? 'Customer' : 'BoloBank'}
        </p>
        <p className="text-base text-charcoal">{message.text}</p>
        {message.textEnglish && (
          <p className="text-sm text-charcoal/60 mt-1 italic">{message.textEnglish}</p>
        )}
      </div>
    </div>
  )
}
