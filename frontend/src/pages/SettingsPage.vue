<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageLoadingState from '../components/PageLoadingState.vue'
import {
  changePassword,
  clearAuthSession,
  deleteAccount,
  getCurrentUser,
  saveStoredUser,
} from '../services/authApi'
import { getSettings, updateSettingsNotifications, updateSettingsProfile } from '../services/settingsApi'

const SETTINGS_NOTIFICATION_META = [
  {
    key: 'polish-completed',
    title: '润色完成通知',
    description: '文档润色完成时通知我',
    icon: '文',
  },
  {
    key: 'batch-completed',
    title: '批量任务完成通知',
    description: '批量润色任务完成时通知我',
    icon: '批',
  },
  {
    key: 'system-announcement',
    title: '系统公告通知',
    description: '系统公告、重要消息通知',
    icon: '公',
  },
  {
    key: 'template-updated',
    title: '模板更新通知',
    description: '润色模板更新时通知我',
    icon: '模',
  },
  {
    key: 'promotion',
    title: '优惠活动通知',
    description: '优惠活动、福利信息通知',
    icon: '惠',
  },
]

const ACCOUNT_ACTIONS = [
  {
    key: 'change-password',
    title: '修改密码',
    description: '定期修改密码，保障账号安全。',
    icon: '密',
  },
  {
    key: 'logout',
    title: '退出登录',
    description: '退出当前登录状态并返回登录页面。',
    icon: '退',
  },
  {
    key: 'deactivate-account',
    title: '注销账号',
    description: '永久注销账号，所有数据将被清除。',
    icon: '号',
  },
]

const DATA_ACTIONS = [
  {
    key: 'clear-cache',
    title: '清除缓存',
    description: '清除系统缓存，提升页面与数据加载效率。',
    icon: '清',
  },
  {
    key: 'export-data',
    title: '导出我的数据',
    description: '导出当前账号下的文档、记录及相关数据。',
    icon: '导',
  },
  {
    key: 'import-data',
    title: '导入数据',
    description: '从本地文件导入历史数据与系统内容。',
    icon: '入',
  },
  {
    key: 'reset-defaults',
    title: '恢复默认设置',
    description: '将当前系统配置恢复为默认状态。',
    icon: '复',
  },
]

const router = useRouter()
const loading = ref(true)
const savingProfile = ref(false)
const savingNotifications = ref(false)
const changingPassword = ref(false)
const deletingAccount = ref(false)
const error = ref('')
const notice = ref('')
const passwordError = ref('')
const deleteError = ref('')
const editingProfile = ref(false)
const runningAction = ref('')
const logoutDialogOpen = ref(false)
const passwordDialogOpen = ref(false)
const deleteDialogOpen = ref(false)
let activatedOnce = false

function normalizeNotifications(items) {
  const valueByKey = new Map(
    (Array.isArray(items) ? items : [])
      .filter((item) => item && typeof item === 'object')
      .map((item) => [String(item.key || ''), Boolean(item.emailEnabled)]),
  )

  return SETTINGS_NOTIFICATION_META.map((item) => ({
    ...item,
    emailEnabled: valueByKey.get(item.key) ?? false,
  }))
}

function normalizeSettings(payload = {}) {
  return {
    profile: payload?.profile && typeof payload.profile === 'object' ? payload.profile : {},
    notifications: normalizeNotifications(payload?.notifications),
    accountActions: ACCOUNT_ACTIONS,
    dataActions: DATA_ACTIONS,
  }
}

const settings = ref(normalizeSettings())

const profileDraft = ref({
  username: '',
  email: '',
  emailVerified: true,
})

const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const deleteForm = ref({
  currentPassword: '',
})

const profileRows = computed(() => [
  { label: '用户名', value: settings.value.profile.username || '--' },
  {
    label: '邮箱',
    value: settings.value.profile.email || '--',
    badge: settings.value.profile.emailVerified ? '已验证' : '未验证',
  },
  { label: '角色', value: settings.value.profile.role || '--' },
  { label: '注册时间', value: settings.value.profile.registeredAt || '--' },
  { label: '最近登录', value: settings.value.profile.lastLoginAt || '--' },
])

