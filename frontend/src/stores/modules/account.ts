/**
 * 账号状态管理 — 全面增强版
 * 统一使用 accountApi（axios 实例自动注入 Token）
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { accountApi } from '@/services/api'

export interface Account {
  id: number
  platform: string
  account_name: string
  username?: string
  status: number
  last_auth_time?: string
  remark?: string
  user_id?: number
  group_id?: number | null
  tags?: string[]
  health_score?: number
  last_check_time?: string
  auth_expires_at?: string
  browser_type?: string
  adspower_profile_id?: string
  created_at: string
  updated_at: string
}

export interface AccountGroup {
  id: number
  name: string
  icon?: string
  color: string
  sort_order: number
  account_count: number
  created_at: string
  updated_at: string
}

export const useAccountStore = defineStore('account', () => {
  // ==================== 状态 ====================

  /** 账号列表 */
  const accounts = ref<Account[]>([])

  /** 分组列表 */
  const groups = ref<AccountGroup[]>([])

  /** 当前选中的账号 */
  const selectedAccountIds = ref<number[]>([])

  /** 加载状态 */
  const loading = ref(false)

  /** 错误信息 */
  const error = ref<string | null>(null)

  // ==================== 计算属性 ====================

  /** 按平台分组的账号 */
  const accountsByPlatform = computed(() => {
    const grouped: Record<string, Account[]> = {}
    accounts.value.forEach(account => {
      if (!grouped[account.platform]) {
        grouped[account.platform] = []
      }
      grouped[account.platform].push(account)
    })
    return grouped
  })

  /** 已授权的账号 */
  const authorizedAccounts = computed(() => {
    return accounts.value.filter(acc => acc.status === 1)
  })

  /** 健康度较低的账号（需要关注） */
  const warningAccounts = computed(() => {
    return accounts.value.filter(acc => acc.health_score !== undefined && acc.health_score < 60)
  })

  /** 获取账号总数 */
  const totalCount = computed(() => accounts.value.length)

  /** 获取已授权账号数 */
  const authorizedCount = computed(() => authorizedAccounts.value.length)

  // ==================== 账号 CRUD ====================

  /**
   * 加载账号列表（自动带 Token）
   */
  async function loadAccounts(params?: { platform?: string; status?: number; group_id?: number; tag?: string; keyword?: string }) {
    loading.value = true
    error.value = null

    try {
      const data: any = await accountApi.getList(params)

      if (data && data.items) {
        accounts.value = data.items
      } else if (Array.isArray(data)) {
        accounts.value = data
      } else {
        accounts.value = []
      }
    } catch (e: any) {
      error.value = e.message || '网络错误'
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建账号
   */
  async function createAccount(accountData: Partial<Account>) {
    loading.value = true
    error.value = null

    try {
      const data: any = await accountApi.create(accountData)
      if (data && !data.success === false) {
        accounts.value.push(data)
        return { success: true, data }
      } else {
        error.value = data?.message || '创建失败'
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
   * 更新账号
   */
  async function updateAccount(id: number, accountData: Partial<Account>) {
    loading.value = true
    error.value = null

    try {
      const data: any = await accountApi.update(id, accountData)
      const updated = data?.data || data
      if (updated) {
        const index = accounts.value.findIndex(acc => acc.id === id)
        if (index !== -1) {
          accounts.value[index] = { ...accounts.value[index], ...updated }
        }
        return { success: true, data: updated }
      } else {
        error.value = data?.message || '更新失败'
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
   * 删除账号
   */
  async function deleteAccount(id: number) {
    loading.value = true
    error.value = null

    try {
      const data: any = await accountApi.delete(id)
      if (data?.success !== false) {
        accounts.value = accounts.value.filter(acc => acc.id !== id)
        selectedAccountIds.value = selectedAccountIds.value.filter(sid => sid !== id)
        return { success: true }
      } else {
        error.value = data?.message || '删除失败'
        return { success: false, message: error.value }
      }
    } catch (e: any) {
      error.value = e.message || '网络错误'
      return { success: false, message: error.value }
    } finally {
      loading.value = false
    }
  }

  // ==================== 授权流程 ====================

  /**
   * 开始授权
   */
  async function startAuth(platform: string, accountId?: number, accountName?: string) {
    try {
      const data: any = await accountApi.startAuth({
        platform,
        account_id: accountId,
        account_name: accountName,
      })

      if (data?.task_id) {
        return { success: true, taskId: data.task_id }
      } else {
        return { success: false, message: data?.message || '授权启动失败' }
      }
    } catch (e: any) {
      return { success: false, message: e.message || '网络错误' }
    }
  }

  /**
   * 检查授权状态
   */
  async function checkAuthStatus(taskId: string) {
    try {
      const data: any = await accountApi.getAuthStatus(taskId)

      // 如果授权成功，自动刷新账号列表
      if (data.status === 'success' && data.account_id) {
        await loadAccounts()
      }

      return data
    } catch (e: any) {
      return { status: 'failed', message: e.message }
    }
  }

  /**
   * 保存授权结果
   */
  async function saveAuth(taskId: string, accountId: number) {
    try {
      const data: any = await accountApi.saveAuth(taskId, accountId)
      if (data?.success !== false) {
        await loadAccounts()
      }
      return data
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  }

  // ==================== 分组管理 ====================

  /**
   * 加载分组列表
   */
  async function loadGroups() {
    try {
      const data: any = await accountApi.getGroups()
      if (data?.success && data.data) {
        groups.value = data.data
      }
    } catch (e: any) {
      console.error('加载分组失败:', e)
    }
  }

  /**
   * 创建分组
   */
  async function createGroup(name: string, color?: string) {
    try {
      const data: any = await accountApi.createGroup({ name, color })
      if (data?.success) {
        await loadGroups()
        return { success: true }
      }
      return { success: false, message: data?.message }
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  }

  /**
   * 删除分组
   */
  async function deleteGroup(id: number) {
    try {
      const data: any = await accountApi.deleteGroup(id)
      if (data?.success) {
        await loadGroups()
        await loadAccounts()
        return { success: true }
      }
      return { success: false }
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  }

  // ==================== 批量操作 ====================

  /**
   * 批量更新状态
   */
  async function batchUpdateStatus(accountIds: number[], status: number) {
    try {
      const data: any = await accountApi.batchStatus(accountIds, status)
      if (data?.success) {
        await loadAccounts()
        return { success: true }
      }
      return { success: false }
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  }

  /**
   * 批量删除
   */
  async function batchDelete(accountIds: number[]) {
    try {
      const data: any = await accountApi.batchDelete(accountIds)
      if (data?.success) {
        accounts.value = accounts.value.filter(acc => !accountIds.includes(acc.id))
        selectedAccountIds.value = selectedAccountIds.value.filter(id => !accountIds.includes(id))
        return { success: true }
      }
      return { success: false }
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  }

  /**
   * 批量移动分组
   */
  async function batchMoveGroup(accountIds: number[], groupId: number | null) {
    try {
      const data: any = await accountApi.batchMoveGroup(accountIds, groupId)
      if (data?.success) {
        await loadAccounts()
        return { success: true }
      }
      return { success: false }
    } catch (e: any) {
      return { success: false, message: e.message }
    }
  }

  // ==================== 选择操作 ====================

  /**
   * 切换账号选中状态
   */
  function toggleAccountSelection(id: number) {
    const index = selectedAccountIds.value.indexOf(id)
    if (index === -1) {
      selectedAccountIds.value.push(id)
    } else {
      selectedAccountIds.value.splice(index, 1)
    }
  }

  /**
   * 全选/取消全选
   */
  function toggleSelectAll(platform?: string) {
    const targetAccounts = platform
      ? accounts.value.filter(acc => acc.platform === platform)
      : accounts.value

    const allSelected = targetAccounts.every(acc =>
      selectedAccountIds.value.includes(acc.id)
    )

    if (allSelected) {
      selectedAccountIds.value = selectedAccountIds.value.filter(
        id => !targetAccounts.some(acc => acc.id === id)
      )
    } else {
      targetAccounts.forEach(acc => {
        if (!selectedAccountIds.value.includes(acc.id)) {
          selectedAccountIds.value.push(acc.id)
        }
      })
    }
  }

  /**
   * 清空选择
   */
  function clearSelection() {
    selectedAccountIds.value = []
  }

  /**
   * 获取授权URL
   */
  function getAuthUrl(platform: string): string {
    const authUrls: Record<string, string> = {
      zhihu: 'https://www.zhihu.com/signin',
      baijiahao: 'https://baijiahao.baidu.com/builder/rc/static/login/index',
      sohu: 'https://mp.sohu.com/',
      toutiao: 'https://mp.toutiao.com/',
    }
    return authUrls[platform] || ''
  }

  return {
    // 状态
    accounts,
    groups,
    selectedAccountIds,
    loading,
    error,

    // 计算属性
    accountsByPlatform,
    authorizedAccounts,
    warningAccounts,
    totalCount,
    authorizedCount,

    // 账号 CRUD
    loadAccounts,
    createAccount,
    updateAccount,
    deleteAccount,

    // 授权
    startAuth,
    checkAuthStatus,
    saveAuth,

    // 分组
    loadGroups,
    createGroup,
    deleteGroup,

    // 批量操作
    batchUpdateStatus,
    batchDelete,
    batchMoveGroup,

    // 选择
    toggleAccountSelection,
    toggleSelectAll,
    clearSelection,
    getAuthUrl,
  }
})
