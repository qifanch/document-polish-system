<script setup>
import { Document, Packer, Paragraph, TextRun } from 'docx'
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import PageLoadingState from '../components/PageLoadingState.vue'
import { recordDashboardExport } from '../services/dashboardApi'
import { getPolishConfig, getPolishRecords, importPolishFile, runPolish } from '../services/polishApi'
import { notifyUsageSummaryUpdated } from '../services/usageApi'

const route = useRoute()
const fileInput = ref(null)

const MAX_SOURCE_CHARS = 10000
const DEFAULT_CONTENT = ''
const EMPTY_FILE_NAME = '未导入文件'
const DIMENSION_META = ['流畅度', '准确性', '专业性', '可读性']

const configLoading = ref(true)
const configError = ref('')
const polishError = ref('')
const polishing = ref(false)
const importingFile = ref(false)
const copied = ref(false)
const downloadMenuOpen = ref(false)
const revisionMode = ref(false)
const importedFileName = ref(EMPTY_FILE_NAME)
const importError = ref('')
const importOverLimit = ref(false)
const recentRecords = ref([])
const resultData = ref(null)
const revertedSegmentKeys = ref([])
let activatedOnce = false

const config = ref({
  templates: [],
  strengths: [],
  tones: [],
  options: [],
  defaultTemplate: 'general',
  defaultStrength: 'medium',
  defaultTone: 'formal',
})

const form = ref({
  content: DEFAULT_CONTENT,
  template: '',
  strength: 'medium',
  tone: 'formal',
  options: ['wording', 'clarity', 'logic', 'sentence'],
})

const sourceCount = computed(() => countChars(form.value.content))
const historyLabel = computed(() =>
  recentRecords.value.length ? `润色历史记录（${recentRecords.value.length}）` : '润色历史记录',
)
const settingsLocked = computed(() => Boolean(form.value.template))
const effectiveTemplateKey = computed(() => form.value.template || '')
const revertedSegmentKeySet = computed(() => new Set(revertedSegmentKeys.value))
const renderedRevisionSegments = computed(() => buildRenderedRevisionSegments(resultData.value?.revisionSegments, revertedSegmentKeySet.value))
const effectiveResultText = computed(() => buildEffectiveResultText(resultData.value, revertedSegmentKeySet.value))
const resultCount = computed(() => countChars(effectiveResultText.value))
const hasRevisionSegments = computed(() => Boolean(resultData.value?.revisionSegments?.length))
const wordCountText = computed(() => {
  if (!resultData.value?.wordCount) return '--'
  const { source, result, delta } = resultData.value.wordCount
  return `${source} → ${result} (${delta >= 0 ? '+' : ''}${delta})`
})
const scoreValue = computed(() => resultData.value?.score || 0)
const scoreLabel = computed(() => resolveScoreLabel(scoreValue.value))
const scoreRingOffset = computed(() => {
  const radius = 56
  const circumference = 2 * Math.PI * radius
  return circumference - (scoreValue.value / 100) * circumference
})
const displayedDimensions = computed(() =>
  DIMENSION_META.map((label) => {
    const matched = resultData.value?.dimensions?.find((item) => item.label === label)
    return {
      label,
      value: matched?.value ?? null,
    }
  }),
)

function countChars(text) {
  return (text || '').replace(/\s+/g, '').length
}

function resolveScoreLabel(score) {
  const value = Number(score || 0)
  if (value >= 90) return '优秀'
  if (value >= 80) return '良好'
  if (value >= 70) return '中等'
  if (value >= 60) return '及格'
  return '待提升'
}

function normalizeSegmentType(type) {
  if (type === 'added' || type === 'deleted') return type
  return 'unchanged'
}

function buildRevisionFingerprint(result) {
  const segments = Array.isArray(result?.revisionSegments) ? result.revisionSegments : []
  return JSON.stringify(
    segments.map((segment) => ({
      type: normalizeSegmentType(segment?.type),
      text: String(segment?.text || ''),
    })),
  )
}

function buildRevisionSegmentKey(segment, index) {
  return `${normalizeSegmentType(segment?.type)}:${index}:${String(segment?.text || '')}`
}

