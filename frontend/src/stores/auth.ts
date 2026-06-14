/**
 * 用户认证状态管理（Pinia）
 * 管理登录态、角色权限、JWT token，数据持久化到 localStorage
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { User, UserRole } from '../types'

const STORAGE_KEY = 'ordering_bot_auth'
const TOKEN_KEY = 'ordering_bot_token'

interface StoredAuth {
  user: User
  token: string
}

function loadAuth(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed.user?.id === 'number' && parsed.user?.username && parsed.user?.role) {
        return parsed.user as User
      }
    }
  } catch (e) {
    console.error('加载认证信息失败', e)
  }
  return null
}

function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch (e) {
    console.error('加载 token 失败', e)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const auth = ref<User | null>(loadAuth())
  const token = ref<string | null>(loadToken())

  const isLoggedIn = computed(() => !!auth.value && !!token.value)
  const user = computed(() => auth.value)
  const isAdmin = computed(() => auth.value?.role === 'admin')
  const isCustomer = computed(() => auth.value?.role === 'customer')
  const userId = computed(() => auth.value?.id ?? null)

  function setAuth(data: StoredAuth) {
    auth.value = data.user
    token.value = data.token
    save()
  }

  function logout() {
    auth.value = null
    token.value = null
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(TOKEN_KEY)
  }

  function save() {
    if (auth.value && token.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: auth.value, token: token.value }))
      localStorage.setItem(TOKEN_KEY, token.value)
    } else {
      localStorage.removeItem(STORAGE_KEY)
      localStorage.removeItem(TOKEN_KEY)
    }
  }

  return { auth, token, isLoggedIn, user, isAdmin, isCustomer, userId, setAuth, logout }
})

export type { UserRole }
