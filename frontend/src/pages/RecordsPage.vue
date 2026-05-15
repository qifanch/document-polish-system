<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import PageLoadingState from '../components/PageLoadingState.vue'
import { getPolishRecordDetail, getPolishRecords } from '../services/polishApi'

const PAGE_SIZE = 10

const loading = ref(true)
const error = ref('')
let activatedOnce = false
const records = ref([])
const detailCache = ref({})
const selectedRecordId = ref('')
const searchQuery = ref('')
const startDate = ref('')
const endDate = ref('')
const currentPage = ref(1)
const drawerOpen = ref(false)
const drawerMode = ref('result')
const drawerRecordId = ref('')

const statusMeta = {
  completed: { label: '已完成', className: 'is-completed' },
  polishing: { label: '润色中', className: 'is-polishing' },
  pending: { label: '待确认', className: 'is-pending' },
  unprocessed: { label: '未润色', className: 'is-unprocessed' },
}

const METHOD_LABELS = {
  polish: '智能润色',
  batch: '批量处理',
}

const filteredRecords = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  const start = startDate.value ? new Date(`${startDate.value}T00:00:00`).getTime() : null
  const end = endDate.value ? new Date(`${endDate.value}T23:59:59`).getTime() : null

  return records.value.filter((item) => {
    const matchesKeyword =
      !keyword ||
      String(item.title || '').toLowerCase().includes(keyword) ||
      String(item.category || '').toLowerCase().includes(keyword) ||
      String(item.templateLabel || item.templateType || '').toLowerCase().includes(keyword) ||
      String(resolveMethodLabel(item) || '').toLowerCase().includes(keyword)

    const createdAt = Date.parse(String(item.createdAt || '').replace(' ', 'T'))
    const matchesDateRange =
      Number.isNaN(createdAt) ||
      ((!start || createdAt >= start) && (!end || createdAt <= end))

    return matchesKeyword && matchesDateRange
  })
})

const pageCount = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / PAGE_SIZE)))

const pagedRecords = computed(() => {
  const page = Math.min(currentPage.value, pageCount.value)
  const startIndex = (page - 1) * PAGE_SIZE
  return filteredRecords.value.slice(startIndex, startIndex + PAGE_SIZE)
})

const pageNumbers = computed(() => Array.from({ length: pageCount.value }, (_, index) => index + 1))

const selectedDetail = computed(() => {
  if (!selectedRecordId.value) return null
  return detailCache.value[selectedRecordId.value] || null
})

const selectedUsesTemplate = computed(() => {
  if (!selectedDetail.value || isBatchRecord(selectedDetail.value)) return false
  return Boolean(selectedDetail.value.usedTemplate || selectedDetail.value.templateInfo?.name)
})

const selectedTemplateInfo = computed(() => {
  if (!selectedUsesTemplate.value) {
    return null
  }
  return selectedDetail.value.templateInfo || null
})

const selectedTemplateDescription = computed(() => {
  const description = String(selectedTemplateInfo.value?.description || '').trim()
  return description
})

const selectedScoreDimensions = computed(() => selectedDetail.value?.dimensions || [])
const selectedSuggestions = computed(() => selectedDetail.value?.suggestions || [])
const selectedBatchFullSummary = computed(() => selectedDetail.value?.fullSummary || selectedDetail.value?.summary || '')

const drawerRecord = computed(() => {
  if (!drawerRecordId.value) return null
  return detailCache.value[drawerRecordId.value] || records.value.find((item) => item.id === drawerRecordId.value) || null
})
const drawerBatchFullSummary = computed(() => drawerRecord.value?.fullSummary || drawerRecord.value?.summary || '')

function resolveStatusMeta(status) {
  return statusMeta[status] || statusMeta.unprocessed
}

function resolveScoreLabel(score) {
  const value = Number(score || 0)
  if (value >= 90) return '优秀'
  if (value >= 80) return '良好'
  if (value >= 70) return '中等'
  if (value >= 60) return '及格'
  return '待提升'
}

