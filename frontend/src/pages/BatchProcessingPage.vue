<script setup>
import { computed, onActivated, onMounted, onUnmounted, ref, watch } from 'vue'
import PageLoadingState from '../components/PageLoadingState.vue'
import {
  confirmBatchProcessing,
  deleteBatchProcessing,
  getBatchProcessing,
  getBatchResult,
  importBatchFiles,
  pickBatchDownloadDirectory,
  recordBatchExport,
  recordBatchTemplateEvent,
  runBatchPolish,
  saveBatchResultAs,
  saveBatchResultToDirectory,
} from '../services/batchProcessingApi'
import { getPolishConfig } from '../services/polishApi'
import { notifyUsageSummaryUpdated } from '../services/usageApi'

const TEMPLATE_OVERRIDE_STORAGE_KEY = 'document-polish:batch-template-overrides'
const DISTRIBUTION_COLORS = ['#2f6df6', '#35c28c', '#8b6ef6', '#5eb4ff', '#f5a54b', '#b4bccb']
const IMPORT_SUCCESS_HOLD_MS = 1200
const IMPORT_FADE_DURATION_MS = 320
const documentInfoCollator = new Intl.Collator('zh-Hans-CN', {
  numeric: true,
  sensitivity: 'base',
})

const loading = ref(true)
const error = ref('')
const batchData = ref({
  summary: [],
  distribution: {
    total: 0,
    items: [],
  },
  documents: [],
  recentActivities: [],
  templates: [],
})
const enabledTemplates = ref([])
const templateOverrides = ref(readTemplateOverrides())

const searchQuery = ref('')
const fileTypeFilter = ref('')
const statusFilter = ref('')
const templateFilter = ref('')
const uploadTimeFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(5)
const selectedIds = ref([])
const bulkMenuOpen = ref(false)
const bulkTemplateMenuOpen = ref(false)
const rowMenuId = ref('')
const rowTemplateMenuId = ref('')
const drawerOpen = ref(false)
const drawerMode = ref('activities')
const selectedDocument = ref(null)
const batchFileInput = ref(null)
const importingFiles = ref(false)
const importMessage = ref('')
const importProgress = ref(0)
const importPhase = ref('')
const importFeedbackVisible = ref(false)
const importFeedbackFading = ref(false)
const batchActionMessage = ref('')
const polishingBatch = ref(false)
const resultLoading = ref(false)
const resultError = ref('')
const resultDetail = ref(null)
let activatedOnce = false
let importFeedbackFadeTimer = null
let importFeedbackHideTimer = null

const statusMeta = {
  completed: { label: '已完成', className: 'is-completed' },
  polishing: { label: '润色中', className: 'is-polishing' },
  pending: { label: '待确认', className: 'is-pending' },
  unprocessed: { label: '未润色', className: 'is-unprocessed' },
}

const fileTypeMeta = {
  Word: { icon: 'W', className: 'word' },
  PDF: { icon: 'P', className: 'pdf' },
  TXT: { icon: 'T', className: 'txt' },
}

const activityMeta = {
  completed: { icon: '✓', className: 'is-completed' },
  confirm: { icon: '◔', className: 'is-pending' },
  export: { icon: '⇩', className: 'is-export' },
  upload: { icon: '↑', className: 'is-upload' },
}

activityMeta.polish = activityMeta.confirm
activityMeta.template = { icon: 'T', className: 'is-pending' }
activityMeta.delete = { icon: 'D', className: 'is-completed' }

const activityFilenameCache = new WeakMap()

const summaryCards = computed(() => batchData.value.summary || [])
const documents = computed(() => batchData.value.documents || [])
const recentActivities = computed(() => batchData.value.recentActivities || [])
const templateMenuOptions = computed(() => enabledTemplates.value)
const distribution = computed(() => buildDistributionFromDocuments(documents.value))

const bulkActions = computed(() => [
  { key: 'import', label: '批量导入' },
  { key: 'template', label: '选择模板', children: templateMenuOptions.value },
  { key: 'polish', label: '批量润色' },
  { key: 'confirm', label: '批量确认' },
  { key: 'download', label: '批量下载' },
  { key: 'delete', label: '批量删除' },
])

const rowActions = computed(() => [
  { key: 'template', label: '选择模板', children: templateMenuOptions.value },
  { key: 'polish', label: '立即润色' },
  { key: 'confirm', label: '确认' },
  { key: 'delete', label: '删除' },
])

const fileTypeOptions = computed(() =>
  [...new Set(documents.value.map((item) => item.fileType).filter(Boolean))],
)

const templateOptions = computed(() =>
  [...new Set(documents.value.map((item) => item.templateType).filter(Boolean))],
)

const filteredDocuments = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()

  return documents.value
    .filter((item) => {
      const matchesKeyword =
        !keyword ||
        item.title.toLowerCase().includes(keyword) ||
        (item.category || '').toLowerCase().includes(keyword) ||
        (item.templateType || '').toLowerCase().includes(keyword)

      const matchesFileType = !fileTypeFilter.value || item.fileType === fileTypeFilter.value
      const matchesStatus = !statusFilter.value || item.status === statusFilter.value
      const matchesTemplate = !templateFilter.value || item.templateType === templateFilter.value
      const matchesUploadTime = !uploadTimeFilter.value || withinTimeRange(item.updatedAt, uploadTimeFilter.value)

      return matchesKeyword && matchesFileType && matchesStatus && matchesTemplate && matchesUploadTime
    })
    .slice()
    .sort(compareDocumentInfo)
})

const pageCount = computed(() => Math.max(1, Math.ceil(filteredDocuments.value.length / pageSize.value)))

const pagedDocuments = computed(() => {
  const page = Math.min(currentPage.value, pageCount.value)
  const start = (page - 1) * pageSize.value
  return filteredDocuments.value.slice(start, start + pageSize.value)
})

const pageNumbers = computed(() =>
  Array.from({ length: pageCount.value }, (_, index) => index + 1),
)

const selectedOnPage = computed(() => pagedDocuments.value.map((item) => item.id))

const allPageSelected = computed(
  () =>
    selectedOnPage.value.length > 0 &&
    selectedOnPage.value.every((id) => selectedIds.value.includes(id)),
)

const donutSegments = computed(() => {
  const total = distribution.value.total || 0
  const radius = 42
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (distribution.value.items || []).map((item) => {
    const length = total ? (item.count / total) * circumference : 0
    const segment = {
      ...item,
      dasharray: `${length} ${circumference - length}`,
      dashoffset: -offset,
    }
    offset += length
    return segment
  })
})

const drawerTitle = computed(() =>
  drawerMode.value === 'activities' ? '最近操作记录' : '查看结果',
)

const drawerDocument = computed(() => ({
  ...(selectedDocument.value || {}),
  ...(resultDetail.value || {}),
}))

function withinTimeRange(updatedAt, range) {
  const parsed = Date.parse(String(updatedAt).replace(' ', 'T'))
  if (Number.isNaN(parsed)) {
    return true
  }

  const diff = Date.now() - parsed
  const day = 24 * 60 * 60 * 1000

  if (range === '24h') {
    return diff <= day
  }
  if (range === '7d') {
    return diff <= 7 * day
  }
  if (range === '30d') {
    return diff <= 30 * day
  }

  return true
}

