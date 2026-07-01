/**
 * 商家管理后台 API
 */
import api from '@/shared/api/client'
import type { MenuItem, Order, PaginatedOrders } from '@/shared/types'

export interface DashboardStats {
  today_orders: number
  today_revenue: number
  total_items: number
  pending_orders: number
}

export interface MenuItemPayload {
  name: string
  description?: string | null
  price: number
  spicy_level: number
  category: string
  tags?: string | null
  stock: number
  is_recommended?: number
}

// Dashboard
export function fetchDashboardStats() {
  return api.get<DashboardStats>('/admin/dashboard')
}

// Menu management
export function fetchAdminMenu() {
  return api.get<MenuItem[]>('/admin/menu')
}

export function createMenuItem(payload: MenuItemPayload) {
  return api.post('/admin/menu', payload)
}

export function updateMenuItem(id: number, payload: MenuItemPayload) {
  return api.put(`/admin/menu/${id}`, payload)
}

export function deleteMenuItem(id: number) {
  return api.delete(`/admin/menu/${id}`)
}

// Orders management
export interface AdminPaginationParams {
  page?: number
  page_size?: number
}

export function fetchAdminOrders(params?: AdminPaginationParams) {
  return api.get<PaginatedOrders>('/admin/orders', { params })
}

export function fetchAdminOrdersCount() {
  return api.get<{ total: number }>('/admin/orders/count')
}

export function fetchPendingOrders() {
  return api.get<Order[]>('/admin/orders/pending')
}

export function completeOrder(orderId: number) {
  return api.post(`/admin/orders/${orderId}/complete`)
}

export function exportAdminOrders(params?: { start_date?: string; end_date?: string }) {
  return api.get<string>('/admin/orders/export', {
    params,
    responseType: 'text',
  })
}
