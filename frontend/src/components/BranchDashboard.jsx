import { useEffect, useState } from 'react'
import {
  AlertTriangle, ArrowDownRight, ArrowUpRight, Bot, Coins, Database, HelpCircle, IndianRupee, Landmark, Languages,
  Loader2, Minus, RefreshCw, Table2, Trash2, Users, UserRound,
} from 'lucide-react'
import { apiFetch } from '../api.js'

/**
 * Branch manager dashboard — what happened in the branch, whether BoloBank
 * is helping, and what to do next. Data: GET /api/dashboard/summary
 * (backend/services/analytics_service.py). Shows counts and topics only;
 * no balances or account numbers.
 */

// Chart series colours — validated pair (lightness, chroma, colour-blind
// separation and contrast all pass). Identity is never colour-only: there is
// a legend, a tooltip and a table view.
const SERIES = { ai: '#2F6FA8', staff: '#C2661E' }
const LANG = { mr: 'Marathi', hi: 'Hindi', kn: 'Kannada', te: 'Telugu', en: 'English' }
const CHANNEL = { customer_portal: 'Customer portal', staff_session: 'Staff-assisted session', copilot: 'AI Copilot' }
const ASSET = { gold: 'Gold', land: 'Farm land', house: 'House / property', fd: 'Fixed deposit' }

const num = (n) => (n ?? 0).toLocaleString('en-IN')
const inr = (n) => {
  if (!n) return '₹0'
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} crore`
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} lakh`
  return `₹${Math.round(n).toLocaleString('en-IN')}`
}
// Knowledge-base titles carry an internal "- Demo SOP" suffix; hide it here.
const topicName = (t) => t.replace(/\s*-\s*Demo SOP$/i, '')
const shortDate = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