function isBatchRecord(item) {
  return item?.recordType === 'batch'
}

function resolveMethodLabel(item) {
  const recordType = isBatchRecord(item) ? 'batch' : 'polish'
  return String(item?.methodLabel || METHOD_LABELS[recordType])
}

function formatWordChange(item) {
  if (!item?.hasResult || !item.wordCount) return '--'

  const source = item.wordCount.source
  const result = item.wordCount.result
  const delta = item.wordCount.delta
  if (source == null || result == null || delta == null) return '--'
  return `${source.toLocaleString()} → ${result.toLocaleString()} (${delta >= 0 ? '+' : ''}${delta})`
}

function formatCount(value) {
  if (value == null || value === '') return '--'
  return Number(value || 0).toLocaleString()
}

function formatPercentChange(item) {
  if (!item?.hasResult || !item.wordCount?.source || !item.wordCount?.result) {
    return '--'
  }

  const delta = item.wordCount.delta || 0
  const percent = item.wordCount.source ? ((delta / item.wordCount.source) * 100).toFixed(2) : '0.00'
  return `${delta >= 0 ? '+' : ''}${delta.toLocaleString()} 字（${delta >= 0 ? '+' : ''}${percent}%）`
}

function formatWordDelta(item) {
  if (!item?.hasResult || item?.wordCount?.delta == null) return '--'
  const delta = item.wordCount.delta
  return `${delta >= 0 ? '+' : ''}${delta} 字`
}

function fileIconLabel(title, fileType = '') {
  const lowerTitle = String(title || '').toLowerCase()
  const lowerType = String(fileType || '').toLowerCase()

  if (lowerType === 'pdf' || lowerTitle.endsWith('.pdf')) return { label: 'P', className: 'pdf' }
  if (lowerType === 'txt' || lowerTitle.endsWith('.txt')) return { label: 'T', className: 'txt' }
  return { label: 'W', className: 'word' }
}

function canViewResult(item) {
  return Boolean(item?.hasResult)
}

function canOpenCompare(item) {
  return Boolean(item?.hasResult && item?.sourceText && item?.resultText)
}

function canConfirmRecord(item) {
  return item?.status === 'pending' && item?.hasResult
}

async function loadRecords(options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    const result = await getPolishRecords()
    records.value = Array.isArray(result) ? result : []
    detailCache.value = {}
    if (silent) {
      error.value = ''
    }

    if (records.value.length) {
      await selectRecord(records.value[0].id)
    } else {
      selectedRecordId.value = ''
    }
  } catch (err) {
    if (!silent) {
      error.value = err.message || '加载润色记录失败，请稍后重试。'
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

async function ensureDetail(recordId) {
  if (!recordId || detailCache.value[recordId]) return

  const detail = await getPolishRecordDetail(recordId)
  detailCache.value = {
    ...detailCache.value,
    [recordId]: detail,
  }
}

async function selectRecord(recordId) {
  selectedRecordId.value = recordId

  try {
    await ensureDetail(recordId)
  } catch (err) {
    error.value = err.message || '加载记录详情失败，请稍后重试。'
  }
}

async function openDrawer(mode, recordId) {
  if (!recordId) return

  drawerMode.value = mode
  drawerRecordId.value = recordId
  drawerOpen.value = true

  try {
    await ensureDetail(recordId)
  } catch (err) {
    error.value = err.message || '加载结果详情失败，请稍后重试。'
  }
}

function closeDrawer() {
  drawerOpen.value = false
  drawerRecordId.value = ''
}

function resetFilters() {
  searchQuery.value = ''
  startDate.value = ''
  endDate.value = ''
  currentPage.value = 1
}

function goToPage(page) {
  currentPage.value = page
}

watch([searchQuery, startDate, endDate], () => {
  currentPage.value = 1
})

watch(pageCount, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value
  }
})

