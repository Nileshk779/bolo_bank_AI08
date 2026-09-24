import { useRef, useState } from 'react'
import MicButton from './MicButton.jsx'
import { LANGUAGES } from './LanguageSelect.jsx'

const API_BASE = '/api'

export default function CustomerPanel({ sessionId, language, onEndSession }) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState('')
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
      const transcribeRes = await fetch(`${API_BASE}/transcribe`, { method: 'POST', body: form })
      if (!transcribeRes.ok) throw new Error('transcribe-failed')
      const { text } = await transcribeRes.json()

      setMessages((m) => [...m, { role: 'customer', text }])
      setStatusText('Thinking…')

      // 2. Ask the assistant
      const chatRes = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, text, language }),
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
      const speakRes = await fetch(`${API_BASE}/speak`, { method: 'POST', body: speakForm })
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
      <div className="bg-white rounded-3xl shadow-sm border border-teal-100 p-8 flex flex-col items-center">
        <p className="text-sm uppercase tracking-wide text-teal-900/60 font-semibold mb-1">
          Customer panel
        </p>
        <p className="text-lg font-display font-semibold text-teal-900 mb-6">
          Language: {langLabel}
        </p>
        <MicButton onRecordingComplete={handleRecording} disabled={busy} />
        {statusText && (
          <p className="mt-4 text-base text-gold-600 font-medium">{statusText}</p>
        )}
        <audio ref={audioRef} className="hidden" />
      </div>

      {/* Staff side — bilingual transcript */}
      <div className="bg-white rounded-3xl shadow-sm border border-teal-100 p-8 flex flex-col">
        <p className="text-sm uppercase tracking-wide text-teal-900/60 font-semibold mb-4">
          Staff panel — live transcript
        </p>
        <div className="flex-1 space-y-4 overflow-y-auto max-h-96 pr-1">
          {messages.length === 0 && (
            <p className="text-teal-900/50 text-base">
              The conversation will appear here as the customer speaks.
            </p>
          )}
          {messages.map((m, i) => (
            <Bubble key={i} message={m} />
          ))}
        </div>
        <button
          onClick={() => onEndSession(messages)}
          className="mt-6 w-full py-4 rounded-2xl bg-coral text-white font-display font-semibold text-lg hover:opacity-90 transition-opacity"
        >
          End session &amp; generate summary
        </button>
      </div>
    </div>
  )
}

function Bubble({ message }) {
  if (message.role === 'system') {
    return (
      <div className="bg-coral/10 text-coral rounded-xl px-4 py-3 text-base">
        {message.text}
      </div>
    )
  }
  const isCustomer = message.role === 'customer'
  return (
    <div className={`rounded-2xl px-5 py-3 max-w-[90%] ${isCustomer ? 'bg-teal-50 ml-0' : 'bg-gold-100 ml-auto'}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-900/60 mb-1">
        {isCustomer ? 'Customer' : 'BoloBank (translated for staff)'}
      </p>
      <p className="text-base text-charcoal">{message.text}</p>
      {message.textEnglish && (
        <p className="text-sm text-charcoal/60 mt-1 italic">{message.textEnglish}</p>
      )}
    </div>
  )
}
