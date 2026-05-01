import { ref } from 'vue'
import { defineStore } from 'pinia'

function getStorageKey() {
  try {
    const authRaw = localStorage.getItem('ordering_bot_auth')
    if (authRaw) {
      const auth = JSON.parse(authRaw)
      return `ordering_bot_chat_messages_${auth.id || 'guest'}`
    }
  } catch (e) {
    console.error('获取用户ID失败', e)
  }
  return 'ordering_bot_chat_messages_guest'
}

function loadMessages() {
  const key = getStorageKey()
  try {
    const raw = localStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed
      }
    }
  } catch (e) {
    console.error('加载聊天记录失败', e)
  }
  return [
    {
      role: 'assistant',
      content:
        '您好！我是智能点餐机器人小餐\n您可以问我：\n• 有什么好吃的推荐？\n• 来一份宫保鸡丁\n• 查询我的订单\n• 或直接打开菜单浏览菜品',
    },
  ]
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref(loadMessages())

  function reloadMessages() {
    messages.value = loadMessages()
  }

  function addMessage(msg) {
    messages.value.push(msg)
    save()
  }

  function setMessages(msgs) {
    messages.value = msgs
    save()
  }

  function clearMessages() {
    messages.value = [
      {
        role: 'assistant',
        content:
          '您好！我是智能点餐机器人小餐\n您可以问我：\n• 有什么好吃的推荐？\n• 来一份宫保鸡丁\n• 查询我的订单\n• 或直接打开菜单浏览菜品',
      },
    ]
    save()
  }

  function save() {
    try {
      localStorage.setItem(getStorageKey(), JSON.stringify(messages.value))
    } catch (e) {
      console.error('保存聊天记录失败', e)
    }
  }

  return { messages, reloadMessages, addMessage, setMessages, clearMessages }
})

/**
 * 清空所有用户的聊天记录（用于项目重新运行时）
 */
export function clearAllChatStorage() {
  const keysToRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith('ordering_bot_chat_messages_')) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k))
}
