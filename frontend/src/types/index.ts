/**
 * 前端共享类型定义
 * 与后端 Pydantic Schema 对齐
 */

export type UserRole = 'admin' | 'customer'

export interface User {
  id: number
  username: string
  role: UserRole
  phone?: string | null
}

export interface AuthResponse {
  user: User
  message: string
  token?: string | null
}

export interface CartItem {
  menu_item_id: number
  name: string
  quantity: number
  unit_price: number
}

export interface MenuCategory {
  id: number
  name: string
  sort_order: number
  description?: string | null
}

export interface MenuItem {
  id: number
  name: string
  description?: string | null
  price: number
  spicy_level: number
  category: string
  tags?: string | null
  stock: number
  is_recommended: number
  sales_count: number
  created_at?: string
  updated_at?: string
}

export interface MenuResponse {
  categories: MenuCategory[]
  items: MenuItem[]
}

export interface OrderItem {
  id: number
  menu_item_id: number
  name: string
  quantity: number
  unit_price: number
  subtotal: number
}

export type OrderStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled'

export interface Order {
  id: number
  user_id: number
  status: OrderStatus
  total_price: number
  remark?: string | null
  items: OrderItem[]
  created_at: string
  updated_at?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  id?: string | number
  imageUrl?: string  // 用户上传的图片本地预览地址
}

export interface ChatRequest {
  user_id: number
  message: string
  cart: CartItem[]
  image_base64?: string
}

export interface ChatResponse {
  response: string
  cart: CartItem[]
  intent?: string | null
  agent?: string | null
}

export interface StartupTimeResponse {
  startup_time: string
}

export interface ApiErrorDetail {
  detail?: string
  message?: string
}

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    role?: UserRole
  }
}
