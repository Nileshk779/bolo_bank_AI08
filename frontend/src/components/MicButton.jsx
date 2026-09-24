import { useRef, useState } from 'react'

/**
 * Big, hold-to-speak microphone button — the app's signature element.
 * Concentric ripple rings expand outward while recording, like a voice
 * reaching out and being heard. Designed for elderly users: huge hit
 * target, no small icons, clear state via color + motion + text.
 */
export default function MicButton({ onRecordingComplete, disabled }) {
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState('')
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  const startRecording = async () => {
    if (disabled) return
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach((t) => t.stop())
        onRecordingComplete(blob)
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setRecording(true)
    } catch (err) {
      setError('Microphone access was blocked. Please allow microphone permission.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
    }
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative flex items-center justify-center h-48 w-48">
        {recording && (
          <>
            <span className="absolute inline-flex h-full w-full rounded-full bg-gold-500 animate-ripple1" />
            <span className="absolute inline-flex h-full w-full rounded-full bg-gold-500 animate-ripple2" />
            <span className="absolute inline-flex h-full w-full rounded-full bg-gold-500 animate-ripple3" />
          </>
        )}
        <button
          type="button"
          disabled={disabled}
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onMouseLeave={() => recording && stopRecording()}
          onTouchStart={(e) => { e.preventDefault(); startRecording() }}
          onTouchEnd={(e) => { e.preventDefault(); stopRecording() }}
          aria-pressed={recording}
          aria-label="Hold to speak"
          className={`relative h-40 w-40 rounded-full flex items-center justify-center shadow-xl
            transition-transform active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed
            ${recording ? 'bg-gold-500' : 'bg-teal-900 hover:bg-teal-800'}
            ${!recording && !disabled ? 'animate-pulseSoft' : ''}`}
        >
          <MicIcon className="h-16 w-16 text-white" />
        </button>
      </div>

      <p className="text-lg font-semibold text-teal-900 font-display">
        {recording ? 'Listening… release to send' : 'Hold to speak'}
      </p>
      {error && <p className="text-coral font-medium text-base max-w-xs text-center">{error}</p>}
    </div>
  )
}

function MicIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Z"
        fill="currentColor"
      />
      <path
        d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.93V20H9a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.07A7 7 0 0 0 19 11Z"
        fill="currentColor"
      />
    </svg>
  )
}
