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
      <p className="text-lg font-semibold text-teal-900 mb-3">
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
              className={`px-6 py-4 rounded-2xl text-lg font-semibold font-display border-2 transition-all
                ${active
                  ? 'bg-teal-900 border-teal-900 text-white shadow-md scale-105'
                  : 'bg-white border-teal-100 text-teal-900 hover:border-teal-900'}`}
            >
              {lang.label}
              <span className="block text-sm font-body font-normal opacity-70">
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