function formatWordCount(value) {
  return `${Number(value || 0).toLocaleString()} 字`
}

function resolveStatusMeta(status) {
  return statusMeta[status] || statusMeta.unprocessed
}

function resolveFileTypeMeta(fileType) {
  return fileTypeMeta[fileType] || { icon: 'F', className: 'word' }
}

function resolveActivityMeta(type) {
  return activityMeta[type] || activityMeta.completed
}

function normalizeTemplateMenuOptions(templates) {
  return (templates || [])
    .map((template, index) => {
      const label = String(template?.label || template?.name || template?.key || '').trim()
      if (!label) {
        return null
      }
      return {
        key: String(template?.key || template?.id || label || index),
        label,
      }
    })
    .filter(Boolean)
}

function resolveTemplateKeyByLabel(label) {
  const normalizedLabel = String(label || '').trim()
  if (!normalizedLabel || normalizedLabel === '未选择') {
    return ''
  }

  return templateMenuOptions.value.find((item) => item.label === normalizedLabel)?.key || ''
}

function normalizeTemplateSelection(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const label = String(value.label || value.templateLabel || value.name || '').trim()
    const key = String(value.key || value.templateKey || resolveTemplateKeyByLabel(label)).trim()
    return label ? { key, label } : null
  }

  const label = String(value || '').trim()
  if (!label) {
    return null
  }
  return {
    key: resolveTemplateKeyByLabel(label),
    label,
  }
}

function readTemplateOverrides() {
  try {
    const raw = window.localStorage.getItem(TEMPLATE_OVERRIDE_STORAGE_KEY)
    if (!raw) {
      return {}
    }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {}
    }

    return Object.fromEntries(
      Object.entries(parsed)
        .map(([documentId, templateSelection]) => [String(documentId), normalizeTemplateSelection(templateSelection)])
        .filter(([, templateSelection]) => Boolean(templateSelection)),
    )
  } catch {
    return {}
  }
}

function writeTemplateOverrides(overrides) {
  try {
    window.localStorage.setItem(TEMPLATE_OVERRIDE_STORAGE_KEY, JSON.stringify(overrides))
  } catch {
    // ignore storage failures
  }
}

function normalizeTemplateType(templateType) {
  return String(templateType || '').trim() || '未选择'
}

function mergeDocumentsWithTemplateOverrides(documentList, overrides = templateOverrides.value) {
  return (documentList || []).map((document) => {
    const override = normalizeTemplateSelection(overrides[String(document?.id || '')])
    const templateType = normalizeTemplateType(document?.templateType)
    if (!override) {
      return {
        ...document,
        templateType,
        templateKey: document?.templateKey || resolveTemplateKeyByLabel(templateType),
      }
    }

    return {
      ...document,
      templateType: normalizeTemplateType(override.label),
      templateKey: override.key,
    }
  })
}

function pruneTemplateOverrides(validDocumentIds) {
  const nextOverrides = Object.fromEntries(
    Object.entries(templateOverrides.value).filter(([documentId]) => validDocumentIds.has(documentId)),
  )
  templateOverrides.value = nextOverrides
  writeTemplateOverrides(nextOverrides)
  return nextOverrides
}

function applyTemplateOverridesToBatchData(data) {
  const mergedDocuments = mergeDocumentsWithTemplateOverrides(data?.documents || [])
  pruneTemplateOverrides(new Set(mergedDocuments.map((item) => String(item.id))))

  return {
    ...data,
    documents: mergeDocumentsWithTemplateOverrides(data?.documents || []),
  }
}

function reconcileSelectedIds(documentList = documents.value) {
  const validIds = new Set((documentList || []).map((item) => String(item?.id || '')).filter(Boolean))
  selectedIds.value = Array.from(
    new Set(selectedIds.value.map((id) => String(id || '')).filter((id) => validIds.has(id))),
  )
}

function buildDistributionFromDocuments(documentList) {
  const counts = {}

  for (const item of documentList || []) {
    const label = normalizeTemplateType(item?.templateType)
    counts[label] = (counts[label] || 0) + 1
  }

  const total = (documentList || []).length
  const items = Object.entries(counts)
    .sort((left, right) => right[1] - left[1])
    .map(([label, count], index) => ({
      label,
      count,
      percent: total ? `${((count / total) * 100).toFixed(1)}%` : '0%',
      color: DISTRIBUTION_COLORS[index % DISTRIBUTION_COLORS.length],
    }))

  return {
    total,
    items,
  }
}

function getActivityDetail(activity) {
  if (!activity || typeof activity !== 'object' || !activity.detail) {
    return null
  }

  try {
    const detail = JSON.parse(activity.detail)
    return detail && typeof detail === 'object' ? detail : null
  } catch {
    return null
  }
}

function getActivityFilenames(activity) {
  if (!activity || typeof activity !== 'object') {
    return []
  }

  const cached = activityFilenameCache.get(activity)
  if (cached) {
    return cached
  }

  const detail = getActivityDetail(activity)
  const filenames = Array.from(
    new Set(
      [
        ...(Array.isArray(activity.importedFilenames) ? activity.importedFilenames : []),
        ...(Array.isArray(activity.filenames) ? activity.filenames : []),
        ...(Array.isArray(detail?.filenames) ? detail.filenames : []),
      ]
        .map((item) => String(item || '').trim())
        .filter(Boolean),
    ),
  )

  activityFilenameCache.set(activity, filenames)
  return filenames
}

function hasActivityFilenames(activity) {
  return getActivityFilenames(activity).length > 0
}

function attachImportedFilenamesToLatestActivity(data, filenames) {
  const cleanedFilenames = Array.from(
    new Set((filenames || []).map((item) => String(item || '').trim()).filter(Boolean)),
  )
  if (!cleanedFilenames.length || !Array.isArray(data?.recentActivities)) {
    return data
  }

  const activityIndex = data.recentActivities.findIndex((item) => item?.type === 'upload')
  if (activityIndex < 0) {
    return data
  }

  const nextActivities = [...data.recentActivities]
  nextActivities[activityIndex] = {
    ...nextActivities[activityIndex],
    importedFilenames: cleanedFilenames,
    detail: nextActivities[activityIndex].detail || JSON.stringify({ filenames: cleanedFilenames }),
  }
  return {
    ...data,
    recentActivities: nextActivities,
  }
}

function updateRecentActivities(recentActivityItems) {
  if (!Array.isArray(recentActivityItems)) {
    return
  }

  batchData.value = {
    ...batchData.value,
    recentActivities: recentActivityItems,
  }
}

function canViewResult(document) {
  if (!document) {
    return false
  }

  if (document.status === 'unprocessed') {
    return false
  }

  return Boolean(document.hasResult)
}

function canConfirmDocument(document) {
  return Boolean(document) && document.status === 'pending' && document.hasResult
}

function canDownloadDocument(document) {
  return Boolean(document) && ['pending', 'completed'].includes(document.status) && document.hasResult
}

