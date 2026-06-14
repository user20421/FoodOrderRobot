/**
 * 前端应用入口
 * 初始化 Vue、Pinia、ElementPlus、路由，启动时检测后端重启并清空聊天记录
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import type { Component } from 'vue'

import App from './App.vue'
import router from './router'
import { getStartupTime } from './api/system'
import { clearAllChatStorage } from './stores/chat'
import { clearAllCartStorage } from './stores/cart'

async function bootstrap() {
  // 启动时检查后端是否重新运行，若是则清空所有聊天记录
  try {
    const res = await getStartupTime()
    const newTime = res.data.startup_time
    const lastTime = localStorage.getItem('ordering_bot_last_startup')
    if (lastTime && lastTime !== newTime) {
      clearAllChatStorage()
      clearAllCartStorage()
    }
    // 清除旧的全局购物车 key（迁移用，一次性）
    localStorage.removeItem('ordering_bot_cart')
    localStorage.setItem('ordering_bot_last_startup', newTime)
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
  app.use(ElementPlus)

  app.mount('#app')
}

bootstrap()
