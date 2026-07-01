<!-- 商家后台：概览仪表盘 -->
<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card>
          <div class="stat-title">今日订单</div>
          <div class="stat-value">{{ stats.today_orders }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-title">今日销售额</div>
          <div class="stat-value">¥{{ stats.today_revenue.toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-title">商品总数</div>
          <div class="stat-value">{{ stats.total_items }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-title">待处理订单</div>
          <div class="stat-value">{{ stats.pending_orders }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-16">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>快捷入口</span>
            </div>
          </template>
          <div class="quick-entry">
            <el-button type="primary" @click="router.push('/admin/menu')">商品管理</el-button>
            <el-button type="success" @click="router.push('/admin/orders')">订单管理</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近订单</span>
            </div>
          </template>
          <el-table :data="recentOrders" size="small" v-loading="loading">
            <el-table-column prop="id" label="订单号" width="80" />
            <el-table-column prop="total_price" label="总价" width="90">
              <template #default="scope">¥{{ scope.row.total_price.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="scope">
                <el-tag :type="statusType(scope.row.status)" size="small">{{ statusText(scope.row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间">
              <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchDashboardStats, fetchAdminOrders } from '@/modules/admin/api/admin.api'
import { formatDate } from '@/shared/utils/date'
import { statusType, statusText } from '@/features/orders/utils/status'
import type { Order } from '@/shared/types'

interface DashboardStats {
  today_orders: number
  today_revenue: number
  total_items: number
  pending_orders: number
}

const router = useRouter()
const stats = ref<DashboardStats>({
  today_orders: 0,
  today_revenue: 0,
  total_items: 0,
  pending_orders: 0,
})
const recentOrders = ref<Order[]>([])
const loading = ref(false)

async function loadDashboard() {
  loading.value = true
  try {
    const [statsRes, ordersRes] = await Promise.all([
      fetchDashboardStats(),
      fetchAdminOrders({ page: 1, page_size: 5 }),
    ])
    stats.value = statsRes.data
    recentOrders.value = ordersRes.data.items.slice(0, 5)
  } catch (e) {
    ElMessage.error('加载仪表盘数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.stat-title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.mt-16 {
  margin-top: 16px;
}

.card-header {
  font-weight: 600;
}

.quick-entry {
  display: flex;
  gap: 12px;
}
</style>
