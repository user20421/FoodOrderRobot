/**
 * 应用级常量配置
 */

/** 默认欢迎语 */
export const DEFAULT_WELCOME_MESSAGE = '你好！我是美味餐厅的小助手，可以帮你点餐、查菜单、问问题。请问今天想吃点什么？'

/** 辣度选项 */
export const SPICY_LEVELS = [0, 1, 2, 3, 4, 5] as const

/** 辣度显示文本 */
export const SPICY_TEXT: Record<number, string> = {
  0: '不辣',
  1: '微辣',
  2: '中辣',
  3: '重辣',
  4: '特辣',
  5: '变态辣',
}

/** 辣度标签类型 */
export const SPICY_TYPE: Record<number, 'info' | 'success' | 'warning' | 'danger'> = {
  0: 'info',
  1: 'success',
  2: 'warning',
  3: 'warning',
  4: 'danger',
  5: 'danger',
}

/** 默认菜单分类 */
export const DEFAULT_MENU_CATEGORIES = ['全部', '热菜', '凉菜', '汤羹', '主食', '饮品', '甜点']

/** 图片上传限制（字节） */
export const IMAGE_UPLOAD_MAX_SIZE = 5 * 1024 * 1024 // 5MB

/** 支持的图片 MIME 类型 */
export const IMAGE_UPLOAD_ACCEPT = 'image/*'

/** 默认后端 API 地址（开发环境通过 Vite proxy 转发） */
export const API_BASE_URL = '/api/v1'

/** 请求超时时间（毫秒） */
export const API_TIMEOUT = 30000
