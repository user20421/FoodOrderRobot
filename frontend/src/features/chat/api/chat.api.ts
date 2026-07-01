/**
 * 聊天相关 API
 */
import api from '@/shared/api/client'
import type { ChatRequest, ChatResponse } from '@/shared/types'

// 普通聊天 60s（大模型响应可能较慢），图片搜菜涉及视觉模型 + LLM，放宽到 100s
const CHAT_TIMEOUT = 60_000
const IMAGE_CHAT_TIMEOUT = 100_000

export function sendChatMessage(payload: ChatRequest) {
  const timeout = payload.image_base64 ? IMAGE_CHAT_TIMEOUT : CHAT_TIMEOUT
  return api.post<ChatResponse>('/chat', payload, { timeout })
}

export function sendChatMessageStream(payload: ChatRequest) {
  const timeout = payload.image_base64 ? IMAGE_CHAT_TIMEOUT : CHAT_TIMEOUT
  return api.post('/chat/stream', payload, {
    responseType: 'text',
    timeout,
    headers: {
      Accept: 'text/event-stream',
    },
  })
}
