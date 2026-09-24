import { useRef, useState } from 'react'
import { Mic, MicOff } from 'lucide-react'

/**
 * Big, hold-to-speak microphone button — the app's signature element.
 * Concentric ripple rings expand outward while recording. Designed for
 * elderly users: huge hit target, no small icons, clear state via color +
 * motion + text (never color alone).
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
            <span className="absolute inline-flex h-full w-full rounded-full bg-secondary-500 animate-ripple1" />
            <span className="absolute inline-flex h-full w-full rounded-full bg-secondary-500 animate-ripple2" />
            <span className="absolute inline-flex h-full w-full rounded-full bg-secondary-500 animate-ripple3" />
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
          className={`relative h-40 w-40 rounded-full flex items-center justify-center shadow-card
            transition-transform active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed
            ${recording ? 'bg-secondary-600' : 'bg-primary-500 hover:bg-primary-600'}
            ${!recording && !disabled ? 'animate-pulseSoft' : ''}`}
        >
          {disabled && error === '' ? (
            <MicOff className="h-16 w-16 text-white/70" strokeWidth={1.75} />
          ) : (
            <Mic className="h-16 w-16 text-white" strokeWidth={1.75} />
          )}
        </button>
      </div>

      <p className="text-lg font-semibold text-charcoal font-display">
        {recording ? 'Listening… release to send' : 'Hold to speak'}
      </p>
      {error && <p className="text-warn-600 font-medium text-base max-w-xs text-center">{error}</p>}
    </div>
  )
}
