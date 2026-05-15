import { authFetch } from './request'

export const USAGE_SUMMARY_UPDATED_EVENT = 'document-polish-usage-summary-updated'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '今日使用次数加载失败，请稍后重试。')
  }

  return data
}

export async function getTodayUsage() {
  const response = await authFetch('/api/usage/today', {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

export function notifyUsageSummaryUpdated() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(USAGE_SUMMARY_UPDATED_EVENT))
  }
}
