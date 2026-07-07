<!-- 商家后台：商品管理页面（增删改查菜品） -->
<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>商品管理</span>
          <el-button type="primary" @click="openAdd">新增商品</el-button>
        </div>
      </template>

      <el-table :data="items" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="菜品名称" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="price" label="价格" width="100">
          <template #default="scope">¥{{ scope.row.price }}</template>
        </el-table-column>
        <el-table-column prop="stock" label="库存" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.stock === 0 ? 'danger' : scope.row.stock < 20 ? 'warning' : 'success'">
              {{ scope.row.stock }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="spicy_level" label="辣度" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button size="small" @click="openEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑商品' : '新增商品'" width="500px">
      <el-form :model="form" label-position="top">
        <el-form-item label="菜品名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%">
            <el-option label="热菜" value="热菜" />
            <el-option label="素菜" value="素菜" />
            <el-option label="海鲜" value="海鲜" />
            <el-option label="凉菜" value="凉菜" />
            <el-option label="汤品" value="汤品" />
            <el-option label="主食" value="主食" />
            <el-option label="饮品" value="饮品" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="form.price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="库存">
          <el-input-number v-model="form.stock" :min="0" :precision="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="辣度 (0-5)">
          <el-input-number v-model="form.spicy_level" :min="0" :max="5" :precision="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="用逗号分隔，如：辣,下饭,经典" />
        </el-form-item>
        <el-form-item label="是否推荐">
          <el-switch v-model="form.is_recommended" active-text="推荐" inactive-text="普通" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saveLoading">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAdminMenu, createMenuItem, updateMenuItem, deleteMenuItem } from '@/modules/admin/api/admin.api'
import type { MenuItem } from '@/shared/types'

interface MenuForm {
  name: string
  category: string
  price: number
  stock: number
  spicy_level: number
  is_recommended: boolean
  description: string
  tags: string
}

const items = ref<MenuItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saveLoading = ref(false)
const isEdit = ref(false)
const form = ref<MenuForm>({
  name: '',
  category: '热菜',
  price: 0,
  stock: 100,
  spicy_level: 0,
  is_recommended: false,
  description: '',
  tags: '',
})
const editingId = ref<number | null>(null)

const defaultForm: MenuForm = {
  name: '',
  category: '热菜',
  price: 0,
  stock: 100,
  spicy_level: 0,
  is_recommended: false,
  description: '',
  tags: '',
}

async function loadItems() {
  loading.value = true
  try {
    const res = await fetchAdminMenu()
    items.value = res.data
  } catch (e) {
    ElMessage.error('获取商品失败')
  } finally {
    loading.value = false
  }
}

function openAdd() {
  isEdit.value = false
  editingId.value = null
  form.value = { ...defaultForm }
  dialogVisible.value = true
}

function openEdit(row: MenuItem) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    category: row.category,
    price: row.price,
    stock: row.stock,
    spicy_level: row.spicy_level,
    is_recommended: !!row.is_recommended,
    description: row.description || '',
    tags: row.tags || '',
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name) {
    ElMessage.warning('请输入菜品名称')
    return
  }
  saveLoading.value = true
  try {
    const payload = {
      ...form.value,
      is_recommended: form.value.is_recommended ? 1 : 0,
    }
    if (isEdit.value && editingId.value) {
      await updateMenuItem(editingId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await createMenuItem(payload)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    await loadItems()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该商品吗？', '提示', { type: 'warning' })
    await deleteMenuItem(id)
    ElMessage.success('删除成功')
    await loadItems()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(loadItems)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
