/**
 * 订单状态映射工具
 */

export type OrderStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled'

export function statusType(status: OrderStatus): 'warning' | 'success' | 'info' | 'danger' {
  const map: Record<OrderStatus, 'warning' | 'success' | 'info' | 'danger'> = {
    pending: 'warning',
    confirmed: 'success',
    completed: 'info',
    cancelled: 'danger',
  }
  return map[status] || 'info'
}

export function statusText(status: OrderStatus): string {
  const map: Record<OrderStatus, string> = {
    pending: '待处理',
    confirmed: '已下单',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[status] || status
}
