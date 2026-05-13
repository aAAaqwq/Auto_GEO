<template>
  <div class="account-list-page">
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="filterPlatform" placeholder="筛选平台" clearable style="width: 150px">
          <el-option
            v-for="p in platformOptions"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>

        <el-select v-model="filterStatus" placeholder="状态筛选" clearable style="width: 120px; margin-left: 10px">
          <el-option label="全部" value="" />
          <el-option label="正常" :value="1" />
          <el-option label="授权过期" :value="-1" />
          <el-option label="禁用" :value="0" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="warning" :loading="checking" @click="handleCheckAll">
          <el-icon><Refresh /></el-icon>
          {{ checking ? `检测中 (${checkProgress.current}/${checkProgress.total})` : '一键检测所有' }}
        </el-button>

        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon> 添加账号
        </el-button>
      </div>
    </div>

    <!-- 账号卡片网格 -->
    <div class="accounts-grid">
      <div
        v-for="account in filteredAccounts"
        :key="account.id"
        class="account-card"
        :class="{ 'expired': account.status === -1 }"
      >
        <div class="account-header">
          <div class="platform-icon" :style="{ backgroundColor: getPlatformColor(account.platform) }">
            {{ getPlatformName(account.platform).substring(0,1) }}
          </div>
          <div class="status-dot" :class="account.status === 1 ? 'online' : 'offline'"></div>
        </div>
        
        <h3 class="account-name">{{ account.account_name }}</h3>
        <p class="account-username">{{ account.username ? '@' + account.username : '已授权' }}</p>
        <p class="account-platform">{{ getPlatformName(account.platform) }}</p>

        <div class="account-actions">
          <el-button
            v-if="account.status !== 1"
            type="warning"
            size="small"
            plain
            @click="handleReAuth(account)"
          >
            去授权
          </el-button>
          <el-button size="small" @click="editAccount(account)">编辑</el-button>
          <el-button type="danger" size="small" text @click="deleteAccount(account)">删除</el-button>
        </div>
      </div>

      <!-- 空状态或添加卡片 -->
      <div class="account-card add-card" @click="showAddDialog">
        <div class="add-icon"><el-icon><Plus /></el-icon></div>
        <p>添加新账号</p>
      </div>
    </div>

    <!-- 添加/授权对话框 (核心逻辑) -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <!-- 阶段1：填写信息 -->
      <div v-if="!authStep" class="form-step">
        <el-form :model="formData" label-width="80px">
          <el-form-item label="平台">
            <el-select v-model="formData.platform" placeholder="选择平台" :disabled="isEdit" style="width: 100%">
              <el-option
                v-for="p in platformOptions"
                :key="p.id"
                :label="p.name"
                :value="p.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="名称">
            <el-input v-model="formData.account_name" placeholder="备注名称 (如: 知乎大号)" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="formData.remark" type="textarea" placeholder="选填" />
          </el-form-item>
        </el-form>
      </div>

      <!-- 阶段2：等待授权 -->
      <div v-else class="auth-step">
        <div class="loading-container">
          <el-icon class="is-loading" size="40" color="#409eff"><Loading /></el-icon>
          <h3>正在等待登录...</h3>
          <p>浏览器已打开，请在弹出的窗口中扫码登录</p>
          <p class="sub-text">登录成功后，此窗口会自动关闭</p>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false" :disabled="authStep">取消</el-button>
          
          <!-- 编辑模式下只保存信息 -->
          <el-button v-if="isEdit && !authStep" type="primary" @click="saveAccountInfo">
            保存信息
          </el-button>
          
          <!-- 添加模式或重新授权模式 -->
          <el-button v-if="!isEdit || authStep" type="primary" :loading="loading" @click="startAuthProcess">
            {{ authStep ? '等待中...' : '启动浏览器授权' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 检测进度对话框 -->
    <el-dialog
      v-model="checkDialogVisible"
      title="账号授权状态检测"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="check-progress">
        <el-progress :percentage="checkProgress.percentage" :status="checkProgress.status" />
        <p class="progress-text">
          正在检测: {{ checkProgress.current }} / {{ checkProgress.total }}
        </p>

        <div class="check-log">
          <div
            v-for="(log, index) in checkLogs"
            :key="index"
            class="log-item"
            :class="{ 'error': !log.is_valid }"
          >
            <span class="log-platform">{{ getPlatformName(log.platform) }}</span>
            <span class="log-name">{{ log.account_name }}</span>
            <span class="log-message">{{ log.message }}</span>
            <el-tag :type="log.is_valid ? 'success' : 'danger'" size="small">
              {{ log.is_valid ? '有效' : '无效' }}
            </el-tag>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button :disabled="!checkCompleted" type="primary" @click="closeCheckDialog">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Plus, Loading, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi } from '@/services/api' // 直接使用 API 避免 store 逻辑复杂化
import { getEnabledPlatforms, getPlatformConfig } from '@/core/config/platform'

// 状态
const accounts = ref<any[]>([])
const filterPlatform = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const authStep = ref(false) // 是否处于授权等待阶段
const loading = ref(false)
const pollTimer = ref<any>(null)
const filterStatus = ref<number | null>(null)

// 检测相关状态
const checking = ref(false)
const checkDialogVisible = ref(false)
const checkCompleted = ref(false)
const checkProgress = ref({
  current: 0,
  total: 0,
  percentage: 0,
  status: '' as '' | 'success' | 'exception'
})
const checkLogs = ref<any[]>([])
let ws: WebSocket | null = null

// 平台选项
const platformOptions = computed(() => getEnabledPlatforms().map(p => ({ id: p.id, name: p.name })))

const formData = ref({
  id: null as number | null,
  platform: 'zhihu',
  account_name: '',
  remark: '',
})

// 计算属性
const filteredAccounts = computed(() => {
  let result = accounts.value
  if (filterPlatform.value) {
    result = result.filter(acc => acc.platform === filterPlatform.value)
  }
  if (filterStatus.value !== null) {
    result = result.filter(acc => acc.status === filterStatus.value)
  }
  return result
})

const dialogTitle = computed(() => {
  if (authStep.value) return '正在授权'
  return isEdit.value ? '编辑账号' : '添加账号'
})

// 加载列表
const loadAccounts = async () => {
  try {
    const res: any = await accountApi.getList()
    accounts.value = Array.isArray(res) ? res : []
  } catch (e) { console.error(e) }
}

// 打开添加
const showAddDialog = () => {
  isEdit.value = false
  authStep.value = false
  formData.value = { id: null, platform: 'zhihu', account_name: '', remark: '' }
  dialogVisible.value = true
}

// 编辑信息
const editAccount = (acc: any) => {
  isEdit.value = true
  authStep.value = false
  formData.value = {
    id: acc.id,
    platform: acc.platform,
    account_name: acc.account_name,
    remark: acc.remark
  }
  dialogVisible.value = true
}

// 重新授权
const handleReAuth = (acc: any) => {
  isEdit.value = false // 视为新授权流程，但带ID
  authStep.value = false
  formData.value = {
    id: acc.id,
    platform: acc.platform,
    account_name: acc.account_name,
    remark: acc.remark
  }
  dialogVisible.value = true
}

// 保存纯文本信息 (不涉及浏览器)
const saveAccountInfo = async () => {
  if (!formData.value.id) return
  try {
    await accountApi.update(formData.value.id, {
      account_name: formData.value.account_name,
      remark: formData.value.remark
    })
    ElMessage.success('更新成功')
    dialogVisible.value = false
    loadAccounts()
  } catch (e) { ElMessage.error('更新失败') }
}

// 启动授权流程 (核心逻辑)
const startAuthProcess = async () => {
  if (authStep.value) return // 防止重复点击

  if (!formData.value.account_name) {
    formData.value.account_name = `${getPlatformName(formData.value.platform)}账号`
  }

  loading.value = true
  try {
    // 调用后端启动浏览器
    const res: any = await accountApi.startAuth({
      platform: formData.value.platform,
      account_name: formData.value.account_name,
      account_id: formData.value.id || undefined
    })

    if (res.task_id) {
      authStep.value = true
      startPolling(res.task_id) // 开始轮询
    } else {
      ElMessage.error(res.message || '启动浏览器失败')
    }
  } catch (e) {
    ElMessage.error('请求失败，请检查后端是否启动')
  } finally {
    loading.value = false
  }
}

// 轮询检查状态
const startPolling = (taskId: string) => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  
  pollTimer.value = setInterval(async () => {
    try {
      const res: any = await accountApi.getAuthStatus(taskId)
      
      if (res.status === 'success') {
        clearInterval(pollTimer.value)
        ElMessage.success('授权成功！')
        dialogVisible.value = false
        loadAccounts()
      } else if (res.status === 'failed' || res.status === 'timeout') {
        clearInterval(pollTimer.value)
        authStep.value = false
        ElMessage.error(res.message || '授权失败')
      }
    } catch (error: any) {
      // 🌟 核心修复：如果后端返回 404 (任务丢失)，立即停止轮询
      if (error.response && error.response.status === 404) {
        console.warn('任务已失效，停止轮询')
        clearInterval(pollTimer.value)
        authStep.value = false
        ElMessage.warning('授权会话已过期，请重试')
      }
    }
  }, 2000)
}

