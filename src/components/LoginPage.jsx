import { useState } from 'react'
import { LogIn, ShieldCheck, AlertCircle } from 'lucide-react'
import { login } from '../api.js'

export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await login(username, password)
      onLoggedIn(data.display_name)
    } catch (err) {
      setError(err.message || 'Could not sign in. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <LogoMark />
          <h1 className="mt-4 text-2xl font-display font-bold text-charcoal">BoloBank</h1>
          <p className="text-charcoal/60 text-base">Staff sign-in</p>
        </div>

        <form
          onSubmit={submit}
          className="bg-white rounded-3xl shadow-card border border-primary-100 p-8 space-y-5"
        >
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1.5">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base
                focus:border-primary-500 outline-none transition-colors"
              placeholder="staff"
            />
          </div>
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border-2 border-primary-100 rounded-xl px-4 py-3 text-base
                focus:border-primary-500 outline-none transition-colors"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-warn-600 bg-warn-100 rounded-xl px-4 py-3 text-base">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full py-4 rounded-2xl bg-primary-500 text-white font-display font-semibold text-lg
              hover:bg-primary-600 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
          >
            <LogIn className="h-5 w-5" strokeWidth={2.5} />
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="mt-5 flex items-start gap-2 text-sm text-charcoal/50 px-2">
          <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5" />
          <p>
            Default demo login — username <strong>staff</strong>, password{' '}
            <strong>bolobank123</strong>. Change this before a real deployment.
          </p>
        </div>
      </div>
    </div>
  )
}

function LogoMark() {
  return (
    <svg width="52" height="52" viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <circle cx="18" cy="18" r="18" fill="#5B9BD5" />
      <path d="M18 9a6 6 0 0 0-6 6v3a6 6 0 0 0 12 0v-3a6 6 0 0 0-6-6Z" fill="#FFFFFF" />
      <path d="M11 18a1 1 0 1 0-2 0 9 9 0 0 0 8 8.94V29h-2a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.06A9 9 0 0 0 27 18a1 1 0 1 0-2 0 7 7 0 0 1-14 0Z" fill="#FFFFFF" />
    </svg>
  )
}
