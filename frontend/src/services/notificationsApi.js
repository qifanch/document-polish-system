import { authFetch } from './request'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '通知数据加载失败，请稍后重试。')
  }

  return data
}

export async function getNotifications() {
  const response = await authFetch('/api/notifications', {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

export async function markNotificationRead(id) {
  const response = await authFetch(`/api/notifications/${id}/read`, {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}
