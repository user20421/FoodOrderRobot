/**
 * localStorage key 常量
 * 集中管理，避免拼写不一致
 */

export const STORAGE_KEY_TOKEN = 'ordering_bot_token'
export const STORAGE_KEY_AUTH = 'ordering_bot_auth'
export const STORAGE_KEY_CHAT_PREFIX = 'ordering_bot_chat_messages_'
export const STORAGE_KEY_CART_PREFIX = 'ordering_bot_cart_'
export const STORAGE_KEY_LAST_STARTUP = 'ordering_bot_last_startup'
export const STORAGE_KEY_SPEECH = 'ordering_bot_speech'
export const STORAGE_KEY_LAST_USER_ID = 'ordering_bot_last_user_id'

export function getChatStorageKey(userId: number): string {
  return `${STORAGE_KEY_CHAT_PREFIX}${userId}`
}

export function getCartStorageKey(userId: number): string {
  return `${STORAGE_KEY_CART_PREFIX}${userId}`
}
