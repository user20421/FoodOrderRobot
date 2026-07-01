<!-- 商家后台：待处理订单 -->
<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>待处理订单</span>
          <el-button type="primary" size="small" @click="loadPendingOrders" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-empty v-if="!loading && orders.length === 0" description="暂无待处理订单" />

      <el-row v-else :gutter="16">
        <el-col
          v-for="order in orders"
          :key="order.id"
          :xs="24"
          :sm="12"
          :md="8"
          class="order-col"
        >
          <el-card class="pending-order-card" shadow="hover">
            <div class="order-header">
              <span class="order-id">订单 #{{ order.id }}</span>
              <el-tag type="warning" effect="dark">正在制作</el-tag>
            </div>

            <div class="order-info">
              <div class="info-row">
                <span class="label">用户ID：</span>
                <span>{{ order.user_id }}</span>
              </div>
              <div class="info-row">
                <span class="label">下单时间：</span>
                <span>{{ formatDate(order.created_at) }}</span>
              </div>
              <div class="info-row">
                <span class="label">合计：</span>
                <span class="price">¥{{ order.total_price.toFixed(2) }}</span>
              </div>
            </div>

            <div class="order-items">
              <div class="section-title">菜品明细</div>
              <div v-for="item in order.items" :key="item.id" class="item-row">
                {{ item.name || ('菜品#' + item.menu_item_id) }} × {{ item.quantity }}
              </div>
            </div>

            <div class="order-action">
              <el-button
                type="success"
                size="large"
                style="width: 100%"
                :loading="completing === order.id"
                @click="handleComplete(order.id)"
              >
                <el-icon><Check /></el-icon>
                完成制作
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchPendingOrders, completeOrder } from '@/modules/admin/api/admin.api'
import { formatDate } from '@/shared/utils/date'
import type { Order } from '@/shared/types'

const orders = ref<Order[]>([])
const loading = ref(false)
const completing = ref<number | null>(null)

async function loadPendingOrders() {
  loading.value = true
  try {
    const res = await fetchPendingOrders()
    orders.value = res.data
  } catch (e) {
    ElMessage.error('获取待处理订单失败')
  } finally {
    loading.value = false
  }
}

async function handleComplete(orderId: number) {
  try {
    await ElMessageBox.confirm('确认该订单已完成制作？完成后将通知用户。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    completing.value = orderId
    await completeOrder(orderId)
    ElMessage.success('订单已完成，已通知用户')
    await loadPendingOrders()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('完成订单失败')
    }
  } finally {
    completing.value = null
  }
}

onMounted(loadPendingOrders)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.order-col {
  margin-bottom: 16px;
}

.pending-order-card {
  border-top: 4px solid #e6a23c;
  height: 100%;
}

.order-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.order-id {
  font-weight: bold;
  font-size: 16px;
}

.order-info {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #dcdfe6;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  line-height: 2;
}

.label {
  color: #909399;
}

.price {
  font-weight: bold;
  color: #f56c6c;
  font-size: 16px;
}

.order-items {
  margin-bottom: 16px;
  min-height: 60px;
}

.section-title {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 600;
}

.item-row {
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
}

.order-action {
  margin-top: auto;
}
</style>
