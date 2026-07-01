<!-- 智能聊天页面：Markdown 渲染、快捷操作、购物车抽屉、自动滚动 -->
<template>
  <div class="chat-container">
    <!-- 数字人 + 语音开关 -->
    <div class="avatar-area">
      <DigitalAvatar :status="avatarStatus" />
      <el-button
        circle
        :type="speechEnabled ? 'success' : 'info'"
        :title="speechEnabled ? '点击关闭语音播报' : '点击开启语音播报'"
        @click="toggleSpeech"
        class="speech-toggle"
      >
        <el-icon size="16">
          <Microphone v-if="speechEnabled" />
          <Mute v-else />
        </el-icon>
      </el-button>
    </div>

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
          <div v-if="msg.imageUrl" class="message-image">
            <el-image :src="msg.imageUrl" fit="cover" class="message-image-thumb" :preview-src-list="[msg.imageUrl]" />
          </div>
          <div
            v-if="msg.content && msg.content !== '[图片]'"
            class="message-text"
            v-html="msg.role === 'assistant' ? renderMarkdown(msg.content) : formatText(msg.content)"
            @click="handleLinkClick"
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
      <el-button size="small" type="success" @click="triggerImageUpload">
        <el-icon><Camera /></el-icon>
        图片搜菜
      </el-button>
      <el-button size="small" type="primary" @click="confirmOrder" :disabled="cartStore.totalCount === 0">
        确认下单 ({{ cartStore.totalCount }})
      </el-button>
      <el-button size="small" type="danger" plain @click="handleClearChat">
        <el-icon><Delete /></el-icon>
        清空对话
      </el-button>
      <input
        ref="imageInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        style="display: none"
        @change="handleImageChange"
      />
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <!-- 图片预览 -->
      <div v-if="imagePreviewUrl" class="image-preview-bar">
        <el-image :src="imagePreviewUrl" fit="cover" class="preview-thumb" />
        <el-button link size="small" @click="clearImage">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <el-input
        v-model="inputMessage"
        :placeholder="imagePreviewUrl ? '可以补充描述，或直接发送图片' : '告诉我你想吃什么，例如：来一份宫保鸡丁'"
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

<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Microphone, Mute, Camera, Close } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { storeToRefs } from 'pinia'
import { useCartStore } from '@/features/cart/stores/cart.store'
import { useChatStore } from '@/features/chat/stores/chat.store'
import { useAuthStore } from '@/features/auth/stores/auth.store'
import { sendChatMessage } from '@/features/chat/api/chat.api'
import DigitalAvatar from '@/components/DigitalAvatar.vue'
import { sanitizeHtml, sanitizeTextHtml } from '@/shared/utils/sanitize'
import type { ChatRequest, CartItem } from '@/shared/types'
import { STORAGE_KEY_SPEECH, IMAGE_UPLOAD_MAX_SIZE } from '@/shared/constants'

type AvatarStatus = 'idle' | 'listening' | 'thinking' | 'speaking'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()
const { messages } = storeToRefs(chatStore)
const inputMessage = ref('')
const loading = ref(false)
const cartVisible = ref(false)
const messageBox = ref<HTMLElement | null>(null)
const cartStore = useCartStore()
const avatarStatus = ref<AvatarStatus>('idle')
const speechEnabled = ref(localStorage.getItem(STORAGE_KEY_SPEECH) !== 'false')

// 拍照搜菜状态
const imageInput = ref<HTMLInputElement | null>(null)
const imageBase64 = ref<string>('')
const imagePreviewUrl = ref<string>('')

watch(speechEnabled, (val) => {
  localStorage.setItem(STORAGE_KEY_SPEECH, val ? 'true' : 'false')
})

// Markdown 渲染缓存，避免重复解析
const markdownCache = new Map<string, string>()

onMounted(async () => {
  await scrollToBottom()
  const preset = route.query.preset
  if (preset) {
    inputMessage.value = String(preset)
    await sendMessage()
  }
})

function formatText(text: string) {
  const html = text.replace(/\n/g, '<br>')
  return sanitizeTextHtml(html)
}

function renderMarkdown(text: string) {
  if (markdownCache.has(text)) {
    return markdownCache.get(text)!
  }
  const rawHtml = marked.parse(text, { breaks: true, gfm: true }) as string
  const html = sanitizeHtml(rawHtml)
  markdownCache.set(text, html)
  return html
}

