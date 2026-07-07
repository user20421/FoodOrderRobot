/**
 * 聊天相关 API
 */
import api from '@/shared/api/client'
import type { ChatRequest, ChatResponse, ChatStreamEvent } from '@/shared/types'
import { API_BASE_URL, STORAGE_KEY_TOKEN } from '@/shared/constants'

// 普通聊天 60s（大模型响应可能较慢），图片搜菜涉及视觉模型 + LLM，放宽到 100s
const CHAT_TIMEOUT = 60_000
const IMAGE_CHAT_TIMEOUT = 100_000

export function sendChatMessage(payload: ChatRequest) {
  const timeout = payload.image_base64 ? IMAGE_CHAT_TIMEOUT : CHAT_TIMEOUT
  return api.post<ChatResponse>('/chat', payload, { timeout })
}

/**
 * SSE 流式聊天
 * 返回异步迭代器，每次 yield 一个流式事件 { type, content?, cart?, message? }
 */
export async function* sendChatMessageStream(payload: ChatRequest): AsyncGenerator<ChatStreamEvent> {
  const timeout = payload.image_base64 ? IMAGE_CHAT_TIMEOUT : CHAT_TIMEOUT
  const token = localStorage.getItem(STORAGE_KEY_TOKEN)

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法读取流式响应')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)
        if (data === '[DONE]') continue

        try {
          const event = JSON.parse(data) as ChatStreamEvent
          yield event
        } catch {
          // 忽略无法解析的行
        }
      }
    }
  } finally {
    clearTimeout(timer)
  }
}