function setNotice(message) {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) notice.value = ''
  }, 2400)
}

function resetDraft() {
  profileDraft.value = {
    username: settings.value.profile.username || '',
    email: settings.value.profile.email || '',
    emailVerified: Boolean(settings.value.profile.emailVerified),
  }
}

function resetPasswordForm() {
  passwordForm.value = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  }
  passwordError.value = ''
}

function resetDeleteForm() {
  deleteForm.value = {
    currentPassword: '',
  }
  deleteError.value = ''
}

function buildDataActionNotice(action) {
  const messages = {
    'clear-cache': '系统缓存已清除。',
    'export-data': '个人数据导出任务已创建。',
    'import-data': '数据导入任务已提交。',
    'reset-defaults': '默认设置已恢复。',
  }
  return messages[String(action?.key || '')] || '操作已完成。'
}

async function redirectToLogin() {
  clearAuthSession()
  await router.replace('/login')
}

async function loadSettings(options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) {
    loading.value = true
    error.value = ''
  }

  try {
    settings.value = normalizeSettings(await getSettings())
    if (silent) {
      error.value = ''
    }
    if (!options.preserveDraft) {
      resetDraft()
    }
  } catch (err) {
    if (!silent) {
      error.value = err.message || '设置中心加载失败，请稍后重试。'
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function startEditProfile() {
  resetDraft()
  editingProfile.value = true
}

function cancelEditProfile() {
  resetDraft()
  editingProfile.value = false
}

function openChangePasswordDialog() {
  resetPasswordForm()
  passwordDialogOpen.value = true
}

function openLogoutDialog() {
  logoutDialogOpen.value = true
}

function closeLogoutDialog() {
  if (runningAction.value === 'logout') return
  logoutDialogOpen.value = false
}

function closeChangePasswordDialog() {
  if (changingPassword.value) return
  passwordDialogOpen.value = false
  resetPasswordForm()
}

function openDeleteDialog() {
  resetDeleteForm()
  deleteDialogOpen.value = true
}

function closeDeleteDialog() {
  if (deletingAccount.value) return
  deleteDialogOpen.value = false
  resetDeleteForm()
}

async function saveProfile() {
  savingProfile.value = true
  error.value = ''

  try {
    const profile = await updateSettingsProfile(profileDraft.value)
    settings.value = {
      ...settings.value,
      profile,
    }
    try {
      const currentUser = await getCurrentUser()
      saveStoredUser(currentUser)
    } catch {
      // Keep the settings save successful even if refreshing cached user info fails.
    }
    editingProfile.value = false
    setNotice('个人资料已保存')
  } catch (err) {
    error.value = err.message || '保存个人资料失败，请稍后重试。'
  } finally {
    savingProfile.value = false
  }
}

async function toggleNotification(item, field) {
  const previous = settings.value.notifications.map((notification) => ({ ...notification }))
  settings.value = {
    ...settings.value,
    notifications: settings.value.notifications.map((notification) =>
      notification.key === item.key
        ? { ...notification, [field]: !notification[field] }
        : notification,
    ),
  }
  savingNotifications.value = true
  error.value = ''

  try {
    const notificationPayload = settings.value.notifications.map((notification) => ({
      key: notification.key,
      emailEnabled: Boolean(notification.emailEnabled),
    }))
    settings.value = {
      ...settings.value,
      notifications: await updateSettingsNotifications(notificationPayload),
    }
    setNotice('通知设置已更新')
  } catch (err) {
    settings.value = { ...settings.value, notifications: previous }
    error.value = err.message || '通知设置保存失败，请稍后重试。'
  } finally {
    savingNotifications.value = false
  }
}

async function submitPasswordChange() {
  passwordError.value = ''

  if (!passwordForm.value.currentPassword || !passwordForm.value.newPassword || !passwordForm.value.confirmPassword) {
    passwordError.value = '请完整填写密码信息。'
    return
  }
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    passwordError.value = '两次输入的新密码不一致。'
    return
  }

  changingPassword.value = true
  try {
    await changePassword(passwordForm.value)
    passwordDialogOpen.value = false
    resetPasswordForm()
    await redirectToLogin()
  } catch (err) {
    passwordError.value = err.message || '修改密码失败，请稍后重试。'
  } finally {
    changingPassword.value = false
  }
}

async function submitDeleteAccount() {
  deleteError.value = ''

  if (!deleteForm.value.currentPassword) {
    deleteError.value = '请输入当前密码以确认注销。'
    return
  }

  deletingAccount.value = true
  try {
    await deleteAccount(deleteForm.value)
    deleteDialogOpen.value = false
    resetDeleteForm()
    await redirectToLogin()
  } catch (err) {
    deleteError.value = err.message || '注销账号失败，请稍后重试。'
  } finally {
    deletingAccount.value = false
  }
}

async function confirmLogout() {
  runningAction.value = 'logout'
  try {
    logoutDialogOpen.value = false
    await redirectToLogin()
  } finally {
    runningAction.value = ''
  }
}

async function handleAccountAction(action) {
  error.value = ''

  if (action.key === 'logout') {
    openLogoutDialog()
    return
  }

  if (action.key === 'change-password') {
    openChangePasswordDialog()
    return
  }

  if (action.key === 'deactivate-account') {
    openDeleteDialog()
    return
  }
}

function handleDataAction(action) {
  error.value = ''
  setNotice(buildDataActionNotice(action))
}

onMounted(loadSettings)
onActivated(() => {
  if (!activatedOnce) {
    activatedOnce = true
    return
  }
  loadSettings({ preserveDraft: editingProfile.value, silent: true })
})
</script>

<template>
  <section class="settings-page">
    <div class="settings-page-header">
      <div>
        <h2 class="page-title">设置中心</h2>
        <p class="page-subtitle">管理您的个人信息、通知偏好和账号设置</p>
      </div>
    </div>

    <div v-if="error" class="card status-card error-card">
      <strong>设置中心请求失败</strong>
      <p>{{ error }}</p>
    </div>

    <div v-if="notice" class="settings-toast">
      {{ notice }}
    </div>

    <PageLoadingState v-if="loading" />

    <div v-else class="settings-grid">
      <section class="card settings-card settings-profile-card">
        <div class="settings-card-head">
          <div class="settings-head-main">
            <span class="settings-head-icon tone-blue">●</span>
            <div>
              <strong>个人信息</strong>
              <span>查看并维护您的账号资料</span>
            </div>
          </div>
          <div class="settings-head-actions">
            <template v-if="editingProfile">
              <button type="button" class="settings-ghost-button" @click="cancelEditProfile">取消</button>
              <button type="button" class="settings-primary-button" :disabled="savingProfile" @click="saveProfile">
                {{ savingProfile ? '保存中...' : '保存' }}
              </button>
            </template>
            <button v-else type="button" class="settings-ghost-button" @click="startEditProfile">编辑资料</button>
          </div>
        </div>

        <div class="settings-profile-body">
          <div class="settings-avatar-large">{{ settings.profile.avatarText || '张' }}</div>

          <div v-if="editingProfile" class="settings-profile-form">
            <label>
              <span>用户名</span>
              <input v-model="profileDraft.username" type="text" />
            </label>
            <label>
              <span>邮箱</span>
              <input v-model="profileDraft.email" type="email" />
            </label>
          </div>

          <div v-else class="settings-profile-list">
            <div v-for="row in profileRows" :key="row.label" class="settings-profile-row">
              <span>{{ row.label }}</span>
              <strong>{{ row.value }}</strong>
              <em v-if="row.badge">{{ row.badge }}</em>
            </div>
          </div>
        </div>
      </section>

      <section class="card settings-card settings-notice-card">
        <div class="settings-card-head">
          <div class="settings-head-main">
            <span class="settings-head-icon tone-purple">◇</span>
            <div>
              <strong>通知设置</strong>
              <span>选择您希望接收的通知类型和方式</span>
            </div>
          </div>
          <span class="settings-saving" :class="{ 'is-active': savingNotifications }">
            {{ savingNotifications ? '保存中' : '已同步' }}
          </span>
        </div>

        <div class="settings-notice-table">
          <div class="settings-notice-header">
            <span></span>
            <span>邮件通知</span>
          </div>
          <div v-for="item in settings.notifications" :key="item.key" class="settings-notice-row">
            <div class="settings-notice-copy">
              <span class="settings-row-icon tone-purple">{{ item.icon }}</span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.description }}</p>
              </div>
            </div>
            <button
              type="button"
              class="settings-switch"
              :class="{ 'is-on': item.emailEnabled }"
              @click="toggleNotification(item, 'emailEnabled')"
            >
              <span></span>
            </button>
          </div>
        </div>
      </section>

      <section class="card settings-card">
        <div class="settings-card-head">
          <div class="settings-head-main">
            <span class="settings-head-icon tone-green">▣</span>
            <div>
              <strong>账号操作</strong>
              <span>管理您的账号安全</span>
            </div>
          </div>
        </div>

        <div class="settings-action-list">
          <button
            v-for="item in settings.accountActions"
            :key="item.key"
            type="button"
            class="settings-action-row"
            :disabled="runningAction === item.key"
            @click="handleAccountAction(item)"
          >
            <span class="settings-row-icon tone-green">{{ item.icon }}</span>
            <span>
              <strong>{{ item.title }}</strong>
              <em>{{ runningAction === item.key ? '处理中...' : item.description }}</em>
            </span>
            <b>›</b>
          </button>
        </div>
      </section>

      <section class="card settings-card">
        <div class="settings-card-head">
          <div class="settings-head-main">
            <span class="settings-head-icon tone-orange">▤</span>
            <div>
              <strong>数据操作</strong>
              <span>管理您的数据和系统缓存</span>
            </div>
          </div>
        </div>

        <div class="settings-action-list">
          <button
            v-for="item in settings.dataActions"
            :key="item.key"
            type="button"
            class="settings-action-row"
            @click="handleDataAction(item)"
          >
            <span class="settings-row-icon tone-orange">{{ item.icon }}</span>
            <span>
              <strong>{{ item.title }}</strong>
              <em>{{ item.description }}</em>
            </span>
            <b>›</b>
          </button>
        </div>
      </section>
    </div>
  </section>

  <div v-if="logoutDialogOpen" class="settings-modal-overlay" @click.self="closeLogoutDialog">
    <section class="settings-modal">
      <div class="settings-modal-head">
        <div>
          <strong>退出登录</strong>
          <p>确认后将退出当前登录状态，并返回登录页面。</p>
        </div>
        <button type="button" class="settings-modal-close" :disabled="runningAction === 'logout'" @click="closeLogoutDialog">
          ×
        </button>
      </div>

      <div class="settings-modal-body">
        <p class="settings-modal-note settings-modal-note-neutral">
          退出后不会删除账号数据，后续仍可重新登录。
        </p>
      </div>

      <div class="settings-modal-actions">
        <button type="button" class="settings-ghost-button" :disabled="runningAction === 'logout'" @click="closeLogoutDialog">
          取消
        </button>
        <button type="button" class="settings-primary-button" :disabled="runningAction === 'logout'" @click="confirmLogout">
          {{ runningAction === 'logout' ? '退出中...' : '确认退出登录' }}
        </button>
      </div>
    </section>
  </div>

  <div v-if="passwordDialogOpen" class="settings-modal-overlay" @click.self="closeChangePasswordDialog">
    <section class="settings-modal">
      <div class="settings-modal-head">
        <div>
          <strong>修改密码</strong>
          <p>请先输入当前密码，再输入两次新密码。提交成功后将返回登录页面。</p>
        </div>
        <button type="button" class="settings-modal-close" :disabled="changingPassword" @click="closeChangePasswordDialog">
          ×
        </button>
      </div>

      <div class="settings-modal-body">
        <label class="settings-modal-field">
          <span>当前密码</span>
          <input v-model="passwordForm.currentPassword" type="password" autocomplete="current-password" />
        </label>
        <label class="settings-modal-field">
          <span>新密码</span>
          <input v-model="passwordForm.newPassword" type="password" autocomplete="new-password" />
        </label>
        <label class="settings-modal-field">
          <span>确认新密码</span>
          <input v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" />
        </label>
        <p v-if="passwordError" class="settings-modal-error">{{ passwordError }}</p>
      </div>

      <div class="settings-modal-actions">
        <button type="button" class="settings-ghost-button" :disabled="changingPassword" @click="closeChangePasswordDialog">
          取消
        </button>
        <button type="button" class="settings-primary-button" :disabled="changingPassword" @click="submitPasswordChange">
          {{ changingPassword ? '提交中...' : '确认修改' }}
        </button>
      </div>
    </section>
  </div>

  <div v-if="deleteDialogOpen" class="settings-modal-overlay" @click.self="closeDeleteDialog">
    <section class="settings-modal settings-modal-danger">
      <div class="settings-modal-head">
        <div>
          <strong>注销账号</strong>
          <p>注销后将删除当前账号在数据库中的关联数据，并清理该账号上传或生成的本地文件。</p>
        </div>
        <button type="button" class="settings-modal-close" :disabled="deletingAccount" @click="closeDeleteDialog">
          ×
        </button>
      </div>

      <div class="settings-modal-body">
        <p class="settings-modal-note">
          此操作不可恢复。确认注销前，请输入当前密码完成身份验证。
        </p>
        <label class="settings-modal-field">
          <span>当前密码</span>
          <input v-model="deleteForm.currentPassword" type="password" autocomplete="current-password" />
        </label>
        <p v-if="deleteError" class="settings-modal-error">{{ deleteError }}</p>
      </div>

      <div class="settings-modal-actions">
        <button type="button" class="settings-ghost-button" :disabled="deletingAccount" @click="closeDeleteDialog">
          取消
        </button>
        <button type="button" class="settings-danger-button" :disabled="deletingAccount" @click="submitDeleteAccount">
          {{ deletingAccount ? '注销中...' : '确认注销账号' }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(16, 22, 35, 0.28);
}

