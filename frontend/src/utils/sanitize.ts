/**
 * XSS 消毒工具
 * 对需要 v-html 渲染的 HTML 内容进行白名单过滤
 */
import DOMPurify from 'dompurify'

/**
 * 消毒 HTML 字符串，移除危险标签和属性。
 * 允许 markdown 常用标签：a, p, br, strong, em, ul, ol, li, code, pre, blockquote, h1-h6
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a', 'p', 'br', 'strong', 'em', 'ul', 'ol', 'li',
      'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'span', 'div', 'hr'
    ],
    ALLOWED_ATTR: ['href', 'title', 'target', 'class'],
    ALLOW_DATA_ATTR: false,
  })
}

/**
 * 消毒纯文本中的换行转换结果（简单 HTML）
 */
export function sanitizeTextHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['br', 'p'],
    ALLOWED_ATTR: [],
  })
}
