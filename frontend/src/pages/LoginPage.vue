<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import backgroundImage from '../assets/a_clean_minimalist_abstract_background_scene_an_o.png'
import { login, register, saveAuthSession } from '../services/authApi'

const route = useRoute()
const router = useRouter()

const mode = ref('login')
const username = ref('')
const password = ref('')
const remember = ref(true)
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')

const registerForm = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})
const acceptedAgreement = ref(false)
const showRegisterPassword = ref(false)
const showConfirmPassword = ref(false)
const registerLoading = ref(false)
const registerError = ref('')
const agreementModal = ref(null)

const passwordType = computed(() => (showPassword.value ? 'text' : 'password'))
const registerPasswordType = computed(() => (showRegisterPassword.value ? 'text' : 'password'))
const confirmPasswordType = computed(() => (showConfirmPassword.value ? 'text' : 'password'))

function switchMode(nextMode) {
  mode.value = nextMode
  error.value = ''
  registerError.value = ''
}

function setNotice(message) {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) notice.value = ''
  }, 2400)
}

function showUnsupported() {
  setNotice('该功能未开发。')
}

function showAgreement(type) {
  agreementModal.value =
    type === 'privacy'
      ? {
          title: '隐私政策',
          content: '本系统仅用于毕业设计演示，注册信息会保存到本地 MySQL 数据库，用于登录验证和页面展示。',
        }
      : {
          title: '用户协议',
          content: '本系统用于文档润色毕业设计演示，请使用测试账号体验功能，不上传敏感或重要资料。',
        }
}

