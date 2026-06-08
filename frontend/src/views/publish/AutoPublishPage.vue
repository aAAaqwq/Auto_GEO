<template>
  <div class="auto-publish-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>自动发布任务管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        创建任务
      </el-button>
    </div>

    <!-- 任务状态过滤 -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-radio-group v-model="statusFilter" @change="loadTasks">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="pending">待执行</el-radio-button>
          <el-radio-button label="running">执行中</el-radio-button>
          <el-radio-button label="completed">已完成</el-radio-button>
          <el-radio-button label="failed">失败</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="platformFilter"
          placeholder="筛选平台"
          clearable
          @change="loadTasks"
          style="width: 150px; margin-left: 12px"
        >
          <el-option label="全部平台" value="" />
          <el-option
            v-for="(platform, key) in PLATFORMS"
            :key="key"
            :label="platform.name"
            :value="key"
          >
            <div class="platform-option">
              <span>{{ platform.name }}</span>
            </div>
          </el-option>
        </el-select>
      </div>
      <el-button @click="loadTasks" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 任务列表 -->
    <div v-loading="loading" class="task-list">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="task-card"
        :class="`status-${task.status}`"
      >
        <div class="task-header">
          <div class="task-title">
            <h3>{{ task.name }}</h3>
            <el-tag :type="getStatusType(task.status)" size="small">
              {{ getStatusText(task.status) }}
            </el-tag>
            <el-tag v-if="task.exec_type === 'immediate'" type="info" size="small">立即执行</el-tag>
            <el-tag v-else-if="task.exec_type === 'scheduled'" type="warning" size="small">定时执行</el-tag>
            <el-tag v-else type="success" size="small">间隔执行</el-tag>
            <el-tag
              v-for="platform in getTaskPlatforms(task.id)"
              :key="platform"
              size="small"
              :color="PLATFORMS[platform]?.color"
              style="margin-left: 4px"
            >
              {{ PLATFORMS[platform]?.name || platform }}
            </el-tag>
          </div>
          <div class="task-actions">
            <el-button
              v-if="task.status === 'pending' || task.status === 'failed'"
              type="primary"
              size="small"
              @click="startTask(task.id)"
              :loading="task.id === startingTaskId"
            >
              启动
            </el-button>
            <el-button
              v-if="task.status === 'running'"
              type="danger"
              size="small"
              @click="cancelTask(task.id)"
            >
              取消
            </el-button>
            <el-button
              v-if="task.status === 'failed'"
              type="warning"
              size="small"
              @click="retryTask(task.id)"
              :loading="task.id === retryingTaskId"
            >
              重试
            </el-button>
            <el-button size="small" @click="viewTaskDetail(task)">
              详情
            </el-button>
            <el-dropdown @command="(cmd) => handleTaskAction(cmd, task)">
              <el-button size="small" :icon="MoreFilled" circle />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="delete" v-if="task.status !== 'running'">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <div class="task-description" v-if="task.description">
          {{ task.description }}
        </div>

        <div class="task-info">
          <div class="info-item">
            <span class="label">文章数量:</span>
            <span class="value">{{ task.article_ids?.length || 0 }}</span>
          </div>
          <div class="info-item">
            <span class="label">账号数量:</span>
            <span class="value">{{ task.account_ids?.length || 0 }}</span>
          </div>
          <div class="info-item">
            <span class="label">总任务数:</span>
            <span class="value">{{ task.total_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">已完成:</span>
            <span class="value success">{{ task.completed_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">失败:</span>
            <span class="value danger">{{ task.failed_count }}</span>
          </div>
          <div class="info-item" v-if="task.scheduled_at">
            <span class="label">定时时间:</span>
            <span class="value">{{ formatTime(task.scheduled_at) }}</span>
          </div>
        </div>

        <div class="task-progress" v-if="task.status === 'running' || task.total_count > 0">
          <el-progress
            :percentage="getProgress(task)"
            :status="task.failed_count > 0 ? 'exception' : (getProgress(task) === 100 ? 'success' : undefined)"
          />
        </div>

        <div class="task-error" v-if="task.error_msg">
          <el-icon><Warning /></el-icon>
          {{ task.error_msg }}
        </div>

        <div class="task-time">
          创建时间: {{ formatTime(task.created_at) }}
          <span v-if="task.started_at"> | 开始: {{ formatTime(task.started_at) }}</span>
          <span v-if="task.completed_at"> | 完成: {{ formatTime(task.completed_at) }}</span>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && tasks.length === 0" class="empty-state">
        <el-empty description="暂无自动发布任务">
          <el-button type="primary" @click="showCreateDialog = true">创建第一个任务</el-button>
        </el-empty>
      </div>
    </div>

    <!-- 创建任务对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建自动发布任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="100px" :rules="formRules" ref="createFormRef">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务描述" prop="description">
          <el-input v-model="createForm.description" type="textarea" placeholder="可选：任务描述" />
        </el-form-item>
        <el-form-item label="选择文章" prop="article_ids">
          <el-select
            v-model="createForm.article_ids"
            multiple
            filterable
            placeholder="请选择要发布的文章"
            style="width: 100%"
          >
            <el-option
              v-for="article in availableArticles"
              :key="article.id"
              :label="article.title || '无标题'"
              :value="article.id"
            >
              <div class="article-option">
                <span>{{ article.title || '无标题' }}</span>
                <el-tag size="small" type="info">{{ article.publish_status }}</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="选择平台" prop="platforms">
          <el-select
            v-model="createForm.platforms"
            multiple
            placeholder="请选择发布平台"
            style="width: 100%"
          >
            <el-option
              v-for="(platform, key) in PLATFORMS"
              :key="key"
              :label="platform.name"
              :value="key"
            >
              <div class="platform-option-item">
                <span>{{ platform.name }}</span>
                <el-tag size="small" type="info">{{ getPlatformAccountCount(key) }}个账号</el-tag>
              </div>
            </el-option>
          </el-select>
          <div class="form-tip">系统将为每个平台自动选择可用账号进行发布</div>
        </el-form-item>
        <el-form-item label="执行类型" prop="exec_type">
          <el-radio-group v-model="createForm.exec_type">
            <el-radio value="immediate">立即执行</el-radio>
            <el-radio value="scheduled">定时执行</el-radio>
            <el-radio value="interval">间隔执行</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="后台运行">
          <el-switch v-model="createForm.run_in_background" />
          <span class="form-tip">开启后任务将在后台运行，可在平台发布监控页面查看进度</span>
        </el-form-item>
        <el-form-item
          v-if="createForm.exec_type === 'scheduled'"
          label="执行时间"
          prop="scheduled_at"
        >
          <el-date-picker
            v-model="createForm.scheduled_at"
            type="datetime"
            placeholder="选择执行时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            :disabled-date="disabledDate"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item
          v-if="createForm.exec_type === 'interval'"
          label="间隔分钟"
          prop="interval_minutes"
        >
          <el-input-number v-model="createForm.interval_minutes" :min="1" :max="10080" />
          <span class="form-tip">每隔N分钟执行一次</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="`任务详情 - ${currentTask?.name}`"
      width="800px"
    >
      <div v-if="currentTask" class="task-detail">
        <div class="detail-section">
          <h4>基本信息</h4>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="label">状态:</span>
              <el-tag :type="getStatusType(currentTask.status)">{{ getStatusText(currentTask.status) }}</el-tag>
            </div>
            <div class="detail-item">
              <span class="label">执行类型:</span>
              <span>{{ getExecTypeText(currentTask.exec_type) }}</span>
            </div>
            <div class="detail-item">
              <span class="label">文章数量:</span>
              <span>{{ currentTask.article_ids?.length || 0 }}</span>
            </div>
            <div class="detail-item">
              <span class="label">账号数量:</span>
              <span>{{ currentTask.account_ids?.length || 0 }}</span>
            </div>
            <div class="detail-item">
              <span class="label">总任务数:</span>
              <span>{{ currentTask.total_count }}</span>
            </div>
            <div class="detail-item">
              <span class="label">已完成:</span>
              <span class="success">{{ currentTask.completed_count }}</span>
            </div>
            <div class="detail-item">
              <span class="label">失败:</span>
              <span class="danger">{{ currentTask.failed_count }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h4>子任务记录</h4>
          <el-table :data="taskRecords" style="width: 100%" max-height="400">
            <el-table-column prop="article_title" label="文章" width="200" show-overflow-tooltip />
            <el-table-column prop="account_name" label="账号" width="120" />
            <el-table-column prop="platform" label="平台" width="100">
              <template #default="{ row }">
                <el-tag size="small" :color="PLATFORMS[row.platform]?.color">
                  {{ PLATFORMS[row.platform]?.name || row.platform }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getRecordStatusType(row.status)" size="small">
                  {{ getRecordStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="platform_url" label="链接" width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <a v-if="row.platform_url" :href="row.platform_url" target="_blank">查看</a>
              </template>
            </el-table-column>
            <el-table-column prop="error_msg" label="错误" show-overflow-tooltip />
            <el-table-column prop="created_at" label="创建时间" width="160">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, MoreFilled, Warning } from '@element-plus/icons-vue'
import { autoPublishApi, geoArticleApi, accountApi } from '@/services/api'
import { useWebSocket } from '@/composables/useWebSocket'
import { PLATFORMS } from '@/core/config/platform'

// WebSocket
const { connect, disconnect, onAutoPublishProgress } = useWebSocket()

// 数据
const tasks = ref<any[]>([])
const loading = ref(false)
const statusFilter = ref('')
const platformFilter = ref('')
const availableArticles = ref<any[]>([])
const availableAccounts = ref<any[]>([])
// 任务的平台信息缓存（从账号数据中提取）
const taskPlatforms = ref<Record<number, string[]>>({})

// 创建任务对话框
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  article_ids: [] as number[],
  platforms: [] as string[],
  exec_type: 'immediate' as 'immediate' | 'scheduled' | 'interval',
  run_in_background: false,
  scheduled_at: '',
  interval_minutes: null as number | null
})
const createFormRef = ref<FormInstance>()
const formRules: FormRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  article_ids: [{ required: true, message: '请选择文章', trigger: 'change' }],
  platforms: [{ required: true, message: '请选择平台', trigger: 'change' }],
  scheduled_at: [{ required: true, message: '请选择执行时间', trigger: 'change' }],
  interval_minutes: [{ required: true, message: '请输入间隔分钟数', trigger: 'blur' }]
}

// 任务详情对话框
const showDetailDialog = ref(false)
const currentTask = ref<any>(null)
const taskRecords = ref<any[]>([])

// 操作状态
const startingTaskId = ref<number | null>(null)
const retryingTaskId = ref<number | null>(null)

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const params: any = { limit: 100 }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    if (platformFilter.value) {
      params.platform = platformFilter.value
    }
    const res: any = await autoPublishApi.getTasks(params)
    tasks.value = res.data?.items || []
    // 提取每个任务涉及的平台信息
    extractTaskPlatforms()
  } catch (e) {
    console.error('加载任务失败:', e)
  } finally {
    loading.value = false
  }
}

// 加载可用文章和账号
const loadAvailableData = async () => {
  try {
    // 加载可发布的文章
    const articlesRes: any = await geoArticleApi.getArticles({
      publish_status: ['completed', 'scheduled', 'failed'],
      limit: 1000
    })
    availableArticles.value = Array.isArray(articlesRes) ? articlesRes : (articlesRes?.data || [])

    // 加载可用账号
    const accountsRes: any = await accountApi.getList({ status: 1 })
    availableAccounts.value = Array.isArray(accountsRes) ? accountsRes : (accountsRes?.data || [])
  } catch (e) {
    console.error('加载数据失败:', e)
  }
}

// 从任务数据中提取涉及的平台
const extractTaskPlatforms = () => {
  taskPlatforms.value = {}
  tasks.value.forEach(task => {
    // 从账号列表中查找该任务使用的账号所属平台
    const platforms = new Set<string>()
    if (task.account_ids && Array.isArray(task.account_ids)) {
      task.account_ids.forEach((accountId: number) => {
        const account = availableAccounts.value.find((a: any) => a.id === accountId)
        if (account?.platform) {
          platforms.add(account.platform)
        }
      })
    }
    taskPlatforms.value[task.id] = Array.from(platforms)
  })
}

// 获取任务涉及的平台列表
const getTaskPlatforms = (taskId: number) => {
  return taskPlatforms.value[taskId] || []
}

// 获取平台的账号数量
const getPlatformAccountCount = (platform: string) => {
  return availableAccounts.value.filter((a: any) => a.platform === platform).length
}

// 创建任务
const createTask = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return

    creating.value = true
    try {
      // 将平台列表转换为账号列表
      const accountIds: number[] = []
      const platformWithoutAccounts: string[] = []
      createForm.value.platforms.forEach(platform => {
        const platformAccounts = availableAccounts.value
          .filter((a: any) => a.platform === platform)
          .map((a: any) => a.id)
        if (platformAccounts.length === 0) {
          platformWithoutAccounts.push(PLATFORMS[platform]?.name || platform)
        }
        accountIds.push(...platformAccounts)
      })

      // 校验：至少有一个平台有可用账号
      if (platformWithoutAccounts.length > 0) {
        ElMessage.warning(`以下平台没有可用账号，请先授权账号: ${platformWithoutAccounts.join('、')}`)
        creating.value = false
        return
      }

      if (accountIds.length === 0) {
        ElMessage.warning('所选平台暂无可用账号，请先在「账号管理」中完成授权')
        creating.value = false
        return
      }

      await autoPublishApi.create({
        name: createForm.value.name,
        description: createForm.value.description || undefined,
        article_ids: createForm.value.article_ids,
        account_ids: accountIds,
        exec_type: createForm.value.exec_type,
        run_in_background: createForm.value.run_in_background || undefined,
        scheduled_at: createForm.value.scheduled_at || undefined,
        interval_minutes: createForm.value.interval_minutes || undefined
      })
      ElMessage.success('任务创建成功')
      showCreateDialog.value = false
      resetCreateForm()
      await loadTasks()
    } catch (e) {
      console.error('创建任务失败:', e)
    } finally {
      creating.value = false
    }
  })
}

