<script setup>
import { computed, inject, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageLoadingState from '../components/PageLoadingState.vue'
import { getDashboard } from '../services/dashboardApi'

const QUICK_ACTIONS = [
  {
    title: '学术论文',
    description: '优化学术表达与论证结构',
    icon: '学',
    tone: 'icon-blue',
  },
  {
    title: '简历优化',
    description: '突出经历重点与成果表达',
    icon: '简',
    tone: 'icon-green',
  },
  {
    title: '商务写作',
    description: '提升专业度与沟通效率',
    icon: '商',
    tone: 'icon-purple',
  },
  {
    title: '公文通知',
    description: '规范正式文书语气与格式',
    icon: '公',
    tone: 'icon-orange',
  },
]

const router = useRouter()
const openNotificationCenter = inject('openNotificationCenter', () => {})
const currentUser = inject('currentUser', ref(null))
const loading = ref(true)
const error = ref('')
let activatedOnce = false
const dashboard = ref({
  summary: [],
  records: [],
  templates: [],
  notices: [],
})

const stats = computed(() => dashboard.value.summary || [])
const quickActions = computed(() => QUICK_ACTIONS)
const records = computed(() => dashboard.value.records || [])
const templates = computed(() => dashboard.value.templates || [])
const notices = computed(() => dashboard.value.notices || [])
const welcomeName = computed(() => currentUser.value?.displayName || currentUser.value?.username || '同学')

async function loadDashboard(options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    dashboard.value = await getDashboard()
    if (silent) {
      error.value = ''
    }
  } catch (err) {
    if (!silent) {
      error.value = err.message
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function goToPolish() {
  router.push({
    path: '/polish',
  })
}

onMounted(loadDashboard)
onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  loadDashboard({ silent: true })
})
</script>

<template>
  <div class="page-grid home-page">
    <section class="welcome-strip">
      <div>
        <h2 class="welcome-title">你好，{{ welcomeName }}</h2>
        <p class="welcome-copy">欢迎使用文档润色系统，选择模板快速开始润色吧！</p>
      </div>
    </section>

    <div v-if="error" class="card status-card error-card">
      <strong>首页数据加载失败</strong>
      <p>{{ error }}</p>
    </div>

    <PageLoadingState v-else-if="loading" />

    <template v-else>
      <section class="stats-grid">
        <article
          v-for="(stat, index) in stats"
          :key="stat.label"
          class="card stat-card"
          :class="[`stat-tone-${index % 4}`]"
        >
          <div class="stat-card-icon"></div>
          <div class="stat-card-body">
            <p class="panel-label">{{ stat.label }}</p>
            <strong>{{ stat.value }}</strong>
            <span class="stat-trend">{{ stat.trend }}</span>
          </div>
        </article>
      </section>

      <section class="dashboard-grid">
        <article class="card section-card quick-start-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">快速开始</h3>
              <p class="section-subtitle">选择润色模板，快速优化你的文档</p>
            </div>
          </div>

          <div class="quick-grid">
            <article
              v-for="item in quickActions"
              :key="item.title"
              class="quick-item"
            >
              <span class="item-icon" :class="item.tone">{{ item.icon }}</span>
              <strong>{{ item.title }}</strong>
              <p class="quick-description">{{ item.description }}</p>
            </article>
          </div>

          <button class="cta-button compact-button" type="button" @click="goToPolish()">开始智能润色</button>
        </article>

        <article class="card section-card records-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">最近润色记录</h3>
              <p class="section-subtitle">最近处理结果</p>
            </div>
            <RouterLink class="section-link" to="/records">查看全部</RouterLink>
          </div>

          <div class="card-scroll-area">
            <div class="record-list">
              <div v-for="record in records" :key="record.title" class="record-item">
                <div>
                  <strong class="record-title">{{ record.title }}</strong>
                  <p class="record-copy">{{ record.meta }}</p>
                </div>
                <div class="record-meta">
                  <span class="meta-text">{{ record.time }}</span>
                  <span class="score-pill">{{ record.score }}</span>
                </div>
              </div>
            </div>
          </div>
        </article>

        <article class="card section-card templates-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">常用模板</h3>
              <p class="section-subtitle">高频模板</p>
            </div>
            <RouterLink class="section-link" to="/templates">管理模板</RouterLink>
          </div>

          <div class="card-scroll-area template-scroll-area">
            <div class="template-grid">
              <div v-for="item in templates" :key="item.name" class="template-item">
                <span class="item-icon" :class="item.tone">{{ item.icon }}</span>
                <div class="template-meta">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.usage }}</span>
                </div>
              </div>
            </div>
          </div>
        </article>

        <article class="card section-card notices-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">系统公告</h3>
              <p class="section-subtitle">更新与提醒</p>
            </div>
            <button class="section-link section-button" type="button" @click="openNotificationCenter()">
              查看全部
            </button>
          </div>

          <div class="card-scroll-area">
            <div class="notice-list">
              <div v-for="notice in notices" :key="notice.title" class="notice-item">
                <div>
                  <strong class="notice-title">{{ notice.title }}</strong>
                  <p>{{ notice.description || '当前暂无更多公告内容。' }}</p>
                </div>
                <span class="meta-text">{{ notice.date }}</span>
              </div>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>