function canPolishDocument(document) {
  return Boolean(document) && !['completed', 'polishing'].includes(document.status)
}

async function loadBatchProcessing(options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    const [batchResult, configResult] = await Promise.all([
      getBatchProcessing(),
      getPolishConfig(),
    ])
    enabledTemplates.value = normalizeTemplateMenuOptions(configResult?.templates)
    const nextData = applyTemplateOverridesToBatchData(batchResult)
    batchData.value = nextData
    reconcileSelectedIds(nextData.documents)
    if (silent) {
      error.value = ''
    }
  } catch (err) {
    error.value = err.message
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function resetFilters() {
  searchQuery.value = ''
  fileTypeFilter.value = ''
  statusFilter.value = ''
  templateFilter.value = ''
  uploadTimeFilter.value = ''
  currentPage.value = 1
  selectedIds.value = []
  closeAllMenus()
}

function toggleSelectAll() {
  if (allPageSelected.value) {
    selectedIds.value = selectedIds.value.filter((id) => !selectedOnPage.value.includes(id))
    return
  }

  const merged = new Set([...selectedIds.value, ...selectedOnPage.value])
  selectedIds.value = [...merged]
}

function toggleRowSelection(id) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
    return
  }

  selectedIds.value = [...selectedIds.value, id]
}

function goToPage(page) {
  currentPage.value = page
  rowMenuId.value = ''
  rowTemplateMenuId.value = ''
}

function closeAllMenus() {
  bulkMenuOpen.value = false
  bulkTemplateMenuOpen.value = false
  rowMenuId.value = ''
  rowTemplateMenuId.value = ''
}

function toggleBulkMenu() {
  bulkMenuOpen.value = !bulkMenuOpen.value
  bulkTemplateMenuOpen.value = false
  rowMenuId.value = ''
  rowTemplateMenuId.value = ''
}

function toggleBulkTemplateMenu() {
  bulkTemplateMenuOpen.value = !bulkTemplateMenuOpen.value
}

function openBatchFilePicker() {
  if (importingFiles.value) {
    return
  }

  closeAllMenus()
  batchFileInput.value?.click()
}

function formatImportMessage(result) {
  const imported = Number(result?.imported || 0)
  const failed = Number(result?.failed || 0)

  if (imported && failed) {
    return `已导入 ${imported} 个文件，${failed} 个文件失败。`
  }

  if (imported) {
    return `已导入 ${imported} 个文件。`
  }

  if (failed) {
    const firstError = result?.errors?.[0]?.error
    return firstError ? `导入失败：${firstError}` : '导入失败，请检查文件格式。'
  }

  return '没有可导入的文件。'
}

function clearImportFeedbackTimers() {
  if (importFeedbackFadeTimer !== null) {
    window.clearTimeout(importFeedbackFadeTimer)
    importFeedbackFadeTimer = null
  }
  if (importFeedbackHideTimer !== null) {
    window.clearTimeout(importFeedbackHideTimer)
    importFeedbackHideTimer = null
  }
}

function scheduleImportFeedbackFadeout() {
  clearImportFeedbackTimers()
  importFeedbackFading.value = false
  importFeedbackVisible.value = true

  importFeedbackFadeTimer = window.setTimeout(() => {
    importFeedbackFading.value = true
    importFeedbackHideTimer = window.setTimeout(() => {
      resetImportFeedback()
    }, IMPORT_FADE_DURATION_MS)
  }, IMPORT_SUCCESS_HOLD_MS)
}

function resetImportFeedback() {
  clearImportFeedbackTimers()
  importMessage.value = ''
  importProgress.value = 0
  importPhase.value = ''
  importFeedbackVisible.value = false
  importFeedbackFading.value = false
}

function beginImportFeedback() {
  clearImportFeedbackTimers()
  importFeedbackVisible.value = true
  importFeedbackFading.value = false
}

function compareDocumentInfo(left, right) {
  const titleComparison = documentInfoCollator.compare(
    String(left?.title || ''),
    String(right?.title || ''),
  )
  if (titleComparison !== 0) {
    return titleComparison
  }

  const categoryComparison = documentInfoCollator.compare(
    String(left?.category || ''),
    String(right?.category || ''),
  )
  if (categoryComparison !== 0) {
    return categoryComparison
  }

  return documentInfoCollator.compare(String(left?.id || ''), String(right?.id || ''))
}

async function handleBatchFileImport(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) {
    return
  }
  const importedFilenames = files.map((file) => file.name || 'imported-file')

  importingFiles.value = true
  resetImportFeedback()
  beginImportFeedback()
  batchActionMessage.value = ''
  importPhase.value = '正在上传文件...'
  error.value = ''

  try {
    const result = await importBatchFiles(files, {
      onProgress(percent) {
        importProgress.value = percent
        importPhase.value = percent >= 100 ? '文件上传完成，正在解析并写入批量列表...' : '正在上传文件...'
      },
    })
    if (result?.data) {
      const nextData = applyTemplateOverridesToBatchData(
        attachImportedFilenamesToLatestActivity(result.data, importedFilenames),
      )
      batchData.value = nextData
      reconcileSelectedIds(nextData.documents)
    } else {
      const freshData = await getBatchProcessing()
      const nextData = applyTemplateOverridesToBatchData(
        attachImportedFilenamesToLatestActivity(freshData, importedFilenames),
      )
      batchData.value = nextData
      reconcileSelectedIds(nextData.documents)
    }
    currentPage.value = 1
    importProgress.value = 100
    importPhase.value = '导入完成'
    importMessage.value = formatImportMessage(result)
    scheduleImportFeedbackFadeout()
  } catch (err) {
    importPhase.value = '导入失败'
    importMessage.value = err.message
    importFeedbackVisible.value = true
    importFeedbackFading.value = false
  } finally {
    importingFiles.value = false
    event.target.value = ''
  }
}

function applyTemplateToDocumentIds(documentIds, template) {
  const normalizedIds = Array.from(new Set((documentIds || []).map((id) => String(id || '')).filter(Boolean)))
  if (!normalizedIds.length) {
    closeAllMenus()
    return null
  }

  const selection = normalizeTemplateSelection(template)
  if (!selection) {
    closeAllMenus()
    return null
  }
  const nextTemplateType = normalizeTemplateType(selection.label)
  const targetIdSet = new Set(normalizedIds)
  const nextOverrides = { ...templateOverrides.value }

  normalizedIds.forEach((id) => {
    nextOverrides[id] = selection
  })

  const nextDocuments = documents.value.map((document) =>
    targetIdSet.has(String(document.id))
      ? {
          ...document,
          templateType: nextTemplateType,
          templateKey: selection.key,
        }
      : document,
  )

  templateOverrides.value = nextOverrides
  writeTemplateOverrides(nextOverrides)
  batchData.value = {
    ...batchData.value,
    documents: nextDocuments,
  }

  if (selectedDocument.value && targetIdSet.has(String(selectedDocument.value.id))) {
    selectedDocument.value = nextDocuments.find((item) => item.id === selectedDocument.value.id) || selectedDocument.value
  }

  closeAllMenus()
  return {
    selection: {
      key: selection.key,
      label: nextTemplateType,
    },
    documents: nextDocuments.filter((document) => targetIdSet.has(String(document.id))),
  }
}

