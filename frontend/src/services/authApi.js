const LOCAL_TOKEN_KEY = 'document-polish-auth-token'
const LOCAL_USER_KEY = 'document-polish-auth-user'
const SESSION_TOKEN_KEY = 'document-polish-session-token'
const SESSION_USER_KEY = 'document-polish-session-user'
export const AUTH_USER_UPDATED_EVENT = 'document-polish-auth-user-updated'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '请求失败，请稍后重试。')
  }

  return data
}

async function authRequest(url, options = {}) {
  const token = getAuthToken()
  if (!token) {
    throw new Error('请先登录。')
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  })

  if (response.status === 401) {
    clearAuthSession()
  }

  return response
}

function readJson(storage, key) {
  try {
    const raw = storage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function getAuthToken() {
  return localStorage.getItem(LOCAL_TOKEN_KEY) || sessionStorage.getItem(SESSION_TOKEN_KEY) || ''
}

export function getStoredUser() {
  return readJson(localStorage, LOCAL_USER_KEY) || readJson(sessionStorage, SESSION_USER_KEY)
}

export function saveStoredUser(user) {
  if (localStorage.getItem(LOCAL_TOKEN_KEY)) {
    localStorage.setItem(LOCAL_USER_KEY, JSON.stringify(user))
  } else if (sessionStorage.getItem(SESSION_TOKEN_KEY)) {
    sessionStorage.setItem(SESSION_USER_KEY, JSON.stringify(user))
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(AUTH_USER_UPDATED_EVENT, { detail: user || null }))
  }
}

export function saveAuthSession({ token, user }, remember = true) {
  clearAuthSession()
  const storage = remember ? localStorage : sessionStorage
  storage.setItem(remember ? LOCAL_TOKEN_KEY : SESSION_TOKEN_KEY, token)
  storage.setItem(remember ? LOCAL_USER_KEY : SESSION_USER_KEY, JSON.stringify(user))
}

export function clearAuthSession() {
  localStorage.removeItem(LOCAL_TOKEN_KEY)
  localStorage.removeItem(LOCAL_USER_KEY)
  sessionStorage.removeItem(SESSION_TOKEN_KEY)
  sessionStorage.removeItem(SESSION_USER_KEY)

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(AUTH_USER_UPDATED_EVENT, { detail: null }))
  }
}

export async function login(payload) {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function register(payload) {
  const response = await fetch('/api/auth/register', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function getCurrentUser() {
  return parseResponse(await authRequest('/api/auth/me'))
}

export async function changePassword(payload) {
  const response = await authRequest('/api/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function deleteAccount(payload) {
  const response = await authRequest('/api/auth/delete-account', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}
