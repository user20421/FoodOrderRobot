/**
 * 菜单相关 API
 */
import api from '@/shared/api/client'
import type { MenuItem } from '@/shared/types'

export function fetchMenuItems() {
  return api.get<MenuItem[]>('/menu')
}
