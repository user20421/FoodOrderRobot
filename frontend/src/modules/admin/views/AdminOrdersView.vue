<!-- 商家后台：订单管理页面（查看全部订单、导出） -->
<template>
  <div class="page-wrapper">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>订单管理</span>
          <div>
            <el-button type="success" size="small" @click="exportAllOrders" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出全部订单
            </el-button>
            <el-button type="primary" size="small" @click="loadOrders">刷新</el-button>
          </div>
        </div>
      </template>

      <div class="table-wrapper">
        <el-table :data="orders" stripe v-loading="loading">
          <el-table-column prop="id" label="订单号" width="80" />
          <el-table-column prop="user_id" label="用户ID" width="90" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="statusType(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_price" label="总价" width="100">
            <template #default="scope">¥{{ scope.row.total_price.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="下单时间">
            <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="菜品明细">
            <template #default="scope">
              <div v-for="it in scope.row.items" :key="it.id" class="item-row">
                {{ it.name || ('菜品#' + it.menu_item_id) }} × {{ it.quantity }} = ¥{{ (it.unit_price * it.quantity).toFixed(2) }}
              </div>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!loading && orders.length === 0" description="暂无订单数据" />
      </div>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[5, 10]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAdminOrders, exportAdminOrders } from '@/modules/admin/api/admin.api'
import { formatDate } from '@/shared/utils/date'
import { downloadPdf } from '@/shared/utils/download'
import { statusType, statusText } from '@/features/orders/utils/status'
import type { Order } from '@/shared/types'

const orders = ref<Order[]>([])
const loading = ref(false)
const exporting = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(5)

async function loadOrders() {
  loading.value = true
  try {
    const res = await fetchAdminOrders({
      page: page.value,
      page_size: pageSize.value,
    })
    orders.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    ElMessage.error('获取订单失败')
  } finally {
    loading.value = false
  }
}

function handleSizeChange(newSize: number) {
  pageSize.value = newSize
  page.value = 1
  loadOrders()
}

function handlePageChange(newPage: number) {
  page.value = newPage
  loadOrders()
}

async function exportAllOrders() {
  exporting.value = true
  try {
    const res = await exportAdminOrders()
    downloadPdf(res.data, 'all_orders.pdf')
    ElMessage.success('全部订单导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
    console.error(e)
  } finally {
    exporting.value = false
  }
}

onMounted(loadOrders)

watch(pageSize, () => {
  page.value = 1
})
</script>

<style scoped>
.page-wrapper {
  height: 100%;
}

.page-wrapper :deep(.el-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-wrapper :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.table-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.item-row {
  font-size: 13px;
  color: #666;
}

.pagination-bar {
  flex-shrink: 0;
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.pagination-bar :deep(.el-pagination .el-select) {
  width: 110px !important;
}
</style>