function buildRenderedRevisionSegments(segments, revertedKeys) {
  if (!Array.isArray(segments) || !segments.length) return []

  return segments
    .map((segment, index) => {
      const text = String(segment?.text || '')
      if (!text) return null
      const type = normalizeSegmentType(segment?.type)
      const revertKey = buildRevisionSegmentKey(segment, index)
      return {
        key: revertKey,
        revertKey,
        text,
        type,
        interactive: type === 'added' || type === 'deleted',
        reverted: revertedKeys.has(revertKey),
      }
    })
    .filter(Boolean)
}

function buildEffectiveResultText(result, revertedKeys) {
  const segments = Array.isArray(result?.revisionSegments) ? result.revisionSegments : []
  if (!segments.length) {
    return String(result?.resultText || '')
  }

  return segments
    .map((segment, index) => {
      const text = String(segment?.text || '')
      if (!text) return ''

      const type = normalizeSegmentType(segment?.type)
      const reverted = revertedKeys.has(buildRevisionSegmentKey(segment, index))
      if (type === 'deleted') {
        return reverted ? text : ''
      }
      if (type === 'added') {
        return reverted ? '' : text
      }
      return text
    })
    .join('')
}

function toggleSegmentRevert(revertKey) {
  const next = new Set(revertedSegmentKeys.value)
  if (next.has(revertKey)) {
    next.delete(revertKey)
  } else {
    next.add(revertKey)
  }
  revertedSegmentKeys.value = [...next]
}

function buildAutoTitle(content) {
  const plain = (content || '').replace(/\s+/g, '')
  if (!plain) return '未命名文档'
  return `${plain.slice(0, 12)}${plain.length > 12 ? '...' : ''}`
}

function syncTemplateFromRoute() {
  const templateFromRoute = typeof route.query.template === 'string' ? route.query.template : ''
  const availableTemplates = config.value.templates.map((item) => item.key)

  if (templateFromRoute && availableTemplates.includes(templateFromRoute)) {
    form.value.template = templateFromRoute
  }
}

async function loadConfig() {
  configLoading.value = true
  configError.value = ''

  try {
    const [configResult, recordsResult] = await Promise.all([
      getPolishConfig(),
      getPolishRecords().catch(() => []),
    ])

    config.value = configResult
    recentRecords.value = Array.isArray(recordsResult) ? recordsResult : []
    form.value.strength = configResult.defaultStrength
    form.value.tone = configResult.defaultTone

    syncTemplateFromRoute()
  } catch (error) {
    configError.value = error.message
  } finally {
    configLoading.value = false
  }
}

