import { useEffect, useState } from 'react'
import {
  ArrowLeft, ArrowRight, BadgeCheck, Ban, Briefcase, Check, Coins, FileText, GraduationCap, HeartPulse,
  HelpCircle, Home, Info, Landmark, Loader2, PiggyBank, RotateCcw, Store, Tractor, UserRound, Users, Wheat,
} from 'lucide-react'
import { t, tf } from '../i18n.js'
import { customerFetch } from '../api.js'

/**
 * Loan / scheme eligibility pre-check for the Customer Portal.
 *
 * Asks one simple question per screen (each question is also spoken), using
 * large tap targets instead of free text so elderly customers never need to
 * type. Answers go to POST /api/customer/eligibility, whose rule engine
 * returns the schemes the customer MAY qualify for. The result is always
 * framed as a first check that a staff member confirms.
 */

const ASSETS = [
  { id: 'gold', icon: Coins },
  { id: 'land', icon: Wheat },
  { id: 'house', icon: Home },
  { id: 'fd', icon: PiggyBank },
]
const GOLD_GRAMS = [10, 20, 50, 100]
const LAND_ACRES = [1, 2, 5, 10]
const FD_AMOUNTS = [50000, 100000, 200000, 500000]
const OCCUPATIONS = [
  { id: 'farmer', icon: Tractor }, { id: 'business', icon: Store }, { id: 'salaried', icon: Briefcase },
  { id: 'pensioner', icon: UserRound }, { id: 'student', icon: GraduationCap }, { id: 'other', icon: Users },
]
const PURPOSES = [
  { id: 'farming', icon: Wheat }, { id: 'business', icon: Store }, { id: 'education', icon: GraduationCap },
  { id: 'home', icon: Home }, { id: 'medical', icon: HeartPulse }, { id: 'personal', icon: Users }, { id: 'not_sure', icon: HelpCircle },
]
// Age bands are easier to answer than an exact number; each maps to a
// representative age for the rule engine.
const AGE_BANDS = [
  { label: '18 – 40', age: 30 }, { label: '41 – 59', age: 50 }, { label: '60 – 75', age: 68 }, { label: '76+', age: 78 },
]

const inr = (n) => `₹${Number(n).toLocaleString('en-IN')}`

