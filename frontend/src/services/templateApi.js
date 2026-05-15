import { authFetch } from './request'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '润色模板请求失败，请稍后重试。')
  }

  return data
}

export async function getPolishTemplates() {
  const response = await authFetch('/api/polish/templates', {
    headers: { Accept: 'application/json' },
  })

  return parseResponse(response)
}

export async function getPolishTemplateDetail(templateId) {
  const response = await authFetch(`/api/polish/templates/${templateId}`, {
    headers: { Accept: 'application/json' },
  })

  return parseResponse(response)
}

export async function createPolishTemplate(payload) {
  const response = await authFetch('/api/polish/templates', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function updatePolishTemplate(templateId, payload) {
  const response = await authFetch(`/api/polish/templates/${templateId}`, {
    method: 'PUT',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function togglePolishTemplateEnabled(templateId, enabled) {
  const response = await authFetch(`/api/polish/templates/${templateId}/toggle-enabled`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ enabled }),
  })

  return parseResponse(response)
}

export async function deletePolishTemplate(templateId) {
  const response = await authFetch(`/api/polish/templates/${templateId}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  })

  return parseResponse(response)
}
