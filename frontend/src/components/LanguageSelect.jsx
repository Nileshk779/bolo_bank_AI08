import { Check, Languages } from 'lucide-react'

const LANGUAGES = [
  { code: 'hi', label: 'हिंदी', english: 'Hindi' },
  { code: 'mr', label: 'मराठी', english: 'Marathi' },
  { code: 'te', label: 'తెలుగు', english: 'Telugu' },
  { code: 'kn', label: 'ಕನ್ನಡ', english: 'Kannada' },
  { code: 'en', label: 'English', english: 'English' },
]

export default function LanguageSelect({ value, onChange }) {
  return (
    <div>
      <p className="flex items-center gap-2 text-lg font-semibold text-charcoal mb-3">
        <Languages className="h-5 w-5 text-primary-500" />
        Select customer language
      </p>
      <div className="flex flex-wrap gap-3">
        {LANGUAGES.map((lang) => {
          const active = value === lang.code
          return (
            <button
              key={lang.code}
              onClick={() => onChange(lang.code)}
              aria-pressed={active}
              className={`relative px-6 py-4 rounded-2xl text-lg font-semibold font-display border-2 transition-colors
                ${active
                  ? 'bg-primary-500 border-primary-500 text-white'
                  : 'bg-white border-primary-100 text-charcoal hover:border-primary-400'}`}
            >
              {active && (
                <span className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-secondary-500 flex items-center justify-center shadow-soft">
                  <Check className="h-3 w-3 text-charcoal" strokeWidth={3} />
                </span>
              )}
              {lang.label}
              <span className={`block text-sm font-body font-normal ${active ? 'text-white/80' : 'text-charcoal/50'}`}>
                {lang.english}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export { LANGUAGES }
