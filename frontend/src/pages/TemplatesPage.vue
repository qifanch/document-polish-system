<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import PageLoadingState from '../components/PageLoadingState.vue'
import {
  createPolishTemplate,
  deletePolishTemplate,
  getPolishTemplateDetail,
  getPolishTemplates,
  togglePolishTemplateEnabled,
  updatePolishTemplate,
} from '../services/templateApi'

const PAGE_SIZE = 6

const loading = ref(true)
const saving = ref(false)
const error = ref('')

const templates = ref([])
const detailCache = ref({})
const selectedTemplateId = ref('')
const currentPage = ref(1)
const isEditing = ref(false)
const isCreating = ref(false)
const moreMenuOpen = ref(false)
const activePanel = ref('basic')
let activatedOnce = false
const draft = ref(createEmptyTemplate())
const lastSelectedTemplateId = ref('')

const pageCount = computed(() => Math.max(1, Math.ceil(templates.value.length / PAGE_SIZE)))

const pagedTemplates = computed(() => {
  const safePage = Math.min(currentPage.value, pageCount.value)
  const start = (safePage - 1) * PAGE_SIZE
  return templates.value.slice(start, start + PAGE_SIZE)
})

const pageNumbers = computed(() => Array.from({ length: pageCount.value }, (_, index) => index + 1))

const selectedTemplate = computed(() => {
  if (!selectedTemplateId.value) return null
  return detailCache.value[selectedTemplateId.value] || templates.value.find((item) => item.id === selectedTemplateId.value) || null
})

const displayTemplate = computed(() => (isEditing.value ? draft.value : selectedTemplate.value))

const panelOptions = [
  { key: 'basic', label: '基本信息' },
  { key: 'prompt', label: '提示词' },
  { key: 'rules', label: '规则库' },
]

function createEmptyTemplate() {
  return {
    name: '',
    description: '',
    icon: 'M',
    tone: 'icon-blue',
    enabled: true,
    usageCount: 0,
    averageScore: 0,
    updatedAt: '',
    systemPrompt: '',
    terminology: [''],
    forbiddenExpressions: [''],
  }
}

function cloneTemplate(template) {
  return {
    ...template,
    terminology: [...(template.terminology || [''])],
    forbiddenExpressions: [...(template.forbiddenExpressions || [''])],
  }
}

function normalizeLines(values) {
  const cleaned = (values || []).map((item) => String(item || '').trim()).filter(Boolean)
  return cleaned.length ? cleaned : ['']
}

function pageTemplateItems(page) {
  const start = (page - 1) * PAGE_SIZE
  return templates.value.slice(start, start + PAGE_SIZE)
}

function formatUpdatedAt(value) {
  return value || '--'
}

function confirmDeleteTemplate(template) {
  if (typeof window === 'undefined' || typeof window.confirm !== 'function') {
    return true
  }

  const name = String(template?.name || '当前模板')
  return window.confirm(`确认删除模板“${name}”吗？默认模板会被隐藏，自定义模板会被永久删除。`)
}

