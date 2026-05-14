/**
 * 用户状态管理
 * 我用这个来管理用户登录状态和认证信息！
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 本地存储键名
const TOKEN_KEY = 'autogeo_token'
const USER_KEY = 'autogeo_user'
const REMEMBER_KEY = 'autogeo_remember'

export interface User {
  id: number
  username: string
  nickname?: string
  email?: string
  role: 'admin' | 'user'
  avatar?: string
  status: number
  created_at?: string
  updated_at?: string
}

export interface LoginCredentials {
  username: string
  password: string
  remember?: boolean
}

export interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
}

export const useUserStore = defineStore('user', () => {
  // ==================== 状态 ====================

  /** 访问令牌 */
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))

  /** 用户信息 */
  const user = ref<User | null>(null)

  /** 加载状态 */
  const loading = ref(false)

  /** 错误信息 */
  const error = ref<string | null>(null)

  /** 是否记住密码 */
  const rememberMe = ref<boolean>(localStorage.getItem(REMEMBER_KEY) === 'true')

  // ==================== 计算属性 ====================

  /** 是否已登录 */
  const isLoggedIn = computed(() => !!token.value && !!user.value)

  /** 是否是管理员 */
  const isAdmin = computed(() => user.value?.role === 'admin')

  /** 用户显示名称 */
  const displayName = computed(() => {
    return user.value?.nickname || user.value?.username || '用户'
  })

  // ==================== 操作 ====================

  /**
   * 初始化用户信息
   * 从本地存储恢复用户数据
   */
  function initUser() {
    const savedUser = localStorage.getItem(USER_KEY)
    if (savedUser) {
      try {
        user.value = JSON.parse(savedUser)
      } catch {
        user.value = null
      }
    }
  }

  /**
   * 登录
   * @param credentials 登录凭证
   */
  async function login(credentials: LoginCredentials): Promise<{ success: boolean; message?: string }> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch('/api/users/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      })

      const data = await response.json()

      if (data.success && data.data?.access_token) {
        // 保存令牌
        token.value = data.data.access_token
        user.value = data.data.user

        // 本地持久化
        localStorage.setItem(TOKEN_KEY, data.data.access_token)
        localStorage.setItem(USER_KEY, JSON.stringify(data.data.user))
        localStorage.setItem(REMEMBER_KEY, String(credentials.remember || false))

        return { success: true }
      } else {
        error.value = data.message || '登录失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * 登出
   */
  async function logout(): Promise<void> {
    try {
      // 调用后端登出接口（可选）
      await fetch('/api/users/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token.value}`,
        },
      })
    } catch {
      // 忽略错误
    } finally {
      // 清除状态
      token.value = null
      user.value = null
      error.value = null

      // 清除本地存储
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    }
  }

  /**
   * 获取当前用户信息
   */
  async function fetchCurrentUser(): Promise<boolean> {
    if (!token.value) return false

    try {
      const response = await fetch('/api/users/me', {
        headers: {
          'Authorization': `Bearer ${token.value}`,
        },
      })

      const data = await response.json()

      if (data.success && data.data) {
        user.value = data.data
        localStorage.setItem(USER_KEY, JSON.stringify(data.data))
        return true
      } else {
        // Token 无效，清除登录状态
        token.value = null
        user.value = null
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
        return false
      }
    } catch {
      return false
    }
  }

  /**
   * 更新用户信息
   */
  async function updateUser(userData: Partial<User>): Promise<{ success: boolean; message?: string }> {
    if (!token.value) {
      return { success: false, message: '未登录' }
    }

    loading.value = true

    try {
      const response = await fetch('/api/users/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token.value}`,
        },
        body: JSON.stringify(userData),
      })

      const data = await response.json()

      if (data.success && data.data) {
        user.value = { ...user.value!, ...data.data }
        localStorage.setItem(USER_KEY, JSON.stringify(user.value))
        return { success: true }
      } else {
        return { success: false, message: data.message || '更新失败' }
      }
    } catch (e: any) {
      return { success: false, message: e.message || '网络错误' }
    } finally {
      loading.value = false
    }
  }

  /**
   * 修改密码
   */
  async function changePassword(oldPassword: string, newPassword: string): Promise<{ success: boolean; message?: string }> {
    if (!token.value) {
      return { success: false, message: '未登录' }
    }

    loading.value = true

    try {
      const response = await fetch('/api/users/me/password', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token.value}`,
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      })

      const data = await response.json()

      if (data.success) {
        return { success: true, message: '密码修改成功' }
      } else {
        return { success: false, message: data.message || '密码修改失败' }
      }
    } catch (e: any) {
      return { success: false, message: e.message || '网络错误' }
    } finally {
      loading.value = false
    }
  }

  /**
   * 清除错误信息
   */
  function clearError() {
    error.value = null
  }

  return {
    // 状态
    token,
    user,
    loading,
    error,
    rememberMe,

    // 计算属性
    isLoggedIn,
    isAdmin,
    displayName,

    // 操作
    initUser,
    login,
    logout,
    fetchCurrentUser,
    updateUser,
    changePassword,
    clearError,
  }
})
