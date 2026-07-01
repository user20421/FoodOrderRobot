/**
 * 聊天记录状态管理（Pinia）
 * 按用户隔离存储聊天消息，支持后端重启后自动清空
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { ChatMessage } from '@/shared/types'
import { STORAGE_KEY_AUTH, STORAGE_KEY_CHAT_PREFIX, getChatStorageKey } from '@/shared/constants'

const WELCOME_MESSAGE: ChatMessage = {
  role: 'assistant',
  content:
    '您好！我是美味餐厅的小餐\n您可以问我：\n• 有什么好吃的推荐？\n• 来一份宫保鸡丁\n• 查询我的订单\n• 或直接打开菜单浏览菜品',
}

function resolveStorageKey(): string {
  try {
    const authRaw = localStorage.getItem(STORAGE_KEY_AUTH)
    if (authRaw) {
      const auth = JSON.parse(authRaw)
      return getChatStorageKey(auth.id || 'guest')
    }
  } catch (e) {
    console.error('获取用户ID失败', e)
  }
  return `${STORAGE_KEY_CHAT_PREFIX}guest`
}

function loadMessages(): ChatMessage[] {
  const key = resolveStorageKey()
  try {
    const raw = localStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed as ChatMessage[]
      }
    }
  } catch (e) {
    console.error('加载聊天记录失败', e)
  }
  return [WELCOME_MESSAGE]
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>(loadMessages())

  function reloadMessages() {
    messages.value = loadMessages()
  }

  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
    save()
  }

  function setMessages(msgs: ChatMessage[]) {
    messages.value = msgs
    save()
  }

  function clearMessages() {
    messages.value = [WELCOME_MESSAGE]
    save()
  }

  function save() {
    try {
      localStorage.setItem(resolveStorageKey(), JSON.stringify(messages.value))
    } catch (e) {
      console.error('保存聊天记录失败', e)
    }
  }

  return { messages, reloadMessages, addMessage, setMessages, clearMessages, save }
})

/**
 * 清空所有用户的聊天记录（用于项目重新运行时）
 */
export function clearAllChatStorage() {
  const keysToRemove: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(STORAGE_KEY_CHAT_PREFIX)) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k))
}
