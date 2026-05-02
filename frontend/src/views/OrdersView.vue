<!-- 我的订单页面：订单列表、状态标签、导出单条/全部订单 -->
<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>订单列表</span>
          <div>
            <el-button type="success" size="small" @click="exportAllOrders" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出全部订单
            </el-button>
            <el-button type="primary" size="small" @click="loadOrders">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="orders" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="订单号" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="statusType(scope.row.status)">
              {{ statusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_price" label="总价" width="120">
          <template #default="scope">¥{{ scope.row.total_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="菜品明细">
          <template #default="scope">
            <div v-for="it in scope.row.items" :key="it.id" class="item-row">
              {{ it.menu_item_name || ('菜品#' + it.menu_item_id) }} × {{ it.quantity }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="scope">
            <el-button size="small" type="primary" plain @click="exportOrder(scope.row.id)">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && orders.length === 0" description="暂无订单数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { formatDate, statusType, statusText, downloadTxt } from '../utils'

const orders = ref([])
const loading = ref(false)
const exporting = ref(false)
const authStore = useAuthStore()

async function loadOrders() {
  loading.value = true
  try {
    const res = await api.get('/orders', { params: { user_id: authStore.userId } })
    orders.value = res.data
  } catch (e) {
    ElMessage.error('获取订单失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function exportOrder(orderId) {
  try {
    const res = await api.get(`/orders/${orderId}/export`, { responseType: 'text' })
    downloadTxt(res.data, `order_${orderId}.txt`)
    ElMessage.success('订单导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
    console.error(e)
  }
}

async function exportAllOrders() {
  exporting.value = true
  try {
    const res = await api.get('/orders/export', {
      params: { user_id: authStore.userId },
      responseType: 'text',
    })
    downloadTxt(res.data, `orders_user_${authStore.userId}.txt`)
    ElMessage.success('全部订单导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
    console.error(e)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadOrders()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.item-row {
  font-size: 13px;
  color: #666;
}
</style>
