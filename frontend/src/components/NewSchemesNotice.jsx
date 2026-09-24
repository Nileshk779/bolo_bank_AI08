import { useEffect } from 'react'
import { Bell, Landmark, Volume2, X } from 'lucide-react'
import { t } from '../i18n.js'

const SEEN_KEY = 'bolobank_seen_new_schemes'

/** Scheme ids this browser has already dismissed. Wrapped in try/catch:
 * storage can be blocked (private window, kiosk settings) and the notice
 * must still work — it just reappears next time. */
export function getSeenSchemes() {
  try { return JSON.parse(localStorage.getItem(SEEN_KEY) || '[]') } catch { return [] }
}

export function markSchemesSeen(ids) {
  try { localStorage.setItem(SEEN_KEY, JSON.stringify([...new Set([...getSeenSchemes(), ...ids])])) } catch { /* ignore */ }
}

/**
 * "New schemes at the bank" pop-up for the Customer Portal, opened only from
 * the header button so the voice assistant stays the main screen. Lists
 * schemes staff approved recently (GET /api/customer/new-schemes) in the
 * customer's language; each has "Can I get this?" (opens the eligibility
 * checker) and, once a session exists, "Listen". Closes with the Close
 * button, Escape, or a tap outside.
 */
export default function NewSchemesNotice({ language, schemes, big, onCheck, onSpeak, onHide }) {
  const tr = (key) => t(language, key)
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onHide() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onHide])
  if (!schemes.length) return null
  return (
    <div className="fixed inset-0 z-40 bg-charcoal/40 flex items-end sm:items-center justify-center p-3 sm:p-6" onClick={onHide}>
    <section role="dialog" aria-modal="true" aria-label={tr('newSchemesTitle')} onClick={(e) => e.stopPropagation()}
      className="bg-white rounded-3xl shadow-card border-2 border-warn-400/70 w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="relative h-11 w-11 rounded-full bg-warn-100 flex items-center justify-center shrink-0">
            <Bell className="h-5 w-5 text-warn-600" />
            <span className="absolute -top-1 -right-1 h-5 min-w-5 px-1 rounded-full bg-warn-500 text-white text-xs font-bold flex items-center justify-center">{schemes.length}</span>
          </span>
          <div>
            <h2 className={`font-display font-bold text-primary-900 ${big ? 'text-2xl' : 'text-xl'}`}>{tr('newSchemesTitle')}</h2>
            <p className="text-charcoal/65">{tr('newSchemesIntro')}</p>
          </div>
        </div>
        <button onClick={onHide} className="shrink-0 inline-flex items-center gap-1 px-3 py-2 rounded-full bg-primary-50 text-primary-700 text-sm font-semibold"><X className="h-4 w-4" />{tr('hideNotice')}</button>
      </div>

      <ul className="mt-4 space-y-3">
        {schemes.map((s) => (
          <li key={s.scheme_id} className="rounded-2xl bg-white border border-primary-100 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-warn-500 text-white">{tr('newScheme')}</span>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${s.kind === 'government_scheme' ? 'bg-secondary-100 text-secondary-600' : 'bg-primary-50 text-primary-700'}`}>{s.kind === 'government_scheme' ? tr('govtScheme') : tr('bankProduct')}</span>
              {s.collateral_free && <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-secondary-50 text-secondary-600 border border-secondary-400/50">{tr('noCollateralTag')}</span>}
              <span className="text-xs text-charcoal/50">{tr('addedOn')} {s.added_on}{s.valid_until ? ` · ${tr('validTill')} ${s.valid_until}` : ''}</span>
            </div>
            <h3 className={`mt-1.5 font-bold text-charcoal ${big ? 'text-xl' : 'text-lg'}`}>{s.name}</h3>
            <p className={`text-charcoal/70 ${big ? 'text-lg' : ''}`}>{s.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button onClick={onCheck} className={`inline-flex items-center gap-2 rounded-xl bg-primary-500 text-white font-semibold ${big ? 'px-5 py-3 text-lg' : 'px-4 py-2'}`}><Landmark className="h-4 w-4" />{tr('canIGetThis')}</button>
              {onSpeak && <button onClick={() => onSpeak(`${s.name}. ${s.summary}`)} className={`inline-flex items-center gap-2 rounded-xl bg-secondary-100 text-charcoal font-semibold ${big ? 'px-5 py-3 text-lg' : 'px-4 py-2'}`}><Volume2 className="h-4 w-4" />{tr('listenScheme')}</button>}
            </div>
          </li>
        ))}
      </ul>
    </section>
    </div>
  )
}

/** Header button that opens the new-schemes pop-up. The badge counts
 * schemes this customer hasn't opened yet; it disappears once they look. */
export function NewSchemesBell({ language, total, unseen, onClick }) {
  if (!total) return null
  const label = t(language, 'showNewSchemes')
  return (
    <button onClick={onClick} className="relative inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-warn-100 text-warn-600 text-sm font-semibold" aria-label={unseen ? `${label} (${unseen})` : label}>
      <Bell className="h-4 w-4" /><span className="hidden sm:inline">{label}</span>
      {unseen > 0 && <span className="h-5 min-w-5 px-1 rounded-full bg-warn-500 text-white text-xs font-bold flex items-center justify-center">{unseen}</span>}
    </button>
  )
}
