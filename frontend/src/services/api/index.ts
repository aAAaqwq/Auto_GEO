/**
 * API 服务 - 完整加固版 v2.2
 * 修复记录：
 * 1. 补全 accountApi.delete (修复删除账号报错)
 * 2. 补全 accountApi.getAuthStatus (修复授权轮询报错)
 * 3. 补全 accountApi.update (修复编辑账号功能)
 * 4. 保持了 reportsApi 和 geoArticleApi 的正确命名
 */

import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

// API 基础地址
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001/api'

/**
 * 创建 axios 实例
 */
const instance: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 300000, // 增加到5分钟超时，适应AI检测的长耗时
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * 响应拦截器
 */
instance.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token
    return config
  },
  (error) => Promise.reject(error)
)

instance.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    console.error('响应错误:', error)
    const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败'
    
    // 如果是 500 错误，在控制台详细打印以便调试
    if (error.response?.status === 500) {
        console.error("🚨 后端 500 错误详情:", error.response.data);
    }

    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// 通用请求方法封装
export const request = async <T = any>(config: AxiosRequestConfig): Promise<T> => {
  return instance.request(config) as Promise<T>
}

export const get = <T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> => {
  return request<T>({ method: 'GET', url, params, ...config })
}

export const post = <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => {
  return request<T>({ method: 'POST', url, data, ...config })
}

export const put = <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => {
  return request<T>({ method: 'PUT', url, data, ...config })
}

export const del = <T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> => {
  return request<T>({ method: 'DELETE', url, params, ...config })
}

// ==================== 1. 账号管理 API (重点修复区域) ====================
export const accountApi = {
  // 获取列表
  getList: (params?: any) => get('/accounts', params),

  // 发起授权 (启动浏览器)
  startAuth: (data: any) => post('/accounts/auth/start', data),

  // 🌟 [新增] 查询授权状态 (AccountList.vue 轮询需要)
  getAuthStatus: (taskId: string) => get(`/accounts/auth/status/${taskId}`),

  // 🌟 [新增] 更新账号备注/名称
  update: (id: number, data: any) => put(`/accounts/${id}`, data),

  // 🌟 [新增] 删除账号 (修复之前的报错)
  delete: (id: number) => del(`/accounts/${id}`),

  // 检测所有账号授权状态
  checkAll: () => post('/accounts/check/all')
}

// ==================== 2. GEO 关键词 API ====================
export const geoKeywordApi = {
  getProjects: () => get('/keywords/projects'),
  getProject: (id: number) => get(`/keywords/projects/${id}`),
  getProjectKeywords: (projectId: number) => get(`/keywords/projects/${projectId}/keywords`),
  
  createProject: (data: any) => post('/keywords/projects', data),
  updateProject: (id: number, data: any) => put(`/keywords/projects/${id}`, data),
  deleteProject: (id: number) => del(`/keywords/projects/${id}`),
  createKeyword: (projectId: number, data: any) => post(`/keywords/projects/${projectId}/keywords`, data),
  
  distill: (data: any) => post('/keywords/distill', data),
  generateQuestions: (data: any) => post('/keywords/generate-questions', data)
}

// ==================== 3. GEO 文章 API ====================
export const geoArticleApi = {
  // 获取文章列表 (对应 Articles.vue)
  // 支持按 publish_status 和 project_id 过滤，用于批量发布时只获取待发布的文章
  getArticles: (params?: { limit?: number; publish_status?: string; project_id?: number }) => get('/geo/articles', params),

  // 生成文章 (5分钟超时) - 新增发布策略参数
  generate: (data: {
    keyword_id: number;
    company_name?: string;
    target_platforms?: string[];
    publish_strategy?: string;
    scheduled_at?: string;
  }) =>
    post('/geo/generate', data, { timeout: 300000 }),

  // 质检
  checkQuality: (id: number) => post(`/geo/articles/${id}/check-quality`),

  // 手动检测收录状态
  checkIndex: (id: number) => post(`/geo/articles/${id}/check-index`),

  getDetail: (id: number) => get(`/geo/articles/${id}`),
  delete: (id: number) => del(`/geo/articles/${id}`)
}

// ==================== 4. 收录检测 API (监控页) ====================
export const indexCheckApi = {
  // 执行收录检测
  checkKeyword: (data: { keyword_id: number; company_name: string; platforms?: string[] }) =>
    post<any>('/index-check/check', data),

  // 批量检测
  batchCheck: (data: { project_id?: number; keyword_ids?: number[]; company_name?: string }) =>
    post<any>('/index-check/batch/check', data),

  // 获取检测记录
  getRecords: (params?: {
    keyword_id?: number
    platform?: string
    limit?: number
    skip?: number
    keyword_found?: boolean
    company_found?: boolean
    start_date?: string
    end_date?: string
    question?: string
  }) => get<any>('/index-check/records', params),

  // 删除单条记录
  deleteRecord: (id: number) => del<any>(`/index-check/records/${id}`),

  // 批量删除记录
  batchDeleteRecords: (recordIds: number[]) => post<any>('/index-check/records/batch-delete', { record_ids: recordIds }),

  // 获取关键词趋势
  getKeywordTrend: (keywordId: number, days?: number) =>
    get<any>(`/index-check/keywords/${keywordId}/trend`, { days }),

  // 获取项目统计
  getProjectStats: (projectId: number) => get<any>(`/index-check/projects/${projectId}/analytics`),

  // 兼容 Monitor.vue 的 runCheck
  check: (data: { keyword_id: number; company_name: string; platforms?: string[] }) => 
    post('/index-check/check', data),
  
  getTrend: (keywordId: number, days = 7) => get(`/index-check/trend/${keywordId}`, { days })
}

