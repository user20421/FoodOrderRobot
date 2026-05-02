/**
 * 购物车状态管理（Pinia）
 * 提供购物车增删改查，数据持久化到 localStorage
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const CART_STORAGE_KEY = 'ordering_bot_cart'

function loadCart() {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY)
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
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items.value))
    } catch (e) {
      console.error('保存购物车失败', e)
    }
  }

  return { items, totalCount, totalPrice, setCart, updateQuantity, removeItem, clearCart }
})