export default function LoanEligibility({ language, sessionId, big, onSpeak, onClose, onTalkToStaff }) {
  const tr = (key) => t(language, key)
  const [owned, setOwned] = useState([])
  const [answers, setAnswers] = useState({})
  const [stepIndex, setStepIndex] = useState(0)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  const steps = [
    'assets',
    ...(owned.includes('gold') ? ['gold'] : []),
    ...(owned.includes('land') ? ['land'] : []),
    ...(owned.includes('fd') ? ['fd'] : []),
    'work', 'purpose', 'age',
  ]
  const step = steps[stepIndex]
  const questionKey = { assets: 'qAssets', gold: 'qGold', land: 'qLand', fd: 'qFd', work: 'qWork', purpose: 'qPurpose', age: 'qAge' }[step]

  useEffect(() => {
    if (!result && !loading && questionKey) onSpeak?.(tr(questionKey))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, result, loading])

  const submit = async (finalAnswers) => {
    setLoading(true); setFailed(false)
    try {
      const res = await customerFetch('/customer/eligibility', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          assets: {
            gold_grams: owned.includes('gold') ? finalAnswers.gold : null,
            land_acres: owned.includes('land') ? finalAnswers.land : null,
            fd_amount: owned.includes('fd') ? finalAnswers.fd : null,
            house: owned.includes('house'),
          },
          occupation: finalAnswers.work,
          purpose: finalAnswers.purpose,
          age: finalAnswers.age,
        }),
      })
      if (!res.ok) throw new Error('eligibility')
      const data = await res.json()
      setResult(data)
      onSpeak?.(data.matches.length ? tf(language, 'resSpoken', { count: data.matches.length }) : tr('resNone'))
    } catch {
      setFailed(true)
    } finally { setLoading(false) }
  }

  const answer = (key, value) => {
    const next = { ...answers, [key]: value }
    setAnswers(next)
    if (stepIndex === steps.length - 1) submit(next)
    else setStepIndex(stepIndex + 1)
  }

  const toggleAsset = (id) => {
    if (id === 'none') { setOwned([]); setAnswers((a) => ({ ...a, noAssets: true })); return }
    setAnswers((a) => ({ ...a, noAssets: false }))
    setOwned((o) => (o.includes(id) ? o.filter((x) => x !== id) : [...o, id]))
  }

  const restart = () => { setOwned([]); setAnswers({}); setStepIndex(0); setResult(null); setFailed(false) }

  const textSize = big ? 'text-xl' : 'text-lg'

  if (loading) return (
    <Panel onClose={onClose} tr={tr}>
      <div className="py-16 flex flex-col items-center gap-4 text-primary-700"><Loader2 className="h-12 w-12 animate-spin" /><p className={`${textSize} font-semibold`}>{tr('eligChecking')}</p></div>
    </Panel>
  )

  if (failed) return (
    <Panel onClose={onClose} tr={tr}>
      <p className="rounded-2xl bg-warn-100/60 px-5 py-4 text-warn-600 text-lg">{tr('aiFailed')}</p>
      <button onClick={() => submit(answers)} className="mt-5 w-full py-4 rounded-2xl bg-primary-500 text-white font-bold text-lg">{tr('eligStartOver')}</button>
    </Panel>
  )

  if (result) return (
    <Panel onClose={onClose} tr={tr}>
      <Results result={result} language={language} big={big} />
      <p className="mt-6 flex items-start gap-2 text-sm text-charcoal/60"><Info className="h-4 w-4 mt-0.5 shrink-0" />{tr('eligDisclaimer')}</p>
      <p className="mt-2 flex items-start gap-2 text-sm text-secondary-600 font-semibold"><Check className="h-4 w-4 mt-0.5 shrink-0" />{tr('eligStaffSeen')}</p>
      <div className="mt-6 grid sm:grid-cols-3 gap-3">
        <button onClick={onTalkToStaff} className="sm:col-span-2 py-4 rounded-2xl bg-primary-500 text-white font-bold text-lg flex items-center justify-center gap-2"><UserRound className="h-5 w-5" />{tr('eligTalkStaff')}</button>
        <button onClick={restart} className="py-4 rounded-2xl bg-primary-50 text-primary-700 font-semibold text-lg flex items-center justify-center gap-2"><RotateCcw className="h-5 w-5" />{tr('eligStartOver')}</button>
      </div>
    </Panel>
  )

  const progress = Math.round(((stepIndex) / steps.length) * 100)

  return (
    <Panel onClose={onClose} tr={tr}>
      <div className="h-2 rounded-full bg-primary-50 overflow-hidden mb-6" aria-hidden="true"><div className="h-full bg-primary-500 transition-all" style={{ width: `${progress}%` }} /></div>
      <h2 className={`font-display font-bold text-primary-900 ${big ? 'text-3xl' : 'text-2xl'}`}>{tr(questionKey)}</h2>

      <div className="mt-6">
        {step === 'assets' && (
          <>
            <div className="grid sm:grid-cols-2 gap-3">
              {ASSETS.map(({ id, icon }) => (
                <Choice key={id} icon={icon} label={tr(`asset_${id}`)} selected={owned.includes(id)} onClick={() => toggleAsset(id)} big={big} multi />
              ))}
              <Choice icon={Ban} label={tr('asset_none')} selected={answers.noAssets} onClick={() => toggleAsset('none')} big={big} multi />
            </div>
            <button
              disabled={!owned.length && !answers.noAssets}
              onClick={() => setStepIndex(1)}
              className="mt-6 w-full py-4 rounded-2xl bg-primary-500 text-white font-bold text-lg flex items-center justify-center gap-2 disabled:opacity-40"
            >{tr('eligNext')}<ArrowRight className="h-5 w-5" /></button>
          </>
        )}
        {step === 'gold' && <Options values={GOLD_GRAMS} format={(v) => `${v} ${tr('unitGrams')}`} icon={Coins} onPick={(v) => answer('gold', v)} selected={answers.gold} big={big} />}
        {step === 'land' && <Options values={LAND_ACRES} format={(v) => `${v}${v === 10 ? '+' : ''} ${tr('unitAcres')}`} icon={Wheat} onPick={(v) => answer('land', v)} selected={answers.land} big={big} />}
        {step === 'fd' && <Options values={FD_AMOUNTS} format={inr} icon={Landmark} onPick={(v) => answer('fd', v)} selected={answers.fd} big={big} />}
        {step === 'work' && (
          <div className="grid sm:grid-cols-2 gap-3">{OCCUPATIONS.map(({ id, icon }) => <Choice key={id} icon={icon} label={tr(`occ_${id}`)} selected={answers.work === id} onClick={() => answer('work', id)} big={big} />)}</div>
        )}
        {step === 'purpose' && (
          <div className="grid sm:grid-cols-2 gap-3">{PURPOSES.map(({ id, icon }) => <Choice key={id} icon={icon} label={tr(`pur_${id}`)} selected={answers.purpose === id} onClick={() => answer('purpose', id)} big={big} />)}</div>
        )}
        {step === 'age' && (
          <div className="grid grid-cols-2 gap-3">{AGE_BANDS.map((b) => <Choice key={b.label} label={`${b.label} ${tr('ageYears')}`} selected={answers.age === b.age} onClick={() => answer('age', b.age)} big={big} />)}</div>
        )}
      </div>

      {stepIndex > 0 && (
        <button onClick={() => setStepIndex(stepIndex - 1)} className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full text-charcoal/65 font-semibold hover:bg-primary-50"><ArrowLeft className="h-4 w-4" />{tr('eligBack')}</button>
      )}
    </Panel>
  )
}

