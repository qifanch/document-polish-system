import { clearAuthSession, getAuthToken } from './authApi'

export async function authFetch(url, options = {}) {
  const token = getAuthToken()
  const headers = {
    ...(options.headers || {}),
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    clearAuthSession()
  }

  return response
}
