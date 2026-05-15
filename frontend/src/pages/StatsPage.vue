<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import PageLoadingState from '../components/PageLoadingState.vue'
import { getStatistics } from '../services/statisticsApi'

const TREND_VIEWBOX = {
  width: 560,
  height: 192,
  paddingLeft: 34,
  paddingRight: 34,
  paddingTop: 14,
  paddingBottom: 28,
}
const SCORE_GAUGE_PATH = 'M 22 112 A 78 78 0 0 1 178 112'
const SCORE_GAUGE_LENGTH = 100

const emptyStatistics = {
  defaultRange: { start: '', end: '' },
  selectedRange: { start: '', end: '' },
  granularity: 'week',
  summary: [],
  processingTrend: { labels: [], values: [] },
  activeUsersTrend: { labels: [], values: [] },
  processingSeries: [],
  activeUserSeries: [],
  statusDistribution: { total: 0, items: [] },
  templateTop5: [],
  scoreDistribution: { averageScore: 0, items: [] },
  toneDistribution: { total: 0, items: [] },
  templateTypeStats: [],
}

const loading = ref(true)
const error = ref('')
let activatedOnce = false
const statistics = ref(emptyStatistics)
const granularity = ref('week')

const granularityOptions = [
  { key: 'day', label: '按日' },
  { key: 'week', label: '按周' },
  { key: 'month', label: '按月' },
]

const summaryCardMeta = [
  { label: '总处理文档数', unit: '', icon: '文', iconTone: 'tone-blue' },
  { label: '总处理字数', unit: '', icon: '字', iconTone: 'tone-green' },
  { label: '平均质量评分', unit: '分', icon: '分', iconTone: 'tone-purple' },
  { label: '总润色次数', unit: '', icon: '次', iconTone: 'tone-orange' },
  { label: '用户总数', unit: '', icon: '人', iconTone: 'tone-cyan' },
  { label: '模板使用次数', unit: '', icon: '模', iconTone: 'tone-teal' },
]

const summaryCards = computed(() =>
  (statistics.value.summary || []).map((item, index) => ({
    ...(summaryCardMeta[index] || {}),
    ...item,
    icon: item?.icon || summaryCardMeta[index]?.icon || '数',
    iconTone: item?.iconTone || summaryCardMeta[index]?.iconTone || 'tone-blue',
    unit: item?.unit ?? summaryCardMeta[index]?.unit ?? '',
  })),
)
const statusDistribution = computed(() => statistics.value.statusDistribution || { total: 0, items: [] })
const scoreDistribution = computed(() => statistics.value.scoreDistribution || { averageScore: 0, items: [] })
const toneDistribution = computed(() => statistics.value.toneDistribution || { total: 0, items: [] })
const templateTypeStats = computed(() => statistics.value.templateTypeStats || [])

const processingTrend = computed(() => normalizeTrendSource(statistics.value.processingTrend))
const activeUsersTrend = computed(() =>
  resolveTrendSource(statistics.value.activeUsersTrend, statistics.value.activeUserSeries, 'day'),
)

const topTemplates = computed(() => {
  const items = statistics.value.templateTop5 || []
  const maxCount = Math.max(...items.map((item) => Number(item.count || 0)), 0)

  return items.map((item) => ({
    ...item,
    barWidth: maxCount > 0 ? `${Math.max((Number(item.count || 0) / maxCount) * 100, 12)}%` : '0%',
  }))
})

const processingLineModel = computed(() =>
  buildLineModel(processingTrend.value, {
    labelCount: 6,
    valueCount: 5,
    showValueLabels: true,
    paddingLeft: 60,
    paddingRight: 24,
  }),
)

const activeUserLineModel = computed(() =>
  buildLineModel(activeUsersTrend.value, {
    labelCount: 6,
    valueCount: 2,
    showValueLabels: true,
    paddingTop: 34,
  }),
)

const statusSegments = computed(() => buildDonutSegments(statusDistribution.value.items, statusDistribution.value.total))
const tonePieSegments = computed(() => buildPieSegments(toneDistribution.value.items, toneDistribution.value.total))
const scoreGaugeSegments = computed(() =>
  buildGaugeSegments(scoreDistribution.value.items, totalByItems(scoreDistribution.value.items)),
)

function normalizeTrendSource(trendSource) {
  if (trendSource && Array.isArray(trendSource.labels) && Array.isArray(trendSource.values)) {
    return {
      labels: trendSource.labels,
      values: trendSource.values,
    }
  }

  return { labels: [], values: [] }
}