// 重置创建表单
const resetCreateForm = () => {
  createForm.value = {
    name: '',
    description: '',
    article_ids: [],
    platforms: [],
    exec_type: 'immediate',
    run_in_background: false,
    scheduled_at: '',
    interval_minutes: null
  }
  createFormRef.value?.resetFields()
}

// 启动任务
const startTask = async (taskId: number) => {
  startingTaskId.value = taskId
  try {
    await autoPublishApi.start(taskId)
    ElMessage.success('任务已启动')
    await loadTasks()
  } catch (e) {
    console.error('启动任务失败:', e)
  } finally {
    startingTaskId.value = null
  }
}

// 取消任务
const cancelTask = async (taskId: number) => {
  try {
    await ElMessageBox.confirm('确认取消此任务？', '提示', {
      type: 'warning'
    })
    await autoPublishApi.cancel(taskId)
    ElMessage.success('任务已取消')
    await loadTasks()
  } catch (e) {
    if (e !== 'cancel') console.error('取消任务失败:', e)
  }
}

// 重试任务
const retryTask = async (taskId: number) => {
  retryingTaskId.value = taskId
  try {
    await autoPublishApi.retry(taskId)
    ElMessage.success('任务已重试')
    await loadTasks()
  } catch (e) {
    console.error('重试任务失败:', e)
  } finally {
    retryingTaskId.value = null
  }
}

