const API_BASE = '/api'
const TOKEN_KEY = 'bolobank_token'
const NAME_KEY = 'bolobank_staff_name'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStaffName() {
  return localStorage.getItem(NAME_KEY) || ''
}

export function setSession(token, displayName) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(NAME_KEY, displayName || '')
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(NAME_KEY)
}

/**
 * Authenticated fetch. Automatically attaches the Bearer token and, on a
 * 401 (expired/invalid session), clears the stored session and reloads to
 * kick the user back to the login screen.
 */
export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    clearSession()
    window.location.reload()
    throw new Error('Session expired')
  }
  return res
}

export async function login(username, password) {
  const form = new FormData()
  form.append('username', username)
  form.append('password', password)
  const res = await fetch(`${API_BASE}/auth/login`, { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || 'Login failed')
  }
  const data = await res.json()
  setSession(data.access_token, data.display_name)
  return data
}

/** Sign in with a Google ID token (obtained client-side via Google Identity
 * Services — see LoginPage.jsx). The token itself is the only thing sent;
 * the backend verifies it and derives the email server-side rather than
 * trusting anything the frontend claims about the user. Issues the same
 * kind of session token as the password login, so the rest of the app
 * doesn't need to know which method was used. */
export async function loginWithGoogle(credential) {
  const res = await fetch(`${API_BASE}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || 'Google sign-in failed')
  }
  const data = await res.json()
  setSession(data.access_token, data.display_name)
  return data
}

/** Whether the backend has GOOGLE_CLIENT_ID configured (unauthenticated —
 * used to decide whether to show the Google sign-in button at all). */
export async function getAuthConfig() {
  try {
    const res = await fetch(`${API_BASE}/auth/config`)
    if (!res.ok) return { google_enabled: false, password_enabled: false }
    return await res.json()
  } catch {
    return { google_enabled: false, password_enabled: false }
  }
}

const CUSTOMER_TOKEN_KEY = 'bolobank_customer_token'

export function setCustomerSession(token) {
  localStorage.setItem(CUSTOMER_TOKEN_KEY, token)
}

export function clearCustomerSession() {
  localStorage.removeItem(CUSTOMER_TOKEN_KEY)
}

export async function customerFetch(path, options = {}) {
  const token = localStorage.getItem(CUSTOMER_TOKEN_KEY)
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (res.status === 401) clearCustomerSession()
  return res
}
