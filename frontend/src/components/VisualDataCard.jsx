import { ShieldCheck } from 'lucide-react'

/**
 * Renders a response's `visual_data` — the structured, screen-only payload
 * the backend sends for sensitive account info (balance, account number,
 * a transaction, a masked card number). This is the ONLY place these
 * values ever appear in the UI; the spoken/TTS text never contains them
 * (see backend/services/response_privacy_service.py).
 */
export default function VisualDataCard({ data, big = false, labels = {} }) {
  if (!data) return null

  return (
    <div
      className={`rounded-2xl border-2 border-primary-200 bg-primary-50/60 shadow-card
        ${big ? 'p-8' : 'p-5'} flex flex-col items-center text-center gap-2 animate-fadeUp`}
    >
      <p className={`flex items-center gap-1.5 font-semibold text-primary-700 uppercase tracking-wide
        ${big ? 'text-base' : 'text-xs'}`}
      >
        <ShieldCheck className={big ? 'h-5 w-5' : 'h-3.5 w-3.5'} />
        {labels.secureScreen || 'Shown on screen only — not spoken aloud'}
      </p>
      <p className={`font-semibold text-charcoal/70 ${big ? 'text-xl' : 'text-sm'}`}>{labels.dataLabel || data.label}</p>
      <ValueDisplay data={data} big={big} />
    </div>
  )
}

function ValueDisplay({ data, big }) {
  const valueClass = `font-display font-bold text-charcoal ${big ? 'text-5xl' : 'text-3xl'}`

  if (data.type === 'transaction' && data.value && typeof data.value === 'object') {
    const { description, amount, currency, date } = data.value
    return (
      <div className="flex flex-col items-center gap-1">
        <p className={valueClass}>
          {currency === 'INR' ? '₹' : currency + ' '}
          {amount}
        </p>
        {!labels.hideDescription && <p className={big ? 'text-lg text-charcoal/70' : 'text-sm text-charcoal/70'}>{description}</p>}
        <p className={big ? 'text-base text-charcoal/50' : 'text-xs text-charcoal/50'}>{date}</p>
      </div>
    )
  }

  if (data.type === 'balance') {
    return (
      <p className={valueClass}>
        {data.currency === 'INR' ? '₹' : (data.currency || '') + ' '}
        {Number(data.value).toLocaleString('en-IN')}
      </p>
    )
  }

  return <p className={valueClass}>{String(data.value)}</p>
}