function handleLinkClick(event: MouseEvent) {
  const anchor = (event.target as HTMLElement).closest('a')
  if (anchor) {
    const href = anchor.getAttribute('href')
    if (href && href.startsWith('/') && !href.startsWith('//')) {
      event.preventDefault()
      router.push(href)
    }
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messageBox.value) {
    messageBox.value.scrollTop = messageBox.value.scrollHeight
  }
}

async function sendQuick(text: string) {
  inputMessage.value = text
  await sendMessage()
}

function triggerImageUpload() {
  imageInput.value?.click()
}

function handleImageChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  // 限制图片大小
  if (file.size > IMAGE_UPLOAD_MAX_SIZE) {
    ElMessage.error('图片大小不能超过5MB')
    target.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    const result = reader.result as string
    imageBase64.value = result
    imagePreviewUrl.value = result
    // 选择图片后自动发送识别
    sendMessage()
  }
  reader.onerror = () => {
    ElMessage.error('图片读取失败')
  }
  reader.readAsDataURL(file)

  // 重置 input，允许再次选择同一张图片
  target.value = ''
}

function clearImage() {
  imageBase64.value = ''
  imagePreviewUrl.value = ''
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  const hasImage = !!imageBase64.value

  if (!text && !hasImage) return

  // 停止语音播报和录音
  if (window.speechSynthesis) window.speechSynthesis.cancel()

  // 构建用户消息：如果有图片则显示图片
  const userMessage: { role: 'user'; content: string; imageUrl?: string } = {
    role: 'user',
    content: text || '[图片]',
  }
  if (hasImage) {
    userMessage.imageUrl = imagePreviewUrl.value
  }
  chatStore.addMessage(userMessage)

  // 清空输入
  inputMessage.value = ''
  const currentImageBase64 = imageBase64.value
  clearImage()

  loading.value = true
  avatarStatus.value = 'thinking'
  await scrollToBottom()

  try {
    // 深拷贝购物车，避免传递 Vue Proxy 对象给 axios
    const currentCart: CartItem[] = JSON.parse(JSON.stringify(cartStore.items || []))
    const payload: ChatRequest = {
      user_id: authStore.userId ?? 0,
      message: text,
      cart: currentCart,
    }
    if (currentImageBase64) {
      payload.image_base64 = currentImageBase64
    }
    const res = await sendChatMessage(payload)
    const data = res.data
    // 构建购物车摘要，作为对话内容的一部分展示给用户
    let responseText = data.response || ''
    if (Array.isArray(data.cart) && data.cart.length > 0) {
      const total = data.cart.reduce((sum, item) => sum + (item.unit_price || 0) * (item.quantity || 1), 0)
      const cartLines = data.cart.map(item => `• ${item.name} x${item.quantity} = ¥${((item.unit_price || 0) * item.quantity).toFixed(0)}`)
      const cartSummary = `\n\n────────────\n🛒 当前购物车（合计 ¥${total.toFixed(0)}）\n${cartLines.join('\n')}`
      // 如果 LLM 回复中已包含"购物车"关键词，避免重复追加
      if (!responseText.includes('购物车')) {
        responseText += cartSummary
      }
      cartStore.setCart(data.cart)
    } else if (Array.isArray(data.cart) && data.cart.length === 0 && cartStore.items.length > 0) {
      // 后端返回空 cart，说明订单已提交或购物车已清空
      cartStore.clearCart()
      if (!responseText.includes('购物车')) {
        responseText += '\n\n────────────\n🛒 购物车已清空'
      }
    }
    chatStore.addMessage({ role: 'assistant', content: responseText })
    avatarStatus.value = 'idle'
    speakText(data.response)
  } catch (err) {
    chatStore.addMessage({ role: 'assistant', content: '抱歉，服务暂时异常，请稍后重试。' })
    avatarStatus.value = 'idle'
    console.error(err)
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

function speakText(text: string) {
  if (!speechEnabled.value || !window.speechSynthesis) return
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'zh-CN'
  utter.rate = 1.1
  window.speechSynthesis.speak(utter)
}

function toggleSpeech() {
  speechEnabled.value = !speechEnabled.value
  localStorage.setItem(STORAGE_KEY_SPEECH, speechEnabled.value ? 'true' : 'false')
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

.avatar-area {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 8px 0 4px;
  min-height: 72px;
}

.speech-toggle {
  margin-top: 4px;
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

.image-preview-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.preview-thumb {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  border: 1px solid #dcdfe6;
}

.message-image {
  margin-bottom: 8px;
}

.message-image-thumb {
  width: 120px;
  height: 120px;
  border-radius: 8px;
  cursor: pointer;
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