// 修改 deleteAccount 函数
const deleteAccount = async (acc: any) => {
  try {
    // 1. 弹出确认框
    await ElMessageBox.confirm(
      `确定要删除账号 "${acc.account_name}" 吗？\n删除后相关的发布记录也会被清除！`, 
      '高风险操作', 
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    // 2. 发送请求
    console.log(`正在请求删除账号 ID: ${acc.id}...`)
    const res: any = await accountApi.delete(acc.id)

    // 3. 判断结果
    if (res.success) {
      ElMessage.success('账号已成功删除')
      await loadAccounts() // 重新加载列表
    } else {
      ElMessage.error(res.message || '删除失败，服务端拒绝')
    }

  } catch (e: any) {
    // 4. 区分是“用户取消”还是“报错”
    if (e === 'cancel') {
      console.log('用户取消删除')
    } else {
      console.error('删除接口报错:', e)
      // 获取更详细的错误信息
      const errorMsg = e.response?.data?.detail || e.message || '未知错误'
      ElMessage.error(`删除失败: ${errorMsg}`)
    }
  }
}

const resetForm = () => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  authStep.value = false
  loading.value = false
}

// 检测相关方法
const handleCheckAll = async () => {
  try {
    await ElMessageBox.confirm(
      '将检测所有已授权账号的登录状态，检测失败的账号状态将更新为"授权过期"，是否继续？',
      '批量检测确认',
      {
        confirmButtonText: '开始检测',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  checkLogs.value = []
  checkCompleted.value = false
  checkProgress.value = { current: 0, total: 0, percentage: 0, status: '' }
  checkDialogVisible.value = true
  checking.value = true

  try {
    const allAccounts: any[] = await accountApi.getList()
    const authorizedAccounts = allAccounts.filter((acc: any) => acc.status === 1)
    checkProgress.value.total = authorizedAccounts.length

    if (authorizedAccounts.length === 0) {
      ElMessage.warning('没有需要检测的账号')
      checkDialogVisible.value = false
      checking.value = false
      return
    }

    setupWsListener()
    await accountApi.checkAll()
  } catch (error: any) {
    console.error('检测失败:', error)
    ElMessage.error('检测过程中发生错误')
    checking.value = false
  }
}

const setupWsListener = () => {
  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8001/ws'
  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.type === 'account_check_progress') {
        checkProgress.value.current = data.current
        checkProgress.value.percentage = data.progress || 0
        checkLogs.value.push(data.result)
      } else if (data.type === 'account_check_complete') {
        checkCompleted.value = true
        checking.value = false
        checkProgress.value.status = data.summary.failed > 0 ? 'exception' : 'success'

        ElMessage.success(
          `检测完成: 共 ${data.summary.total} 个账号, ` +
          `成功 ${data.summary.success} 个, ` +
          `失败 ${data.summary.failed} 个`
        )

        loadAccounts()
      }
    } catch (error) {
      console.error('解析WebSocket消息失败:', error)
    }
  }
}