// 查看任务详情
const viewTaskDetail = async (task: any) => {
  currentTask.value = task
  showDetailDialog.value = true
  try {
    const res: any = await autoPublishApi.getTask(task.id)
    taskRecords.value = res.data?.records || []
  } catch (e) {
    console.error('加载任务详情失败:', e)
  }
}

// 处理任务操作
const handleTaskAction = async (command: string, task: any) => {
  if (command === 'delete') {
    try {
      await ElMessageBox.confirm('确认删除此任务？', '提示', {
        type: 'warning'
      })
      await autoPublishApi.delete(task.id)
      ElMessage.success('任务已删除')
      await loadTasks()
    } catch (e) {
      if (e !== 'cancel') console.error('删除任务失败:', e)
    }
  }
}

// 工具方法
const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return textMap[status] || status
}

const getExecTypeText = (execType: string) => {
  const textMap: Record<string, string> = {
    immediate: '立即执行',
    scheduled: '定时执行',
    interval: '间隔执行'
  }
  return textMap[execType] || execType
}

const getRecordStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'info',
    publishing: 'warning',
    success: 'success',
    failed: 'danger',
    skipped: 'info'
  }
  return typeMap[status] || 'info'
}

const getRecordStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待发布',
    publishing: '发布中',
    success: '成功',
    failed: '失败',
    skipped: '跳过'
  }
  return textMap[status] || status
}

