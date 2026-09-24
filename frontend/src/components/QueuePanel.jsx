import { useEffect, useState } from 'react'

const API_BASE = '/api'

export default function QueuePanel() {
  const [queue, setQueue] = useState({ waiting: [], serving: [], done: [] })
  const [name, setName] = useState('')
  const [serviceType, setServiceType] = useState('Loan enquiry')
  const [customerType, setCustomerType] = useState('general')

  const refresh = async () => {
    const res = await fetch(`${API_BASE}/queue`)
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
    await fetch(`${API_BASE}/queue/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_name: name, service_type: serviceType, customer_type: customerType }),
    })
    setName('')
    refresh()
  }

  const callNext = async () => {
    await fetch(`${API_BASE}/queue/call-next`, { method: 'POST' })
    refresh()
  }

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="bg-white rounded-3xl shadow-sm border border-teal-100 p-8">
        <h3 className="text-xl font-display font-bold text-teal-900 mb-6">Generate token</h3>
        <form onSubmit={generateToken} className="space-y-4">
          <div>
            <label className="block text-base font-semibold text-teal-900 mb-1">Customer name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border-2 border-teal-100 rounded-xl px-4 py-3 text-base focus:border-teal-900 outline-none"
              placeholder="e.g. Ramesh Patil"
            />
          </div>
          <div>
            <label className="block text-base font-semibold text-teal-900 mb-1">Service type</label>
            <select
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
              className="w-full border-2 border-teal-100 rounded-xl px-4 py-3 text-base focus:border-teal-900 outline-none"
            >
              <option>Loan enquiry</option>
              <option>Account opening</option>
              <option>Pension services</option>
              <option>Card / passbook issue</option>
              <option>General enquiry</option>
            </select>
          </div>
          <div>
            <label className="block text-base font-semibold text-teal-900 mb-1">Customer type</label>
            <select
              value={customerType}
              onChange={(e) => setCustomerType(e.target.value)}
              className="w-full border-2 border-teal-100 rounded-xl px-4 py-3 text-base focus:border-teal-900 outline-none"
            >
              <option value="general">General</option>
              <option value="elderly">Elderly (priority lane)</option>
              <option value="rural">Rural</option>
            </select>
          </div>
          <button
            type="submit"
            className="w-full py-4 rounded-2xl bg-gold-500 text-teal-950 font-display font-semibold text-lg hover:bg-gold-400 transition-colors"
          >
            Generate token
          </button>
        </form>
      </div>

      <div className="bg-white rounded-3xl shadow-sm border border-teal-100 p-8">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-display font-bold text-teal-900">Queue status</h3>
          <button
            onClick={callNext}
            className="px-5 py-2 rounded-full bg-teal-900 text-white font-semibold text-base hover:bg-teal-800"
          >
            Call next
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-6 text-center">
          <StatCard label="Waiting" value={queue.waiting.length} color="bg-gold-100 text-gold-600" />
          <StatCard label="Serving" value={queue.serving.length} color="bg-teal-100 text-teal-900" />
          <StatCard label="Done" value={queue.done.length} color="bg-leaf/10 text-leaf" />
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {queue.waiting.map((t) => (
            <div key={t.token} className="flex justify-between items-center bg-cream rounded-xl px-4 py-3">
              <span className="font-semibold text-teal-900">{t.token} · {t.customer_name}</span>
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

function StatCard({ label, value, color }) {
  return (
    <div className={`rounded-2xl py-4 ${color}`}>
      <p className="text-3xl font-display font-bold">{value}</p>
      <p className="text-sm font-semibold">{label}</p>
    </div>
  )
}
