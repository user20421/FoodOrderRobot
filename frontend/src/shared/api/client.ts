/**
 * Axios 实例封装
 * 统一配置 baseURL、超时、请求/响应拦截器（注入 JWT、处理 401/403）
 */
import axios, { AxiosError, AxiosHeaders } from 'axios'
import type { ApiErrorDetail } from '@/shared/types'
import { useAuthStore } from '@/features/auth/stores/auth.store'
import router from '@/app/router'
import { ElMessage } from 'element-plus'
import { API_BASE_URL, API_TIMEOUT, STORAGE_KEY_TOKEN } from '@/shared/constants'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：自动注入 JWT
api.interceptors.request.use(
  (config) => {
    try {
      const token = localStorage.getItem(STORAGE_KEY_TOKEN)
      if (token) {
        const headers = AxiosHeaders.from(config.headers)
        headers.set('Authorization', `Bearer ${token}`)
        config.headers = headers
      }
    } catch (e) {
      console.error('读取 token 失败', e)
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorDetail>) => {
    if (error.response) {
      const status = error.response.status
      const detail = error.response.data?.detail || '请求失败'
      if (status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        const authStore = useAuthStore()
        authStore.logout()
        router.push('/login')
      } else if (status === 403) {
        ElMessage.error('权限不足：' + detail)
      } else {
        ElMessage.error(`请求错误 ${status}：` + detail)
      }
    } else if (error.request) {
      ElMessage.error('网络错误，无法连接到服务器')
    }
    return Promise.reject(error)
  }
)

export default api
