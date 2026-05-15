import { authFetch } from './request'
import { clearAuthSession, getAuthToken } from './authApi'

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '批量处理数据加载失败，请稍后重试。')
  }

  return data
}

export async function getBatchProcessing() {
  const response = await authFetch('/api/batch-processing', {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

export async function runBatchPolish(payload) {
  const response = await authFetch('/api/batch-processing/polish', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function confirmBatchProcessing(payload) {
  const response = await authFetch('/api/batch-processing/confirm', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function deleteBatchProcessing(payload) {
  const response = await authFetch('/api/batch-processing/delete', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function recordBatchTemplateEvent(payload) {
  const response = await authFetch('/api/batch-processing/template-event', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function recordBatchExport(payload) {
  const response = await authFetch('/api/batch-processing/export', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function getBatchResult(documentId) {
  const response = await authFetch(`/api/batch-processing/${encodeURIComponent(documentId)}/result`, {
    headers: {
      Accept: 'application/json',
    },
  })

  return parseResponse(response)
}

function parseDownloadFilename(contentDisposition) {
  const header = String(contentDisposition || '')
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim())
    } catch {
      return utf8Match[1].trim()
    }
  }

  const plainMatch = header.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1]?.trim() || ''
}

function isAbortError(error) {
  return error instanceof DOMException && error.name === 'AbortError'
}

function ensureFileSystemAccessSupport(methodName, message) {
  if (typeof window === 'undefined' || typeof window[methodName] !== 'function') {
    throw new Error(message)
  }
}

function splitFilename(filename) {
  const normalized = String(filename || '').trim() || 'batch-result'
  const dotIndex = normalized.lastIndexOf('.')
  if (dotIndex <= 0 || dotIndex === normalized.length - 1) {
    return {
      basename: normalized,
      extension: '',
    }
  }

  return {
    basename: normalized.slice(0, dotIndex),
    extension: normalized.slice(dotIndex),
  }
}

function buildPickerTypes(filename) {
  const extension = splitFilename(filename).extension.toLowerCase()
  if (extension === '.docx') {
    return [
      {
        description: 'Word Document',
        accept: {
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
        },
      },
    ]
  }
  if (extension === '.txt') {
    return [
      {
        description: 'Text File',
        accept: {
          'text/plain': ['.txt'],
        },
      },
    ]
  }
  return []
}

async function writeBlobToFileHandle(fileHandle, blob) {
  const writable = await fileHandle.createWritable()
  try {
    await writable.write(blob)
  } finally {
    await writable.close()
  }
}

async function resolveUniqueDirectoryFilename(directoryHandle, filename) {
  const { basename, extension } = splitFilename(filename)
  let candidate = `${basename}${extension}`
  let suffix = 1

  while (true) {
    try {
      await directoryHandle.getFileHandle(candidate)
      candidate = `${basename} (${suffix})${extension}`
      suffix += 1
    } catch (error) {
      if (error instanceof DOMException && error.name === 'NotFoundError') {
        return candidate
      }
      throw error
    }
  }
}

export async function downloadBatchResult(documentId, fallbackFilename = 'batch-result') {
  const response = await authFetch(`/api/batch-processing/${encodeURIComponent(documentId)}/download`, {
    headers: {
      Accept: 'application/octet-stream',
    },
  })

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const detail = data && typeof data === 'object' ? data.detail : ''
    throw new Error(detail || '下载润色结果失败，请稍后重试。')
  }

  const filename = parseDownloadFilename(response.headers.get('Content-Disposition')) || fallbackFilename
  const blob = await response.blob()
  return { filename, blob }
}

export async function saveBatchResultAs(documentId, fallbackFilename = 'batch-result') {
  ensureFileSystemAccessSupport('showSaveFilePicker', '当前浏览器不支持指定保存地址。')

  const payload = await downloadBatchResult(documentId, fallbackFilename)
  try {
    const fileHandle = await window.showSaveFilePicker({
      suggestedName: payload.filename,
      types: buildPickerTypes(payload.filename),
    })
    await writeBlobToFileHandle(fileHandle, payload.blob)
    return { filename: payload.filename }
  } catch (error) {
    if (isAbortError(error)) {
      throw new Error('已取消选择保存位置。')
    }
    throw error
  }
}

export async function pickBatchDownloadDirectory() {
  ensureFileSystemAccessSupport('showDirectoryPicker', '当前浏览器不支持选择下载目录。')

  try {
    return await window.showDirectoryPicker({
      mode: 'readwrite',
    })
  } catch (error) {
    if (isAbortError(error)) {
      throw new Error('已取消选择下载目录。')
    }
    throw error
  }
}

export async function saveBatchResultToDirectory(directoryHandle, documentId, fallbackFilename = 'batch-result') {
  const payload = await downloadBatchResult(documentId, fallbackFilename)
  const targetName = await resolveUniqueDirectoryFilename(directoryHandle, payload.filename)
  const fileHandle = await directoryHandle.getFileHandle(targetName, { create: true })
  await writeBlobToFileHandle(fileHandle, payload.blob)
  return { filename: targetName }
}

export async function importBatchFiles(files, options = {}) {
  const formData = new FormData()
  Array.from(files || []).forEach((file) => {
    formData.append('files', file)
  })

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/batch-processing/import')
    xhr.setRequestHeader('Accept', 'application/json')

    const token = getAuthToken()
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || typeof options.onProgress !== 'function') {
        return
      }

      const percent = Math.min(100, Math.round((event.loaded / event.total) * 100))
      options.onProgress(percent)
    }

    xhr.upload.onload = () => {
      if (typeof options.onProgress === 'function') {
        options.onProgress(100)
      }
    }

    xhr.onload = () => {
      let data = null
      try {
        data = JSON.parse(xhr.responseText || 'null')
      } catch {
        data = null
      }
      if (xhr.status === 401) {
        clearAuthSession()
      }

      if (xhr.status < 200 || xhr.status >= 300) {
        const detail = data && typeof data === 'object' ? data.detail : ''
        reject(new Error(detail || '批量处理数据加载失败，请稍后重试。'))
        return
      }

      resolve(data)
    }

    xhr.onerror = () => {
      reject(new Error('批量导入请求失败，请检查网络后重试。'))
    }

    xhr.onabort = () => {
      reject(new Error('批量导入已取消。'))
    }

    xhr.send(formData)
  })
}