// ==================== 5. 报表 API ====================
export const reportsApi = {
  // 获取总览数据
  getOverview: () => get<any>('/reports/overview'),

  // 获取收录趋势
  getIndexTrend: (params?: { project_id?: number; days?: number; platform?: string }) =>
    get<any>('/reports/trends', params),

  // 获取平台分布
  getPlatformDistribution: (params?: { project_id?: number }) =>
    get<any>('/reports/distribution/platform', params),

  // 获取关键词排名
  getKeywordRanking: (params?: { project_id?: number; limit?: number }) =>
    get<any>('/reports/ranking/keywords', params),

  // 获取项目统计
  getProjectStats: (projectId: number) => get<any>(`/reports/stats/project/${projectId}`),

  // 🌟 [新增] 获取文章统计
  getArticleStats: (params?: { project_id?: number }) => get<any>('/reports/article-stats', params),

  // 趋势图数据 (Monitor.vue 使用)
  getTrends: (days: number = 30) => get('/reports/trends', { days }),

  // 🌟 [新增] 数据总览卡片
  getStats: (params: { project_id?: number; days?: number }) => get('/reports/stats', params),

  // 🌟 [新增] AI 平台对比分析
  getPlatformComparison: (params: { project_id?: number; days?: number }) => get('/reports/platform-comparison', params),

  // 🌟 [新增] 项目影响力排行榜
  getProjectLeaderboard: (params: { days?: number }) => get('/reports/project-leaderboard', params),

  // 🌟 [新增] 执行收录检测
  runCheck: (data: { project_id: number; platforms?: string[] }) =>
    post('/reports/run-check', data)
}

// ==================== 6. 定时任务 API ====================
export const schedulerApi = {
  getJobs: () => get('/scheduler/jobs'),
  start: () => post('/scheduler/start', {}),
  stop: () => post('/scheduler/stop', {})
}

// ==================== 7. 发布管理 API ====================
export const publishApi = {
  // 获取支持的发布平台
  getPlatforms: () => get('/publish/platforms'),

  // 创建发布任务
  create: (data: { article_ids: number[]; account_ids: number[] }) => post('/publish/create', data),

  // 批量发布 GEO 文章（针对 GeoArticle，支持状态过滤）
  batch: (data: { article_ids: number[]; account_ids: number[]; scheduled_time?: string }) =>
    post('/publish/batch', data),

  // 🌟 立即发布 - 将文章状态设为 publishing 并立即启动
  start: (data: { article_ids: number[]; account_ids: number[] }) => post('/publish/start', data),

  // 🌟 定时发布 - 设置 scheduled_at 时间，等待调度器执行
  schedule: (data: { article_ids: number[]; account_ids: number[]; scheduled_time: string }) =>
    put('/publish/schedule', data),

  // 🌟 手动插队发布 - 无视定时时间，直接执行发布
  trigger: (articleId: number) => post(`/publish/trigger/${articleId}`),

  // 获取发布进度
  getProgress: (taskId: string) => get(`/publish/progress/${taskId}`),

  // 获取发布记录
  getRecords: (params?: any) => get('/publish/records', params),

  // 重试发布
  retry: (recordId: number) => post(`/publish/retry/${recordId}`)
}

// ==================== 8. 客户管理 API ====================
export const clientApi = {
  // 获取客户列表
  getList: (params?: {
    page?: number
    limit?: number
    status?: number
    keyword?: string
    industry?: string
  }) => get<any>('/clients', params),

  // 获取客户详情
  getDetail: (id: number) => get<any>(`/clients/${id}`),

  // 获取客户项目列表
  getProjects: (clientId: number) => get<any>(`/clients/${clientId}/projects`),

  // 创建客户
  create: (data: {
    name: string
    company_name?: string
    contact_person?: string
    phone?: string
    email?: string
    industry?: string
    address?: string
    description?: string
    status?: number
  }) => post<any>('/clients', data),

  // 更新客户
  update: (id: number, data: any) => put<any>(`/clients/${id}`, data),

  // 删除客户
  delete: (id: number) => del<any>(`/clients/${id}`),

  // 获取统计数据
  getStats: () => get<any>('/clients/stats/overview'),

  // 获取行业列表
  getIndustries: () => get<any>('/clients/indicators/list')
}

