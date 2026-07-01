/**
 * 认证相关 API
 */
import api from '@/shared/api/client'
import type { AuthResponse } from '@/shared/types'

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  phone?: string
  role?: 'customer' | 'admin'
}

export function login(payload: LoginPayload) {
  return api.post<AuthResponse>('/auth/login', payload)
}

export function register(payload: RegisterPayload) {
  return api.post<AuthResponse>('/auth/register', payload)
}