async function handleBulkTemplateSelect(template) {
  const result = applyTemplateToDocumentIds(selectedIds.value, template)
  if (!result) {
    return
  }

  try {
    await logTemplateSelection(result.documents, result.selection)
  } catch (err) {
    batchActionMessage.value = `模板已更新，但最近操作记录失败：${err.message || '请稍后重试。'}`
  }
}

async function handleRowTemplateSelect(documentId, template) {
  const result = applyTemplateToDocumentIds([documentId], template)
  if (!result) {
    return
  }

  try {
    await logTemplateSelection(result.documents, result.selection)
  } catch (err) {
    batchActionMessage.value = `模板已更新，但最近操作记录失败：${err.message || '请稍后重试。'}`
  }
}

function resolveDocumentTemplateSelection(document) {
  const override = normalizeTemplateSelection(templateOverrides.value[String(document?.id || '')])
  if (override?.label && override?.key) {
    return override
  }

  const label = normalizeTemplateType(override?.label || document?.templateType)
  return {
    key: override?.key || document?.templateKey || resolveTemplateKeyByLabel(label),
    label,
  }
}

function getSelectedDocuments() {
  const selectedIdSet = new Set(selectedIds.value.map((id) => String(id)))
  return documents.value.filter((item) => selectedIdSet.has(String(item.id)))
}

function updateLocalDocumentState(documentIds, updater) {
  const targetIdSet = new Set((documentIds || []).map((id) => String(id || '')).filter(Boolean))
  if (!targetIdSet.size) {
    return
  }

  const nextDocuments = documents.value.map((document) => {
    const documentId = String(document?.id || '')
    if (!targetIdSet.has(documentId)) {
      return document
    }
    return updater(document)
  })

  batchData.value = {
    ...batchData.value,
    documents: nextDocuments,
  }

  if (selectedDocument.value && targetIdSet.has(String(selectedDocument.value.id || ''))) {
    selectedDocument.value =
      nextDocuments.find((item) => String(item.id) === String(selectedDocument.value.id || '')) || selectedDocument.value
  }
}

function buildBatchPolishPayloadItems(targetDocuments) {
  return targetDocuments.map((document) => {
    const template = resolveDocumentTemplateSelection(document)
    return {
      documentId: String(document.id),
      templateKey: template.key,
      templateLabel: template.label,
    }
  })
}

function validateBatchPolishDocuments(targetDocuments) {
  if (!targetDocuments.length) {
    return '请先选择需要批量润色的文件。'
  }

  const completedDocument = targetDocuments.find((document) => document.status === 'completed')
  if (completedDocument) {
    return `已确认的文档不可再次润色：${completedDocument.title}`
  }

  const pdfDocument = targetDocuments.find((document) => document.fileType === 'PDF')
  if (pdfDocument) {
    return `PDF 文件不支持智能润色或批量处理：${pdfDocument.title}`
  }

  const missingTemplate = targetDocuments.find((document) => {
    const template = resolveDocumentTemplateSelection(document)
    return !template.key || !template.label || template.label === '未选择'
  })
  if (missingTemplate) {
    return `请先为文件选择润色模板：${missingTemplate.title}`
  }

  return ''
}

function formatBatchPolishMessage(result) {
  const processed = Number(result?.processed || 0)
  const failed = Number(result?.failed || 0)
  if (processed && failed) {
    const firstError = result?.errors?.[0]?.error
    return firstError
      ? `已润色 ${processed} 个文件，${failed} 个失败：${firstError}`
      : `已润色 ${processed} 个文件，${failed} 个失败。`
  }
  if (processed) {
    return `已提交 ${processed} 个文件的润色结果，请在列表中查看。`
  }
  const firstError = result?.errors?.[0]?.error
  return firstError ? `批量润色失败：${firstError}` : '批量润色失败，请稍后重试。'
}

function formatBatchConfirmMessage(result) {
  const processed = Number(result?.processed || 0)
  const failed = Number(result?.failed || 0)
  if (processed && failed) {
    const firstError = result?.errors?.[0]?.error
    return firstError
      ? `已确认 ${processed} 个文件，${failed} 个失败：${firstError}`
      : `已确认 ${processed} 个文件，${failed} 个失败。`
  }
  if (processed) {
    return `已确认 ${processed} 个文件。`
  }
  const firstError = result?.errors?.[0]?.error
  return firstError ? `批量确认失败：${firstError}` : '批量确认失败，请稍后重试。'
}

function getConfirmableDocuments(targetDocuments) {
  return (targetDocuments || []).filter((document) => canConfirmDocument(document))
}

function getDownloadableDocuments(targetDocuments) {
  return (targetDocuments || []).filter((document) => canDownloadDocument(document))
}

function buildDeletePayload(targetDocuments) {
  return (targetDocuments || []).map((document) => ({
    documentId: String(document.id),
  }))
}

function buildDeleteTargetLabel(targetDocuments) {
  const count = (targetDocuments || []).length
  if (count <= 1) {
    return '这条文档记录'
  }
  return `这 ${count} 条文档记录`
}

function confirmDeleteDocuments(targetDocuments) {
  if (typeof window === 'undefined' || typeof window.confirm !== 'function') {
    return true
  }
  return window.confirm(`确认删除${buildDeleteTargetLabel(targetDocuments)}吗？这会同时删除后端文件。`)
}

function formatBatchDeleteMessage(result) {
  const deleted = Number(result?.deleted || 0)
  const failed = Number(result?.failed || 0)
  const firstError = result?.errors?.[0]?.error

  if (deleted && failed) {
    return firstError
      ? `已删除 ${deleted} 条，失败 ${failed} 条：${firstError}`
      : `已删除 ${deleted} 条，失败 ${failed} 条。`
  }
  if (deleted) {
    return `已删除 ${deleted} 条批量文档记录，并清理对应后端文件。`
  }
  return firstError ? `删除失败：${firstError}` : '删除失败，请稍后重试。'
}

function syncBatchDataAfterMutation(data, options = {}) {
  const nextData = applyTemplateOverridesToBatchData(data)
  batchData.value = nextData
  reconcileSelectedIds(nextData.documents)
  const nextIdSet = new Set((nextData.documents || []).map((item) => String(item.id || '')))
  const deletedIdSet = options.requestedIdSet
    ? new Set([...options.requestedIdSet].filter((id) => !nextIdSet.has(id)))
    : options.deletedIdSet || new Set()

  if (deletedIdSet.size && selectedDocument.value) {
    const selectedId = String(selectedDocument.value.id || '')
    if (deletedIdSet.has(selectedId)) {
      closeDrawer()
    }
  }
}

function buildActivityDocumentsPayload(targetDocuments, filenameResolver) {
  return (targetDocuments || []).map((document) => ({
    documentId: String(document.id),
    title: String(document.title || ''),
    filename: typeof filenameResolver === 'function' ? String(filenameResolver(document) || '') : '',
  }))
}