async function handleLogin() {
  error.value = ''

  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码。'
    return
  }

  loading.value = true
  try {
    const result = await login({
      username: username.value.trim(),
      password: password.value,
    })
    saveAuthSession(result, remember.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/workspace'
    router.replace(redirect || '/workspace')
  } catch (err) {
    error.value = err.message || '登录失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  registerError.value = ''

  const payload = {
    username: registerForm.value.username.trim(),
    email: registerForm.value.email.trim(),
    password: registerForm.value.password,
    confirmPassword: registerForm.value.confirmPassword,
  }

  if (!payload.username || !payload.email || !payload.password || !payload.confirmPassword) {
    registerError.value = '请完整填写注册信息。'
    return
  }
  if (payload.password !== payload.confirmPassword) {
    registerError.value = '两次输入的密码不一致。'
    return
  }
  if (!acceptedAgreement.value) {
    registerError.value = '请先阅读并同意用户协议和隐私政策。'
    return
  }

  registerLoading.value = true
  try {
    await register(payload)
    username.value = payload.username
    password.value = ''
    registerForm.value = {
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
    }
    acceptedAgreement.value = false
    mode.value = 'login'
    setNotice('注册成功，请登录。')
  } catch (err) {
    registerError.value = err.message || '注册失败，请稍后重试。'
  } finally {
    registerLoading.value = false
  }
}
</script>

<template>
  <main class="login-page" :style="{ backgroundImage: `url(${backgroundImage})` }">
    <div v-if="notice" class="settings-toast">
      {{ notice }}
    </div>

    <section class="login-brand">
      <div class="login-logo" aria-hidden="true">
        <span></span>
      </div>
      <div>
        <h1>文档润色系统</h1>
        <p>智能润色，让表达更出色</p>
      </div>
    </section>

    <form v-if="mode === 'login'" class="login-card" @submit.prevent="handleLogin">
      <div class="login-card-head">
        <h2>登录账号</h2>
        <p>欢迎回来！请登录您的账号</p>
      </div>

      <label class="login-field">
        <span>用户名</span>
        <div class="login-input-wrap">
          <span class="login-input-icon">⌕</span>
          <input v-model="username" autocomplete="username" type="text" placeholder="请输入用户名" />
        </div>
      </label>

      <label class="login-field">
        <span>密码</span>
        <div class="login-input-wrap">
          <span class="login-input-icon">▣</span>
          <input
            v-model="password"
            :type="passwordType"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
          <button
            class="login-icon-button"
            type="button"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            @click="showPassword = !showPassword"
          >
            <svg class="login-eye-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M2.2 12c1.9-3.6 5.6-6 9.8-6s7.9 2.4 9.8 6c-1.9 3.6-5.6 6-9.8 6s-7.9-2.4-9.8-6Z"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
              />
              <circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8" />
            </svg>
          </button>
        </div>
      </label>

      <div class="login-options">
        <label class="login-check">
          <input v-model="remember" type="checkbox" />
          <span>记住我</span>
        </label>
        <button type="button" class="login-text-button" @click="showUnsupported">忘记密码?</button>
      </div>

      <p v-if="error" class="login-message is-error">{{ error }}</p>

      <button class="login-submit" type="submit" :disabled="loading">
        {{ loading ? '登录中...' : '登录' }}
      </button>

      <div class="login-divider">
        <span></span>
        <em>其他登录方式</em>
        <span></span>
      </div>

      <button type="button" class="wechat-button" aria-label="微信登录" @click="showUnsupported">
        微
      </button>

      <p class="auth-switch-text">
        还没有账号？
        <button type="button" @click="switchMode('register')">去注册</button>
      </p>
    </form>

    <form v-else class="login-card register-card" @submit.prevent="handleRegister">
      <div class="login-card-head">
        <h2>注册账号</h2>
        <p>创建新账号，开启智能润色之旅</p>
      </div>

      <label class="login-field">
        <span>用户名</span>
        <div class="login-input-wrap">
          <span class="login-input-icon">⌕</span>
          <input v-model="registerForm.username" autocomplete="username" type="text" placeholder="请输入用户名" />
        </div>
      </label>

      <label class="login-field">
        <span>邮箱</span>
        <div class="login-input-wrap">
          <span class="login-input-icon">✉</span>
          <input v-model="registerForm.email" autocomplete="email" type="email" placeholder="请输入邮箱地址" />
        </div>
      </label>

      <label class="login-field">
        <span>密码</span>
        <div class="login-input-wrap">
          <span class="login-input-icon">▣</span>
          <input
            v-model="registerForm.password"
            :type="registerPasswordType"
            autocomplete="new-password"
            placeholder="请输入密码"
          />
          <button
            class="login-icon-button"
            type="button"
            :aria-label="showRegisterPassword ? '隐藏密码' : '显示密码'"
            @click="showRegisterPassword = !showRegisterPassword"
          >
            <svg class="login-eye-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M2.2 12c1.9-3.6 5.6-6 9.8-6s7.9 2.4 9.8 6c-1.9 3.6-5.6 6-9.8 6s-7.9-2.4-9.8-6Z"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
              />
              <circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8" />
            </svg>
          </button>
        </div>
      </label>

      <label class="login-field">
        <span>确认密码</span>
        <div class="login-input-wrap">
          <span class="login-input-icon">▣</span>
          <input
            v-model="registerForm.confirmPassword"
            :type="confirmPasswordType"
            autocomplete="new-password"
            placeholder="请再次输入密码"
          />
          <button
            class="login-icon-button"
            type="button"
            :aria-label="showConfirmPassword ? '隐藏密码' : '显示密码'"
            @click="showConfirmPassword = !showConfirmPassword"
          >
            <svg class="login-eye-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M2.2 12c1.9-3.6 5.6-6 9.8-6s7.9 2.4 9.8 6c-1.9 3.6-5.6 6-9.8 6s-7.9-2.4-9.8-6Z"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
              />
              <circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8" />
            </svg>
          </button>
        </div>
      </label>

      <label class="login-check register-agreement">
        <input v-model="acceptedAgreement" type="checkbox" />
        <span>
          我已阅读并同意
          <button type="button" @click="showAgreement('terms')">《用户协议》</button>
          和
          <button type="button" @click="showAgreement('privacy')">《隐私政策》</button>
        </span>
      </label>

      <p v-if="registerError" class="login-message is-error">{{ registerError }}</p>

      <button class="login-submit" type="submit" :disabled="registerLoading">
        {{ registerLoading ? '注册中...' : '注册' }}
      </button>

      <div class="login-divider">
        <span></span>
        <em>其他登录方式</em>
        <span></span>
      </div>

      <button type="button" class="wechat-button" aria-label="微信登录" @click="showUnsupported">
        微
      </button>

      <p class="auth-switch-text">
        已有账号？
        <button type="button" @click="switchMode('login')">去登录</button>
      </p>
    </form>

    <div v-if="agreementModal" class="agreement-overlay" @click.self="agreementModal = null">
      <section class="agreement-modal">
        <h3>{{ agreementModal.title }}</h3>
        <p>{{ agreementModal.content }}</p>
        <button type="button" class="login-submit" @click="agreementModal = null">我知道了</button>
      </section>
    </div>

    <p class="login-copyright">© 2026 文档润色系统. 保留所有权利。</p>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  height: 100dvh;
  display: grid;
  grid-template-rows: auto auto auto;
  justify-items: center;
  align-content: center;
  gap: 16px;
  padding: 16px;
  overflow: hidden;
  background-color: #f7fbff;
  background-position: center;
  background-size: cover;
  color: #1e2a3d;
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  transform: translateX(-9px);
}