async function loadTemplates(selectId = '', options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    templates.value = await getPolishTemplates()
    detailCache.value = {}

    if (!templates.value.length) {
      selectedTemplateId.value = ''
      return
    }

    const nextId = selectId || selectedTemplateId.value || templates.value[0].id
    currentPage.value = Math.min(currentPage.value, pageCount.value)
    await selectTemplate(nextId)
    if (silent) {
      error.value = ''
    }
  } catch (err) {
    if (!silent) {
      error.value = err.message || '加载润色模板失败，请稍后重试。'
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

async function ensureTemplateDetail(templateId) {
  if (!templateId || detailCache.value[templateId]) return
  const detail = await getPolishTemplateDetail(templateId)
  detailCache.value = {
    ...detailCache.value,
    [templateId]: {
      ...detail,
      terminology: normalizeLines(detail.terminology),
      forbiddenExpressions: normalizeLines(detail.forbiddenExpressions),
    },
  }
}

async function selectTemplate(templateId) {
  if (!templateId) return
  selectedTemplateId.value = templateId
  lastSelectedTemplateId.value = templateId
  isEditing.value = false
  isCreating.value = false
  moreMenuOpen.value = false
  activePanel.value = 'basic'

  try {
    await ensureTemplateDetail(templateId)
  } catch (err) {
    error.value = err.message || '加载模板详情失败，请稍后重试。'
  }
}

function goToPage(page) {
  currentPage.value = page
  const pageItems = pageTemplateItems(page)
  if (pageItems.length && !pageItems.some((item) => item.id === selectedTemplateId.value)) {
    selectTemplate(pageItems[0].id)
  }
}

function startCreateTemplate() {
  lastSelectedTemplateId.value = selectedTemplateId.value
  selectedTemplateId.value = ''
  moreMenuOpen.value = false
  isCreating.value = true
  isEditing.value = true
  activePanel.value = 'basic'
  draft.value = createEmptyTemplate()
}

function startEditTemplate() {
  if (!selectedTemplate.value) return
  moreMenuOpen.value = false
  isCreating.value = false
  isEditing.value = true
  draft.value = cloneTemplate(selectedTemplate.value)
}

function cancelEditing() {
  isCreating.value = false
  isEditing.value = false
  draft.value = createEmptyTemplate()
  activePanel.value = 'basic'
  const nextId = lastSelectedTemplateId.value || templates.value[0]?.id || ''
  if (nextId) {
    selectTemplate(nextId)
  }
}

function prepareTemplatePayload(source) {
  return {
    name: String(source.name || '').trim(),
    description: String(source.description || '').trim(),
    icon: String(source.icon || 'M').trim() || 'M',
    tone: String(source.tone || 'icon-blue').trim() || 'icon-blue',
    enabled: Boolean(source.enabled),
    usageCount: Number(source.usageCount || 0),
    averageScore: Number(source.averageScore || 0),
    systemPrompt: String(source.systemPrompt || '').trim(),
    terminology: normalizeLines(source.terminology).filter(Boolean),
    forbiddenExpressions: normalizeLines(source.forbiddenExpressions).filter(Boolean),
  }
}

async function saveTemplate() {
  const payload = prepareTemplatePayload(draft.value)
  if (!payload.name) {
    error.value = '模板名称不能为空。'
    return
  }

  saving.value = true
  error.value = ''

  try {
    let saved
    if (isCreating.value) {
      saved = await createPolishTemplate(payload)
    } else {
      saved = await updatePolishTemplate(lastSelectedTemplateId.value, payload)
    }

    isCreating.value = false
    isEditing.value = false
    draft.value = createEmptyTemplate()
    await loadTemplates(saved.id)
    activePanel.value = 'basic'
  } catch (err) {
    error.value = err.message || '保存模板失败，请稍后重试。'
  } finally {
    saving.value = false
  }
}

function applyLocalTemplate(template) {
  templates.value = templates.value.map((item) => (item.id === template.id ? { ...item, ...template } : item))
  detailCache.value = {
    ...detailCache.value,
    [template.id]: {
      ...(detailCache.value[template.id] || {}),
      ...template,
      terminology: normalizeLines(template.terminology),
      forbiddenExpressions: normalizeLines(template.forbiddenExpressions),
    },
  }
  if (selectedTemplateId.value === template.id && isEditing.value) {
    draft.value = cloneTemplate(detailCache.value[template.id])
  }
}

async function handleToggleEnabled(nextEnabled) {
  if (!displayTemplate.value) return

  if (isEditing.value) {
    draft.value.enabled = nextEnabled
    return
  }

  const templateId = selectedTemplateId.value
  const previousSummary = templates.value.map((item) => ({ ...item }))
  const previousDetail = detailCache.value[templateId] ? { ...detailCache.value[templateId] } : null

  applyLocalTemplate({ ...selectedTemplate.value, enabled: nextEnabled })

  try {
    const saved = await togglePolishTemplateEnabled(templateId, nextEnabled)
    applyLocalTemplate(saved)
  } catch (err) {
    templates.value = previousSummary
    if (previousDetail) {
      detailCache.value = { ...detailCache.value, [templateId]: previousDetail }
    }
    error.value = err.message || '切换模板状态失败，请稍后重试。'
  }
}

async function handleDeleteTemplate() {
  if (!selectedTemplate.value) return
  if (!confirmDeleteTemplate(selectedTemplate.value)) return

  const templateId = selectedTemplate.value.id

  try {
    await deletePolishTemplate(templateId)
    moreMenuOpen.value = false

    const remaining = templates.value.filter((item) => item.id !== templateId)
    templates.value = remaining

    const nextCache = { ...detailCache.value }
    delete nextCache[templateId]
    detailCache.value = nextCache

    const nextPage = Math.min(currentPage.value, Math.max(1, Math.ceil(remaining.length / PAGE_SIZE)))
    currentPage.value = nextPage

    const nextId = pageTemplateItems(nextPage)[0]?.id || remaining[0]?.id || ''
    selectedTemplateId.value = nextId

    if (nextId) {
      await selectTemplate(nextId)
    }
  } catch (err) {
    error.value = err.message || '删除模板失败，请稍后重试。'
  }
}

function updateTerminology(index, value) {
  draft.value.terminology[index] = value
}

function updateForbidden(index, value) {
  draft.value.forbiddenExpressions[index] = value
}

function addTerminology() {
  draft.value.terminology.push('')
}

function removeTerminology(index) {
  draft.value.terminology.splice(index, 1)
  if (!draft.value.terminology.length) {
    draft.value.terminology.push('')
  }
}

function addForbiddenExpression() {
  draft.value.forbiddenExpressions.push('')
}

function removeForbiddenExpression(index) {
  draft.value.forbiddenExpressions.splice(index, 1)
  if (!draft.value.forbiddenExpressions.length) {
    draft.value.forbiddenExpressions.push('')
  }
}

watch(pageCount, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value
  }
})

