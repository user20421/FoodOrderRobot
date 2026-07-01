/**
 * 前端应用入口
 * 初始化 Vue、Pinia、ElementPlus、路由，启动时检测后端重启并清空聊天记录
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import type { Component } from 'vue'

import App from '@/app/App.vue'
import router from '@/app/router'
import { getStartupTime } from '@/shared/api/system'
import { clearAllChatStorage } from '@/features/chat/stores/chat.store'
import { clearAllCartStorage } from '@/features/cart/stores/cart.store'
import { STORAGE_KEY_LAST_STARTUP, STORAGE_KEY_CART_PREFIX } from '@/shared/constants'

async function bootstrap() {
  // 启动时检查后端是否重新运行，若是则清空所有聊天记录
  try {
    const res = await getStartupTime()
    const newTime = res.data.startup_time
    const lastTime = localStorage.getItem(STORAGE_KEY_LAST_STARTUP)
    if (lastTime && lastTime !== newTime) {
      clearAllChatStorage()
      clearAllCartStorage()
    }
    // 清除旧的全局购物车 key（迁移用，一次性）
    localStorage.removeItem(STORAGE_KEY_CART_PREFIX.replace(/_$/, ''))
    localStorage.setItem(STORAGE_KEY_LAST_STARTUP, newTime)
  } catch (e) {
    console.error('获取启动时间失败', e)
  }

  const app = createApp(App)

  // 注册所有图标
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component as Component)
  }

  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus, {
    locale: {
      ...zhCn,
      el: {
        ...zhCn.el,
        pagination: {
          ...zhCn.el.pagination,
          total: '总数 {total}',
        },
      },
    },
  })

  app.mount('#app')
}

bootstrap()
