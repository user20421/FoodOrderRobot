/**
 * 订单相关 API（顾客端）
 */
import api from '@/shared/api/client'
import type { PaginatedOrders } from '@/shared/types'

export interface PaginationParams {
  page?: number
  page_size?: number
}

export function fetchMyOrders(userId: number, params?: PaginationParams) {
  return api.get<PaginatedOrders>('/orders', { params: { user_id: userId, ...params } })
}

export function fetchMyOrdersCount(userId: number) {
  return api.get<{ total: number }>('/orders/count', { params: { user_id: userId } })
}

export function fetchAllOrders(userId: number) {
  // 订单状态页需要全部订单用于筛选，使用较大 page_size 一次性获取
  return api.get<PaginatedOrders>('/orders', { params: { user_id: userId, page: 1, page_size: 1000 } })
}

export function exportOrder(orderId: number) {
  return api.get<Blob>(`/orders/${orderId}/export`, { responseType: 'blob' })
}

export function exportAllOrders(params?: { user_id?: number; start_date?: string; end_date?: string }) {
  return api.get<Blob>('/orders/export', {
    params,
    responseType: 'blob',
  })
}
