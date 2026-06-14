/**
 * 公共工具函数
 */

export type OrderStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled'

export function formatDate(iso: string | undefined | null): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

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

export function downloadTxt(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
