import { useEffect, useState } from 'react'
import { Clock, PhoneCall, CheckCircle2, Ticket, ChevronRight } from 'lucide-react'
import { apiFetch } from '../api.js'

export default function QueuePanel() {
  const [queue, setQueue] = useState({ waiting: [], serving: [], done: [] })
  const [name, setName] = useState('')
  const [serviceType, setServiceType] = useState('Loan enquiry')
  const [customerType, setCustomerType] = useState('general')

  const refresh = async () => {
    const res = await apiFetch('/queue')
    if (res.ok) setQueue(await res.json())
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [])

  const generateToken = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    await apiFetch('/queue/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_name: name, service_type: serviceType, customer_type: customerType }),
    })
    setName('')
    refresh()
  }

  const callNext = async () => {
    await apiFetch('/queue/call-next', { method: 'POST' })
    refresh()
  }

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-8">
        <h3 className="flex items-center gap-2 text-xl font-display font-bold text-charcoal mb-6">
          <Ticket className="h-5 w-5 text-primary-500" />
          Generate token
        </h3>
        <form onSubmit={generateToken} className="space-y-4">
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1">Customer name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base focus:border-primary-500 outline-none transition-colors"
              placeholder="e.g. Ramesh Patil"
            />
          </div>
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1">Service type</label>
            <select
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
              className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base focus:border-primary-500 outline-none transition-colors"
            >
              <option>Loan enquiry</option>
              <option>Account opening</option>
              <option>Pension services</option>
              <option>Card / passbook issue</option>
              <option>General enquiry</option>
            </select>
          </div>
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1">Customer type</label>
            <select
              value={customerType}
              onChange={(e) => setCustomerType(e.target.value)}
              className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base focus:border-primary-500 outline-none transition-colors"
            >
              <option value="general">General</option>
              <option value="elderly">Elderly (priority lane)</option>
              <option value="rural">Rural</option>
            </select>
          </div>
          <button
            type="submit"
            className="w-full py-4 rounded-2xl bg-secondary-500 text-charcoal font-display font-semibold text-lg
              hover:bg-secondary-600 transition-colors flex items-center justify-center gap-2"
          >
            Generate token
            <ChevronRight className="h-5 w-5" strokeWidth={2.5} />
          </button>
        </form>
      </div>

      <div className="bg-white rounded-3xl shadow-card border border-primary-100 p-8">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-display font-bold text-charcoal">Queue status</h3>
          <button
            onClick={callNext}
            className="flex items-center gap-1.5 px-5 py-2 rounded-full bg-primary-500 text-white font-semibold text-base
              hover:bg-primary-600 transition-colors"
          >
            <PhoneCall className="h-4 w-4" />
            Call next
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-6">
          <StatCard label="Waiting" value={queue.waiting.length} icon={Clock} color="bg-warn-100 text-warn-600" />
          <StatCard label="Serving" value={queue.serving.length} icon={PhoneCall} color="bg-primary-100 text-primary-600" />
          <StatCard label="Done" value={queue.done.length} icon={CheckCircle2} color="bg-secondary-100 text-secondary-600" />
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {queue.waiting.map((t) => (
            <div key={t.token} className="flex justify-between items-center bg-offwhite rounded-xl px-4 py-3 border border-primary-100/60">
              <span className="font-semibold text-charcoal">{t.token} · {t.customer_name}</span>
              <span className="text-sm text-charcoal/60">{t.service_type}</span>
            </div>
          ))}
          {queue.waiting.length === 0 && (
            <p className="text-charcoal/50 text-base">No one waiting right now.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className={`rounded-2xl py-4 flex flex-col items-center gap-1 ${color}`}>
      <Icon className="h-4 w-4 opacity-70" />
      <p className="text-3xl font-display font-bold">{value}</p>
      <p className="text-sm font-semibold">{label}</p>
    </div>
  )
}