// ==================== 9. 自动发布任务 API ====================
export const autoPublishApi = {
  // 获取任务列表
  getTasks: (params?: { status?: string; limit?: number; offset?: number }) =>
    get('/auto-publish/tasks', params),

  // 获取任务详情（含子任务记录）
  getTask: (taskId: number) => get(`/auto-publish/tasks/${taskId}`),

  // 创建任务
  create: (data: {
    name: string
    description?: string
    article_ids: number[]
    account_ids: number[]
    exec_type: 'immediate' | 'scheduled' | 'interval'
    scheduled_at?: string
    interval_minutes?: number
  }) => post('/auto-publish/tasks', data),

  // 更新任务
  update: (taskId: number, data: {
    name?: string
    description?: string
    status?: string
    scheduled_at?: string
    interval_minutes?: number
  }) => put(`/auto-publish/tasks/${taskId}`, data),

  // 删除任务
  delete: (taskId: number) => del(`/auto-publish/tasks/${taskId}`),

  // 手动启动任务
  start: (taskId: number) => post(`/auto-publish/tasks/${taskId}/start`),

  // 取消任务
  cancel: (taskId: number) => post(`/auto-publish/tasks/${taskId}/cancel`),

  // 重试失败任务
  retry: (taskId: number) => post(`/auto-publish/tasks/${taskId}/retry`)
}

// ==================== 10. 健康检查 API ====================
export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error'
  timestamp: string
  services: {
    database: { status: 'connected' | 'error' | 'not_configured' | 'unknown'; message?: string }
    ragflow: { status: 'connected' | 'error' | 'not_configured' | 'unknown'; message?: string; code?: number }
    n8n: { status: 'connected' | 'error' | 'not_configured' | 'unknown'; message?: string; code?: number }
  }
}

export const systemApi = {
  // 获取健康状态
  getHealth: () => get<HealthStatus>('/health')
}

// ==================== 11. 知识库 API ====================
export const knowledgeApi = {
  // 企业分类
  getCategories: (params?: { keyword?: string }) => get<any>('/knowledge/categories', params),
  createCategory: (data: any) => post<any>('/knowledge/categories', data),
  updateCategory: (id: number, data: any) => put<any>(`/knowledge/categories/${id}`, data),
  deleteCategory: (id: number) => del<any>(`/knowledge/categories/${id}`),

  // 知识项
  getKnowledgeByCategory: (categoryId: number, params?: { keyword?: string }) =>
    get<any>(`/knowledge/categories/${categoryId}/knowledge`, params),
  createKnowledge: (categoryId: number, data: any) =>
    post<any>(`/knowledge/categories/${categoryId}/knowledge`, data),
  updateKnowledge: (id: number, data: any) => put<any>(`/knowledge/knowledge/${id}`, data),
  deleteKnowledge: (id: number) => del<any>(`/knowledge/knowledge/${id}`),

  // RAGFlow 直接管理
  getRAGFlowStatus: () => get<any>('/knowledge/ragflow/status'),
  getRAGFlowDatasets: (params?: { page?: number; limit?: number; search?: string }) =>
    get<any>('/knowledge/ragflow/datasets', params),
  createRAGFlowDataset: (data: { name: string; description?: string }) =>
    post<any>('/knowledge/ragflow/datasets', data),
  getRAGFlowDataset: (datasetId: string) => get<any>(`/knowledge/ragflow/datasets/${datasetId}`),
  updateRAGFlowDataset: (datasetId: string, data: any) =>
    put<any>(`/knowledge/ragflow/datasets/${datasetId}`, data),
  deleteRAGFlowDataset: (datasetId: string) =>
    del<any>(`/knowledge/ragflow/datasets/${datasetId}`),
  getRAGFlowDocuments: (datasetId: string, params?: any) =>
    get<any>(`/knowledge/ragflow/datasets/${datasetId}/documents`, params),
  getRAGFlowDocument: (datasetId: string, documentId: string) =>
    get<any>(`/knowledge/ragflow/datasets/${datasetId}/documents/${documentId}`),
  getRAGFlowDocumentDownloadUrl: (datasetId: string, documentId: string) =>
    get<any>(`/knowledge/ragflow/datasets/${datasetId}/documents/${documentId}/download`),
  deleteRAGFlowDocument: (datasetId: string, documentId: string) =>
    del<any>(`/knowledge/ragflow/datasets/${datasetId}/documents/${documentId}`),
  parseRAGFlowDocument: (datasetId: string, documentId: string) =>
    post<any>(`/knowledge/ragflow/datasets/${datasetId}/documents/${documentId}/parse`, {}),
  uploadRAGFlowDocument: (datasetId: string, formData: FormData) =>
    post<any>(`/knowledge/ragflow/datasets/${datasetId}/documents`, formData),
  getRAGFlowChunks: (datasetId: string, params?: { document_id?: string; page?: number; limit?: number }) =>
    get<any>(`/knowledge/ragflow/datasets/${datasetId}/chunks`, params)
}

// 导出统一的api对象
export const api = {
  account: accountApi,
  client: clientApi,
  geoKeyword: geoKeywordApi,
  geoArticle: geoArticleApi,
  indexCheck: indexCheckApi,
  reports: reportsApi,
  scheduler: schedulerApi,
  publish: publishApi,
  autoPublish: autoPublishApi,
  system: systemApi,
  knowledge: knowledgeApi
}

// 导出默认实例
export default instance
