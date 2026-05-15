import { authFetch } from './request'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '设置数据请求失败，请稍后重试。')
  }

  return data
}

export async function getSettings() {
  const response = await authFetch('/api/settings', {
    headers: { Accept: 'application/json' },
  })

  return parseResponse(response)
}

export async function updateSettingsProfile(payload) {
  const response = await authFetch('/api/settings/profile', {
    method: 'PUT',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function updateSettingsNotifications(notifications) {
  const response = await authFetch('/api/settings/notifications', {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ notifications }),
  })

  return parseResponse(response)
}
