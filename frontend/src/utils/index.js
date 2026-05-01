/**
 * 公共工具函数
 */

export function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

export function statusType(status) {
  const map = { pending: 'warning', confirmed: 'success', completed: 'info', cancelled: 'danger' }
  return map[status] || 'info'
}

export function statusText(status) {
  const map = { pending: '待处理', confirmed: '已确认', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}

export function downloadTxt(content, filename) {
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
