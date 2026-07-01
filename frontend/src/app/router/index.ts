/**
 * Vue Router 配置
 * 定义路由表，导航守卫处理登录鉴权、角色权限、用户切换时重载聊天记录
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/features/auth/stores/auth.store'
import { useChatStore } from '@/features/chat/stores/chat.store'
import { useCartStore } from '@/features/cart/stores/cart.store'
import { STORAGE_KEY_LAST_USER_ID } from '@/shared/constants'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/chat', name: 'Chat', component: () => import('@/views/ChatView.vue'), meta: { role: 'customer' } },
  { path: '/menu', name: 'Menu', component: () => import('@/views/MenuView.vue'), meta: { role: 'customer' } },
  { path: '/cart', name: 'Cart', component: () => import('@/views/CartView.vue'), meta: { role: 'customer' } },
  { path: '/orders', name: 'Orders', component: () => import('@/views/OrdersView.vue'), meta: { role: 'customer' } },
  { path: '/order-status', name: 'OrderStatus', component: () => import('@/views/OrderStatusView.vue'), meta: { role: 'customer' } },
  { path: '/admin', redirect: '/admin/dashboard' },
  { path: '/admin/dashboard', name: 'AdminDashboard', component: () => import('@/modules/admin/views/AdminDashboardView.vue'), meta: { role: 'admin' } },
  { path: '/admin/menu', name: 'AdminMenu', component: () => import('@/modules/admin/views/AdminMenuView.vue'), meta: { role: 'admin' } },
  { path: '/admin/orders', name: 'AdminOrders', component: () => import('@/modules/admin/views/AdminOrdersView.vue'), meta: { role: 'admin' } },
  { path: '/admin/pending-orders', name: 'AdminPendingOrders', component: () => import('@/modules/admin/views/AdminPendingOrdersView.vue'), meta: { role: 'admin' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', redirect: '/chat' },
]

const router = createRouter({ history: createWebHistory(), routes })

// 从 sessionStorage 恢复 lastUserId，避免刷新时误触发 reloadMessages
let lastUserId: string | number | null = sessionStorage.getItem(STORAGE_KEY_LAST_USER_ID)

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const isLoggedIn = authStore.isLoggedIn
  const isAdmin = authStore.isAdmin
  const isCustomer = authStore.isCustomer

  // 根路径按角色动态重定向
  if (to.path === '/') {
    if (!isLoggedIn) return next('/login')
    return next(isAdmin ? '/admin' : '/chat')
  }

  if (to.meta.public) {
    if (isLoggedIn) return next(isAdmin ? '/admin' : '/chat')
    return next()
  }

  if (!isLoggedIn) return next('/login')

  // 角色权限控制
  if (to.meta.role === 'admin' && !isAdmin) return next('/chat')
  if (to.meta.role === 'customer' && !isCustomer) return next('/admin')

  // 检测用户切换：只在用户确实切换时才重载聊天记录
  const currentUserId = authStore.user?.id ?? null
  if (currentUserId !== lastUserId) {
    lastUserId = currentUserId
    sessionStorage.setItem(STORAGE_KEY_LAST_USER_ID, String(lastUserId ?? ''))
    const chatStore = useChatStore()
    const cartStore = useCartStore()
    chatStore.reloadMessages()
    cartStore.reloadCart()
  }

  next()
})

export default router
