import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, sendCode as sendCodeApi, logout as logoutApi, getUserInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('user_info') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  function saveTokens(access, refresh) {
    token.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function saveUserInfo(info) {
    userInfo.value = info
    localStorage.setItem('user_info', JSON.stringify(info))
  }

  async function login(account, password) {
    // 切换账号时清空旧数据
    const { useChatStore } = await import('@/stores/chat')
    useChatStore().reset()
    const res = await loginApi({ account, password })
    saveTokens(res.access_token, res.refresh_token)
    saveUserInfo(res.user)
    return res
  }

  async function register(data) {
    const { useChatStore } = await import('@/stores/chat')
    useChatStore().reset()
    const res = await registerApi(data)
    saveTokens(res.access_token, res.refresh_token)
    saveUserInfo(res.user)
    return res
  }

  async function sendCode(email) {
    return await sendCodeApi(email)
  }

  async function fetchUserInfo() {
    try {
      const res = await getUserInfo()
      saveUserInfo(res)
      return res
    } catch {
      return null
    }
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {
      // ignore
    }
    token.value = ''
    refreshToken.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
  }

  return {
    token,
    refreshToken,
    userInfo,
    isLoggedIn,
    login,
    register,
    sendCode,
    fetchUserInfo,
    logout,
  }
})