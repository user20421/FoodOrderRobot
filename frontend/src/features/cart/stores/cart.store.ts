/**
 * 购物车状态管理（Pinia）
 * 按用户隔离存储购物车数据，持久化到 localStorage
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { CartItem } from '@/shared/types'
import { STORAGE_KEY_AUTH, STORAGE_KEY_CART_PREFIX, getCartStorageKey } from '@/shared/constants'

function resolveCartStorageKey(): string {
  try {
    const authRaw = localStorage.getItem(STORAGE_KEY_AUTH)
    if (authRaw) {
      const auth = JSON.parse(authRaw)
      return getCartStorageKey(auth.id || 'guest')
    }
  } catch (e) {
    console.error('获取用户ID失败', e)
  }
  return `${STORAGE_KEY_CART_PREFIX}guest`
}

function loadCart(): CartItem[] {
  const key = resolveCartStorageKey()
  try {
    const raw = localStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed as CartItem[]
    }
  } catch (e) {
    console.error('加载购物车失败', e)
  }
  return []
}

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>(loadCart())

  const totalCount = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0)
  )

  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.unit_price * item.quantity, 0)
  )

  function reloadCart() {
    items.value = loadCart()
  }

  function setCart(newItems: CartItem[]) {
    items.value = newItems || []
    save()
  }

  function updateQuantity(menuItemId: number, quantity: number) {
    const item = items.value.find((i) => i.menu_item_id === menuItemId)
    if (item) {
      item.quantity = quantity
      save()
    }
  }

  function removeItem(menuItemId: number) {
    items.value = items.value.filter((i) => i.menu_item_id !== menuItemId)
    save()
  }

  function clearCart() {
    items.value = []
    save()
  }

  function save() {
    try {
      const key = resolveCartStorageKey()
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
  const keysToRemove: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(STORAGE_KEY_CART_PREFIX)) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k))
}
