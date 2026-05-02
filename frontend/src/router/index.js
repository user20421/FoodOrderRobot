/**
 * Vue Router 配置
 * 定义路由表，导航守卫处理登录鉴权、角色权限、用户切换时重载聊天记录
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'Chat', component: () => import('../views/ChatView.vue'), meta: { role: 'customer' } },
  { path: '/menu', name: 'Menu', component: () => import('../views/MenuView.vue'), meta: { role: 'customer' } },
  { path: '/cart', name: 'Cart', component: () => import('../views/CartView.vue'), meta: { role: 'customer' } },
  { path: '/orders', name: 'Orders', component: () => import('../views/OrdersView.vue'), meta: { role: 'customer' } },
  { path: '/admin', redirect: '/admin/menu' },
  { path: '/admin/menu', name: 'AdminMenu', component: () => import('../views/admin/AdminMenuView.vue'), meta: { role: 'admin' } },
  { path: '/admin/orders', name: 'AdminOrders', component: () => import('../views/admin/AdminOrdersView.vue'), meta: { role: 'admin' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', redirect: '/chat' },
]

const router = createRouter({ history: createWebHistory(), routes })

// 从 sessionStorage 恢复 lastUserId，避免刷新时误触发 reloadMessages
let lastUserId = sessionStorage.getItem('ordering_bot_last_user_id') || null

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn
  const isAdmin = authStore.isAdmin
  const isCustomer = authStore.isCustomer

  if (to.meta.public) {
    if (isLoggedIn) return next(isAdmin ? '/admin' : '/chat')
    return next()
  }

  if (!isLoggedIn) return next('/login')
  if (to.meta.role === 'admin' && !isAdmin) return next('/chat')
  if (to.meta.role === 'customer' && !isCustomer && !isAdmin) return next('/login')

  // 检测用户切换：只在用户确实切换时才重载聊天记录
  const currentUserId = authStore.user?.id || null
  if (currentUserId !== lastUserId) {
    lastUserId = currentUserId
    sessionStorage.setItem('ordering_bot_last_user_id', lastUserId || '')
    const chatStore = useChatStore()
    chatStore.reloadMessages()
  }

  next()
})

export default router
