import { authFetch } from './request'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '首页数据加载失败，请稍后重试。')
  }

  return data
}

export async function getDashboard() {
  const response = await authFetch('/api/dashboard', {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

export async function recordDashboardExport(source = '') {
  const response = await authFetch('/api/dashboard/export-events', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ source }),
  })

  return parseResponse(response)
}