export default function BranchDashboard({ onOpenSchemes }) {
  const [days, setDays] = useState(7)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = async (d = days) => {
    setLoading(true); setError('')
    try {
      const r = await apiFetch(`/dashboard/summary?days=${d}`)
      if (!r.ok) throw new Error()
      setData(await r.json())
    } catch { setError('Could not load the dashboard. Check that the backend is running.') } finally { setLoading(false) }
  }
  useEffect(() => { load(days) }, [days])

  const demo = async (method) => {
    setBusy(true)
    try { await apiFetch('/dashboard/demo-data', { method }); await load() } finally { setBusy(false) }
  }

  const k = data?.kpis
  const trend = k && k.previous_questions ? Math.round(((k.questions - k.previous_questions) / k.previous_questions) * 100) : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-secondary-600 bg-secondary-50 px-3 py-1.5 rounded-full mb-3"><Landmark className="h-3.5 w-3.5" />Branch manager</span>
          <h1 className="text-3xl sm:text-4xl font-display font-semibold text-primary-900">Branch insights</h1>
          <p className="mt-1 text-charcoal/65">How BoloBank is helping customers in this branch, and what needs attention.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex bg-primary-50 border border-primary-100 rounded-full p-1" role="group" aria-label="Time period">
            {[1, 7, 30].map((d) => (
              <button key={d} onClick={() => setDays(d)} aria-pressed={days === d}
                className={`px-4 py-1.5 rounded-full text-sm font-semibold ${days === d ? 'bg-white text-primary-900 shadow-soft' : 'text-charcoal/60'}`}>
                {d === 1 ? 'Today' : `${d} days`}
              </button>
            ))}
          </div>
          <button onClick={() => load()} className="p-2.5 rounded-full bg-primary-50 text-primary-700" aria-label="Refresh"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>
        </div>
      </div>

      {data && (data.demo_events > 0 ? (
        <div className="rounded-2xl border border-warn-400 bg-warn-100/50 px-5 py-3 flex flex-wrap items-center gap-3">
          <Database className="h-5 w-5 text-warn-600" />
          <p className="flex-1 text-charcoal/80"><b>Includes {num(data.demo_events)} demo records</b> — sample activity for presentations, not real customers.</p>
          <button disabled={busy} onClick={() => demo('DELETE')} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border-2 border-warn-400 text-warn-600 font-semibold text-sm"><Trash2 className="h-4 w-4" />Remove demo data</button>
        </div>
      ) : (
        <div className="rounded-2xl border border-primary-100 bg-white/70 px-5 py-3 flex flex-wrap items-center gap-3">
          <Database className="h-5 w-5 text-primary-600" />
          <p className="flex-1 text-charcoal/70">Showing real activity only. For a presentation, you can load two weeks of clearly-labelled sample data.</p>
          <button disabled={busy} onClick={() => demo('POST')} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary-50 text-primary-700 font-semibold text-sm">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}Load demo data</button>
        </div>
      ))}

      {error && <p className="text-warn-600">{error}</p>}
      {loading && !data && <div className="py-24 flex justify-center text-primary-600"><Loader2 className="h-8 w-8 animate-spin" /></div>}

      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Tile icon={Users} label="Customers helped" value={num(k.conversations)} sub={`${num(k.questions)} questions${trend !== null ? '' : ''}`} trend={trend} />
            <Tile icon={Bot} label="Answered by AI" value={k.answered_by_ai_pct == null ? '—' : `${k.answered_by_ai_pct}%`} sub={`${num(k.handed_to_staff)} passed to staff`} />
            <Tile icon={IndianRupee} label="Loan leads" value={inr(k.loan_pipeline_inr)} sub={`${num(k.eligibility_checks)} eligibility checks`} />
            <Tile icon={Coins} label="AI cost" value={k.ai_cost_per_conversation_inr == null ? '—' : `₹${k.ai_cost_per_conversation_inr.toFixed(2)}`} sub={`per customer · ${inr(k.ai_cost_inr)} total`} />
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            <Card title="Questions per day" className="lg:col-span-2">
              <DailyChart daily={data.daily} />
            </Card>
            <Card title="Languages" icon={Languages}>
              <HBars rows={Object.entries(data.languages).map(([code, n]) => ({ label: LANG[code] || code, value: n }))} empty="No questions yet" />
              <div className="mt-5 pt-4 border-t border-primary-100 grid grid-cols-2 gap-3 text-sm">
                <Mini label="Elderly Voice Mode" value={k.elderly_mode_pct == null ? '—' : `${k.elderly_mode_pct}%`} />
                <Mini label={'"Didn\'t understand"'} value={num(k.didnt_understand)} />
              </div>
            </Card>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <Card title="What customers ask about">
              <TopicsTable rows={data.top_topics} />
            </Card>
            <Card title="Needs attention: questions the AI couldn't answer" icon={AlertTriangle} accent>
              {data.unanswered.length === 0 ? <p className="text-charcoal/55">Nothing unanswered in this period.</p> : (
                <>
                  <ul className="divide-y divide-primary-100">
                    {data.unanswered.map((u) => (
                      <li key={u.text} className="py-2.5 flex items-start gap-3">
                        <span className="shrink-0 mt-0.5 h-7 min-w-7 px-2 rounded-full bg-warn-100 text-warn-600 text-sm font-bold flex items-center justify-center" aria-label={`${u.count} times`}>{u.count}×</span>
                        <div className="min-w-0"><p className="text-charcoal break-words">{u.text}</p><p className="text-xs text-charcoal/50">{u.languages.map((l) => LANG[l] || l).join(', ')}</p></div>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-sm text-charcoal/60">These went to staff. Adding the common ones to the knowledge base lets BoloBank answer them next time.</p>
                </>
              )}
            </Card>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            <Card title="Loan leads from the eligibility checker" className="lg:col-span-2">
              <div className="grid sm:grid-cols-2 gap-6">
                <div>
                  <p className="text-sm font-semibold text-charcoal/60 mb-2">What customers own</p>
                  <HBars rows={Object.entries(data.eligibility.assets).map(([a, n]) => ({ label: ASSET[a] || a, value: n }))} empty="No eligibility checks yet" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-charcoal/60 mb-2">Most matched schemes</p>
                  <HBars rows={data.eligibility.top_schemes.map((s) => ({ label: s.name, value: s.count }))} empty="No matches yet" />
                </div>
              </div>
              <p className="mt-4 text-sm text-charcoal/55">Loan-lead value is the sum of the best estimate from each check (mainly gold loans) — indicative only; staff confirm every loan.</p>
            </Card>
            <Card title="New schemes">
              <div className="space-y-3">
                <Mini label="Approved in this period" value={num(data.schemes.approved_in_period)} />
                <Mini label="Average time to approve" value={data.schemes.avg_hours_to_approve == null ? '—' : data.schemes.avg_hours_to_approve < 1 ? 'under 1 h' : `${data.schemes.avg_hours_to_approve} h`} />
                <Mini label="Waiting for review" value={num(data.schemes.pending_review)} />
                <div className="pt-3 border-t border-primary-100">
                  <p className="text-sm font-semibold text-charcoal/60 mb-1.5">Customer matches</p>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <Mini label="To contact" value={num(data.schemes.matches.to_contact)} />
                    <Mini label="Contacted" value={num(data.schemes.matches.contacted)} />
                    <Mini label="Not suitable" value={num(data.schemes.matches.not_suitable)} />
                  </div>
                </div>
                {onOpenSchemes && <button onClick={onOpenSchemes} className="w-full mt-1 py-2.5 rounded-xl bg-primary-50 text-primary-700 font-semibold text-sm">Open Schemes</button>}
              </div>
            </Card>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            <Card title="Where questions come from">
              <HBars rows={Object.entries(data.channels).map(([c, n]) => ({ label: CHANNEL[c] || c, value: n }))} empty="No questions yet" />
            </Card>
            <Card title="AI cost" icon={Coins} className="lg:col-span-2">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Mini label="AI calls" value={num(data.cost.llm_calls)} />
                <Mini label="Tokens" value={num(data.cost.prompt_tokens + data.cost.completion_tokens)} />
                <Mini label="Total cost" value={inr(data.cost.cost_inr)} />
                <Mini label="Per question" value={data.cost.cost_per_question_inr == null ? '—' : `₹${data.cost.cost_per_question_inr.toFixed(3)}`} />
              </div>
              <p className="mt-4 text-xs text-charcoal/55">
                Estimate for {data.cost.assumptions.model} at ${data.cost.assumptions.input_usd_per_million_tokens} / ${data.cost.assumptions.output_usd_per_million_tokens} per million input / output tokens and ₹{data.cost.assumptions.usd_to_inr} per US$ — set current prices in backend/.env. {data.cost.assumptions.note}
              </p>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function Card({ title, icon: Icon, accent, className = '', children }) {
  return (
    <section className={`premium-card p-5 sm:p-6 ${accent ? '!border-warn-400/60 border-2' : ''} ${className}`}>
      <h2 className="flex items-center gap-2 text-lg font-display font-bold text-charcoal mb-4">{Icon && <Icon className={`h-5 w-5 ${accent ? 'text-warn-600' : 'text-primary-600'}`} />}{title}</h2>
      {children}
    </section>
  )
}

function Tile({ icon: Icon, label, value, sub, trend }) {
  return (
    <div className="premium-card p-5">
      <p className="flex items-center gap-2 text-sm font-semibold text-charcoal/60"><Icon className="h-4 w-4 text-primary-600" />{label}</p>
      <p className="mt-2 text-3xl font-display font-bold text-charcoal">{value}</p>
      <p className="mt-1 text-sm text-charcoal/55 flex items-center gap-1.5 flex-wrap">
        {sub}
        {trend != null && (
          <span className={`inline-flex items-center gap-0.5 font-semibold ${trend >= 0 ? 'text-secondary-600' : 'text-warn-600'}`}>
            {trend > 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : trend < 0 ? <ArrowDownRight className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}
            {trend > 0 ? '+' : ''}{trend}% vs previous
          </span>
        )}
      </p>
    </div>
  )
}

function Mini({ label, value }) {
  return <div><p className="text-xs text-charcoal/55">{label}</p><p className="text-xl font-display font-bold text-charcoal">{value}</p></div>
}

/** Stacked daily bars: answered by AI (blue) and passed to staff (orange).
 * Legend + hover tooltip + table view, so identity is never colour-only. */
function DailyChart({ daily }) {
  const [hover, setHover] = useState(null)
  const [asTable, setAsTable] = useState(false)
  const max = Math.max(1, ...daily.map((d) => d.questions))
  const labelEvery = daily.length > 14 ? 5 : daily.length > 7 ? 2 : 1
  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-4 text-sm text-charcoal/70">
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: SERIES.ai }} />Answered by AI</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: SERIES.staff }} />Passed to staff</span>
        </div>
        <button onClick={() => setAsTable((v) => !v)} className="inline-flex items-center gap-1 text-sm font-semibold text-primary-700"><Table2 className="h-4 w-4" />{asTable ? 'Chart' : 'Table'}</button>
      </div>
      {asTable ? (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-charcoal/55"><th className="py-1 font-semibold">Date</th><th className="font-semibold text-right">Answered by AI</th><th className="font-semibold text-right">Passed to staff</th><th className="font-semibold text-right">Eligibility checks</th></tr></thead>
          <tbody>{daily.map((d) => <tr key={d.date} className="border-t border-primary-100"><td className="py-1.5">{shortDate(d.date)}</td><td className="text-right">{d.answered_by_ai}</td><td className="text-right">{d.handed_to_staff}</td><td className="text-right">{d.eligibility_checks}</td></tr>)}</tbody>
        </table>
      ) : (
        <div className="relative">
          <div className="h-48 flex items-end gap-1 border-b border-charcoal/15" onMouseLeave={() => setHover(null)}>
            {daily.map((d, i) => (
              <div key={d.date} className="flex-1 h-full flex flex-col justify-end items-stretch cursor-default" onMouseEnter={() => setHover(i)}
                role="img" aria-label={`${shortDate(d.date)}: ${d.answered_by_ai} answered by AI, ${d.handed_to_staff} passed to staff`}>
                {d.handed_to_staff > 0 && <div className="rounded-t-[4px] mb-[2px]" style={{ height: `${(d.handed_to_staff / max) * 100}%`, background: SERIES.staff, opacity: hover == null || hover === i ? 1 : 0.45 }} />}
                {d.answered_by_ai > 0 && <div className={d.handed_to_staff > 0 ? '' : 'rounded-t-[4px]'} style={{ height: `${(d.answered_by_ai / max) * 100}%`, background: SERIES.ai, opacity: hover == null || hover === i ? 1 : 0.45 }} />}
              </div>
            ))}
          </div>
          <div className="flex gap-1 mt-1.5 text-[11px] text-charcoal/50">
            {daily.map((d, i) => <span key={d.date} className="flex-1 text-center">{i % labelEvery === 0 || i === daily.length - 1 ? shortDate(d.date) : ''}</span>)}
          </div>
          {hover != null && (
            <div className="absolute top-0 pointer-events-none bg-white border border-primary-100 shadow-card rounded-xl px-3 py-2 text-sm"
              style={{ left: `min(calc(${((hover + 0.5) / daily.length) * 100}% + 8px), calc(100% - 11rem))` }}>
              <p className="font-semibold text-charcoal">{shortDate(daily[hover].date)}</p>
              <p className="text-charcoal/75"><span className="inline-block h-2.5 w-2.5 rounded-sm mr-1.5" style={{ background: SERIES.ai }} />{daily[hover].answered_by_ai} answered by AI</p>
              <p className="text-charcoal/75"><span className="inline-block h-2.5 w-2.5 rounded-sm mr-1.5" style={{ background: SERIES.staff }} />{daily[hover].handed_to_staff} passed to staff</p>
              <p className="text-charcoal/55 text-xs mt-0.5">{daily[hover].eligibility_checks} eligibility checks</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Single-series horizontal bars with the value printed beside each bar. */
function HBars({ rows, empty }) {
  if (!rows.length) return <p className="text-charcoal/55">{empty}</p>
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="flex justify-between text-sm"><span className="text-charcoal/80 truncate pr-2">{r.label}</span><span className="font-semibold text-charcoal">{num(r.value)}</span></div>
          <div className="mt-1 h-2 rounded-full bg-primary-50"><div className="h-2 rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: SERIES.ai }} /></div>
        </li>
      ))}
    </ul>
  )
}

function TopicsTable({ rows }) {
  if (!rows.length) return <p className="text-charcoal/55">No answered questions yet.</p>
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-left text-charcoal/55"><th className="pb-2 font-semibold">Topic</th><th className="pb-2 font-semibold text-right">Questions</th><th className="pb-2 font-semibold text-right">Trend</th><th className="pb-2 font-semibold text-right" title={'Times customers said "I didn\'t understand"'}><HelpCircle className="inline h-4 w-4" /></th></tr></thead>
      <tbody>
        {rows.map((r) => {
          const change = r.previous ? Math.round(((r.count - r.previous) / r.previous) * 100) : null
          return (
            <tr key={r.topic} className="border-t border-primary-100 align-middle">
              <td className="py-2 pr-2">
                <p className="text-charcoal">{topicName(r.topic)}</p>
                <div className="mt-1 h-1.5 rounded-full bg-primary-50"><div className="h-1.5 rounded-full" style={{ width: `${(r.count / max) * 100}%`, background: SERIES.ai }} /></div>
              </td>
              <td className="py-2 text-right font-semibold text-charcoal">{r.count}</td>
              <td className="py-2 text-right whitespace-nowrap">
                {change == null ? <span className="text-charcoal/45">new</span> : (
                  <span className={`inline-flex items-center gap-0.5 ${change > 0 ? 'text-secondary-600' : change < 0 ? 'text-warn-600' : 'text-charcoal/55'}`}>
                    {change > 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : change < 0 ? <ArrowDownRight className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}{change > 0 ? '+' : ''}{change}%
                  </span>
                )}
              </td>
              <td className="py-2 text-right">{r.didnt_understand > 0 ? <span className="inline-flex items-center gap-1 text-warn-600 font-semibold"><UserRound className="h-3.5 w-3.5" />{r.didnt_understand}</span> : <span className="text-charcoal/35">0</span>}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