async function logTemplateSelection(documentsToRecord, templateSelection) {
  const result = await recordBatchTemplateEvent({
    documents: buildActivityDocumentsPayload(documentsToRecord),
    templateKey: String(templateSelection?.key || ''),
    templateLabel: String(templateSelection?.label || ''),
  })
  updateRecentActivities(result?.recentActivities)
  return result
}

async function logBatchExport(documentsToRecord) {
  const result = await recordBatchExport({
    documents: documentsToRecord,
  })
  updateRecentActivities(result?.recentActivities)
  return result
}

function sanitizeDownloadFilenamePart(value) {
  const cleaned = String(value || '')
    .replace(/[\\/:*?"<>|]+/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^[._\s]+|[._\s]+$/g, '')
  return cleaned || 'batch-document'
}

function buildDownloadFallbackFilename(document) {
  const sourceName = String(document?.title || document?.originalFilename || '').trim()
  const fileType = String(document?.fileType || '').toUpperCase()
  const extension =
    String(document?.resultFilePath || '').match(/(\.[^./\\]+)$/)?.[1] ||
    (fileType === 'WORD' ? '.docx' : fileType === 'TXT' ? '.txt' : '.txt')
  const baseName = sanitizeDownloadFilenamePart(sourceName.replace(/\.[^./\\]+$/, ''))
  return `${baseName}_polished${extension}`
}

async function polishDocuments(targetDocuments) {
  const validationMessage = validateBatchPolishDocuments(targetDocuments)
  if (validationMessage) {
    batchActionMessage.value = validationMessage
    closeAllMenus()
    return
  }

  polishingBatch.value = true
  batchActionMessage.value = ''
  error.value = ''
  closeAllMenus()
  const payloadItems = buildBatchPolishPayloadItems(targetDocuments)
  const payloadById = new Map(payloadItems.map((item) => [String(item.documentId), item]))
  updateLocalDocumentState(
    payloadItems.map((item) => item.documentId),
    (document) => {
      const payloadItem = payloadById.get(String(document.id)) || {}
      return {
        ...document,
        templateType: normalizeTemplateType(payloadItem.templateLabel || document.templateType),
        templateKey: String(payloadItem.templateKey || document.templateKey || ''),
        status: 'polishing',
        hasResult: false,
      }
    },
  )

  try {
    const result = await runBatchPolish({
      documents: payloadItems,
    })
    if (result?.data) {
      const nextData = applyTemplateOverridesToBatchData(result.data)
      batchData.value = nextData
      reconcileSelectedIds(nextData.documents)
    } else {
      const nextData = applyTemplateOverridesToBatchData(await getBatchProcessing())
      batchData.value = nextData
      reconcileSelectedIds(nextData.documents)
    }
    batchActionMessage.value = formatBatchPolishMessage(result)
    notifyUsageSummaryUpdated()
  } catch (err) {
    updateLocalDocumentState(
      payloadItems.map((item) => item.documentId),
      (document) => ({
        ...document,
        status: 'unprocessed',
        hasResult: false,
      }),
    )
    batchActionMessage.value = err.message || '批量润色失败，请稍后重试。'
  } finally {
    polishingBatch.value = false
  }
}

async function confirmDocuments(targetDocuments, options = {}) {
  const confirmableDocuments = getConfirmableDocuments(targetDocuments)
  if (!confirmableDocuments.length) {
    batchActionMessage.value = '请先选择待确认的文档。'
    closeAllMenus()
    return false
  }

  polishingBatch.value = true
  batchActionMessage.value = ''
  error.value = ''
  closeAllMenus()

  try {
    const result = await confirmBatchProcessing({
      documents: confirmableDocuments.map((document) => ({
        documentId: String(document.id),
      })),
    })
    if (result?.data) {
      const nextData = applyTemplateOverridesToBatchData(result.data)
      batchData.value = nextData
      reconcileSelectedIds(nextData.documents)
    } else {
      const nextData = applyTemplateOverridesToBatchData(await getBatchProcessing())
      batchData.value = nextData
      reconcileSelectedIds(nextData.documents)
    }
    batchActionMessage.value = formatBatchConfirmMessage(result)
    notifyUsageSummaryUpdated()
    if (options.closeDrawer) {
      closeDrawer()
    }
    return true
  } catch (err) {
    batchActionMessage.value = err.message || '批量确认失败，请稍后重试。'
    return false
  } finally {
    polishingBatch.value = false
  }
}

async function downloadDocuments(targetDocuments) {
  const downloadableDocuments = getDownloadableDocuments(targetDocuments)
  const skippedCount = (targetDocuments || []).length - downloadableDocuments.length

  if (!downloadableDocuments.length) {
    batchActionMessage.value = '请先选择可下载的润色结果。'
    closeAllMenus()
    return
  }

  polishingBatch.value = true
  batchActionMessage.value = ''
  error.value = ''
  closeAllMenus()

  let downloadedCount = 0
  const exportedDocuments = []
  try {
    const directoryHandle = await pickBatchDownloadDirectory()
    for (const document of downloadableDocuments) {
      const result = await saveBatchResultToDirectory(
        directoryHandle,
        String(document.id),
        buildDownloadFallbackFilename(document),
      )
      exportedDocuments.push({
        documentId: String(document.id),
        title: String(document.title || ''),
        filename: String(result.filename || ''),
      })
      downloadedCount += 1
    }

    try {
      if (exportedDocuments.length) {
        await logBatchExport(exportedDocuments)
      }
    } catch (err) {
      batchActionMessage.value = `已保存 ${downloadedCount} 个文件，但最近操作记录失败：${err.message || '请稍后重试。'}`
      return
    }

    if (skippedCount > 0) {
      batchActionMessage.value = `已保存 ${downloadedCount} 个文件，已跳过 ${skippedCount} 个不可下载文件。`
    } else {
      batchActionMessage.value = `已保存 ${downloadedCount} 个润色结果文件。`
    }
  } catch (err) {
    batchActionMessage.value =
      downloadedCount > 0
        ? `已保存 ${downloadedCount} 个文件，后续保存失败：${err.message || '请稍后重试。'}`
        : err.message || '保存润色结果失败，请稍后重试。'
  } finally {
    polishingBatch.value = false
  }
}

async function downloadSingleDocument(document) {
  polishingBatch.value = true
  batchActionMessage.value = ''
  error.value = ''
  closeAllMenus()

  try {
    const result = await saveBatchResultAs(
      String(document.id),
      buildDownloadFallbackFilename(document),
    )
    try {
      await logBatchExport([
        {
          documentId: String(document.id),
          title: String(document.title || ''),
          filename: String(result.filename || ''),
        },
      ])
    } catch (logError) {
      batchActionMessage.value = `已保存文件：${result.filename}，但最近操作记录失败：${logError.message || '请稍后重试。'}`
      return
    }
    batchActionMessage.value = `已保存文件：${result.filename}`
  } catch (err) {
    batchActionMessage.value = err.message || '保存润色结果失败，请稍后重试。'
  } finally {
    polishingBatch.value = false
  }
}

async function deleteDocuments(targetDocuments) {
  if (!targetDocuments.length) {
    batchActionMessage.value = '请先选择需要删除的批量文档。'
    closeAllMenus()
    return
  }

  if (!confirmDeleteDocuments(targetDocuments)) {
    closeAllMenus()
    return
  }

  polishingBatch.value = true
  batchActionMessage.value = ''
  error.value = ''
  closeAllMenus()

  const payload = buildDeletePayload(targetDocuments)
  const requestedIdSet = new Set(payload.map((item) => item.documentId))

  try {
    const result = await deleteBatchProcessing({
      documents: payload,
    })
    if (result?.data) {
      syncBatchDataAfterMutation(result.data, { requestedIdSet })
    } else {
      syncBatchDataAfterMutation(await getBatchProcessing(), { requestedIdSet })
    }
    batchActionMessage.value = formatBatchDeleteMessage(result)
    notifyUsageSummaryUpdated()
  } catch (err) {
    batchActionMessage.value = err.message || '删除失败，请稍后重试。'
  } finally {
    polishingBatch.value = false
  }
}

function handleBulkPolish() {
  polishDocuments(getSelectedDocuments())
}

function handleRowPolish(document) {
  polishDocuments([document])
}

function handleBulkConfirm() {
  confirmDocuments(getSelectedDocuments())
}

function handleRowConfirm(document) {
  confirmDocuments([document])
}

function handleBulkDownload() {
  downloadDocuments(getSelectedDocuments())
}

function handleBulkDelete() {
  deleteDocuments(getSelectedDocuments())
}

function handleRowDownload(document) {
  if (!canDownloadDocument(document)) {
    return
  }

  downloadSingleDocument(document)
}

function handleRowDelete(document) {
  deleteDocuments([document])
}

function handleBulkMenuItem(item) {
  if (item.children) {
    toggleBulkTemplateMenu()
    return
  }

  if (item.key === 'import') {
    openBatchFilePicker()
    return
  }

  if (item.key === 'polish') {
    handleBulkPolish()
    return
  }

  if (item.key === 'confirm') {
    handleBulkConfirm()
    return
  }

  if (item.key === 'download') {
    handleBulkDownload()
    return
  }

  if (item.key === 'delete') {
    handleBulkDelete()
    return
  }

  handleDisplayAction()
}

function handleRowAction(action, document) {
  if (action?.key === 'polish') {
    handleRowPolish(document)
    return
  }

  if (action?.key === 'confirm') {
    handleRowConfirm(document)
    return
  }

  if (action?.key === 'download') {
    handleRowDownload(document)
    return
  }

  if (action?.key === 'delete') {
    handleRowDelete(document)
    return
  }

  handleDisplayAction()
}

function isRowActionDisabled(action, document) {
  if (action?.key === 'polish') {
    return polishingBatch.value || !canPolishDocument(document)
  }
  if (action?.key === 'confirm') {
    return polishingBatch.value || !canConfirmDocument(document)
  }
  if (action?.key === 'download') {
    return polishingBatch.value || !canDownloadDocument(document)
  }
  if (action?.key === 'delete') {
    return polishingBatch.value || document?.status === 'polishing'
  }
  return polishingBatch.value
}

function toggleRowMenu(id) {
  rowMenuId.value = rowMenuId.value === id ? '' : id
  rowTemplateMenuId.value = ''
  bulkMenuOpen.value = false
  bulkTemplateMenuOpen.value = false
}

function toggleRowTemplateMenu(id) {
  rowTemplateMenuId.value = rowTemplateMenuId.value === id ? '' : id
}

function openActivitiesDrawer() {
  drawerMode.value = 'activities'
  selectedDocument.value = null
  resultDetail.value = null
  resultError.value = ''
  resultLoading.value = false
  drawerOpen.value = true
  closeAllMenus()
}

async function openResultDrawer(document) {
  if (!canViewResult(document)) {
    return
  }

  drawerMode.value = 'result'
  selectedDocument.value = document
  resultDetail.value = null
  resultError.value = ''
  resultLoading.value = true
  drawerOpen.value = true
  closeAllMenus()

  try {
    resultDetail.value = await getBatchResult(document.id)
  } catch (err) {
    resultError.value = err.message || '润色结果加载失败，请稍后重试。'
  } finally {
    resultLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  resultLoading.value = false
  selectedDocument.value = null
  resultDetail.value = null
  resultError.value = ''
}

async function confirmResultReview() {
  if (!canConfirmDocument(drawerDocument.value)) {
    closeDrawer()
    return
  }

  await confirmDocuments([drawerDocument.value], { closeDrawer: true })
}

function handleDisplayAction() {
  closeAllMenus()
}

watch(
  [searchQuery, fileTypeFilter, statusFilter, templateFilter, uploadTimeFilter, pageSize],
  () => {
    currentPage.value = 1
    selectedIds.value = []
    closeAllMenus()
  },
)

watch(pageCount, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value
  }
})

onMounted(loadBatchProcessing)
onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  if (!importingFiles.value) {
    loadBatchProcessing({ silent: true })
  }
})

