/**
 * Axios 实例封装
 * 统一配置 baseURL、超时、请求/响应拦截器（注入认证头、处理 401/403）
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：自动注入用户认证信息
api.interceptors.request.use(
  (config) => {
    try {
      const authRaw = localStorage.getItem('ordering_bot_auth')
      if (authRaw) {
        const auth = JSON.parse(authRaw)
        if (auth.id) {
          config.headers['X-User-ID'] = auth.id
        }
        if (auth.role) {
          config.headers['X-User-Role'] = auth.role
        }
      }
    } catch (e) {
      console.error('读取认证信息失败', e)
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status
      const detail = error.response.data?.detail || '请求失败'
      if (status === 401) {
        console.error('未登录或登录已过期')
      } else if (status === 403) {
        console.error('权限不足:', detail)
      } else {
        console.error(`请求错误 ${status}:`, detail)
      }
    } else if (error.request) {
      console.error('网络错误，无法连接到服务器')
    }
    return Promise.reject(error)
  }
)

export default api
