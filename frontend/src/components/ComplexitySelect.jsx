import { Gauge } from 'lucide-react'

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
