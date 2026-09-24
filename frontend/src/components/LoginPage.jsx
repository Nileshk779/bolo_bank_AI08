import { useEffect, useRef, useState } from 'react'
import { LogIn, ShieldCheck, AlertCircle } from 'lucide-react'
import { getAuthConfig, login, loginWithGoogle } from '../api.js'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [googleEnabled, setGoogleEnabled] = useState(false)
  const [passwordEnabled, setPasswordEnabled] = useState(false)
  const googleButtonRef = useRef(null)

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

  // Ask the backend whether Google sign-in is configured (GOOGLE_CLIENT_ID
  // set server-side) before bothering to load Google's script or render
  // the button — keeps the login page working exactly as before if an
  // admin hasn't set up Google sign-in yet.
  useEffect(() => {
    getAuthConfig().then((cfg) => {
      setGoogleEnabled(!!cfg.google_enabled)
      setPasswordEnabled(!!cfg.password_enabled)
    })
  }, [])

  useEffect(() => {
    if (!googleEnabled || !GOOGLE_CLIENT_ID) return

    const handleCredential = async (response) => {
      setError('')
      setBusy(true)
      try {
        const data = await loginWithGoogle(response.credential)
        onLoggedIn(data.display_name)
      } catch (err) {
        setError(err.message || 'Google sign-in failed. Please try again.')
      } finally {
        setBusy(false)
      }
    }

    const initGoogle = () => {
      if (!window.google || !googleButtonRef.current) return
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredential,
      })
      window.google.accounts.id.renderButton(googleButtonRef.current, {
        theme: 'outline',
        size: 'large',
        width: 320,
        text: 'signin_with',
        shape: 'pill',
      })
    }

    if (window.google) {
      initGoogle()
      return
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = initGoogle
    document.head.appendChild(script)
  }, [googleEnabled])

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <LogoMark />
          <h1 className="mt-4 text-2xl font-display font-bold text-charcoal">BoloBank</h1>
          <p className="text-charcoal/60 text-base">Staff sign-in</p>
        </div>

        {googleEnabled && (
          <div className="mb-5 flex flex-col items-center gap-4">
            <div ref={googleButtonRef} />
            {passwordEnabled && <div className="flex items-center gap-3 w-full max-w-sm">
              <span className="h-px flex-1 bg-primary-100" />
              <span className="text-xs font-semibold text-charcoal/40 uppercase tracking-wide">or</span>
              <span className="h-px flex-1 bg-primary-100" />
            </div>}
          </div>
        )}

        {passwordEnabled && <form
          onSubmit={submit}
          className="premium-card p-8 space-y-5"
        >
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1.5">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              className="w-full border border-primary-100 rounded-2xl shadow-[0_1px_0_rgba(255,255,255,.8)_inset] px-4 py-3 text-base
                focus:border-primary-400 focus:ring-4 focus:ring-primary-100/60 outline-none transition-all"
              placeholder="staff"
            />
          </div>
          <div>
            <label className="block text-base font-semibold text-charcoal mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-primary-100 rounded-2xl shadow-[0_1px_0_rgba(255,255,255,.8)_inset] px-4 py-3 text-base
                focus:border-primary-400 focus:ring-4 focus:ring-primary-100/60 outline-none transition-all"
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
            className="w-full py-4 rounded-2xl bg-primary-500 text-white font-display font-semibold shadow-soft hover:shadow-card text-lg
              hover:bg-primary-600 hover:-translate-y-0.5 transition-all disabled:opacity-60 flex items-center justify-center gap-2"
          >
            <LogIn className="h-5 w-5" strokeWidth={2.5} />
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>}

        <div className="mt-5 flex items-start gap-2 text-sm text-charcoal/50 px-2">
          <ShieldCheck className="h-4 w-4 shrink-0 mt-0.5" />
          <p>
            {passwordEnabled ? <>Local demo password login is enabled. Disable it for production.</> : <>Password login is disabled.</>}
            {googleEnabled && ' Google sign-in is for bank employees only — customers using the voice assistant never need a Google account.'}
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
