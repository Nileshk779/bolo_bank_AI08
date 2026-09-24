import { Gauge, Wand2 } from 'lucide-react'

const LEVEL_NAMES = { simple: 'Simple', normal: 'Normal', detailed: 'Detailed' }
const CHANGE_TEXT = {
  simpler: (level) => `Customer didn't understand — switched to ${LEVEL_NAMES[level]}`,
  reexplain: () => 'Customer still didn\'t understand — re-explaining in different words with an example',
  more_detail: (level) => `Customer asked for more — switched to ${LEVEL_NAMES[level]}`,
}

/** Shown when the backend changed the explanation level automatically
 * (backend/services/clarification_service.py). Staff can still override
 * it with the selector. */
export function LevelChangeNote({ change, level, question, className = '' }) {
  if (!change) return null
  return (
    <p className={`flex items-start gap-1.5 text-xs font-semibold text-primary-700 bg-primary-50 border border-primary-100 rounded-lg px-2.5 py-1.5 ${className}`}>
      <Wand2 className="h-3.5 w-3.5 mt-0.5 shrink-0" />
      <span>{CHANGE_TEXT[change]?.(level)}{question ? ` · answering again: “${question}”` : ''}</span>
    </p>
  )
}

const LEVELS = [
  { id: 'simple', label: 'Simple', hint: "Explain Like I'm 60" },
  { id: 'normal', label: 'Normal', hint: 'Everyday banking terms' },
  { id: 'detailed', label: 'Detailed', hint: 'Full precision' },
]

export default function ComplexitySelect({ value, onChange }) {
  return (
    <div>
      <p className="flex items-center gap-2 text-sm font-semibold text-charcoal/70 mb-2">
        <Gauge className="h-4 w-4 text-primary-500" />
        Explanation level
      </p>
      <div className="inline-flex bg-primary-50 rounded-full p-1 gap-1">
        {LEVELS.map((lvl) => {
          const active = value === lvl.id
          return (
            <button
              key={lvl.id}
              type="button"
              onClick={() => onChange(lvl.id)}
              title={lvl.hint}
              className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors
                ${active ? 'bg-primary-500 text-white' : 'text-primary-700 hover:bg-primary-100'}`}
            >
              {lvl.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
