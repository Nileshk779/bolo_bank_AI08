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