watch(pagedRecords, (next) => {
  if (!next.length) return
  if (!next.some((item) => item.id === selectedRecordId.value)) {
    selectRecord(next[0].id)
  }
})

onMounted(loadRecords)
onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  loadRecords({ silent: true })
})
</script>

<template>
  <section class="page-grid records-page">
    <div class="records-page-header">
      <div>
        <h2 class="page-title">润色记录</h2>
        <p class="page-subtitle">查看和管理您的智能润色与批量处理记录，支持重新查看、对比和下载结果。</p>
      </div>
    </div>

    <div v-if="error" class="card status-card error-card">
      <strong>润色记录数据加载失败</strong>
      <p>{{ error }}</p>
    </div>

    <PageLoadingState v-else-if="loading" />

    <template v-else>
      <div class="records-layout">
        <section class="records-main">
          <article class="card records-shell-card">
            <div class="records-toolbar-card">
              <div class="records-filters">
                <label class="batch-search-field records-search-field">
                  <input
                    v-model="searchQuery"
                    type="search"
                    placeholder="搜索文档标题或所属内容..."
                  />
                  <span>⌕</span>
                </label>

                <div class="records-date-group">
                  <input v-model="startDate" type="date" class="batch-filter-select records-date-input" />
                  <span class="records-date-separator">-</span>
                  <input v-model="endDate" type="date" class="batch-filter-select records-date-input" />
                </div>

                <button type="button" class="batch-reset-button" @click="resetFilters">重置</button>
              </div>
            </div>

            <div class="records-table-region">
              <div class="batch-table-wrap records-table-wrap">
                <table class="batch-table records-table">
                  <thead>
                    <tr>
                      <th>文档信息</th>
                      <th>润色方式</th>
                      <th>字数变化</th>
                      <th>质量评分</th>
                      <th>润色时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="item in pagedRecords"
                      :key="item.id"
                      class="records-row"
                      :class="{ 'is-selected': item.id === selectedRecordId }"
                      @click="selectRecord(item.id)"
                    >
                      <td>
                        <div class="batch-document-cell">
                          <span
                            class="batch-file-icon"
                            :class="fileIconLabel(item.title, item.fileType).className"
                          >
                            {{ fileIconLabel(item.title, item.fileType).label }}
                          </span>
                          <div class="batch-document-meta">
                            <strong>{{ item.title }}</strong>
                            <span>{{ item.category }}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span class="records-method-pill" :class="isBatchRecord(item) ? 'is-batch' : 'is-polish'">
                          <span class="records-method-pill-icon" aria-hidden="true">
                            <svg v-if="isBatchRecord(item)" viewBox="0 0 16 16">
                              <path
                                d="M3.5 3.25A1.25 1.25 0 0 1 4.75 2h6.5A1.25 1.25 0 0 1 12.5 3.25v5.5A1.25 1.25 0 0 1 11.25 10h-6.5A1.25 1.25 0 0 1 3.5 8.75v-5.5Zm1.25-.25a.25.25 0 0 0-.25.25v5.5c0 .14.11.25.25.25h6.5a.25.25 0 0 0 .25-.25v-5.5a.25.25 0 0 0-.25-.25h-6.5ZM5 5h6v1H5V5Zm0 2h4.5v1H5V7Zm-1.75 3.25A1.25 1.25 0 0 1 4.5 9h6A1.25 1.25 0 0 1 11.75 10.25v2A1.75 1.75 0 0 1 10 14H5a1.75 1.75 0 0 1-1.75-1.75v-2Zm1.25-.25a.25.25 0 0 0-.25.25v2c0 .41.34.75.75.75h5c.41 0 .75-.34.75-.75v-2a.25.25 0 0 0-.25-.25h-6Z"
                                fill="currentColor"
                              />
                            </svg>
                            <svg v-else viewBox="0 0 16 16">
                              <path
                                d="M4.3 3.2a1.1 1.1 0 1 1 0 2.2 1.1 1.1 0 0 1 0-2.2Zm5.9 1.3a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm-6 4.6a1.05 1.05 0 1 1 0 2.1 1.05 1.05 0 0 1 0-2.1Zm6.15 1.2a.95.95 0 1 0 0-1.9.95.95 0 0 0 0 1.9ZM6.1 4.2l2.15-.48.22.98-2.16.48-.21-.98Zm-.37 5.58 2.43-.44.18.98-2.44.44-.17-.98Zm-1.04-3.22.7 1.56-.9.4-.7-1.56.9-.4Zm5.62-.5.93.32-.63 1.8-.94-.33.64-1.8Z"
                                fill="currentColor"
                              />
                            </svg>
                          </span>
                          <span>{{ resolveMethodLabel(item) }}</span>
                        </span>
                      </td>
                      <td>
                        <div class="records-word-change">
                          <strong>{{ formatWordChange(item) }}</strong>
                          <span v-if="item.hasResult">
                            {{ formatWordDelta(item) }}
                          </span>
                          <span v-else>--</span>
                        </div>
                      </td>
                      <td>
                        <span v-if="item.score != null" class="records-score-pill">
                          {{ item.score }} 分
                        </span>
                        <span v-else class="records-score-empty">--</span>
                      </td>
                      <td>{{ item.createdAt }}</td>
                    </tr>

                    <tr v-if="pagedRecords.length === 0">
                      <td colspan="5" class="batch-empty-cell">暂无匹配的润色记录，请调整筛选条件。</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="batch-table-footer records-table-footer">
              <div class="batch-footer-total">
                共 <strong>{{ filteredRecords.length }}</strong> 条
              </div>

              <div class="batch-pagination">
                <button
                  type="button"
                  class="batch-page-button"
                  :disabled="currentPage === 1"
                  @click="goToPage(Math.max(1, currentPage - 1))"
                >
                  ←
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
                  →
                </button>
              </div>
            </div>
          </article>
        </section>

        <aside class="card records-detail-card">
          <div v-if="selectedDetail" class="records-detail-body">
            <div class="records-detail-scroll">
              <div class="records-detail-header">
                <div class="batch-document-cell records-detail-title">
                  <span
                    class="batch-file-icon"
                    :class="fileIconLabel(selectedDetail.title, selectedDetail.fileType).className"
                  >
                    {{ fileIconLabel(selectedDetail.title, selectedDetail.fileType).label }}
                  </span>
                  <div class="batch-document-meta">
                    <strong>{{ selectedDetail.title }}</strong>
                    <span>{{ selectedDetail.category }} ｜ {{ selectedDetail.createdAt }}</span>
                  </div>
                </div>
              </div>

              <section class="records-detail-section">
                <h3 class="section-title">{{ isBatchRecord(selectedDetail) ? '处理信息' : '润色信息' }}</h3>
                <div v-if="isBatchRecord(selectedDetail)" class="records-info-grid">
                  <div><span class="panel-label">润色方式</span><strong>{{ resolveMethodLabel(selectedDetail) }}</strong></div>
                  <div><span class="panel-label">文件类型</span><strong>{{ selectedDetail.fileType || '--' }}</strong></div>
                  <div><span class="panel-label">处理状态</span><strong>{{ resolveStatusMeta(selectedDetail.status).label }}</strong></div>
                  <div><span class="panel-label">处理时间</span><strong>{{ selectedDetail.createdAt || '--' }}</strong></div>
                </div>
                <template v-else-if="selectedUsesTemplate">
                  <div class="records-info-grid records-template-info-grid">
                    <div><span class="panel-label">润色方式</span><strong>{{ resolveMethodLabel(selectedDetail) }}</strong></div>
                    <div><span class="panel-label">模板名称</span><strong>{{ selectedTemplateInfo?.name || selectedDetail.templateLabel || '--' }}</strong></div>
                  </div>
                  <div class="records-template-summary">
                    <span class="panel-label">模板说明</span>
                    <p>{{ selectedTemplateDescription || '当前模板暂无说明。' }}</p>
                  </div>
                </template>
                <div v-else class="records-info-grid">
                  <div><span class="panel-label">润色方式</span><strong>{{ resolveMethodLabel(selectedDetail) }}</strong></div>
                  <div><span class="panel-label">语言风格</span><strong>{{ selectedDetail.toneLabel }}</strong></div>
                  <div><span class="panel-label">润色强度</span><strong>{{ selectedDetail.strengthLabel }}</strong></div>
                  <div><span class="panel-label">更多设置</span><strong>{{ selectedDetail.optionLabels?.join('、') || '--' }}</strong></div>
                </div>
              </section>

              <section class="records-detail-section">
                <h3 class="section-title">{{ isBatchRecord(selectedDetail) ? '结果概览' : '字数变化' }}</h3>
                <div class="records-word-summary">
                  <div><span class="panel-label">原文字数</span><strong>{{ formatCount(selectedDetail.wordCount?.source) }} 字</strong></div>
                  <div><span class="panel-label">润色后字数</span><strong>{{ formatCount(selectedDetail.wordCount?.result) }}<template v-if="selectedDetail.wordCount?.result != null"> 字</template></strong></div>
                  <div><span class="panel-label">变化情况</span><strong>{{ formatPercentChange(selectedDetail) }}</strong></div>
                  <div v-if="isBatchRecord(selectedDetail)"><span class="panel-label">模板类型</span><strong>{{ selectedDetail.templateLabel || selectedDetail.templateType || '--' }}</strong></div>
                  <div v-if="isBatchRecord(selectedDetail)"><span class="panel-label">质量评分</span><strong>{{ selectedDetail.score ?? '--' }}</strong></div>
                </div>
              </section>

              <section v-if="!isBatchRecord(selectedDetail)" class="records-detail-section records-score-section">
                <h3 class="section-title">润色结果</h3>
                <div class="records-score-card" :class="{ 'is-empty': !selectedDetail.hasResult }">
                  <div class="records-score-main">
                    <strong>{{ selectedDetail.score ?? '--' }}</strong>
                    <span>{{ selectedDetail.score != null ? resolveScoreLabel(selectedDetail.score) : '未润色' }}</span>
                  </div>
                  <div v-if="selectedScoreDimensions.length" class="records-score-dimensions">
                    <div
                      v-for="dimension in selectedScoreDimensions"
                      :key="dimension.key || dimension.label"
                      class="records-score-dimension"
                    >
                      <div>
                        <span>{{ dimension.label }}</span>
                        <strong>{{ dimension.value }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section v-else class="records-detail-section">
                <h3 class="section-title">全文摘要</h3>
                <div class="records-batch-summary-card">
                  <p>{{ selectedBatchFullSummary || '当前暂无可展示的全文摘要。' }}</p>
                  <div v-if="selectedScoreDimensions.length" class="records-batch-dimensions">
                    <span
                      v-for="dimension in selectedScoreDimensions"
                      :key="dimension.key || dimension.label"
                      class="records-batch-dimension"
                    >
                      {{ dimension.label }} {{ dimension.value }}
                    </span>
                  </div>
                  <div v-if="selectedSuggestions.length" class="records-batch-suggestions">
                    <span
                      v-for="suggestion in selectedSuggestions"
                      :key="suggestion.label"
                      class="records-batch-suggestion"
                    >
                      {{ suggestion.label }}<template v-if="suggestion.count != null"> {{ suggestion.count }}</template>
                    </span>
                  </div>
                </div>
              </section>

            </div>
          </div>

          <div v-else class="records-detail-empty">
            <strong>请选择一条润色记录</strong>
            <p>右侧将显示该记录的润色信息、字数变化和结果操作。</p>
          </div>
        </aside>
      </div>
    </template>

    <div v-if="drawerOpen && drawerRecord" class="records-drawer-overlay" @click.self="closeDrawer">
      <aside class="records-drawer">
        <div class="records-drawer-header">
          <div>
            <h3>{{ drawerMode === 'compare' ? '对比原文' : '查看结果' }}</h3>
            <p>
              {{ drawerMode === 'compare'
                ? '请核对原文与处理结果之间的差异。'
                : isBatchRecord(drawerRecord)
                  ? '请查看当前批量处理结果、评分和建议信息。'
                  : '请查看当前润色结果，并确认内容是否满足要求。' }}
            </p>
          </div>
          <button type="button" class="icon-button" aria-label="关闭抽屉" @click="closeDrawer">×</button>
        </div>

        <div class="records-drawer-body">
          <div v-if="drawerMode === 'compare'" class="records-compare-grid">
            <section class="records-compare-block">
              <h4>润色前</h4>
              <div class="records-compare-scroll">
                <p>{{ drawerRecord.sourceText || '暂无原文内容。' }}</p>
              </div>
            </section>

            <section class="records-compare-block">
              <h4>润色后</h4>
              <div class="records-compare-scroll">
                <p>{{ drawerRecord.resultText || '当前暂无润色结果。' }}</p>
              </div>
            </section>
          </div>

          <div v-else-if="isBatchRecord(drawerRecord)" class="records-result-preview records-batch-preview">
            <div class="batch-result-meta">
              <div>
                <span class="panel-label">文档标题</span>
                <strong>{{ drawerRecord.title }}</strong>
              </div>
              <span
                class="batch-status-pill"
                :class="resolveStatusMeta(drawerRecord.status).className"
              >
                {{ resolveStatusMeta(drawerRecord.status).label }}
              </span>
            </div>

            <div class="batch-result-score">
              <div>
                <span class="panel-label">质量评分</span>
                <strong>{{ drawerRecord.score ?? '--' }}</strong>
              </div>
              <div>
                <span class="panel-label">模板类型</span>
                <strong>{{ drawerRecord.templateLabel || drawerRecord.templateType || '未选择' }}</strong>
              </div>
              <div>
                <span class="panel-label">字数变化</span>
                <strong>{{ formatWordChange(drawerRecord) }}</strong>
              </div>
            </div>

            <div v-if="drawerBatchFullSummary" class="records-batch-summary-card">
              <p>{{ drawerBatchFullSummary }}</p>
            </div>

            <div v-if="drawerRecord.dimensions?.length" class="records-batch-dimensions">
              <span
                v-for="dimension in drawerRecord.dimensions"
                :key="dimension.key || dimension.label"
                class="records-batch-dimension"
              >
                {{ dimension.label }} {{ dimension.value }}
              </span>
            </div>

            <div v-if="drawerRecord.suggestions?.length" class="records-batch-suggestions">
              <span
                v-for="suggestion in drawerRecord.suggestions"
                :key="suggestion.label"
                class="records-batch-suggestion"
              >
                {{ suggestion.label }}<template v-if="suggestion.count != null"> {{ suggestion.count }}</template>
              </span>
            </div>

            <div class="records-compare-scroll records-result-scroll">
              <p>{{ drawerRecord.resultText || '当前暂无润色结果。' }}</p>
            </div>
          </div>

          <div v-else class="records-result-preview">
              <div class="records-preview-meta">
                <span class="panel-label">{{ resolveMethodLabel(drawerRecord) }} ｜ {{ resolveStatusMeta(drawerRecord.status).label }}</span>
                <strong>{{ drawerRecord.title }}</strong>
              </div>
              <div class="records-compare-scroll records-result-scroll">
                <p>{{ drawerRecord.resultText || '当前暂无润色结果。' }}</p>
              </div>
            </div>
        </div>

        <div class="records-drawer-footer">
          <button
            v-if="canConfirmRecord(drawerRecord)"
            type="button"
            class="cta-button"
            @click="handleDisplayOnlyAction('确认记录'); closeDrawer()"
          >
            确认
          </button>
        </div>
      </aside>
    </div>
  </section>
</template>