watch(pagedTemplates, (next) => {
  if (isEditing.value || !next.length) return
  if (!next.some((item) => item.id === selectedTemplateId.value)) {
    selectTemplate(next[0].id)
  }
})

onMounted(() => {
  loadTemplates()
})

onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  if (!isEditing.value) {
    loadTemplates(selectedTemplateId.value, { silent: true })
  }
})
</script>

<template>
  <section class="page-grid templates-page">
    <div class="templates-page-header">
      <div>
        <h2 class="page-title">润色模板</h2>
        <p class="page-subtitle">模板由提示词、术语库和禁用表达组成，用于控制 AI 润色的方向与风格。</p>
      </div>

      <div class="templates-page-actions">
        <button type="button" class="template-primary-button" @click="startCreateTemplate">新增模板</button>
      </div>
    </div>

    <div v-if="error" class="card status-card error-card">
      <strong>润色模板数据加载失败</strong>
      <p>{{ error }}</p>
    </div>

    <PageLoadingState v-else-if="loading" />

    <template v-else>
      <div class="templates-layout templates-layout-slim">
        <aside class="card templates-sidebar templates-sidebar-slim">
          <div class="templates-sidebar-head">
            <strong>模板列表（{{ templates.length }}）</strong>
            <span>按更新时间展示</span>
          </div>

          <div class="templates-list">
            <button
              v-for="item in pagedTemplates"
              :key="item.id"
              type="button"
              class="template-list-item"
              :class="{ 'is-active': item.id === selectedTemplateId }"
              @click="selectTemplate(item.id)"
            >
              <span class="template-list-icon">{{ item.icon || 'M' }}</span>
              <div class="template-list-body">
                <div class="template-list-topline">
                  <strong>{{ item.name }}</strong>
                  <span class="template-disabled-pill" :class="item.enabled ? 'is-enabled' : 'is-disabled'">
                    {{ item.enabled ? '已启用' : '已停用' }}
                  </span>
                </div>
                <p>{{ item.description }}</p>
                <div class="template-list-meta">
                  <span>使用 {{ item.usageCount }} 次</span>
                  <span>平均评分 {{ item.averageScore }} 分</span>
                  <span>更新于 {{ formatUpdatedAt(item.updatedAt) }}</span>
                </div>
              </div>
            </button>
          </div>

          <div class="templates-pagination">
            <span>共 {{ templates.length }} 条</span>
            <div class="templates-page-switch">
              <button
                type="button"
                class="records-page-button"
                :disabled="currentPage <= 1"
                @click="goToPage(currentPage - 1)"
              >
                上一页
              </button>
              <button
                v-for="page in pageNumbers"
                :key="page"
                type="button"
                class="records-page-button"
                :class="{ 'is-active': page === currentPage }"
                @click="goToPage(page)"
              >
                {{ page }}
              </button>
              <button
                type="button"
                class="records-page-button"
                :disabled="currentPage >= pageCount"
                @click="goToPage(currentPage + 1)"
              >
                下一页
              </button>
            </div>
          </div>
        </aside>

        <section class="card templates-detail-card templates-detail-card-slim">
          <template v-if="displayTemplate">
            <div class="templates-detail-header">
              <div class="templates-detail-main">
                <span class="templates-detail-icon">{{ displayTemplate.icon || 'M' }}</span>
                <div class="templates-detail-copy">
                  <h3>{{ displayTemplate.name }}</h3>
                  <p>{{ displayTemplate.description || '当前模板暂无额外描述。' }}</p>
                  <div class="templates-detail-meta">
                    <span>使用 {{ displayTemplate.usageCount || 0 }} 次</span>
                    <span>平均评分 {{ displayTemplate.averageScore || 0 }} 分</span>
                    <span>更新于 {{ formatUpdatedAt(displayTemplate.updatedAt) }}</span>
                  </div>
                </div>
              </div>

              <div class="templates-detail-actions">
                <button
                  type="button"
                  class="template-secondary-button"
                  :disabled="!selectedTemplate || isEditing"
                  @click="startEditTemplate"
                >
                  编辑模板
                </button>
                <div class="templates-more-wrap">
                  <button
                    type="button"
                    class="template-secondary-button"
                    :disabled="!selectedTemplate || isEditing"
                    @click="moreMenuOpen = !moreMenuOpen"
                  >
                    更多
                  </button>
                  <div v-if="moreMenuOpen" class="templates-more-menu">
                    <button type="button" class="is-danger" @click="handleDeleteTemplate">删除模板</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="templates-switch-row">
              <span>启用状态</span>
              <button
                type="button"
                class="templates-switch"
                :class="{ 'is-on': displayTemplate.enabled }"
                @click="handleToggleEnabled(!displayTemplate.enabled)"
              >
                <span />
              </button>
            </div>

            <div class="templates-panel-tabs" role="tablist" aria-label="模板编辑分区">
              <button
                v-for="panel in panelOptions"
                :key="panel.key"
                type="button"
                class="templates-panel-tab"
                :class="{ 'is-active': activePanel === panel.key }"
                @click="activePanel = panel.key"
              >
                {{ panel.label }}
              </button>
            </div>

            <div class="templates-detail-scroll">
              <section v-if="activePanel === 'basic'" class="templates-section-card">
                <div class="templates-section-head">
                  <strong>基本信息</strong>
                </div>
                <div class="templates-form-grid templates-form-grid-single">
                  <label class="templates-field">
                    <span>模板名称</span>
                    <input v-if="isEditing" v-model="draft.name" type="text" />
                    <strong v-else>{{ displayTemplate.name }}</strong>
                  </label>

                  <label class="templates-field templates-field-wide">
                    <span>模板描述</span>
                    <textarea v-if="isEditing" v-model="draft.description" rows="4" />
                    <p v-else class="templates-static-paragraph">{{ displayTemplate.description || '当前模板暂无额外描述。' }}</p>
                  </label>
                </div>
              </section>

              <section v-else-if="activePanel === 'prompt'" class="templates-section-card">
                <div class="templates-section-head">
                  <strong>提示词</strong>
                </div>
                <p class="templates-helper-text">提示词用于告诉 AI 以什么角色、标准和步骤润色文本，会直接影响润色方向、语气和输出要求。</p>
                <textarea
                  v-if="isEditing"
                  v-model="draft.systemPrompt"
                  rows="12"
                  class="templates-large-textarea"
                />
                <pre v-else class="templates-preformatted">{{ displayTemplate.systemPrompt || '当前模板暂未设置系统提示词。' }}</pre>
              </section>

              <section v-else class="templates-section-card">
                <div class="templates-section-head">
                  <strong>规则库</strong>
                </div>

                <div class="templates-rule-grid">
                  <article class="templates-rule-panel">
                    <div class="templates-subsection-head">
                      <strong>术语库</strong>
                      <button v-if="isEditing" type="button" class="template-link-button" @click="addTerminology">新增术语</button>
                    </div>
                    <p class="templates-helper-text">术语库用于列出需要保留、统一或优先使用的关键词、专有名词和业务表达。</p>

                    <template v-if="isEditing">
                      <div class="templates-inline-editor-list">
                        <div v-for="(term, index) in draft.terminology" :key="`term-${index}`" class="templates-inline-editor">
                          <input :value="term" type="text" @input="updateTerminology(index, $event.target.value)" />
                          <button type="button" class="template-link-button" @click="removeTerminology(index)">删除</button>
                        </div>
                      </div>
                    </template>
                    <ul v-else class="templates-bullet-list">
                      <li v-for="term in displayTemplate.terminology" :key="term">{{ term }}</li>
                    </ul>
                  </article>

                  <article class="templates-rule-panel">
                    <div class="templates-subsection-head">
                      <strong>禁用表达</strong>
                      <button v-if="isEditing" type="button" class="template-link-button" @click="addForbiddenExpression">新增表达</button>
                    </div>
                    <p class="templates-helper-text">禁用表达用于列出润色时应避免出现、弱化或替换掉的不合适措辞。</p>

                    <template v-if="isEditing">
                      <div class="templates-inline-editor-list">
                        <div
                          v-for="(phrase, index) in draft.forbiddenExpressions"
                          :key="`forbidden-${index}`"
                          class="templates-inline-editor"
                        >
                          <input :value="phrase" type="text" @input="updateForbidden(index, $event.target.value)" />
                          <button type="button" class="template-link-button" @click="removeForbiddenExpression(index)">删除</button>
                        </div>
                      </div>
                    </template>
                    <ul v-else class="templates-bullet-list">
                      <li v-for="phrase in displayTemplate.forbiddenExpressions" :key="phrase">{{ phrase }}</li>
                    </ul>
                  </article>
                </div>
              </section>
            </div>

            <div v-if="isEditing" class="templates-editor-actions">
              <button type="button" class="template-secondary-button" @click="cancelEditing">取消</button>
              <button type="button" class="template-primary-button" :disabled="saving" @click="saveTemplate">
                {{ saving ? '保存中...' : '保存模板' }}
              </button>
            </div>
          </template>

          <div v-else class="templates-empty-state">
            <strong>当前暂无可展示的模板</strong>
            <p>请先新增模板，建立可用于智能润色的模板配置。</p>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>