const closeCheckDialog = () => {
  checkDialogVisible.value = false
  if (ws) {
    ws.close()
    ws = null
  }
}

// 工具函数
const getPlatformName = (p: string) => {
  const config = getPlatformConfig(p)
  return config ? config.name : p
}

const getPlatformColor = (p: string) => {
  const config = getPlatformConfig(p)
  return config ? config.color : '#999'
}

onMounted(loadAccounts)
onUnmounted(() => {
  resetForm()
  if (ws) {
    ws.close()
    ws = null
  }
})
</script>

<style scoped lang="scss">
.account-list-page { padding: 20px; display: flex; flex-direction: column; gap: 20px; }
.toolbar { display: flex; justify-content: space-between; }

.accounts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }

.account-card {
  background: var(--bg-secondary); border-radius: 12px; padding: 20px; position: relative; border: 1px solid var(--border);
  transition: transform 0.2s;
  &:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }

  &.expired {
    border: 2px solid #f56c6c;
    background: linear-gradient(135deg, rgba(245, 108, 108, 0.05), var(--bg-secondary));
  }
  
  &.add-card {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    border: 2px dashed var(--border); cursor: pointer; color: var(--text-secondary);
    &:hover { border-color: var(--primary); color: var(--primary); }
    .add-icon { font-size: 32px; margin-bottom: 10px; }
  }
}

.account-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;
  .platform-icon {
    width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
    color: white; font-weight: bold; font-size: 18px;
  }
  .status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    &.online { background: #67C23A; box-shadow: 0 0 5px #67C23A; }
    &.offline { background: #909399; }
  }
}

.account-name { margin: 0 0 5px 0; font-size: 16px; color: var(--text-primary); }
.account-username { font-size: 13px; color: var(--text-secondary); margin-bottom: 5px; }
.account-platform { font-size: 12px; color: var(--text-tertiary); margin-bottom: 15px; }

.account-actions {
  display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--border); padding-top: 10px;
}

.auth-step {
  text-align: center; padding: 30px 0;
  h3 { margin: 20px 0 10px; color: var(--text-primary); }
  .sub-text { color: var(--text-secondary); font-size: 12px; }
}

.check-progress {
  .progress-text {
    text-align: center;
    margin: 15px 0;
    color: var(--text-secondary);
  }

  .check-log {
    max-height: 300px;
    overflow-y: auto;
    margin-top: 15px;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px;

    .log-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px;
      border-bottom: 1px solid var(--border);

      &:last-child {
        border-bottom: none;
      }

      &.error {
        background: rgba(245, 108, 108, 0.05);
      }

      .log-platform {
        font-weight: 500;
        color: var(--primary);
        min-width: 80px;
      }

      .log-name {
        flex: 1;
        color: var(--text-primary);
      }

      .log-message {
        color: var(--text-secondary);
        font-size: 13px;
      }
    }
  }
}
</style>