.login-logo {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: linear-gradient(145deg, #1d7aff, #1763e6);
  box-shadow: 0 12px 24px rgba(31, 112, 255, 0.22);
}

.login-logo::before {
  content: "";
  position: absolute;
  top: 9px;
  right: 9px;
  width: 13px;
  height: 13px;
  border-top: 2px solid rgba(255, 255, 255, 0.9);
  border-right: 2px solid rgba(255, 255, 255, 0.9);
}

.login-logo::after {
  content: "";
  position: absolute;
  left: 13px;
  top: 16px;
  width: 20px;
  height: 4px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 10px 0 rgba(255, 255, 255, 0.92), 0 20px 0 rgba(255, 255, 255, 0.86);
}

.login-logo span {
  position: absolute;
  right: -3px;
  bottom: 5px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ffffff;
}

.login-logo span::before,
.login-logo span::after {
  content: "";
  position: absolute;
  background: #2477ff;
}

.login-logo span::before {
  inset: 4px 8px;
}

.login-logo span::after {
  inset: 8px 4px;
}

.login-brand h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.15;
  color: #22304a;
}

.login-brand p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #7a869c;
}

.login-card {
  width: min(100%, 360px);
  padding: 24px 24px 22px;
  border: 1px solid rgba(214, 225, 240, 0.9);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 20px 48px rgba(33, 55, 91, 0.13);
  backdrop-filter: blur(10px);
}

.login-card-head h2 {
  margin: 0;
  font-size: 19px;
  line-height: 1.2;
  color: #1d2a3f;
}

.login-card-head p {
  margin: 10px 0 4px;
  font-size: 12px;
  color: #8792a6;
}

.login-field {
  display: grid;
  gap: 7px;
  margin-top: 14px;
  font-size: 13px;
  font-weight: 700;
  color: #23314a;
}

.login-input-wrap {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  align-items: center;
  height: 40px;
  border: 1px solid #d9e2ef;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.86);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.login-input-wrap:focus-within {
  border-color: #2b78ff;
  box-shadow: 0 0 0 3px rgba(43, 120, 255, 0.1);
}

.login-input-icon {
  color: #8795aa;
  text-align: center;
  font-size: 15px;
}

.login-input-wrap input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #1d2a3f;
  font-size: 13px;
}

.login-input-wrap input::-ms-reveal,
.login-input-wrap input::-ms-clear {
  display: none;
}

.login-input-wrap input::placeholder {
  color: #9aa7ba;
}

.login-icon-button,
.login-text-button,
.auth-switch-text button,
.register-agreement button {
  border: 0;
  background: transparent;
  font: inherit;
  cursor: pointer;
}

.login-icon-button {
  width: 34px;
  height: 100%;
  padding: 0;
  appearance: none;
  -webkit-appearance: none;
  color: #7d8ca3;
  display: grid;
  place-items: center;
}

.login-eye-icon {
  width: 18px;
  height: 18px;
  display: block;
}

.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0 14px;
}

.login-check {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: #364258;
}

.login-check input {
  width: 14px;
  height: 14px;
  margin: 0;
  accent-color: #1f78ff;
}

