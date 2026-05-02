/**
 * 系统信息 API
 */
import api from './index'

export function getStartupTime() {
  return api.get('/system/startup')
}
