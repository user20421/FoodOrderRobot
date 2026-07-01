/**
 * 系统信息 API
 */
import api from '@/shared/api/client'
import type { StartupTimeResponse } from '@/shared/types'

export function getStartupTime() {
  return api.get<StartupTimeResponse>('/system/startup')
}
