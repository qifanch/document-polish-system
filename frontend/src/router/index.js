import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import BatchProcessingPage from '../pages/BatchProcessingPage.vue'
import HomePage from '../pages/HomePage.vue'
import LoginPage from '../pages/LoginPage.vue'
import PolishPage from '../pages/PolishPage.vue'
import RecordsPage from '../pages/RecordsPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import StatsPage from '../pages/StatsPage.vue'
import TemplatesPage from '../pages/TemplatesPage.vue'
import { clearAuthSession, getAuthToken, getCurrentUser, saveStoredUser } from '../services/authApi'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/workspace' },
    { path: '/login', name: '登录', component: LoginPage, meta: { guestOnly: true } },
    {
      path: '/',
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: 'workspace', name: '工作台', component: HomePage },
        { path: 'polish', name: '智能润色', component: PolishPage },
        { path: 'documents', name: '批量处理', component: BatchProcessingPage },
        { path: 'records', name: '润色记录', component: RecordsPage },
        { path: 'templates', name: '润色模板', component: TemplatesPage },
        { path: 'stats', name: '数据统计', component: StatsPage },
        { path: 'settings', name: '设置中心', component: SettingsPage },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const token = getAuthToken()

  if (to.meta.guestOnly && token) {
    try {
      const user = await getCurrentUser()
      saveStoredUser(user)
      return '/workspace'
    } catch {
      clearAuthSession()
      return true
    }
  }

  if (to.matched.some((record) => record.meta.requiresAuth)) {
    if (!token) {
      return {
        path: '/login',
        query: { redirect: to.fullPath },
      }
    }

    try {
      const user = await getCurrentUser()
      saveStoredUser(user)
    } catch {
      clearAuthSession()
      return {
        path: '/login',
        query: { redirect: to.fullPath },
      }
    }
  }

  return true
})

export default router