function Panel({ onClose, tr, children }) {
  return (
    <div className="max-w-3xl mx-auto premium-card p-6 sm:p-9">
      <div className="flex items-center justify-between gap-3 mb-5">
        <span className="inline-flex items-center gap-2 text-sm font-bold text-primary-700 uppercase tracking-wide"><Landmark className="h-4 w-4" />{tr('eligCardTitle')}</span>
        <button onClick={onClose} className="px-4 py-2 rounded-full bg-primary-50 text-primary-700 text-sm font-semibold">{tr('eligDone')}</button>
      </div>
      {children}
    </div>
  )
}

function Choice({ icon: Icon, label, selected, onClick, big, multi }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={!!selected}
      className={`w-full rounded-2xl border-2 text-left flex items-center gap-4 transition ${big ? 'p-5 text-xl' : 'p-4 text-lg'} font-semibold
        ${selected ? 'border-primary-500 bg-primary-50 text-primary-900' : 'border-primary-100 bg-white text-charcoal hover:border-primary-400'}`}
    >
      {Icon && <span className={`shrink-0 rounded-full flex items-center justify-center ${big ? 'h-12 w-12' : 'h-10 w-10'} ${selected ? 'bg-primary-500 text-white' : 'bg-primary-50 text-primary-700'}`}><Icon className={big ? 'h-6 w-6' : 'h-5 w-5'} /></span>}
      <span className="flex-1">{label}</span>
      {multi && <span className={`h-7 w-7 rounded-lg border-2 flex items-center justify-center ${selected ? 'bg-primary-500 border-primary-500 text-white' : 'border-primary-400'}`}>{selected && <Check className="h-4 w-4" />}</span>}
    </button>
  )
}

function Options({ values, format, icon, onPick, selected, big }) {
  return <div className="grid grid-cols-2 gap-3">{values.map((v) => <Choice key={v} icon={icon} label={format(v)} selected={selected === v} onClick={() => onPick(v)} big={big} />)}</div>
}

function Results({ result, language, big }) {
  const tr = (key) => t(language, key)
  if (!result.matches.length) return (
    <div className="text-center py-6">
      <div className="h-16 w-16 mx-auto rounded-full bg-warn-100 flex items-center justify-center mb-4"><HelpCircle className="h-8 w-8 text-warn-600" /></div>
      <h2 className="text-2xl font-display font-bold text-primary-900">{tr('resNoneTitle')}</h2>
      <p className="mt-2 text-lg text-charcoal/65">{tr('resNone')}</p>
    </div>
  )
  return (
    <>
      <h2 className={`font-display font-bold text-primary-900 ${big ? 'text-3xl' : 'text-2xl'}`}>{tr('resTitle')}</h2>
      <div className="mt-5 space-y-4">{result.matches.map((m) => <SchemeCard key={m.scheme_id} m={m} language={language} big={big} />)}</div>
    </>
  )
}