.login-text-button,
.auth-switch-text button,
.register-agreement button {
  padding: 0;
  color: #1374ff;
  font-size: 12px;
}

.login-message {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.45;
  color: #16724f;
}

.login-message.is-error {
  color: #c24135;
}

.login-submit {
  width: 100%;
  height: 40px;
  border: 0;
  border-radius: 6px;
  background: #1977ff;
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 20px rgba(25, 119, 255, 0.2);
  transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
}

.login-submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 14px 24px rgba(25, 119, 255, 0.26);
}

.login-submit:disabled {
  cursor: not-allowed;
  opacity: 0.68;
}

.login-divider {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  margin: 18px 0 14px;
  color: #8792a6;
}

.login-divider span {
  height: 1px;
  background: #dfe6f0;
}

.login-divider em {
  font-style: normal;
  font-size: 12px;
}

.wechat-button {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  border: 1px solid #dce5f0;
  border-radius: 50%;
  background: #ffffff;
  color: #19b563;
  font-size: 18px;
  font-weight: 800;
  cursor: pointer;
}

.auth-switch-text {
  margin: 10px 0 0;
  color: #5f6b80;
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
}

.register-card {
  padding: 22px 24px 18px;
}

.register-card .login-card-head p {
  margin: 8px 0 2px;
}

.register-card .login-field {
  gap: 5px;
  margin-top: 10px;
}

.register-card .login-input-wrap {
  height: 36px;
}

.register-card .login-submit {
  height: 38px;
}

.register-card .login-divider {
  margin: 14px 0 10px;
}

.register-card .wechat-button {
  width: 38px;
  height: 38px;
  font-size: 16px;
}

.register-agreement {
  align-items: flex-start;
  margin: 10px 0;
  line-height: 1.45;
  font-weight: 500;
  color: #5f6b80;
}

.register-agreement input {
  margin-top: 2px;
  flex: 0 0 auto;
}

.register-agreement span {
  min-width: 0;
}

.agreement-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(24, 36, 56, 0.18);
}

.agreement-modal {
  width: min(100%, 340px);
  padding: 18px;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 20px 48px rgba(33, 55, 91, 0.2);
}

.agreement-modal h3 {
  margin: 0 0 10px;
  font-size: 17px;
  color: #1f2c42;
}

.agreement-modal p {
  margin: 0;
  color: #607086;
  font-size: 13px;
  line-height: 1.7;
}

.agreement-modal .login-submit {
  margin-top: 16px;
  height: 36px;
}

.login-copyright {
  margin: 0;
  font-size: 12px;
  color: #7a869c;
}

@media (max-height: 720px) {
  .login-page {
    gap: 10px;
    padding: 10px;
  }

  .login-logo {
    width: 42px;
    height: 42px;
  }

  .login-brand h1 {
    font-size: 21px;
  }

  .login-card {
    padding: 18px 20px 16px;
  }

  .login-card-head h2 {
    font-size: 17px;
  }

  .login-card-head p {
    margin-top: 6px;
  }

  .login-field {
    margin-top: 10px;
  }

  .login-options {
    margin: 12px 0 10px;
  }

  .login-divider {
    margin: 14px 0 10px;
  }

  .register-card {
    padding: 14px 18px 12px;
  }

  .register-card .login-field {
    margin-top: 7px;
  }

  .register-card .login-input-wrap {
    height: 34px;
  }

  .register-card .login-divider {
    margin: 10px 0 8px;
  }

  .register-card .wechat-button {
    width: 34px;
    height: 34px;
  }

  .register-agreement {
    margin: 8px 0;
  }

  .auth-switch-text {
    margin-top: 7px;
  }
}

@media (max-width: 720px) {
  .login-page {
    gap: 10px;
    padding: 10px;
  }

  .login-brand {
    gap: 9px;
    transform: translateX(-6px);
  }

  .login-logo {
    width: 40px;
    height: 40px;
  }

  .login-brand h1 {
    font-size: 19px;
  }

  .login-brand p {
    margin-top: 4px;
    font-size: 11px;
  }

  .login-card {
    width: min(100%, 340px);
    padding: 18px 18px 16px;
  }

  .register-card {
    padding: 14px 16px 12px;
  }
}
</style>
