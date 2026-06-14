/**
 * 系统信息 API
 */
import api from './index'
import type { StartupTimeResponse } from '../types'

export function getStartupTime() {
  return api.get<StartupTimeResponse>('/system/startup')
}