function resolveTrendSource(trendSource, seriesSource, selectedGranularity) {
  if (Array.isArray(seriesSource) && seriesSource.length) {
    return aggregateStatisticsSeries(seriesSource, selectedGranularity)
  }

  return normalizeTrendSource(trendSource)
}

function parseSeriesDate(value) {
  const [year, month, day] = String(value || '').split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function formatSeriesDay(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

function formatSeriesMonth(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${date.getFullYear()}-${month}`
}

function aggregateStatisticsSeries(seriesSource, selectedGranularity) {
  const normalized = (seriesSource || [])
    .map((item) => ({
      date: parseSeriesDate(item.date),
      value: Number(item.value || 0),
    }))
    .filter((item) => item.date instanceof Date && !Number.isNaN(item.date.getTime()))
    .sort((left, right) => left.date - right.date)

  if (!normalized.length) {
    return { labels: [], values: [] }
  }

  if (selectedGranularity === 'day') {
    return {
      labels: normalized.map((item) => formatSeriesDay(item.date)),
      values: normalized.map((item) => item.value),
    }
  }

  if (selectedGranularity === 'month') {
    const grouped = new Map()

    normalized.forEach((item) => {
      const key = formatSeriesMonth(item.date)
      const existing = grouped.get(key) || { label: key, value: 0 }
      existing.value += item.value
      grouped.set(key, existing)
    })

    return {
      labels: Array.from(grouped.values(), (item) => item.label),
      values: Array.from(grouped.values(), (item) => item.value),
    }
  }

  const labels = []
  const values = []

  for (let index = 0; index < normalized.length; index += 7) {
    const chunk = normalized.slice(index, index + 7)
    const startLabel = formatSeriesDay(chunk[0].date)
    const endLabel = formatSeriesDay(chunk[chunk.length - 1].date)
    labels.push(`${startLabel} ~ ${endLabel}`)
    values.push(chunk.reduce((sum, item) => sum + item.value, 0))
  }

  return { labels, values }
}

function totalByItems(items) {
  return (items || []).reduce((sum, item) => sum + Number(item.count || 0), 0)
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function formatSummaryValue(item) {
  const value = item?.value
  if (typeof value === 'number') return value.toLocaleString()
  return String(value ?? '--')
}

function formatScore(value) {
  const numeric = Number(value || 0)
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1)
}

function formatProcessingThousands(value) {
  return formatNumber(Math.round(Number(value || 0) / 1000))
}

function buildSparseIndexes(length, targetCount) {
  if (length <= 0 || targetCount <= 0) return []
  if (length <= targetCount) return Array.from({ length }, (_, index) => index)

  const indexes = [0, length - 1]
  const step = (length - 1) / Math.max(targetCount - 1, 1)

  for (let index = 1; index < targetCount - 1; index += 1) {
    indexes.push(Math.round(index * step))
  }

  return [...new Set(indexes)].sort((a, b) => a - b)
}

function buildValueLabelIndexes(values, targetCount) {
  const sparseIndexes = buildSparseIndexes(values.length, targetCount)
  if (!values.length) return sparseIndexes

  const maxIndex = values.reduce((currentMax, value, index, source) =>
    Number(value || 0) > Number(source[currentMax] || 0) ? index : currentMax,
  0)

  return [...new Set([...sparseIndexes, maxIndex, values.length - 1])].sort((a, b) => a - b)
}

function buildLineModel(source, options = {}) {
  const labels = source?.labels || []
  const values = source?.values || []
  const { width, height, paddingLeft, paddingRight, paddingTop, paddingBottom } = TREND_VIEWBOX
  const axisStartX = options.paddingLeft ?? paddingLeft
  const axisEndX = width - (options.paddingRight ?? paddingRight)
  const usableWidth = axisEndX - axisStartX
  const usableHeight = height - paddingTop - paddingBottom
  const maxValue = Math.max(...values.map((value) => Number(value || 0)), 1)
  const labelIndexes = buildSparseIndexes(labels.length, options.labelCount || 6)
  const valueLabelIndexes = options.showValueLabels ? buildValueLabelIndexes(values, options.valueCount || 4) : []

  const points = values.map((value, index) => {
    const x = labels.length === 1 ? axisStartX + usableWidth / 2 : axisStartX + (usableWidth * index) / Math.max(labels.length - 1, 1)
    const y = paddingTop + usableHeight - (Number(value || 0) / maxValue) * usableHeight
    return { x, y, value, label: labels[index] || '' }
  })

  const polyline = points.map((point) => `${point.x},${point.y}`).join(' ')
  const areaPath = points.length
    ? `M ${points[0].x} ${height - paddingBottom} L ${points.map((point) => `${point.x} ${point.y}`).join(' L ')} L ${points[points.length - 1].x} ${height - paddingBottom} Z`
    : ''

  const guideValues = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
    y: paddingTop + usableHeight - usableHeight * ratio,
    value: Math.round(maxValue * ratio),
  }))

  return {
    points,
    polyline,
    areaPath,
    guideValues,
    width,
    height,
    axisStartX,
    axisEndX,
    labelIndexes,
    valueLabelIndexes,
  }
}

function buildDonutSegments(items, total) {
  const radius = 42
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (items || []).map((item) => {
    const count = Number(item.count || 0)
    const ratio = total ? count / total : 0
    const length = ratio * circumference
    const segment = {
      ...item,
      dasharray: `${length} ${Math.max(circumference - length, 0)}`,
      dashoffset: -offset,
    }
    offset += length
    return segment
  })
}

function getPiePoint(centerX, centerY, radius, angle) {
  const radians = ((angle - 90) * Math.PI) / 180
  return {
    x: centerX + radius * Math.cos(radians),
    y: centerY + radius * Math.sin(radians),
  }
}

function buildPieSegments(items, total) {
  const centerX = 60
  const centerY = 60
  const radius = 52
  let angleOffset = 0

  return (items || []).map((item) => {
    const count = Number(item.count || 0)
    const ratio = total ? count / total : 0

    if (ratio >= 0.999) {
      return {
        ...item,
        path: `M ${centerX} ${centerY} m -${radius} 0 a ${radius} ${radius} 0 1 0 ${radius * 2} 0 a ${radius} ${radius} 0 1 0 -${radius * 2} 0`,
      }
    }

    const startAngle = angleOffset
    const endAngle = angleOffset + ratio * 360
    const start = getPiePoint(centerX, centerY, radius, startAngle)
    const end = getPiePoint(centerX, centerY, radius, endAngle)
    const largeArc = endAngle - startAngle > 180 ? 1 : 0
    angleOffset = endAngle

    return {
      ...item,
      path:
        ratio > 0
          ? `M ${centerX} ${centerY} L ${start.x.toFixed(3)} ${start.y.toFixed(3)} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x.toFixed(3)} ${end.y.toFixed(3)} Z`
          : '',
    }
  })
}

function buildGaugeSegments(items, total) {
  let offset = 0

  return (items || []).flatMap((item) => {
    const count = Number(item.count || 0)
    if (count <= 0 || total <= 0) {
      return []
    }
    const ratio = total ? count / total : 0
    const length = ratio * SCORE_GAUGE_LENGTH
    const segment = {
      ...item,
      dasharray: `${length} ${SCORE_GAUGE_LENGTH}`,
      dashoffset: -offset,
    }
    offset += length
    return [segment]
  })
}

async function loadStatistics(options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    const data = await getStatistics({
      granularity: granularity.value,
    })

    statistics.value = {
      ...emptyStatistics,
      ...data,
    }
    granularity.value = data.granularity || 'week'
    if (silent) {
      error.value = ''
    }
  } catch (err) {
    if (!silent) {
      error.value = err.message || '加载统计数据失败，请稍后重试。'
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function handleGranularityChange(nextGranularity) {
  if (granularity.value === nextGranularity) return
  granularity.value = nextGranularity
  loadStatistics({ silent: true })
}

onMounted(loadStatistics)
onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  loadStatistics({ silent: true })
})
</script>

<template>
  <section class="page-grid stats-page">
    <div class="stats-page-header">
      <div class="stats-title-block">
        <h2 class="page-title">数据统计</h2>
        <p class="page-subtitle">多维度统计系统使用情况，帮助了解润色效果与用户行为</p>
      </div>
    </div>

    <div v-if="error" class="card status-card error-card">
      <strong>数据统计加载失败</strong>
      <p>{{ error }}</p>
    </div>

    <PageLoadingState v-else-if="loading" />

    <template v-else>
      <div class="stats-summary-grid">
        <article v-for="item in summaryCards" :key="item.label" class="card stats-summary-card" :class="item.iconTone">
          <div class="stats-summary-icon">{{ item.icon || '数' }}</div>
          <div class="stats-summary-copy">
            <span>{{ item.label }}</span>
            <strong>{{ formatSummaryValue(item) }}<small v-if="item.unit">{{ item.unit }}</small></strong>
          </div>
        </article>
      </div>

      <div class="stats-chart-grid">
        <section class="card stats-card stats-trend-card">
          <div class="stats-card-head">
            <div class="stats-title-stack">
              <strong>处理字数趋势</strong>
              <span>单位：千字</span>
            </div>
            <div class="stats-segmented">
              <button
                v-for="item in granularityOptions"
                :key="item.key"
                type="button"
                class="stats-segmented-button"
                :class="{ 'is-active': granularity === item.key }"
                @click="handleGranularityChange(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="stats-line-chart">
            <svg class="stats-line-svg" :viewBox="`0 0 ${processingLineModel.width} ${processingLineModel.height}`" aria-hidden="true">
              <g v-for="guide in processingLineModel.guideValues" :key="guide.y">
                <line
                  :x1="processingLineModel.axisStartX"
                  :y1="guide.y"
                  :x2="processingLineModel.axisEndX"
                  :y2="guide.y"
                  class="stats-grid-line"
                />
                <text x="0" :y="guide.y + 4" class="stats-grid-label">{{ formatProcessingThousands(guide.value) }}</text>
              </g>
              <path :d="processingLineModel.areaPath" class="stats-area-fill" />
              <polyline :points="processingLineModel.polyline" class="stats-line-path" />
              <g v-for="(point, index) in processingLineModel.points" :key="`${point.label}-${point.value}`">
                <circle :cx="point.x" :cy="point.y" r="3.2" class="stats-line-point" />
                <text
                  v-if="processingLineModel.valueLabelIndexes.includes(index)"
                  :x="point.x"
                  :y="point.y - 8"
                  class="stats-point-value"
                >
                  {{ formatProcessingThousands(point.value) }}
                </text>
                <text
                  v-if="processingLineModel.labelIndexes.includes(index)"
                  :x="point.x"
                  :y="processingLineModel.height - 6"
                  class="stats-bottom-label"
                >
                  {{ point.label }}
                </text>
              </g>
            </svg>
          </div>
        </section>

        <section class="card stats-card stats-status-card">
          <div class="stats-card-head">
            <strong>文档状态分布</strong>
          </div>

          <div class="stats-distribution-layout stats-distribution-layout-status">
            <div class="stats-donut-wrap">
              <svg class="stats-donut" viewBox="0 0 120 120" aria-hidden="true">
                <circle cx="60" cy="60" r="42" class="stats-donut-track" />
                <circle
                  v-for="segment in statusSegments"
                  :key="segment.label"
                  cx="60"
                  cy="60"
                  r="42"
                  class="stats-donut-segment"
                  :stroke="segment.color"
                  :stroke-dasharray="segment.dasharray"
                  :stroke-dashoffset="segment.dashoffset"
                  transform="rotate(-90 60 60)"
                />
              </svg>
              <div class="stats-donut-center stats-donut-center-status">
                <strong>{{ formatNumber(statusDistribution.total) }}</strong>
                <span>总处理数</span>
              </div>
            </div>

            <div class="stats-legend stats-legend-status">
              <div v-for="item in statusDistribution.items" :key="item.label" class="stats-legend-row">
                <span class="stats-legend-dot" :style="{ background: item.color }" />
                <span>{{ item.label }}</span>
                <strong>{{ formatNumber(item.count) }}</strong>
                <em>{{ item.percent }}</em>
              </div>
            </div>
          </div>
        </section>

        <section class="card stats-card stats-top-card">
          <div class="stats-card-head">
            <strong>模板使用排行 TOP 5</strong>
            <span>次数</span>
          </div>

          <div class="stats-top-list">
            <div v-for="(item, index) in topTemplates" :key="item.label" class="stats-top-row">
              <span class="stats-rank-pill">{{ index + 1 }}</span>
              <div class="stats-top-copy">
                <strong>{{ item.label }}</strong>
                <div class="stats-top-bar">
                  <span :style="{ width: item.barWidth, background: item.color }" />
                </div>
              </div>
              <em>{{ formatNumber(item.count) }}</em>
            </div>
          </div>
        </section>

        <section class="card stats-card stats-score-card">
          <div class="stats-card-head">
            <strong>质量评分分布</strong>
          </div>

          <div class="stats-score-layout">
            <div class="stats-score-gauge-wrap">
              <svg class="stats-score-gauge" viewBox="0 0 200 124" aria-hidden="true">
                <path :d="SCORE_GAUGE_PATH" class="stats-score-track" :pathLength="SCORE_GAUGE_LENGTH" />
                <path
                  v-for="segment in scoreGaugeSegments"
                  :key="segment.label"
                  :d="SCORE_GAUGE_PATH"
                  class="stats-score-segment"
                  :stroke="segment.color"
                  :stroke-dasharray="segment.dasharray"
                  :stroke-dashoffset="segment.dashoffset"
                  :pathLength="SCORE_GAUGE_LENGTH"
                />
              </svg>
              <div class="stats-score-center">
                <strong>{{ formatScore(scoreDistribution.averageScore) }}</strong>
                <span>平均质量评分</span>
              </div>
            </div>

            <div class="stats-legend stats-legend-compact">
              <div v-for="item in scoreDistribution.items" :key="item.label" class="stats-legend-row">
                <span class="stats-legend-dot" :style="{ background: item.color }" />
                <span>{{ item.label }}</span>
                <strong>{{ formatNumber(item.count) }}</strong>
                <em>{{ item.percent }}</em>
              </div>
            </div>
          </div>
        </section>

        <section class="card stats-card stats-tone-card">
          <div class="stats-card-head">
            <strong>语言风格使用分布</strong>
          </div>

          <div class="stats-tone-layout">
            <div class="stats-tone-pie-wrap">
              <svg class="stats-tone-pie" viewBox="0 0 120 120" aria-hidden="true">
                <path
                  v-for="segment in tonePieSegments"
                  :key="segment.label"
                  class="stats-tone-pie-segment"
                  :d="segment.path"
                  :fill="segment.color"
                />
              </svg>
            </div>

            <div class="stats-legend stats-tone-legend">
              <div v-for="item in toneDistribution.items" :key="item.label" class="stats-legend-row">
                <span class="stats-legend-dot" :style="{ background: item.color }" />
                <span>{{ item.label }}</span>
                <strong>{{ formatNumber(item.count) }}</strong>
                <em>{{ item.percent }}</em>
              </div>
            </div>
          </div>
        </section>

        <section class="card stats-card stats-active-card">
          <div class="stats-card-head">
            <strong>最近30天活跃用户趋势</strong>
            <span>单位：人</span>
          </div>

          <div class="stats-line-chart compact">
            <svg class="stats-line-svg" :viewBox="`0 0 ${activeUserLineModel.width} ${activeUserLineModel.height}`" aria-hidden="true">
              <g v-for="guide in activeUserLineModel.guideValues" :key="guide.y">
                <line
                  :x1="activeUserLineModel.axisStartX"
                  :y1="guide.y"
                  :x2="activeUserLineModel.axisEndX"
                  :y2="guide.y"
                  class="stats-grid-line"
                />
                <text x="4" :y="guide.y + 4" class="stats-grid-label">{{ formatNumber(guide.value) }}</text>
              </g>
              <path :d="activeUserLineModel.areaPath" class="stats-area-fill secondary" />
              <polyline :points="activeUserLineModel.polyline" class="stats-line-path secondary" />
              <g v-for="(point, index) in activeUserLineModel.points" :key="`${point.label}-${point.value}`">
                <circle :cx="point.x" :cy="point.y" r="3" class="stats-line-point secondary" />
                <text
                  v-if="activeUserLineModel.valueLabelIndexes.includes(index)"
                  :x="point.x"
                  :y="point.y - 8"
                  class="stats-point-value secondary"
                >
                  {{ formatNumber(point.value) }}
                </text>
                <text
                  v-if="activeUserLineModel.labelIndexes.includes(index)"
                  :x="point.x"
                  :y="activeUserLineModel.height - 6"
                  class="stats-bottom-label"
                >
                  {{ point.label }}
                </text>
              </g>
            </svg>
          </div>
        </section>
      </div>

      <section class="card stats-table-card">
        <div class="stats-card-head">
          <strong>模板类型处理统计</strong>
        </div>

        <div class="stats-table-wrap">
          <table class="stats-table">
            <thead>
              <tr>
                <th>模板类型</th>
                <th>处理文档数</th>
                <th>处理字数</th>
                <th>平均质量评分</th>
                <th>润色次数</th>
                <th>占比</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in templateTypeStats" :key="item.label">
                <td>
                  <div class="stats-type-cell">
                    <span class="stats-type-dot" :style="{ background: item.color }" />
                    <strong>{{ item.label }}</strong>
                  </div>
                </td>
                <td>{{ formatNumber(item.processedCount) }}</td>
                <td>{{ formatNumber(item.wordCount) }}</td>
                <td>{{ formatScore(item.averageScore) }}</td>
                <td>{{ formatNumber(item.polishCount) }}</td>
                <td>
                  <div class="stats-ratio-cell">
                    <div class="stats-ratio-bar">
                      <span :style="{ width: item.ratio, background: item.color }" />
                    </div>
                    <em>{{ item.ratio }}</em>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>
