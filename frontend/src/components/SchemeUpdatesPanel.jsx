import { useEffect, useState } from 'react'
import { AlertTriangle, BadgeCheck, Bot, CalendarClock, Check, ChevronDown, FileText, Loader2, MapPin, PhoneCall, RefreshCw, ShieldCheck, UserRound, Volume2, X } from 'lucide-react'
import { apiFetch } from '../api.js'

/**
 * Staff review queue for the daily scheme update job
 * (backend/services/scheme_update_service.py). New announcements are
 * extracted by AI into draft schemes; an employee checks each against the
 * original announcement, corrects it if needed, and approves or rejects it.
 * Only approved schemes reach the customer eligibility checker.
 */

const LABELS = {
  gold: 'Gold', land: 'Farm land', house: 'House / property', fd: 'Fixed deposit',
  farmer: 'Farmer', business: 'Business', salaried: 'Salaried', pensioner: 'Pensioner', student: 'Student', other: 'Other',
  farming: 'Farming', education: 'Education', home: 'Home', medical: 'Medical', personal: 'Personal',
  bank_product: 'Bank product', government_scheme: 'Government scheme',
}
const METHOD = {
  llm: { label: 'AI-extracted', cls: 'bg-primary-50 text-primary-700' },
  preset: { label: 'Demo preset (AI off)', cls: 'bg-charcoal/5 text-charcoal/60' },
  preset_after_llm_error: { label: 'Demo preset (AI failed)', cls: 'bg-warn-100 text-warn-600' },
}
const LANG_NAMES = { hi: 'Hindi', mr: 'Marathi', kn: 'Kannada', te: 'Telugu' }
const ALL_LANG_NAMES = { en: 'English', ...LANG_NAMES }
const label = (v) => LABELS[v] || v.replace(/_/g, ' ')
const when = (iso) => (iso ? new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—')

export default function SchemeUpdatesPanel() {
  const [status, setStatus] = useState(null)
  const [view, setView] = useState('pending')
  const [drafts, setDrafts] = useState([])
  const [catalogue, setCatalogue] = useState([])
  const [options, setOptions] = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [alertStatus, setAlertStatus] = useState('new')
  const [notice, setNotice] = useState('')

  const loadStatus = async () => { const r = await apiFetch('/schemes/updates/status'); if (r.ok) setStatus(await r.json()) }
  const loadView = async (v = view) => {
    setLoading(true)
    try {
      if (v === 'catalogue') { const r = await apiFetch('/schemes/catalogue'); if (r.ok) setCatalogue((await r.json()).schemes) }
      else if (v === 'alerts') { const r = await apiFetch(`/schemes/alerts?status=${alertStatus}`); if (r.ok) setAlerts(await r.json()) }
      else { const r = await apiFetch(`/schemes/updates?status=${v}`); if (r.ok) setDrafts(await r.json()) }
    } finally { setLoading(false) }
  }

  useEffect(() => {
    loadStatus()
    apiFetch('/schemes/options').then((r) => (r.ok ? r.json() : null)).then(setOptions)
  }, [])
  useEffect(() => { loadView(view) }, [view, alertStatus])

  const runNow = async () => {
    setRunning(true); setRunResult(null)
    try {
      const r = await apiFetch('/schemes/updates/run', { method: 'POST' })
      if (r.ok) setRunResult(await r.json())
      await loadStatus(); await loadView()
    } finally { setRunning(false) }
  }
  const afterReview = async (result) => {
    if (result?.status === 'approved') {
      const n = result.customers_matched || 0
      setNotice({
        text: `“${result.draft.name?.en}” is now live for customers. ` + (n ? `${n} existing customer${n > 1 ? 's' : ''} may benefit.` : 'No existing customers matched.'),
        hasMatches: n > 0,
      })
    }
    await loadStatus(); await loadView()
  }

  const counts = status?.counts || {}
  const tabs = [
    { id: 'pending', label: `Needs review (${counts.pending ?? 0})` },
    { id: 'alerts', label: `Customer matches (${counts.alerts_new ?? 0})` },
    { id: 'approved', label: `Approved (${counts.approved ?? 0})` },
    { id: 'rejected', label: `Rejected (${counts.rejected ?? 0})` },
    { id: 'catalogue', label: 'Live catalogue' },
  ]

  return (
    <div className="space-y-6">
      <div className="grid lg:grid-cols-5 gap-6 items-start">
        <div className="lg:col-span-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-secondary-600 bg-secondary-50 px-3 py-1.5 rounded-full mb-3"><ShieldCheck className="h-3.5 w-3.5" />Human approval required</span>
          <h1 className="text-3xl sm:text-4xl font-display font-semibold text-primary-900">Scheme updates</h1>
          <p className="mt-2 text-charcoal/65 text-lg">New loan schemes found by the daily check. AI reads each announcement and drafts a scheme; nothing reaches customers until you check it against the original and approve it.</p>
        </div>
        <div className="lg:col-span-2 premium-card p-5">
          <p className="flex items-center gap-2 font-bold text-charcoal"><CalendarClock className="h-5 w-5 text-primary-600" />Daily check</p>
          <dl className="mt-3 text-sm grid grid-cols-2 gap-y-1.5">
            <dt className="text-charcoal/55">Last checked</dt><dd className="font-semibold text-charcoal">{when(status?.last_run?.finished_at)}</dd>
            <dt className="text-charcoal/55">Triggered by</dt><dd className="font-semibold text-charcoal">{status?.last_run?.trigger ?? '—'}</dd>
            <dt className="text-charcoal/55">Schedule</dt><dd className="font-semibold text-charcoal">{status ? (status.auto_update ? `Every ${status.interval_hours} h` : 'Manual only') : '—'}</dd>
            <dt className="text-charcoal/55">Extraction</dt><dd className="font-semibold text-charcoal">{status?.extraction_mode === 'llm' ? 'AI (Groq)' : 'Demo preset'}</dd>
          </dl>
          {status?.last_run?.error && <p className="mt-3 text-sm text-warn-600">Last run failed: {status.last_run.error}</p>}
          <button onClick={runNow} disabled={running} className="mt-4 w-full py-3 rounded-xl bg-primary-500 text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-50">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Check for new schemes now
          </button>
          {runResult && <p className="mt-2 text-sm text-charcoal/65">{runResult.new_drafts ? `${runResult.new_drafts} new scheme(s) added for review.` : 'No new announcements since the last check.'}</p>}
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto bg-primary-50/80 border border-primary-100 rounded-full p-1 w-fit max-w-full">
        {tabs.map((t) => <button key={t.id} onClick={() => setView(t.id)} className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap ${view === t.id ? 'bg-white text-primary-900 shadow-soft' : 'text-charcoal/60 hover:bg-white'}`}>{t.label}</button>)}
      </div>

      {notice && (
        <div className="rounded-2xl border border-secondary-400 bg-secondary-50 px-5 py-4 flex items-start gap-3">
          <BadgeCheck className="h-5 w-5 text-secondary-600 shrink-0 mt-0.5" />
          <p className="flex-1 text-charcoal/80">{notice.text}</p>
          {notice.hasMatches && <button onClick={() => { setAlertStatus('new'); setView('alerts'); setNotice('') }} className="text-sm font-bold text-primary-700 whitespace-nowrap">Open customer matches</button>}
          <button onClick={() => setNotice('')} aria-label="Dismiss" className="text-charcoal/40"><X className="h-4 w-4" /></button>
        </div>
      )}

      {loading ? <div className="py-16 flex justify-center text-primary-600"><Loader2 className="h-8 w-8 animate-spin" /></div>
        : view === 'catalogue' ? <Catalogue schemes={catalogue} />
        : view === 'alerts' ? <AlertsView alerts={alerts} status={alertStatus} setStatus={setAlertStatus} onChanged={async () => { await loadStatus(); await loadView() }} />
        : drafts.length === 0 ? <p className="text-center py-16 text-charcoal/55">{view === 'pending' ? 'Nothing waiting for review. Use “Check for new schemes now” to look for new announcements.' : `No ${view} schemes yet.`}</p>
        : <div className="space-y-5">{drafts.map((d) => view === 'pending'
            ? <DraftReview key={d.id} draft={d} options={options} onDone={afterReview} />
            : <ReviewedCard key={d.id} draft={d} />)}</div>}
    </div>
  )
}

function DraftReview({ draft, options, onDone }) {
  const [form, setForm] = useState(() => toForm(draft.draft))
  const [dirty, setDirty] = useState(false)
  const [issues, setIssues] = useState(draft.validation_issues)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const method = METHOD[draft.extraction_method] || METHOD.preset

  const update = (patch) => { setForm((f) => ({ ...f, ...patch })); setDirty(true) }

  const save = async () => {
    const r = await apiFetch(`/schemes/updates/${draft.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fromForm(form)) })
    const body = await r.json()
    if (!r.ok) throw new Error(body.detail?.message || 'Could not save changes')
    setIssues(body.validation_issues); setDirty(false)
    return body.validation_issues
  }

  const act = async (action) => {
    setBusy(true); setError('')
    try {
      if (action === 'save') { await save(); return }
      if (action === 'approve' && dirty) { const remaining = await save(); if (remaining.length) return }
      const r = await apiFetch(`/schemes/updates/${draft.id}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: note || null }) })
      const body = await r.json()
      if (!r.ok) { if (body.detail?.issues) setIssues(body.detail.issues); throw new Error(body.detail?.message || 'Action failed') }
      await onDone(body)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <article className="premium-card p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-display font-bold text-charcoal">{draft.title}</h2>
          <p className="text-sm text-charcoal/55 mt-0.5">{draft.source_name} · published {draft.published_on} · fetched {when(draft.fetched_at)}</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${method.cls}`}><Bot className="h-3.5 w-3.5" />{method.label}</span>
      </header>

      {issues.length > 0 && (
        <div className="mt-4 rounded-xl border border-warn-400 bg-warn-100/50 p-4">
          <p className="flex items-center gap-2 font-bold text-warn-600"><AlertTriangle className="h-4 w-4" />Fix before approving</p>
          <ul className="mt-2 list-disc pl-5 text-sm text-charcoal/80 space-y-0.5">{issues.map((i) => <li key={i}>{i}</li>)}</ul>
        </div>
      )}

      <div className="mt-5 grid lg:grid-cols-2 gap-6">
        <section>
          <h3 className="text-sm font-bold uppercase tracking-wide text-charcoal/55 mb-2">Original announcement</h3>
          <p className="rounded-xl bg-offwhite border border-primary-100 p-4 text-charcoal/80 leading-relaxed whitespace-pre-line">{draft.raw_text}</p>
          {draft.source_url && <a href={draft.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm text-primary-700 underline">Open source</a>}
          <Translations draft={draft.draft} />
        </section>

        <section className="space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wide text-charcoal/55">Drafted scheme — check every field</h3>
          <Field label="Name (English)"><input value={form.name_en} onChange={(e) => update({ name_en: e.target.value })} className="input" /></Field>
          <Field label="Summary (English)"><textarea rows={3} value={form.summary_en} onChange={(e) => update({ summary_en: e.target.value })} className="input" /></Field>
          <Field label="Type">
            <select value={form.kind} onChange={(e) => update({ kind: e.target.value })} className="input">{(options?.kinds || ['bank_product', 'government_scheme']).map((k) => <option key={k} value={k}>{label(k)}</option>)}</select>
          </Field>
          <Chips title="Security needed (none = collateral-free)" allowed={options?.collateral} value={form.collateral} onChange={(v) => update({ collateral: v })} />
          <Chips title="Who can apply" allowed={options?.occupations} value={form.occupations} anyLabel="Anyone" onChange={(v) => update({ occupations: v })} />
          <Chips title="Purpose" allowed={options?.purposes} value={form.purposes} anyLabel="Any purpose" onChange={(v) => update({ purposes: v })} />
          <div className="grid grid-cols-3 gap-3">
            <Field label="Min age"><input type="number" min={18} max={110} value={form.min_age} onChange={(e) => update({ min_age: e.target.value })} className="input" /></Field>
            <Field label="Max age"><input type="number" min={18} max={110} value={form.max_age} onChange={(e) => update({ max_age: e.target.value })} className="input" placeholder="none" /></Field>
            <Field label="Valid until"><input type="date" value={form.valid_until} onChange={(e) => update({ valid_until: e.target.value })} className="input" /></Field>
          </div>
          <Chips title="Documents" allowed={options?.documents} value={form.documents} onChange={(v) => update({ documents: v })} />
          <Field label="Conditions the rules can't check (one per line — shown to staff with every customer match)">
            <textarea rows={3} value={form.staff_checks} onChange={(e) => update({ staff_checks: e.target.value })} className="input" placeholder="e.g. Applicant must be a woman" />
          </Field>
        </section>
      </div>

      <footer className="mt-6 pt-5 border-t border-primary-100 flex flex-col sm:flex-row gap-3 sm:items-center">
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Review note (e.g. checked against circular)" className="input flex-1" />
        <div className="flex gap-2">
          {dirty && <button disabled={busy} onClick={() => act('save')} className="px-4 py-2.5 rounded-xl bg-primary-50 text-primary-700 font-semibold">Save changes</button>}
          <button disabled={busy} onClick={() => act('reject')} className="px-4 py-2.5 rounded-xl border-2 border-warn-400 text-warn-600 font-semibold flex items-center gap-1.5"><X className="h-4 w-4" />Reject</button>
          <button disabled={busy || (!dirty && issues.length > 0)} onClick={() => act('approve')} className="px-5 py-2.5 rounded-xl bg-secondary-600 text-white font-semibold flex items-center gap-1.5 disabled:opacity-40">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Approve for customers
          </button>
        </div>
      </footer>
      {error && <p className="mt-3 text-sm text-warn-600">{error}</p>}
    </article>
  )
}

function Field({ label: text, children }) {
  return <label className="block"><span className="block text-sm font-semibold text-charcoal/70 mb-1">{text}</span>{children}</label>
}

/** Multi-select chips. `null` value = no restriction (when anyLabel is given).
 * Values the system doesn't know (e.g. from a bad AI extraction) are shown
 * highlighted so staff can remove them. */
function Chips({ title, allowed = [], value, onChange, anyLabel }) {
  const any = value === null
  const current = value || []
  const unknown = current.filter((v) => !allowed.includes(v))
  const toggle = (v) => onChange(current.includes(v) ? current.filter((x) => x !== v) : [...current, v])
  return (
    <div>
      <p className="text-sm font-semibold text-charcoal/70 mb-1.5">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {anyLabel && <Chip on={any} onClick={() => onChange(any ? [] : null)}>{anyLabel}</Chip>}
        {!any && allowed.map((v) => <Chip key={v} on={current.includes(v)} onClick={() => toggle(v)}>{label(v)}</Chip>)}
        {!any && unknown.map((v) => <Chip key={v} on bad onClick={() => toggle(v)}>{v} — unknown, remove</Chip>)}
      </div>
    </div>
  )
}

function Chip({ on, bad, onClick, children }) {
  const cls = bad ? 'bg-warn-100 border-warn-400 text-warn-600' : on ? 'bg-primary-500 border-primary-500 text-white' : 'bg-white border-primary-100 text-charcoal/65 hover:border-primary-400'
  return <button type="button" onClick={onClick} className={`px-3 py-1.5 rounded-full border text-sm font-semibold ${cls}`}>{on && !bad && <Check className="inline h-3.5 w-3.5 mr-1 -mt-0.5" />}{children}</button>
}

function Translations({ draft }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-4 rounded-xl border border-primary-100">
      <button onClick={() => setOpen((o) => !o)} className="w-full px-4 py-3 flex items-center justify-between text-sm font-semibold text-charcoal/75">
        Customer-language text (machine-translated — have a native speaker check)<ChevronDown className={`h-4 w-4 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <dl className="px-4 pb-4 space-y-3">
          {Object.entries(LANG_NAMES).map(([code, name]) => (
            <div key={code}>
              <dt className="text-xs font-bold text-charcoal/50">{name}</dt>
              <dd className="font-semibold text-charcoal">{draft.name?.[code] || <span className="text-warn-600">missing</span>}</dd>
              <dd className="text-sm text-charcoal/70">{draft.summary?.[code] || <span className="text-warn-600">missing</span>}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

function ReviewedCard({ draft }) {
  const approved = draft.status === 'approved'
  const r = draft.draft.rules || {}
  return (
    <article className="premium-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-display font-bold text-charcoal">{draft.draft.name?.en || draft.title}</h2>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${approved ? 'bg-secondary-100 text-secondary-600' : 'bg-warn-100 text-warn-600'}`}>
          {approved ? <BadgeCheck className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}{approved ? 'Live for customers' : 'Rejected'}
        </span>
      </div>
      <p className="text-sm text-charcoal/65 mt-1">{draft.draft.summary?.en}</p>
      {approved && <p className="text-sm text-charcoal/55 mt-2">Security: {(r.collateral_any || []).map(label).join(', ') || 'none'} · Who: {r.occupations ? r.occupations.map(label).join(', ') : 'anyone'} · Purpose: {r.purposes ? r.purposes.map(label).join(', ') : 'any'}{draft.draft.valid_until ? ` · until ${draft.draft.valid_until}` : ''}</p>}
      {approved && draft.draft.staff_checks?.length > 0 && <p className="text-sm text-warn-600 mt-1">Staff checks: {draft.draft.staff_checks.join(' · ')}</p>}
      <p className="text-xs text-charcoal/50 mt-3">{approved ? 'Approved' : 'Rejected'} by {draft.reviewed_by} · {when(draft.reviewed_at)}{draft.review_note ? ` · “${draft.review_note}”` : ''}</p>
    </article>
  )
}

function Catalogue({ schemes }) {
  return (
    <div className="premium-card p-5 sm:p-6">
      <p className="text-sm text-charcoal/60 mb-4">Every scheme the customer eligibility checker currently uses.</p>
      <ul className="divide-y divide-primary-100">
        {schemes.map((s) => (
          <li key={s.id} className="py-3 flex flex-wrap items-center gap-2">
            <FileText className="h-4 w-4 text-primary-600" />
            <span className="font-semibold text-charcoal">{s.name}</span>
            <span className="text-xs text-charcoal/50">{label(s.kind)}</span>
            <span className={`ml-auto px-2.5 py-0.5 rounded-full text-xs font-bold ${s.origin === 'base' ? 'bg-primary-50 text-primary-700' : 'bg-secondary-100 text-secondary-600'}`}>
              {s.origin === 'base' ? 'Base catalogue' : `Added ${s.added_on}${s.valid_until ? ` · until ${s.valid_until}` : ''}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function AlertsView({ alerts, status, setStatus, onChanged }) {
  const [rescanning, setRescanning] = useState(false)
  const rescan = async () => { setRescanning(true); try { await apiFetch('/schemes/alerts/rescan', { method: 'POST' }); await onChanged() } finally { setRescanning(false) } }
  const filters = [{ id: 'new', label: 'To contact' }, { id: 'contacted', label: 'Contacted' }, { id: 'not_suitable', label: 'Not suitable' }]
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-charcoal/65 max-w-2xl">Existing customers who agreed to receive offers and whose profile fits a newly approved scheme. Nothing is sent automatically — you decide whether to contact them.</p>
        <div className="flex items-center gap-2">
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="input !w-auto">{filters.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}</select>
          <button onClick={rescan} disabled={rescanning} className="px-4 py-2 rounded-xl bg-primary-50 text-primary-700 font-semibold text-sm flex items-center gap-1.5 whitespace-nowrap">{rescanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Re-check customers</button>
        </div>
      </div>
      {alerts.length === 0
        ? <p className="text-center py-16 text-charcoal/55">{status === 'new' ? 'No customers to contact. Matches appear here when you approve a new scheme.' : 'Nothing here yet.'}</p>
        : <div className="grid xl:grid-cols-2 gap-5">{alerts.map((a) => <AlertCard key={a.id} alert={a} onChanged={onChanged} />)}</div>}
    </div>
  )
}

function AlertCard({ alert: a, onChanged }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [playing, setPlaying] = useState(false)
  const open = a.status === 'new'

  const mark = async (status) => {
    setBusy(true)
    try {
      await apiFetch(`/schemes/alerts/${a.id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, note: note || null }) })
      await onChanged()
    } finally { setBusy(false) }
  }
  // Staff can play the message aloud (e.g. at the desk or on a call) —
  // useful when they don't read the customer's language.
  const play = async () => {
    setPlaying(true)
    try {
      const form = new FormData(); form.append('text', a.message_local); form.append('language', a.language); form.append('elderly_mode', 'true')
      const r = await apiFetch('/speak', { method: 'POST', body: form })
      if (!r.ok) { setPlaying(false); return }
      const audio = new Audio(URL.createObjectURL(await r.blob()))
      audio.onended = () => setPlaying(false)
      await audio.play()
    } catch { setPlaying(false) }
  }

  return (
    <article className="premium-card p-5 sm:p-6 flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="h-11 w-11 rounded-full bg-primary-50 flex items-center justify-center shrink-0"><UserRound className="h-5 w-5 text-primary-700" /></div>
          <div>
            <h2 className="text-lg font-display font-bold text-charcoal">{a.customer_name}</h2>
            <p className="text-sm text-charcoal/55 flex flex-wrap items-center gap-x-2">{a.customer_id} · {a.customer_age} yrs · {ALL_LANG_NAMES[a.language]}{a.customer_branch && <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{a.customer_branch}</span>}</p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-bold bg-secondary-100 text-secondary-600 text-right">{a.scheme_name}</span>
      </div>

      <div className="mt-4">
        <p className="text-sm font-bold text-charcoal/70 mb-1">Why they match</p>
        <ul className="space-y-1">{a.reasons.map((r) => <li key={r} className="flex items-start gap-2 text-sm text-charcoal/75"><Check className="h-4 w-4 mt-0.5 text-secondary-600 shrink-0" />{r}</li>)}</ul>
      </div>

      {a.staff_checks.length > 0 && (
        <div className="mt-4 rounded-xl border border-warn-400 bg-warn-100/50 p-3">
          <p className="flex items-center gap-1.5 text-sm font-bold text-warn-600"><AlertTriangle className="h-4 w-4" />Check before contacting — the rules can't verify this</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-charcoal/80">{a.staff_checks.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}

      <div className="mt-4 rounded-xl bg-offwhite border border-primary-100 p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-bold text-charcoal/70">Suggested message ({ALL_LANG_NAMES[a.language]})</p>
          <button onClick={play} disabled={playing} className="inline-flex items-center gap-1 text-sm font-semibold text-primary-700 disabled:opacity-50">{playing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}Listen</button>
        </div>
        <p className="mt-1 text-charcoal">{a.message_local}</p>
        {a.language !== 'en' && <p className="mt-2 text-sm text-charcoal/55">{a.message_english}</p>}
      </div>

      {open ? (
        <div className="mt-auto pt-4 space-y-3">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (e.g. called, visiting on Monday)" className="input" />
          <div className="flex gap-2">
            <button disabled={busy} onClick={() => mark('contacted')} className="flex-1 py-2.5 rounded-xl bg-primary-500 text-white font-semibold flex items-center justify-center gap-1.5"><PhoneCall className="h-4 w-4" />Mark contacted</button>
            <button disabled={busy} onClick={() => mark('not_suitable')} className="flex-1 py-2.5 rounded-xl border-2 border-warn-400 text-warn-600 font-semibold flex items-center justify-center gap-1.5"><X className="h-4 w-4" />Not suitable</button>
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-charcoal/50">{a.status === 'contacted' ? 'Contacted' : 'Marked not suitable'} by {a.handled_by} · {when(a.handled_at)}{a.note ? ` · “${a.note}”` : ''}</p>
      )}
    </article>
  )
}

function toForm(d) {
  const r = d.rules || {}
  return {
    name_en: d.name?.en || '', summary_en: d.summary?.en || '', kind: d.kind || 'bank_product',
    collateral: r.collateral_any || [], occupations: r.occupations ?? null, purposes: r.purposes ?? null,
    min_age: r.min_age ?? '', max_age: r.max_age ?? '', documents: d.documents || [], valid_until: d.valid_until || '',
    staff_checks: (d.staff_checks || []).join('\n'),
  }
}

function fromForm(f) {
  const age = (v) => (v === '' || v === null ? null : Number(v))
  return {
    name_en: f.name_en, summary_en: f.summary_en, kind: f.kind,
    rules: { collateral_any: f.collateral, occupations: f.occupations, purposes: f.purposes, min_age: age(f.min_age), max_age: age(f.max_age) },
    documents: f.documents, valid_until: f.valid_until || null,
    staff_checks: f.staff_checks.split('\n'),
  }
}