async function refreshConfigData() {
  configError.value = ''

  try {
    const [configResult, recordsResult] = await Promise.all([
      getPolishConfig(),
      getPolishRecords().catch(() => recentRecords.value),
    ])

    config.value = configResult
    recentRecords.value = Array.isArray(recordsResult) ? recordsResult : recentRecords.value
    syncTemplateFromRoute()
  } catch (error) {
    configError.value = error.message
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function handleImportFile(event) {
  const file = event.target.files?.[0]
  if (!file) return

  importingFile.value = true
  importError.value = ''
  importOverLimit.value = false

  try {
    const result = await importPolishFile(file)
    const text = result?.text || ''
    const charCount = Number(result?.charCount ?? countChars(text))

    if (charCount > MAX_SOURCE_CHARS) {
      importOverLimit.value = true
      importError.value = `解析成功，但正文 ${charCount.toLocaleString()} 字，超过智能润色 ${MAX_SOURCE_CHARS.toLocaleString()} 字上限。请前往批量处理。`
      return
    }

    form.value.content = text
    importedFileName.value = result?.filename || file.name
    resultData.value = null
    revertedSegmentKeys.value = []
    copied.value = false
    revisionMode.value = false
  } catch (error) {
    importError.value = error.message || '文件导入失败，请稍后重试。'
  } finally {
    importingFile.value = false
    event.target.value = ''
  }
}

function clearSource() {
  form.value.content = ''
  importedFileName.value = EMPTY_FILE_NAME
  importError.value = ''
  importOverLimit.value = false
  resultData.value = null
  revertedSegmentKeys.value = []
  copied.value = false
  revisionMode.value = false
}

function toggleOption(key) {
  if (settingsLocked.value) return

  const options = new Set(form.value.options)
  if (options.has(key)) {
    options.delete(key)
  } else {
    options.add(key)
  }
  form.value.options = [...options]
}

async function handlePolish() {
  if (!form.value.content.trim()) {
    return
  }

  polishing.value = true
  copied.value = false
  resultData.value = null
  revertedSegmentKeys.value = []
  revisionMode.value = false
  downloadMenuOpen.value = false
  polishError.value = ''

  try {
    const title = buildAutoTitle(form.value.content)
    const polishPayload = {
      title,
      description: '',
      content: form.value.content,
      strength: form.value.strength,
      tone: form.value.tone,
      options: form.value.options,
      ...(effectiveTemplateKey.value ? { template: effectiveTemplateKey.value } : {}),
    }

    const result = await runPolish(polishPayload)
    resultData.value = result
    revertedSegmentKeys.value = []
    recentRecords.value = await getPolishRecords().catch(() => recentRecords.value)
    notifyUsageSummaryUpdated()
  } catch (error) {
    polishError.value = error.message || '智能润色失败，请稍后重试。'
  } finally {
    polishing.value = false
  }
}

async function copyResult() {
  if (!effectiveResultText.value) return

  try {
    await navigator.clipboard.writeText(effectiveResultText.value)
    copied.value = true
  } catch {}
}

function triggerBlobDownload(blob, extension) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const title = buildAutoTitle(form.value.content).replace(/[\\/:*?"<>|]/g, '-')
  link.href = url
  link.download = `${title}.${extension}`
  link.click()
  URL.revokeObjectURL(url)
}

function createDocxParagraphs(content) {
  return String(content || '')
    .split(/\r?\n/)
    .map((line) =>
      new Paragraph({
        children: line ? [new TextRun(line)] : [],
        spacing: {
          after: line ? 120 : 240,
        },
      }),
    )
}

async function buildDocxBlob(content) {
  const doc = new Document({
    sections: [
      {
        children: createDocxParagraphs(content),
      },
    ],
  })

  return Packer.toBlob(doc)
}

async function recordExportMetric() {
  try {
    await recordDashboardExport('polish-result')
  } catch {
    // The local download should still succeed if export metrics fail.
  }
}

function toggleDownloadMenu() {
  if (!effectiveResultText.value) return
  downloadMenuOpen.value = !downloadMenuOpen.value
}

async function downloadResult(format) {
  const content = effectiveResultText.value
  if (!content) return

  downloadMenuOpen.value = false

  if (format === 'docx') {
    const blob = await buildDocxBlob(content)
    triggerBlobDownload(blob, 'docx')
  } else {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    triggerBlobDownload(blob, 'txt')
  }

  await recordExportMetric()
}

watch(
  () => route.query.template,
  () => {
    if (!configLoading.value) {
      syncTemplateFromRoute()
    }
  },
)

watch(resultData, (next, previous) => {
  if (!next) {
    downloadMenuOpen.value = false
    revertedSegmentKeys.value = []
    return
  }

  if (buildRevisionFingerprint(next) !== buildRevisionFingerprint(previous)) {
    revertedSegmentKeys.value = []
  }
})

onMounted(loadConfig)
onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  refreshConfigData()
})
</script>

<template>
  <section class="page-grid polish-page polish-page-v4">
    <div class="polish-page-header">
      <div>
        <h2 class="page-title">智能润色</h2>
        <p class="page-subtitle">基于 AI 大模型，优化语言表达，提升文本质量</p>
      </div>
      <RouterLink class="section-link polish-history-link" to="/records">
        {{ historyLabel }}
      </RouterLink>
    </div>

    <div v-if="configError" class="card status-card error-card">
      <strong>智能润色数据加载失败</strong>
      <p>{{ configError }}</p>
    </div>

    <PageLoadingState v-else-if="configLoading" />

    <template v-else>
      <div v-if="polishError" class="card status-card error-card">
        <strong>智能润色失败</strong>
        <p>{{ polishError }}</p>
      </div>

      <div class="polish-workspace-v4">
        <article class="card polish-main-card-v4 polish-source-card-v4">
          <div class="panel-topline">
            <h3 class="section-title">原文内容</h3>
            <div class="panel-topline-meta">
              <span class="meta-text">{{ sourceCount }} / 10,000 字</span>
              <button class="ghost-inline-button" type="button" @click="clearSource">清空</button>
            </div>
          </div>

          <div class="import-row">
            <button
              class="ghost-inline-button import-button"
              type="button"
              :disabled="importingFile"
              @click="openFilePicker"
            >
              {{ importingFile ? '解析中...' : '导入文件' }}
            </button>
            <span class="import-file-name">{{ importedFileName }}</span>
            <input
              ref="fileInput"
              class="hidden-file-input"
              type="file"
              accept=".txt,.text,.docx"
              @change="handleImportFile"
            />
          </div>
          <div v-if="importError" class="import-message" :class="{ 'is-over-limit': importOverLimit }">
            <span>{{ importError }}</span>
            <RouterLink v-if="importOverLimit" class="section-link import-message-link" to="/documents">
              去批量处理
            </RouterLink>
          </div>

          <div class="polish-editor-shell-v4">
            <textarea
              v-model="form.content"
              class="polish-textarea polish-textarea-v4"
              maxlength="10000"
              placeholder="请输入需要润色的原文内容，或导入 txt、docx 文件后继续编辑。"
            />
          </div>

          <div class="polish-main-footer-v4">
            <p class="editor-hint">支持中文文本输入与 txt、docx 文件导入，建议输入 100 字以上以获得更稳定的润色结果。</p>
            <button
              type="button"
              class="cta-button polish-submit-button"
              :disabled="polishing || !form.content.trim()"
              @click="handlePolish"
            >
              {{ polishing ? '正在智能润色...' : '开始智能润色' }}
            </button>
          </div>
        </article>

        <article class="card polish-main-card-v4 polish-result-card-v4">
          <div class="polish-result-header-v4">
            <div class="polish-result-toprow-v4">
              <div class="polish-result-title-wrap-v4">
                <h3 class="section-title">润色结果</h3>
              </div>

              <div class="polish-result-actions-v4">
                <span class="meta-text polish-result-count-v4">{{ resultCount }} 字</span>
                <button class="ghost-inline-button" type="button" :disabled="!resultData" @click="copyResult">
                  {{ copied ? '已复制' : '复制' }}
                </button>
                <div class="polish-download-menu">
                  <button
                    class="ghost-inline-button polish-download-button"
                    type="button"
                    :disabled="!resultData"
                    :aria-expanded="downloadMenuOpen"
                    aria-haspopup="menu"
                    @click="toggleDownloadMenu"
                  >
                    下载
                  </button>
                  <div v-if="downloadMenuOpen" class="polish-download-options" role="menu">
                    <button type="button" role="menuitem" @click="downloadResult('txt')">TXT</button>
                    <button type="button" role="menuitem" @click="downloadResult('docx')">DOCX</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="polish-result-toolbar-v4">
              <button
                class="revision-toggle-button"
                :class="{ 'is-active': revisionMode }"
                type="button"
                :disabled="!resultData"
                :aria-pressed="revisionMode"
                @click="revisionMode = !revisionMode"
              >
                <span class="revision-toggle-copy">显示修改痕迹</span>
                <span class="revision-toggle-track">
                  <span class="revision-toggle-thumb"></span>
                </span>
              </button>
              <span v-if="revisionMode && hasRevisionSegments" class="revision-toggle-hint">点击高亮处撤回</span>
            </div>
          </div>

          <div class="polish-result-shell-v4">
            <div class="result-scroll-shell polish-result-scroll-v4">
              <div v-if="resultData" class="result-text polish-result-text-v4">
                <template v-if="revisionMode && hasRevisionSegments">
                  <template v-for="segment in renderedRevisionSegments" :key="segment.key">
                    <span
                      v-if="segment.interactive"
                      class="polish-revision-token"
                      :class="[
                        segment.type === 'deleted' ? 'polish-revision-del' : 'polish-revision-add',
                        { 'is-reverted': segment.reverted },
                      ]"
                      role="button"
                      tabindex="0"
                      :aria-pressed="segment.reverted"
                      @click="toggleSegmentRevert(segment.revertKey)"
                      @keydown.enter.prevent="toggleSegmentRevert(segment.revertKey)"
                      @keydown.space.prevent="toggleSegmentRevert(segment.revertKey)"
                    >
                      <span>{{ segment.text }}</span>
                    </span>
                    <span v-else>{{ segment.text }}</span>
                  </template>
                </template>
                <template v-else>{{ effectiveResultText }}</template>
              </div>
              <div v-else-if="polishing" class="result-loading result-loading-v4" aria-live="polite">
                <div class="polish-dot-spinner" aria-hidden="true">
                  <span
                    v-for="dot in 12"
                    :key="dot"
                    :style="{
                      transform: `rotate(${(dot - 1) * 30}deg) translateY(-23px)`,
                      opacity: 0.25 + dot * 0.055,
                    }"
                  ></span>
                </div>
                <strong>正在生成润色结果...</strong>
              </div>
              <div v-else class="result-empty result-empty-v4">
                <strong>等待生成润色结果</strong>
                <p>输入或导入原文后，点击“开始智能润色”，这里会展示润色后的内容。</p>
              </div>
            </div>

            <div class="result-footer-line polish-result-footer-static-v4">
              <span class="meta-text">字数变化：{{ wordCountText }}</span>
            </div>
          </div>
        </article>

        <aside class="polish-side-column-v4">
          <section class="card polish-side-card-v4 polish-settings-card-v4">
            <h3 class="section-title section-title-large">润色设置</h3>

            <div class="setting-group">
              <span class="field-label field-label-large">套用模板</span>
              <select v-model="form.template" class="template-select">
                <option value="">无</option>
                <option v-for="template in config.templates" :key="template.key" :value="template.key">
                  {{ template.label }}
                </option>
              </select>
            </div>

            <div class="setting-group">
              <span class="field-label field-label-large">润色强度</span>
              <div class="chip-row">
                <button
                  v-for="strength in config.strengths"
                  :key="strength.key"
                  type="button"
                  class="choice-chip choice-chip-large"
                  :class="{ 'is-active': form.strength === strength.key, 'is-disabled': settingsLocked }"
                  :disabled="settingsLocked"
                  @click="form.strength = strength.key"
                >
                  {{ strength.label }}
                </button>
              </div>
            </div>

            <div class="setting-group">
              <span class="field-label field-label-large">语言风格</span>
              <div class="chip-row">
                <button
                  v-for="tone in config.tones"
                  :key="tone.key"
                  type="button"
                  class="choice-chip choice-chip-large"
                  :class="{ 'is-active': form.tone === tone.key, 'is-disabled': settingsLocked }"
                  :disabled="settingsLocked"
                  @click="form.tone = tone.key"
                >
                  {{ tone.label }}
                </button>
              </div>
            </div>

            <div class="setting-group">
              <span class="field-label field-label-large">更多设置</span>
              <div class="option-grid">
                <label
                  v-for="option in config.options"
                  :key="option.key"
                  class="option-check option-check-large"
                  :class="{ 'is-disabled': settingsLocked }"
                >
                  <input
                    type="checkbox"
                    :checked="form.options.includes(option.key)"
                    :disabled="settingsLocked"
                    @change="toggleOption(option.key)"
                  />
                  <span>{{ option.label }}</span>
                </label>
              </div>
            </div>
          </section>

          <section class="card polish-side-card-v4 polish-score-card-v4">
            <h3 class="section-title">润色质量评分</h3>

            <div v-if="resultData" class="polish-score-state-v4">
              <div class="score-ring-box polish-score-ring-box-v4">
                <svg class="score-ring polish-score-ring-v4" viewBox="0 0 160 160" aria-hidden="true">
                  <defs>
                    <linearGradient id="polishScoreGradient" x1="20" y1="20" x2="140" y2="140" gradientUnits="userSpaceOnUse">
                      <stop offset="0%" stop-color="#2f80ff" />
                      <stop offset="43%" stop-color="#8c63ff" />
                      <stop offset="72%" stop-color="#f06fd8" />
                      <stop offset="100%" stop-color="#ff9966" />
                    </linearGradient>
                  </defs>
                  <circle class="score-ring-track" cx="80" cy="80" r="56" />
                  <circle
                    class="score-ring-value"
                    cx="80"
                    cy="80"
                    r="56"
                    :style="{ strokeDashoffset: scoreRingOffset, strokeDasharray: 351.86 }"
                  />
                </svg>
                <div class="score-ring-text">
                  <strong>{{ resultData.score }}</strong>
                  <span>{{ scoreLabel }}</span>
                </div>
              </div>
            </div>

            <div v-else class="polish-score-empty-v4 polish-score-state-v4">
              <div class="polish-score-empty-ring-v4"></div>
              <strong>暂无评分</strong>
            </div>

            <div class="score-dimension-list polish-score-dimensions-v4">
              <div v-for="dimension in displayedDimensions" :key="dimension.label" class="dimension-item">
                <div class="dimension-head">
                  <span>{{ dimension.label }}</span>
                  <strong>{{ dimension.value ?? '--' }}</strong>
                </div>
                <div class="dimension-bar">
                  <span class="dimension-bar-fill" :style="{ width: `${dimension.value || 0}%` }"></span>
                </div>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
