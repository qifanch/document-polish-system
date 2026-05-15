import { authFetch } from './request'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '加载统计数据失败，请稍后重试。')
  }

  return data
}

export async function getStatistics(params = {}) {
  const search = new URLSearchParams()

  if (params.rangeStart) {
    search.set('rangeStart', params.rangeStart)
  }

  if (params.rangeEnd) {
    search.set('rangeEnd', params.rangeEnd)
  }

  if (params.granularity) {
    search.set('granularity', params.granularity)
  }

  const query = search.toString()
  const response = await authFetch(`/api/statistics${query ? `?${query}` : ''}`, {
    headers: { Accept: 'application/json' },
  })

  return parseResponse(response)
}
