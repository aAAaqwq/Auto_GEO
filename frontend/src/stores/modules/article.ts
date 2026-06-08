/**
 * 文章状态管理
 * 使用 axios（带 JWT 认证拦截器）替代原生 fetch
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { get, post, put, del } from '@/services/api'

export interface Article {
  id: number
  title: string
  content: string
  tags?: string
  category?: string
  cover_image?: string
  status: number       // 前端使用的数字状态: 0=草稿, 1=已发布
  publish_status?: string  // 后端使用的字符串状态
  view_count: number
  created_at: string
  updated_at: string
  published_at?: string
}

export const useArticleStore = defineStore('article', () => {
  // ==================== 状态 ====================

  const articles = ref<Article[]>([])
  const selectedArticleIds = ref<number[]>([])
  const currentArticle = ref<Partial<Article>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pagination = ref({ page: 1, pageSize: 20, total: 0 })

  // ==================== 计算属性 ====================

  const draftArticles = computed(() => articles.value.filter(art => art.status === 0))
  const publishedArticles = computed(() => articles.value.filter(art => art.status === 1))
  const totalCount = computed(() => pagination.value.total)
  const selectedArticles = computed(() =>
    articles.value.filter(art => selectedArticleIds.value.includes(art.id))
  )

  // ==================== 操作 ====================

  /**
   * 加载文章列表（使用 axios → 自动带 JWT Token）
   */
  async function loadArticles(params: {
    page?: number
    pageSize?: number
    status?: number
    keyword?: string
  } = {}) {
    loading.value = true
    error.value = null

    try {
      const queryParams: Record<string, any> = {
        page: params.page || 1,
        limit: params.pageSize || 20,
      }
      // 将前端数字 status 映射为后端 publish_status 字符串
      if (params.status !== undefined) {
        if (params.status === 1) queryParams.publish_status = 'published'
        else if (params.status === 0) queryParams.publish_status = 'draft'
      }
      if (params.keyword) queryParams.keyword = params.keyword

      const data: any = await get('/articles', queryParams)

      if (data.success !== false && data.items) {
        articles.value = (data.items || []).map((item: any) => ({
          ...item,
          // 后端 publish_status 字符串 → 前端 status 数字
          status: item.publish_status === 'published' ? 1 : (item.status ?? 0),
          view_count: item.view_count || 0,
        }))
        pagination.value.total = data.total || articles.value.length
        pagination.value.page = params.page || 1
        // 如果是搜索/过滤的结果，total 可能不是全量
        if (!params.keyword && params.status === undefined) {
          pagination.value.total = data.total || articles.value.length
        }
      } else if (data.success === false) {
        error.value = data.message || '加载失败'
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载文章详情（使用 axios → 自动带 JWT Token）
   */
  async function loadArticleDetail(id: number) {
    loading.value = true
    error.value = null

    try {
      const data: any = await get(`/articles/${id}`)

      if (data.success !== false) {
        const articleData = data.data || data
        currentArticle.value = {
          ...articleData,
          status: articleData.publish_status === 'published' ? 1 : (articleData.status ?? 0),
        }
        return { success: true, data: currentArticle.value }
      } else {
        error.value = data.message || '加载失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建文章（使用 axios → 自动带 JWT Token）
   */
  async function createArticle(articleData: Partial<Article>) {
    loading.value = true
    error.value = null

    try {
      const data: any = await post('/articles', {
        title: articleData.title,
        content: articleData.content,
        status: articleData.status,
        tags: articleData.tags,
        category: articleData.category,
      })

      if (data.success !== false) {
        const newArticle = {
          ...(data.data || data),
          status: data.data?.publish_status === 'published' ? 1 : (articleData.status ?? 0),
          view_count: 0,
        }
        articles.value.unshift(newArticle)
        return { success: true, data: newArticle }
      } else {
        error.value = data.message || '创建失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新文章（使用 axios → 自动带 JWT Token）
   */
  async function updateArticle(id: number, articleData: Partial<Article>) {
    loading.value = true
    error.value = null

    try {
      const data: any = await put(`/articles/${id}`, {
        title: articleData.title,
        content: articleData.content,
        status: articleData.status,
        tags: articleData.tags,
        category: articleData.category,
      })

      if (data.success !== false) {
        const updated = {
          ...(data.data || {}),
          status: data.data?.publish_status === 'published' ? 1 : (articleData.status ?? 0),
        }
        const index = articles.value.findIndex(art => art.id === id)
        if (index !== -1) {
          articles.value[index] = { ...articles.value[index], ...updated }
        }
        return { success: true, data: updated }
      } else {
        error.value = data.message || '更新失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除文章（使用 axios → 自动带 JWT Token）
   */
  async function deleteArticle(id: number) {
    loading.value = true
    error.value = null

    try {
      const data: any = await del(`/articles/${id}`)

      if (data.success !== false) {
        articles.value = articles.value.filter(art => art.id !== id)
        selectedArticleIds.value = selectedArticleIds.value.filter(sid => sid !== id)
        return { success: true }
      } else {
        error.value = data.message || '删除失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * 发布文章到指定平台账号
   * —— 这是我新加的一键发布功能！
   */
  async function publishToAccount(articleId: number, accountId: number) {
    loading.value = true
    error.value = null

    try {
      const data: any = await post('/publish/start', {
        article_ids: [articleId],
        account_ids: [accountId],
      })

      if (data.success !== false) {
        return { success: true, taskId: data.data?.task_id }
      } else {
        error.value = data.message || '发布失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  /**
   * 批量发布文章到多个平台账号
   */
  async function batchPublish(articleIds: number[], accountIds: number[]) {
    loading.value = true
    error.value = null

    try {
      const data: any = await post('/publish/start', {
        article_ids: articleIds,
        account_ids: accountIds,
      })

      if (data.success !== false) {
        return { success: true, taskId: data.data?.task_id }
      } else {
        error.value = data.message || '批量发布失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  function toggleArticleSelection(id: number) {
    const index = selectedArticleIds.value.indexOf(id)
    if (index === -1) {
      selectedArticleIds.value.push(id)
    } else {
      selectedArticleIds.value.splice(index, 1)
    }
  }

  function toggleSelectAll() {
    if (articles.value.every(art => selectedArticleIds.value.includes(art.id))) {
      selectedArticleIds.value = []
    } else {
      selectedArticleIds.value = articles.value.map(art => art.id)
    }
  }

  function clearSelection() {
    selectedArticleIds.value = []
  }

  function setCurrentArticle(article: Partial<Article>) {
    currentArticle.value = { ...article }
  }

  function resetCurrentArticle() {
    currentArticle.value = {}
  }

  return {
    articles,
    selectedArticleIds,
    currentArticle,
    loading,
    error,
    pagination,
    draftArticles,
    publishedArticles,
    totalCount,
    selectedArticles,
    loadArticles,
    loadArticleDetail,
    createArticle,
    updateArticle,
    deleteArticle,
    publishToAccount,
    batchPublish,
    toggleArticleSelection,
    toggleSelectAll,
    clearSelection,
    setCurrentArticle,
    resetCurrentArticle,
  }
})
