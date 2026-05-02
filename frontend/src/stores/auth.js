/**
 * 用户认证状态管理（Pinia）
 * 管理登录态、角色权限，数据持久化到 localStorage
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'ordering_bot_auth'

function loadAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) {
    console.error('加载认证信息失败', e)
  }
  return null
}

export const useAuthStore = defineStore('auth', () => {
  const auth = ref(loadAuth())

  const isLoggedIn = computed(() => !!auth.value)
  const user = computed(() => auth.value)
  const isAdmin = computed(() => auth.value?.role === 'admin')
  const isCustomer = computed(() => auth.value?.role === 'customer')
  const userId = computed(() => auth.value?.id || 1)

  function setAuth(data) {
    auth.value = data
    save()
  }

  function logout() {
    auth.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  function save() {
    if (auth.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(auth.value))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  return { auth, isLoggedIn, user, isAdmin, isCustomer, userId, setAuth, logout }
})
