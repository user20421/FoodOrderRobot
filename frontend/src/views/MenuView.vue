<!-- 菜单浏览页面：分类筛选、搜索、卡片式展示、一键加购 -->
<template>
  <div>
    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索菜品名称"
        clearable
        style="width: 300px"
        prefix-icon="Search"
      />
      <el-radio-group v-model="filterCategory">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="热菜">热菜</el-radio-button>
        <el-radio-button label="素菜">素菜</el-radio-button>
        <el-radio-button label="海鲜">海鲜</el-radio-button>
        <el-radio-button label="汤品">汤品</el-radio-button>
        <el-radio-button label="主食">主食</el-radio-button>
        <el-radio-button label="凉菜">凉菜</el-radio-button>
      </el-radio-group>
    </div>

    <el-row :gutter="16">
      <el-col
        v-for="item in filteredItems"
        :key="item.id"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <el-card class="menu-card" shadow="hover">
          <div class="card-header">
            <span class="dish-name">{{ item.name }}</span>
            <el-tag size="small" :type="spicyType(item.spicy_level)">
              {{ spicyText(item.spicy_level) }}
            </el-tag>
          </div>
          <div class="dish-category">
            {{ item.category }}
            <el-tag size="small" :type="item.stock === 0 ? 'danger' : item.stock < 20 ? 'warning' : 'success'" style="margin-left: 8px;">
              库存: {{ item.stock }}
            </el-tag>
          </div>
          <div class="dish-desc">{{ item.description }}</div>
          <div class="card-footer">
            <span class="price">¥{{ item.price.toFixed(2) }}</span>
            <el-button
              type="primary"
              size="small"
              :disabled="item.stock === 0"
              :loading="loadingId === item.id"
              @click="addToCart(item)"
            >
              {{ item.stock === 0 ? '已售罄' : '点餐' }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchMenuItems } from '@/features/menu/api/menu.api'
import { useCartStore } from '@/features/cart/stores/cart.store'
import type { MenuItem, CartItem } from '@/shared/types'

const items = ref<MenuItem[]>([])
const search = ref('')
const filterCategory = ref('')
const loadingId = ref<number | null>(null)
const cartStore = useCartStore()

const filteredItems = computed(() => {
  return items.value.filter((item) => {
    const matchName = item.name.toLowerCase().includes(search.value.toLowerCase())
    const matchCategory = !filterCategory.value || item.category === filterCategory.value
    return matchName && matchCategory
  })
})

function spicyType(level: number): 'info' | 'warning' | 'danger' {
  if (level === 0) return 'info'
  if (level <= 2) return 'warning'
  return 'danger'
}

function spicyText(level: number): string {
  if (level === 0) return '不辣'
  return '辣'.repeat(level)
}

function addToCart(item: MenuItem) {
  loadingId.value = item.id

  // 本地直接操作购物车，不经过 LLM，更可靠
  const existing = cartStore.items.find((i) => i.menu_item_id === item.id)
  let newItems: CartItem[]
  if (existing) {
    newItems = cartStore.items.map((i) =>
      i.menu_item_id === item.id
        ? { ...i, quantity: i.quantity + 1 }
        : i
    )
  } else {
    newItems = [
      ...cartStore.items,
      {
        menu_item_id: item.id,
        name: item.name,
        quantity: 1,
        unit_price: item.price,
      },
    ]
  }
  cartStore.setCart(newItems)
  ElMessage.success({ message: `已加购：${item.name}`, duration: 1500 })

  loadingId.value = null
}

onMounted(async () => {
  try {
    const res = await fetchMenuItems()
    items.value = res.data
  } catch (e) {
    ElMessage.error('获取菜单失败')
  }
})
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.menu-card {
  margin-bottom: 16px;
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.dish-name {
  font-size: 16px;
  font-weight: bold;
  color: #333;
}

.dish-category {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.dish-desc {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 12px;
  min-height: 60px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.price {
  font-size: 18px;
  font-weight: bold;
  color: #f56c6c;
}
</style>
