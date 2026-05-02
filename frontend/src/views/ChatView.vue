<!-- 智能聊天页面：Markdown 渲染、快捷操作、购物车抽屉、自动滚动 -->
<template>
  <div class="chat-container">
    <!-- 聊天消息区域 -->
    <div class="chat-messages" ref="messageBox">
      <div
        v-for="(msg, index) in messages"
        :key="msg.id || `${msg.role}-${index}-${msg.content?.slice(0, 20)}`"
        :class="['message-row', msg.role === 'user' ? 'user' : 'bot']"
      >
        <el-avatar
          :size="40"
          :icon="msg.role === 'user' ? 'UserFilled' : 'Food'"
          :class="msg.role === 'user' ? 'user-avatar' : 'bot-avatar'"
        />
        <div class="message-bubble">
          <div
            class="message-text"
            v-html="msg.role === 'assistant' ? renderMarkdown(msg.content) : formatText(msg.content)"
          ></div>
        </div>
      </div>
      <div v-if="loading" class="message-row bot">
        <el-avatar :size="40" icon="Food" class="bot-avatar" />
        <div class="message-bubble">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span style="margin-left: 6px">思考中...</span>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions">
      <el-button size="small" @click="sendQuick('有什么推荐的菜品？')">推荐菜品</el-button>
      <el-button size="small" @click="sendQuick('查看菜单')">查看菜单</el-button>
      <el-button size="small" @click="sendQuick('查询我的订单')">查询订单</el-button>
      <el-button size="small" type="primary" @click="confirmOrder" :disabled="cartStore.totalCount === 0">
        确认下单 ({{ cartStore.totalCount }})
      </el-button>
      <el-button size="small" type="danger" plain @click="handleClearChat">
        <el-icon><Delete /></el-icon>
        清空对话
      </el-button>
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <el-input
        v-model="inputMessage"
        placeholder="告诉我你想吃什么，例如：来一份宫保鸡丁"
        @keyup.enter="sendMessage"
        size="large"
      >
        <template #append>
          <el-button type="primary" @click="sendMessage" :loading="loading">
            发送
          </el-button>
        </template>
      </el-input>
    </div>

    <!-- 购物车抽屉 -->
    <el-drawer v-model="cartVisible" title="购物车" size="360px">
      <div v-if="cartStore.items.length === 0" class="empty-cart">
        <el-empty description="购物车是空的" />
      </div>
      <div v-else>
        <el-table :data="cartStore.items" size="small">
          <el-table-column prop="name" label="菜品" />
          <el-table-column prop="quantity" label="数量" width="80" />
          <el-table-column label="单价" width="80">
            <template #default="scope">¥{{ scope.row.unit_price }}</template>
          </el-table-column>
        </el-table>
        <div class="cart-footer">
          <div class="cart-total">合计：¥{{ cartStore.totalPrice.toFixed(2) }}</div>
          <el-button type="primary" @click="confirmOrderFromDrawer">确认下单</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 悬浮购物车按钮 -->
    <el-badge :value="cartStore.totalCount" class="cart-fab" v-if="cartStore.totalCount > 0">
      <el-button circle size="large" type="warning" @click="cartVisible = true">
        <el-icon><ShoppingCart /></el-icon>
      </el-button>
    </el-badge>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { storeToRefs } from 'pinia'
import api from '../api'
import { useCartStore } from '../stores/cart'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const chatStore = useChatStore()
const authStore = useAuthStore()
const { messages } = storeToRefs(chatStore)
const inputMessage = ref('')
const loading = ref(false)
const cartVisible = ref(false)
const messageBox = ref(null)
const cartStore = useCartStore()

// Markdown 渲染缓存，避免重复解析
const markdownCache = new Map()

onMounted(async () => {
  await scrollToBottom()
  const preset = route.query.preset
  if (preset) {
    inputMessage.value = preset
    await sendMessage()
  }
})

function formatText(text) {
  return text.replace(/\n/g, '<br>')
}

function renderMarkdown(text) {
  if (markdownCache.has(text)) {
    return markdownCache.get(text)
  }
  const html = marked.parse(text, { breaks: true, gfm: true })
  markdownCache.set(text, html)
  return html
}

async function scrollToBottom() {
  await nextTick()
  if (messageBox.value) {
    messageBox.value.scrollTop = messageBox.value.scrollHeight
  }
}

async function sendQuick(text) {
  inputMessage.value = text
  await sendMessage()
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text) return

  chatStore.addMessage({ role: 'user', content: text })
  inputMessage.value = ''
  loading.value = true
  await scrollToBottom()

  try {
    const res = await api.post('/chat', {
      user_id: authStore.userId,
      message: text,
      cart: cartStore.items,
    })
    const data = res.data
    chatStore.addMessage({ role: 'assistant', content: data.response })
    if (data.cart) {
      cartStore.setCart(data.cart)
    }
  } catch (err) {
    chatStore.addMessage({ role: 'assistant', content: '抱歉，服务暂时异常，请稍后重试。' })
    console.error(err)
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function confirmOrder() {
  await sendQuick('确认下单')
}

async function confirmOrderFromDrawer() {
  cartVisible.value = false
  await sendQuick('确认下单')
}

async function handleClearChat() {
  try {
    await ElMessageBox.confirm('确定要清空当前对话记录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    chatStore.clearMessages()
    markdownCache.clear()
    await scrollToBottom()
    ElMessage.success('对话已清空')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  padding: 16px;
  position: relative;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  margin-bottom: 10px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 10px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.user-avatar {
  background-color: #409eff;
  flex-shrink: 0;
}

.bot-avatar {
  background-color: #67c23a;
  flex-shrink: 0;
}

.message-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  word-break: break-word;
}

.message-row.user .message-bubble {
  background-color: #dfebff;
  color: #333;
}

.message-row.bot .message-bubble {
  background-color: #f4f4f5;
  color: #333;
}

/* Markdown 渲染样式 */
.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3) {
  margin: 8px 0 4px;
  font-weight: 600;
}

.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
}

.message-text :deep(th),
.message-text :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
  text-align: left;
}

.message-text :deep(th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

.message-text :deep(tr:nth-child(even)) {
  background-color: #fafafa;
}

.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.message-text :deep(li) {
  margin: 2px 0;
}

.message-text :deep(code) {
  background-color: #f0f0f0;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 12px;
}

.message-text :deep(pre) {
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
}

.message-text :deep(blockquote) {
  border-left: 3px solid #409eff;
  margin: 8px 0;
  padding-left: 10px;
  color: #666;
}

.quick-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  padding: 0 4px;
}

.chat-input-area {
  padding: 0 4px;
}

.cart-fab {
  position: absolute;
  right: 24px;
  bottom: 80px;
}

.cart-footer {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cart-total {
  font-size: 16px;
  font-weight: bold;
  color: #f56c6c;
}
</style>
