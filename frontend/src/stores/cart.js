/**
 * 购物车状态管理（Pinia）
 * 按用户隔离存储购物车数据，持久化到 localStorage
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function getCartStorageKey() {
  try {
    const authRaw = localStorage.getItem('ordering_bot_auth')
    if (authRaw) {
      const auth = JSON.parse(authRaw)
      return `ordering_bot_cart_${auth.id || 'guest'}`
    }
  } catch (e) {
    console.error('获取用户ID失败', e)
  }
  return 'ordering_bot_cart_guest'
}

function loadCart() {
  const key = getCartStorageKey()
  try {
    const raw = localStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed
    }
  } catch (e) {
    console.error('加载购物车失败', e)
  }
  return []
}

export const useCartStore = defineStore('cart', () => {
  const items = ref(loadCart())

  const totalCount = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0)
  )

  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.unit_price * item.quantity, 0)
  )

  function reloadCart() {
    items.value = loadCart()
  }

  function setCart(newItems) {
    items.value = newItems || []
    save()
  }

  function updateQuantity(menuItemId, quantity) {
    const item = items.value.find((i) => i.menu_item_id === menuItemId)
    if (item) {
      item.quantity = quantity
      save()
    }
  }

  function removeItem(menuItemId) {
    items.value = items.value.filter((i) => i.menu_item_id !== menuItemId)
    save()
  }

  function clearCart() {
    items.value = []
    save()
  }

  function save() {
    try {
      const key = getCartStorageKey()
      localStorage.setItem(key, JSON.stringify(items.value))
    } catch (e) {
      console.error('保存购物车失败', e)
    }
  }

  return { items, totalCount, totalPrice, reloadCart, setCart, updateQuantity, removeItem, clearCart }
})

/**
 * 清空所有用户的购物车数据（用于项目重新运行时）
 */
export function clearAllCartStorage() {
  const keysToRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith('ordering_bot_cart_')) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k))
}
