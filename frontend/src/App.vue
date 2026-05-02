<!-- 根布局组件：侧边栏导航 + 主内容区，根据角色渲染不同菜单 -->
<template>
  <el-container v-if="!isLoginPage" class="layout-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="32" color="#fff"><Food /></el-icon>
        <span class="title">{{ isAdmin ? '商家后台' : '点餐机器人' }}</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <!-- 用户端菜单 -->
        <template v-if="isCustomer">
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能点餐</span>
          </el-menu-item>
          <el-menu-item index="/menu">
            <el-icon><Dish /></el-icon>
            <span>菜单浏览</span>
          </el-menu-item>
          <el-menu-item index="/cart">
            <el-icon><ShoppingCart /></el-icon>
            <span>购物车</span>
            <el-badge v-if="cartStore.totalCount > 0" :value="cartStore.totalCount" style="margin-left: 8px;" />
          </el-menu-item>
          <el-menu-item index="/orders">
            <el-icon><List /></el-icon>
            <span>我的订单</span>
          </el-menu-item>
        </template>

        <!-- 商家端菜单 -->
        <template v-if="isAdmin">
          <el-menu-item index="/admin/menu">
            <el-icon><Dish /></el-icon>
            <span>商品管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/orders">
            <el-icon><List /></el-icon>
            <span>订单管理</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">{{ pageTitle }}</div>
        <div class="header-right">
          <span v-if="authStore.user" style="margin-right: 12px; color: #666;">
            {{ authStore.user.username }}
          </span>
          <el-button size="small" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- 登录页不需要侧边栏 -->
  <router-view v-else />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useCartStore } from './stores/cart'
import { useChatStore } from './stores/chat'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const cartStore = useCartStore()
const chatStore = useChatStore()

const isLoginPage = computed(() => route.path === '/login')
const isAdmin = computed(() => authStore.isAdmin)
const isCustomer = computed(() => authStore.isCustomer)

const pageTitle = computed(() => {
  const titles = {
    '/chat': '智能点餐助手',
    '/menu': '本店菜单',
    '/cart': '购物车',
    '/orders': '我的订单',
    '/admin/menu': '商品管理',
    '/admin/orders': '订单管理',
  }
  return titles[route.path] || '点餐机器人'
})

function handleLogout() {
  authStore.logout()
  chatStore.clearMessages()
  cartStore.clearCart()
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid #1f2d3d;
}

.title {
  color: #fff;
  font-size: 18px;
  font-weight: bold;
}

.header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 10;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.main-content {
  background-color: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}
</style>