const getProgress = (task: any) => {
  if (task.total_count === 0) return 0
  return Math.round((task.completed_count / task.total_count) * 100)
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const disabledDate = (time: Date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return time.getTime() < today.getTime()
}

// WebSocket 监听进度更新
const setupWebSocket = () => {
  connect()
  onAutoPublishProgress((data: any) => {
    // 更新任务列表中的进度
    const task = tasks.value.find(t => t.id === data.task_id)
    if (task) {
      task.completed_count = data.completed_count || task.completed_count
      task.failed_count = data.failed_count || task.failed_count
    }

    // 如果详情页打开，也更新详情
    if (currentTask.value && currentTask.value.id === data.task_id) {
      const record = taskRecords.value.find(r => r.id === data.record_id)
      if (record) {
        record.status = data.status
        record.platform_url = data.platform_url
        record.error_msg = data.error_msg
      }
    }
  })
}

onMounted(() => {
  loadTasks()
  loadAvailableData()
  setupWebSocket()
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped lang="scss">
.auto-publish-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-base);
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    color: var(--text-primary, #fff);
  }
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-secondary, #2a2a2a);
  border-radius: 8px;

  .filter-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.task-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-card {
  background: var(--bg-secondary, #2a2a2a);
  border-radius: 12px;
  padding: 20px;
  border-left: 4px solid transparent;
  transition: all 0.3s;

  &:hover {
    background: var(--bg-tertiary, #3a3a3a);
  }

  &.status-pending {
    border-left-color: #909399;
  }

  &.status-running {
    border-left-color: #e6a23c;
  }

  &.status-completed {
    border-left-color: #67c23a;
  }

  &.status-failed {
    border-left-color: #f56c6c;
  }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 12px;

  h3 {
    margin: 0;
    color: var(--text-primary, #fff);
    font-size: 18px;
  }
}

.task-actions {
  display: flex;
  gap: 8px;
}

.task-description {
  color: var(--text-secondary, #6b7280);
  margin-bottom: 12px;
  font-size: 14px;
}

.task-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;

  .info-item {
    display: flex;
    align-items: center;
    gap: 8px;

    .label {
      color: var(--text-secondary, #6b7280);
      font-size: 14px;
    }

    .value {
      color: var(--text-primary, #fff);
      font-weight: 500;

      &.success {
        color: #67c23a;
      }

      &.danger {
        color: #f56c6c;
      }
    }
  }
}

.task-progress {
  margin-bottom: 12px;
}

.task-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(245, 108, 108, 0.1);
  border-radius: 6px;
  color: #f56c6c;
  font-size: 14px;
  margin-bottom: 12px;
}

.task-time {
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.article-option,
.account-option,
.platform-option-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.platform-option {
  width: 100%;
}

.account-selector {
  width: 100%;
}

.form-tip {
  margin-left: 12px;
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
}

.task-detail {
  .detail-section {
    margin-bottom: 24px;

    h4 {
      margin: 0 0 16px 0;
      color: var(--text-primary, #fff);
    }
  }

  .detail-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;

    .detail-item {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 16px;
      background: var(--bg-tertiary, #3a3a3a);
      border-radius: 8px;

      .label {
        color: var(--text-secondary, #6b7280);
        font-size: 12px;
      }

      .success {
        color: #67c23a;
      }

      .danger {
        color: #f56c6c;
      }
    }
  }
}
</style>
