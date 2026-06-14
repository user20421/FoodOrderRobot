<!-- 用户端：订单状态跟踪 -->
<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>我的订单状态</span>
          <el-button type="primary" size="small" @click="loadOrders" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-empty v-if="!loading && activeOrders.length === 0" description="暂无进行中的订单" />

      <div v-else class="order-list">
        <el-card
          v-for="order in activeOrders"
          :key="order.id"
          class="order-card making"
          shadow="hover"
        >
          <div class="order-header">
            <span class="order-id">订单 #{{ order.id }}</span>
            <el-tag type="warning" size="large" effect="dark">
              正在制作
            </el-tag>
          </div>

          <div class="order-items">
            <div v-for="item in order.items" :key="item.id" class="item-row">
              {{ item.name }} × {{ item.quantity }}
            </div>
          </div>

          <div class="order-footer">
            <span class="order-time">{{ formatDate(order.created_at) }}</span>
            <span class="order-total">合计 ¥{{ order.total_price.toFixed(2) }}</span>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { formatDate } from '@/utils'
import type { Order } from '@/types'

const orders = ref<Order[]>([])
const loading = ref(false)

const activeOrders = computed(() => orders.value.filter(o => o.status !== 'completed'))

async function loadOrders() {
  loading.value = true
  try {
    const res = await api.get<Order[]>('/orders')
    orders.value = res.data
  } catch (e) {
    ElMessage.error('获取订单状态失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadOrders)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.order-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.order-card {
  border-left: 4px solid #e6a23c;
}

.order-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.order-id {
  font-weight: bold;
  font-size: 16px;
}

.order-items {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #dcdfe6;
}

.item-row {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
}

.order-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.order-time {
  color: #909399;
}

.order-total {
  font-weight: bold;
  color: #f56c6c;
  font-size: 16px;
}
</style>