function reasonText(language, reason) {
  const p = { ...reason.params }
  if (p.occupation) p.occupation = t(language, `occ_${p.occupation}`)
  if (p.purpose) p.purpose = t(language, `pur_${p.purpose}`)
  if (p.amount) p.amount = Number(p.amount).toLocaleString('en-IN')
  return tf(language, `reason_${reason.code}`, p)
}

function SchemeCard({ m, language, big }) {
  const tr = (key) => t(language, key)
  const likely = m.status === 'likely'
  const est = m.estimate
  return (
    <article className="rounded-2xl border-2 border-primary-100 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className={`px-3 py-1 rounded-full text-xs font-bold ${m.kind === 'government_scheme' ? 'bg-secondary-100 text-secondary-600' : 'bg-primary-50 text-primary-700'}`}>{m.kind === 'government_scheme' ? tr('govtScheme') : tr('bankProduct')}</span>
        {m.is_new && <span className="px-3 py-1 rounded-full text-xs font-bold bg-warn-500 text-white">{tr('newScheme')}{m.added_on ? ` · ${m.added_on}` : ''}</span>}
        {m.collateral_free && <span className="px-3 py-1 rounded-full text-xs font-bold bg-secondary-50 text-secondary-600 border border-secondary-400/50">{tr('noCollateralTag')}</span>}
        <span className={`ml-auto inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-bold ${likely ? 'bg-secondary-500 text-charcoal' : 'bg-warn-100 text-warn-600'}`}>
          {likely ? <BadgeCheck className="h-4 w-4" /> : <HelpCircle className="h-4 w-4" />}{likely ? tr('statusLikely') : tr('statusPossible')}
        </span>
      </div>
      <h3 className={`font-display font-bold text-charcoal ${big ? 'text-2xl' : 'text-xl'}`}>{m.name}</h3>
      <p className={`mt-1 text-charcoal/70 ${big ? 'text-lg' : ''}`}>{m.summary}</p>

      {est && (
        <div className="mt-4 rounded-xl bg-primary-50 border border-primary-100 p-4">
          <p className="text-sm font-semibold text-primary-700">{tr('estimateLabel')}</p>
          <p className={`font-display font-bold text-primary-900 ${big ? 'text-4xl' : 'text-3xl'}`}>{inr(est.max_amount_inr)}</p>
          <p className="text-xs text-charcoal/60 mt-1">
            {est.basis === 'gold_value'
              ? tf(language, 'estimateGold', { pct: Math.round(est.ratio * 100), rate: Number(est.rate_per_gram_inr).toLocaleString('en-IN') })
              : tf(language, 'estimateFd', { pct: Math.round(est.ratio * 100) })}
          </p>
        </div>
      )}

      <div className="mt-4 grid sm:grid-cols-2 gap-4">
        <div>
          <p className="text-sm font-bold text-charcoal/80 mb-2">{tr('whyMatch')}</p>
          <ul className="space-y-1.5">{m.reasons.map((r, i) => <li key={i} className="flex items-start gap-2 text-charcoal/75"><Check className="h-4 w-4 mt-1 text-secondary-600 shrink-0" />{reasonText(language, r)}</li>)}</ul>
        </div>
        <div>
          <p className="text-sm font-bold text-charcoal/80 mb-2">{tr('docsTitle')}</p>
          <ul className="space-y-1.5">{m.documents.map((d) => <li key={d} className="flex items-start gap-2 text-charcoal/75"><FileText className="h-4 w-4 mt-1 text-primary-600 shrink-0" />{tr(`doc_${d}`)}</li>)}</ul>
        </div>
      </div>

      <p className="mt-4 text-xs text-charcoal/45">
        {tr('source')}: {m.source.url ? <a href={m.source.url} target="_blank" rel="noreferrer" className="underline">{m.source.name}</a> : m.source.name}
      </p>
    </article>
  )
}
