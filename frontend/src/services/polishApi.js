import { authFetch } from './request'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '智能润色请求失败，请稍后重试。')
  }

  return data
}

export async function getPolishConfig() {
  const response = await authFetch('/api/polish/config', {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

export async function runPolish(payload) {
  const response = await authFetch('/api/polish', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function importPolishFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await authFetch('/api/polish/import-file', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    body: formData,
  })

  return parseResponse(response)
}

export async function createSummary(payload) {
  const response = await authFetch('/api/polish/summary', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function getPolishRecords() {
  const response = await authFetch('/api/polish/records', {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

export async function getPolishRecordDetail(recordId) {
  const response = await authFetch(`/api/polish/records/${recordId}`, {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}
