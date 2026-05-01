import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { getStartupTime } from './api/system'
import { clearAllChatStorage } from './stores/chat'

async function bootstrap() {
  // 启动时检查后端是否重新运行，若是则清空所有聊天记录
  try {
    const res = await getStartupTime()
    const newTime = res.data.startup_time
    const lastTime = localStorage.getItem('ordering_bot_last_startup')
    if (lastTime && lastTime !== newTime) {
      clearAllChatStorage()
    }
    localStorage.setItem('ordering_bot_last_startup', newTime)
  } catch (e) {
    console.error('获取启动时间失败', e)
  }

  const app = createApp(App)

  // 注册所有图标
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus)

  app.mount('#app')
}

bootstrap()
