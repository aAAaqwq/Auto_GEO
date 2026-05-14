/**
 * 用户相关 API 服务
 * 我用这个来封装用户认证相关的 API 调用！
 */

import {
  get,
  post,
  put,
  del,
} from '@/services/api'

// ==================== 认证 API ====================

/**
 * 用户登录
 */
export interface LoginRequest {
  username: string
  password: string
  remember?: boolean
}

export interface LoginResponse {
  token: string
  user: {
    id: number
    username: string
    nickname?: string
    email?: string
    role: 'admin' | 'user'
    avatar?: string
    status: number
  }
}

/**
 * 用户登录
 */
export function login(data: LoginRequest): Promise<{ success: boolean; data?: LoginResponse; message?: string }> {
  return post('/users/login', data)
}

/**
 * 用户注册
 */
export function register(data: { username: string; password: string; nickname?: string; email?: string }): Promise<{ success: boolean; data?: LoginResponse['user']; message?: string }> {
  return post('/users/register', data)
}

/**
 * 用户登出
 */
export function logout(): Promise<{ success: boolean; message?: string }> {
  return post('/users/logout', {})
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser(): Promise<{ success: boolean; data?: LoginResponse['user']; message?: string }> {
  return get('/users/me')
}

/**
 * 刷新令牌
 */
export function refreshToken(): Promise<{ success: boolean; data?: { token: string }; message?: string }> {
  return post('/users/refresh', {})
}

/**
 * 修改密码
 */
export function changePassword(oldPassword: string, newPassword: string): Promise<{ success: boolean; message?: string }> {
  return put('/users/me/password', { old_password: oldPassword, new_password: newPassword })
}

/**
 * 更新用户资料
 */
export function updateProfile(data: { nickname?: string; email?: string; avatar?: string }): Promise<{ success: boolean; data?: any; message?: string }> {
  return put('/users/profile', data)
}

// ==================== 用户管理 API (管理员) ====================

/**
 * 用户列表查询参数
 */
export interface UserListParams {
  page?: number
  pageSize?: number
  keyword?: string
  role?: string
  status?: number
}

/**
 * 创建用户请求
 */
export interface CreateUserRequest {
  username: string
  password: string
  nickname?: string
  email?: string
  role: 'admin' | 'user'
  status?: number
}

/**
 * 更新用户请求
 */
export interface UpdateUserRequest {
  nickname?: string
  email?: string
  role?: 'admin' | 'user'
  status?: number
}

/**
 * 获取用户列表
 */
export function getUserList(params?: UserListParams): Promise<{ success: boolean; data?: { total: number; items: any[] }; message?: string }> {
  return get('/users', params)
}

/**
 * 获取用户详情
 */
export function getUserDetail(id: number): Promise<{ success: boolean; data?: any; message?: string }> {
  return get(`/users/${id}`)
}

/**
 * 创建用户
 */
export function createUser(data: CreateUserRequest): Promise<{ success: boolean; data?: any; message?: string }> {
  return post('/users/register', data)
}

/**
 * 更新用户
 */
export function updateUser(id: number, data: UpdateUserRequest): Promise<{ success: boolean; data?: any; message?: string }> {
  return put(`/users/${id}`, data)
}

/**
 * 删除用户
 */
export function deleteUser(id: number): Promise<{ success: boolean; message?: string }> {
  return del(`/users/${id}`)
}

/**
 * 重置用户密码
 */
export function resetUserPassword(id: number, newPassword: string): Promise<{ success: boolean; message?: string }> {
  return post(`/users/${id}/reset-password`, { new_password: newPassword })
}

/**
 * 启用/禁用用户
 */
export function toggleUserStatus(id: number, status: number): Promise<{ success: boolean; message?: string }> {
  return put(`/users/${id}/status`, { status })
}

// ==================== 系统配置 API (管理员) ====================

/**
 * 系统配置
 */
export interface SystemConfig {
  database_url?: string
  api_port?: number
  ws_port?: number
  log_level?: string
  max_upload_size?: number
  allowed_hosts?: string[]
}

/**
 * 获取系统配置
 */
export function getSystemConfig(): Promise<{ success: boolean; data?: SystemConfig; message?: string }> {
  return get('/admin/config')
}

/**
 * 更新系统配置
 */
export function updateSystemConfig(data: SystemConfig): Promise<{ success: boolean; message?: string }> {
  return put('/admin/config', data)
}

/**
 * 测试数据库连接
 */
export function testDatabaseConnection(config: { database_url: string }): Promise<{ success: boolean; message?: string }> {
  return post('/admin/config/test-db', config)
}

// ==================== 服务状态 API ====================

/**
 * 服务状态
 */
export interface ServiceStatus {
  status: 'running' | 'stopped' | 'error'
  uptime: number
  version: string
  pid: number
  memory_usage: number
  cpu_usage: number
}

/**
 * 获取服务状态
 */
export function getServiceStatus(): Promise<{ success: boolean; data?: ServiceStatus; message?: string }> {
  return get('/admin/service/status')
}

/**
 * 重启服务
 */
export function restartService(): Promise<{ success: boolean; message?: string }> {
  return post('/admin/service/restart', {})
}

/**
 * 停止服务
 */
export function stopService(): Promise<{ success: boolean; message?: string }> {
  return post('/admin/service/stop', {})
}

/**
 * 启动服务
 */
export function startService(): Promise<{ success: boolean; message?: string }> {
  return post('/admin/service/start', {})
}

// ==================== 系统日志 API ====================

/**
 * 获取系统日志
 */
export function getSystemLogs(params?: { level?: string; limit?: number; offset?: number }): Promise<{ success: boolean; data?: { total: number; items: any[] }; message?: string }> {
  return get('/admin/logs', params)
}

/**
 * 清空系统日志
 */
export function clearSystemLogs(): Promise<{ success: boolean; message?: string }> {
  return del('/admin/logs')
}

// ==================== 导出 API 对象 ====================

export const userApi = {
  // 认证
  login,
  logout,
  getCurrentUser,
  refreshToken,
  changePassword,
  updateProfile,

  // 用户管理
  getUserList,
  getUserDetail,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
  toggleUserStatus,

  // 系统配置
  getSystemConfig,
  updateSystemConfig,
  testDatabaseConnection,

  // 服务状态
  getServiceStatus,
  restartService,
  stopService,
  startService,

  // 系统日志
  getSystemLogs,
  clearSystemLogs,
}

export default userApi
