<script setup>
import { computed, onMounted, onUnmounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NotificationDetailModal from './NotificationDetailModal.vue'
import NotificationDrawer from './NotificationDrawer.vue'
import { navigationItems } from '../config/navigation'
import {
  AUTH_USER_UPDATED_EVENT,
  clearAuthSession,
  getCurrentUser,
  getStoredUser,
  saveStoredUser,
} from '../services/authApi'
import { getNotifications, markNotificationRead } from '../services/notificationsApi'
import { getTodayUsage, USAGE_SUMMARY_UPDATED_EVENT } from '../services/usageApi'

const route = useRoute()
const router = useRouter()
const notifications = ref([])
const drawerOpen = ref(false)
const detailOpen = ref(false)
const selectedNotification = ref(null)
const todayUsageCount = ref(0)
const weeklyUsageWords = ref(0)
const currentUser = ref(getStoredUser() || null)

const activeItem = computed(
  () => navigationItems.find((item) => route.path.startsWith(item.path)) || navigationItems[0],
)

const unreadCount = computed(
  () => notifications.value.filter((notification) => !notification.isRead).length,
)

const formattedWeeklyUsageWords = computed(() => weeklyUsageWords.value.toLocaleString())
const displayName = computed(() => currentUser.value?.displayName || currentUser.value?.username || '用户')
const avatarText = computed(() => currentUser.value?.avatarText || displayName.value.slice(0, 1) || '用')

async function loadNotifications() {
  try {
    const result = await getNotifications()
    notifications.value = Array.isArray(result) ? result : []
  } catch {
    notifications.value = []
  }
}

async function loadTodayUsage() {
  try {
    const result = await getTodayUsage()
    const used = Number(result?.used)
    const weeklyWords = Number(result?.weeklyWords)
    todayUsageCount.value = Number.isFinite(used) ? used : 0
    weeklyUsageWords.value = Number.isFinite(weeklyWords) ? weeklyWords : 0
  } catch {
    todayUsageCount.value = 0
    weeklyUsageWords.value = 0
  }
}

async function loadCurrentUser() {
  try {
    const user = await getCurrentUser()
    currentUser.value = user
    saveStoredUser(user)
  } catch {
    clearAuthSession()
    router.replace({ path: '/login', query: { redirect: route.fullPath } })
  }
}

function handleAuthUserUpdated(event) {
  currentUser.value = event?.detail || getStoredUser() || null
  if (currentUser.value) {
    loadTodayUsage()
    return
  }
  todayUsageCount.value = 0
  weeklyUsageWords.value = 0
}

function handleUsageSummaryUpdated() {
  loadTodayUsage()
}

function openNotificationCenter() {
  drawerOpen.value = true
}

function closeNotificationCenter() {
  drawerOpen.value = false
}

async function openNotificationDetail(notification) {
  selectedNotification.value = notification
  detailOpen.value = true

  if (!notification.isRead) {
    try {
      const updated = await markNotificationRead(notification.id)
      notifications.value = notifications.value.map((item) =>
        item.id === updated.id ? updated : item,
      )
      selectedNotification.value = updated
    } catch {
      notifications.value = notifications.value.map((item) =>
        item.id === notification.id ? { ...item, isRead: true } : item,
      )
      selectedNotification.value = { ...notification, isRead: true }
    }
  }
}

function closeNotificationDetail() {
  detailOpen.value = false
  selectedNotification.value = null
}

provide('openNotificationCenter', openNotificationCenter)
provide('currentUser', currentUser)

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener(AUTH_USER_UPDATED_EVENT, handleAuthUserUpdated)
    window.addEventListener(USAGE_SUMMARY_UPDATED_EVENT, handleUsageSummaryUpdated)
  }
  loadCurrentUser()
  loadNotifications()
  loadTodayUsage()
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener(AUTH_USER_UPDATED_EVENT, handleAuthUserUpdated)
    window.removeEventListener(USAGE_SUMMARY_UPDATED_EVENT, handleUsageSummaryUpdated)
  }
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-card">
        <div class="brand-mark">✦</div>
        <div>
          <strong>文档润色系统</strong>
          <p>智能润色，让表达更出色</p>
        </div>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <RouterLink
          v-for="item in navigationItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ 'is-active': activeItem.path === item.path }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="usage-card">
        <p class="panel-label">今日使用情况</p>
        <strong>{{ todayUsageCount }}次</strong>
        <p class="panel-copy">本周已处理 {{ formattedWeeklyUsageWords }} 字</p>
      </div>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div class="topbar-title">
          <h1>{{ activeItem.label }}</h1>
        </div>
        <div class="topbar-user">
          <button
            type="button"
            class="notification-link"
            aria-label="查看通知提醒"
            @click="openNotificationCenter"
          >
            <span class="notification-icon">🔔</span>
            <span v-if="unreadCount" class="badge-alert">{{ unreadCount }}</span>
          </button>
          <div class="avatar">{{ avatarText }}</div>
          <strong>{{ displayName }}</strong>
        </div>
      </header>

      <main class="shell-content">
        <RouterView v-slot="{ Component }">
          <KeepAlive>
            <component :is="Component" />
          </KeepAlive>
        </RouterView>
      </main>
    </div>

    <NotificationDrawer
      :open="drawerOpen"
      :notifications="notifications"
      :unread-count="unreadCount"
      @close="closeNotificationCenter"
      @open-detail="openNotificationDetail"
    />
    <NotificationDetailModal
      :open="detailOpen"
      :notification="selectedNotification"
      @close="closeNotificationDetail"
    />
  </div>
</template>