.settings-modal {
  width: min(100%, 460px);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 20px 60px rgba(20, 35, 70, 0.18);
  padding: 20px;
  display: grid;
  gap: 16px;
}

.settings-modal-danger {
  border: 1px solid rgba(220, 91, 106, 0.18);
}

.settings-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.settings-modal-head strong {
  display: block;
  color: var(--text-strong);
  font-size: 18px;
}

.settings-modal-head p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
}

.settings-modal-close {
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 26px;
  line-height: 1;
  cursor: pointer;
}

.settings-modal-body {
  display: grid;
  gap: 12px;
}

.settings-modal-field {
  display: grid;
  gap: 6px;
}

.settings-modal-field span {
  color: var(--text-strong);
  font-size: 12px;
  font-weight: 600;
}

.settings-modal-field input {
  min-height: 38px;
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 0 12px;
  color: var(--text-strong);
  outline: none;
}

.settings-modal-field input:focus {
  border-color: rgba(25, 102, 227, 0.38);
  box-shadow: 0 0 0 3px rgba(25, 102, 227, 0.08);
}

.settings-modal-note {
  margin: 0;
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(220, 91, 106, 0.08);
  color: #9d3040;
  font-size: 12px;
  line-height: 1.7;
}

.settings-modal-note-neutral {
  background: rgba(32, 118, 255, 0.08);
  color: #2859b8;
}

.settings-modal-error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.settings-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.settings-danger-button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--danger);
  border-radius: 8px;
  background: var(--danger);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}

.settings-danger-button:disabled,
.settings-modal-close:disabled {
  opacity: 0.62;
  cursor: wait;
}

@media (max-width: 720px) {
  .settings-modal {
    width: min(100%, 100vw - 24px);
    padding: 16px;
  }

  .settings-modal-actions {
    flex-direction: column-reverse;
  }
}
</style>