onUnmounted(() => {
  clearImportFeedbackTimers()
})
</script>

<template>
  <div class="page-grid batch-page">
    <section class="batch-page-header">
      <div>
        <h2 class="welcome-title">批量处理</h2>
        <p class="welcome-copy">管理和查看待处理文档，支持筛选、勾选与批量润色。</p>
      </div>
    </section>

    <div v-if="error" class="card status-card error-card">
      <strong>批量处理数据加载失败</strong>
      <p>{{ error }}</p>
    </div>

    <PageLoadingState v-else-if="loading" />

    <template v-else>
      <input
        ref="batchFileInput"
        class="hidden-file-input"
        type="file"
        multiple
        accept=".txt,.text,.docx"
        @change="handleBatchFileImport"
      />

      <div
        v-if="importMessage && importFeedbackVisible"
        class="batch-import-message"
        :class="{ 'is-fading': importFeedbackFading }"
      >
        {{ importMessage }}
      </div>

      <div v-if="batchActionMessage" class="batch-import-message">
        {{ batchActionMessage }}
      </div>

      <div
        v-if="importingFiles || importFeedbackVisible"
        class="batch-import-progress"
        :class="{ 'is-fading': importFeedbackFading }"
      >
        <div class="batch-import-progress-head">
          <span>{{ importPhase }}</span>
          <strong>{{ importProgress }}%</strong>
        </div>
        <div class="batch-import-progress-track">
          <span class="batch-import-progress-bar" :style="{ width: `${importProgress}%` }"></span>
        </div>
      </div>

      <section class="batch-layout">
        <div class="batch-left-column">
          <div class="batch-summary-grid">
            <article
              v-for="card in summaryCards"
              :key="card.label"
              class="card batch-summary-card"
            >
              <div class="batch-summary-icon" :class="card.tone">{{ card.icon }}</div>
              <div class="batch-summary-body">
                <p class="panel-label">{{ card.label }}</p>
                <strong>{{ card.count }}</strong>
                <span>{{ formatWordCount(card.wordCount) }}</span>
              </div>
            </article>
          </div>

          <article class="card batch-table-card">
            <div class="batch-toolbar">
              <label class="batch-search-field">
                <input
                  v-model="searchQuery"
                  type="search"
                  placeholder="搜索文档标题或所属场景..."
                />
                <span>⌕</span>
              </label>

              <select v-model="fileTypeFilter" class="batch-filter-select">
                <option value="">文档类型</option>
                <option v-for="item in fileTypeOptions" :key="item" :value="item">{{ item }}</option>
              </select>

              <select v-model="statusFilter" class="batch-filter-select">
                <option value="">润色状态</option>
                <option value="completed">已完成</option>
                <option value="polishing">润色中</option>
                <option value="pending">待确认</option>
                <option value="unprocessed">未润色</option>
              </select>

              <select v-model="templateFilter" class="batch-filter-select">
                <option value="">模板类型</option>
                <option v-for="item in templateOptions" :key="item" :value="item">{{ item }}</option>
              </select>

              <select v-model="uploadTimeFilter" class="batch-filter-select">
                <option value="">上传时间</option>
                <option value="24h">近 24 小时</option>
                <option value="7d">近 7 天</option>
                <option value="30d">近 30 天</option>
              </select>

              <button type="button" class="batch-reset-button" @click="resetFilters">重置</button>

              <div class="batch-menu-wrap batch-menu-wrap-left">
                <button
                  type="button"
                  class="batch-action-button"
                  :disabled="importingFiles || polishingBatch"
                  @click="toggleBulkMenu"
                >
                  {{ polishingBatch ? '润色中...' : '批量操作' }}
                  <span>▾</span>
                </button>
                <div v-if="bulkMenuOpen" class="batch-menu batch-menu-left">
                  <div
                    v-for="item in bulkActions"
                    :key="item.key"
                    class="batch-menu-row"
                  >
                    <button
                      type="button"
                      class="batch-menu-item"
                      :disabled="polishingBatch || (importingFiles && item.key === 'import')"
                      @click="handleBulkMenuItem(item)"
                    >
                      <span>{{ item.label }}</span>
                      <span v-if="item.children">›</span>
                    </button>

                    <div
                      v-if="item.children && bulkTemplateMenuOpen"
                      class="batch-submenu"
                    >
                      <button
                        v-for="template in item.children"
                        :key="template.key"
                        type="button"
                        class="batch-menu-item"
                        :disabled="polishingBatch"
                        @click="handleBulkTemplateSelect(template)"
                      >
                        {{ template.label }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="batch-table-wrap">
              <table class="batch-table">
                <thead>
                  <tr>
                    <th class="batch-checkbox-cell">
                      <input
                        :checked="allPageSelected"
                        type="checkbox"
                        @change="toggleSelectAll"
                      />
                    </th>
                    <th>文档信息</th>
                    <th>文档类型</th>
                    <th>模板类型</th>
                    <th>字数</th>
                    <th>润色状态</th>
                    <th>最后更新</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in pagedDocuments" :key="item.id">
                    <td class="batch-checkbox-cell">
                      <input
                        :checked="selectedIds.includes(item.id)"
                        type="checkbox"
                        @change="toggleRowSelection(item.id)"
                      />
                    </td>
                    <td>
                      <div class="batch-document-cell">
                        <span
                          class="batch-file-icon"
                          :class="resolveFileTypeMeta(item.fileType).className"
                        >
                          {{ resolveFileTypeMeta(item.fileType).icon }}
                        </span>
                        <div class="batch-document-meta">
                          <strong>{{ item.title }}</strong>
                          <span>{{ item.category }}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span class="batch-type-pill">{{ item.fileType }}</span>
                    </td>
                    <td>
                      <span class="batch-template-pill">{{ item.templateType }}</span>
                    </td>
                    <td>{{ item.wordCount.toLocaleString() }}</td>
                    <td>
                      <span
                        class="batch-status-pill"
                        :class="resolveStatusMeta(item.status).className"
                      >
                        {{ resolveStatusMeta(item.status).label }}
                      </span>
                    </td>
                    <td>{{ item.updatedAt }}</td>
                    <td>
                      <div class="batch-row-actions">
                        <button
                          type="button"
                          class="batch-inline-button"
                          :disabled="!canViewResult(item)"
                          @click="openResultDrawer(item)"
                        >
                          查看结果
                        </button>
                        <button
                          type="button"
                          class="icon-button"
                          aria-label="下载"
                          :disabled="polishingBatch || !canDownloadDocument(item)"
                          @click="handleRowDownload(item)"
                        >
                          ⬇
                        </button>
                        <div class="batch-menu-wrap">
                          <button
                            type="button"
                            class="icon-button"
                            aria-label="更多操作"
                            :disabled="polishingBatch"
                            @click="toggleRowMenu(item.id)"
                          >
                            ⋯
                          </button>
                          <div v-if="rowMenuId === item.id" class="batch-menu batch-row-menu">
                            <div
                              v-for="action in rowActions"
                              :key="action.key"
                              class="batch-menu-row"
                            >
                              <button
                                type="button"
                                class="batch-menu-item"
                                :disabled="action.children ? polishingBatch : isRowActionDisabled(action, item)"
                                @click="action.children ? toggleRowTemplateMenu(item.id) : handleRowAction(action, item)"
                              >
                                <span>{{ action.label }}</span>
                                <span v-if="action.children">›</span>
                              </button>
                              <div
                                v-if="action.children && rowTemplateMenuId === item.id"
                                class="batch-submenu batch-submenu-left"
                              >
                                <button
                                  v-for="template in action.children"
                                  :key="template.key"
                                  type="button"
                                  class="batch-menu-item"
                                  :disabled="polishingBatch"
                                  @click="handleRowTemplateSelect(item.id, template)"
                                >
                                  {{ template.label }}
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>

                  <tr v-if="pagedDocuments.length === 0">
                    <td colspan="8" class="batch-empty-cell">
                      暂无匹配的文档，请调整搜索词或筛选条件。
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="batch-table-footer">
              <div class="batch-footer-total">
                共 <strong>{{ filteredDocuments.length }}</strong> 条
              </div>

              <div class="batch-pagination">
                <button
                  type="button"
                  class="batch-page-button"
                  :disabled="currentPage === 1"
                  @click="goToPage(Math.max(1, currentPage - 1))"
                >
                  ‹
                </button>

                <button
                  v-for="page in pageNumbers"
                  :key="page"
                  type="button"
                  class="batch-page-button"
                  :class="{ 'is-active': page === currentPage }"
                  @click="goToPage(page)"
                >
                  {{ page }}
                </button>

                <button
                  type="button"
                  class="batch-page-button"
                  :disabled="currentPage === pageCount"
                  @click="goToPage(Math.min(pageCount, currentPage + 1))"
                >
                  ›
                </button>

                <select v-model.number="pageSize" class="batch-page-size">
                  <option :value="5">5 条/页</option>
                  <option :value="10">10 条/页</option>
                </select>
              </div>
            </div>
          </article>
        </div>

        <aside class="batch-right-column">
          <article class="card batch-distribution-card">
            <div class="section-heading">
              <div>
                <h3 class="section-title">模板类型分布</h3>
              </div>
            </div>

            <div class="batch-distribution-body">
              <div class="batch-donut-wrap">
                <svg class="batch-donut" viewBox="0 0 120 120" aria-hidden="true">
                  <g transform="rotate(-90 60 60)">
                    <circle class="batch-donut-track" cx="60" cy="60" r="42" />
                    <circle
                      v-for="segment in donutSegments"
                      :key="segment.label"
                      class="batch-donut-segment"
                      cx="60"
                      cy="60"
                      r="42"
                      :stroke="segment.color"
                      :stroke-dasharray="segment.dasharray"
                      :stroke-dashoffset="segment.dashoffset"
                    />
                  </g>
                </svg>
                <div class="batch-donut-center">
                  <strong>{{ distribution.total }}</strong>
                  <span>总文档</span>
                </div>
              </div>

              <div class="batch-distribution-legend">
                <div
                  v-for="item in distribution.items"
                  :key="item.label"
                  class="batch-legend-item"
                >
                  <span class="batch-legend-dot" :style="{ backgroundColor: item.color }"></span>
                  <span class="batch-legend-label">{{ item.label }}</span>
                  <span class="batch-legend-value">{{ item.count }}（{{ item.percent }}）</span>
                </div>
              </div>
            </div>
          </article>

          <article class="card batch-activity-card">
            <div class="section-heading">
              <div>
                <h3 class="section-title">最近操作</h3>
              </div>
            </div>

            <div class="batch-activity-list">
              <div
                v-for="item in recentActivities.slice(0, 5)"
                :key="item.id"
                class="batch-activity-item"
              >
                <span
                  class="batch-activity-icon"
                  :class="resolveActivityMeta(item.type).className"
                >
                  {{ resolveActivityMeta(item.type).icon }}
                </span>
                <div class="batch-activity-meta">
                  <div
                    class="batch-activity-title-wrap"
                    :class="{ 'has-files': hasActivityFilenames(item) }"
                  >
                    <strong>{{ item.title }}</strong>
                    <button
                      v-if="hasActivityFilenames(item)"
                      type="button"
                      class="batch-activity-files-toggle"
                      aria-label="查看导入文件"
                    >
                      ▾
                    </button>
                    <div v-if="hasActivityFilenames(item)" class="batch-activity-file-dropdown">
                      <span
                        v-for="filename in getActivityFilenames(item)"
                        :key="filename"
                        class="batch-activity-file-name"
                        :title="filename"
                      >
                        {{ filename }}
                      </span>
                    </div>
                  </div>
                  <span>{{ item.timeAgo }}</span>
                </div>
              </div>
            </div>

            <button type="button" class="section-link batch-activity-link" @click="openActivitiesDrawer">
              查看全部记录
            </button>
          </article>
        </aside>
      </section>
    </template>

    <div v-if="drawerOpen" class="batch-drawer-overlay" @click.self="closeDrawer">
      <aside class="batch-drawer">
        <div class="batch-drawer-header">
            <div>
              <h3>{{ drawerTitle }}</h3>
              <p v-if="drawerMode === 'activities'">展示最近批量处理记录。</p>
              <p v-else>请核对该文档的润色前后内容，并完成确认。</p>
            </div>
          <button type="button" class="icon-button" aria-label="关闭抽屉" @click="closeDrawer">×</button>
        </div>

        <div v-if="drawerMode === 'activities'" class="batch-drawer-body">
          <div v-for="item in recentActivities" :key="item.id" class="batch-activity-detail">
            <span
              class="batch-activity-icon"
              :class="resolveActivityMeta(item.type).className"
            >
              {{ resolveActivityMeta(item.type).icon }}
            </span>
            <div class="batch-activity-meta">
              <div
                class="batch-activity-title-wrap"
                :class="{ 'has-files': hasActivityFilenames(item) }"
              >
                <strong>{{ item.title }}</strong>
                <button
                  v-if="hasActivityFilenames(item)"
                  type="button"
                  class="batch-activity-files-toggle"
                  aria-label="查看导入文件"
                >
                  ▾
                </button>
                <div v-if="hasActivityFilenames(item)" class="batch-activity-file-dropdown">
                  <span
                    v-for="filename in getActivityFilenames(item)"
                    :key="filename"
                    class="batch-activity-file-name"
                    :title="filename"
                  >
                    {{ filename }}
                  </span>
                </div>
              </div>
              <span>{{ item.timeAgo }}</span>
            </div>
          </div>
        </div>

        <div v-else-if="resultLoading" class="batch-drawer-body">
          <PageLoadingState title="正在加载结果..." description="请稍候，正在读取润色结果" />
        </div>

        <div v-else-if="resultError" class="batch-drawer-body">
          <div class="card status-card error-card">
            <strong>润色结果加载失败</strong>
            <p>{{ resultError }}</p>
          </div>
        </div>

        <div v-else class="batch-drawer-body">
          <div class="batch-result-layout">
            <div class="batch-result-meta">
              <div>
                <span class="panel-label">文档标题</span>
                <strong>{{ drawerDocument.title }}</strong>
              </div>
              <span
                class="batch-status-pill"
                :class="resolveStatusMeta(drawerDocument.status).className"
              >
                {{ resolveStatusMeta(drawerDocument.status).label }}
              </span>
            </div>

            <div class="batch-result-score">
              <div>
                <span class="panel-label">质量评分</span>
                <strong>{{ drawerDocument.score ?? '--' }}</strong>
              </div>
              <div>
                <span class="panel-label">润色模板</span>
                <strong>{{ drawerDocument.templateLabel || drawerDocument.templateType || '未选择' }}</strong>
              </div>
              <div>
                <span class="panel-label">字数变化</span>
                <strong>
                  {{ drawerDocument.wordCount?.source ?? drawerDocument.wordCount ?? 0 }}
                  →
                  {{ drawerDocument.wordCount?.result ?? 0 }}
                </strong>
              </div>
            </div>

            <div v-if="drawerDocument.dimensions?.length" class="batch-result-dimensions">
              <span
                v-for="dimension in drawerDocument.dimensions"
                :key="dimension.label"
                class="batch-result-dimension"
              >
                {{ dimension.label }} {{ dimension.value }}
              </span>
            </div>

            <div class="batch-result-compare">
              <section class="batch-result-block">
                <h4>润色前</h4>
                <div class="batch-result-scroll">
                  <p>{{ drawerDocument.sourceText || '暂无原文内容。' }}</p>
                </div>
              </section>

              <section class="batch-result-block">
                <h4>润色后</h4>
                <div class="batch-result-scroll">
                  <p>{{ drawerDocument.resultText || '当前暂无润色结果。' }}</p>
                </div>
              </section>
            </div>
          </div>
        </div>

        <div
          v-if="drawerMode === 'result' && !resultLoading && !resultError && canConfirmDocument(drawerDocument)"
          class="batch-drawer-footer"
        >
          <button
            type="button"
            class="cta-button"
            :disabled="polishingBatch"
            @click="confirmResultReview"
          >
            确认
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>
