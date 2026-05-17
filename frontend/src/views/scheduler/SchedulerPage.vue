<template>
  <div class="scheduler-page">
    <!-- 头部 -->
    <header class="page-header">
      <div class="header-left">
        <div class="header-icon">
          <el-icon><Timer /></el-icon>
        </div>
        <div class="header-text">
          <h1 class="page-title">定时任务调度中心</h1>
          <p class="page-desc">动态管理后台任务频率，无需重启服务即刻生效</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="loadTasks" :loading="loading">
          <el-icon class="mr-1"><Refresh /></el-icon> 刷新状态
        </el-button>
      </div>
    </header>

    <!-- 任务卡片网格 -->
    <div class="tasks-section" v-loading="loading">
      <el-row :gutter="20">
        <el-col
          v-for="task in tasks"
          :key="task.id"
          :xs="24"
          :sm="12"
          :md="12"
          :lg="8"
          :xl="6"
        >
          <el-card class="task-card" shadow="hover">
            <!-- 卡片头部 -->
            <template #header>
              <div class="card-header">
                <div class="header-left">
                  <div class="task-icon" :class="{ active: task.is_active }">
                    <el-icon>
                      <component :is="getTaskIcon(task.task_key)" />
                    </el-icon>
                  </div>
                  <div>
                    <h3 class="task-name">{{ task.name }}</h3>
                    <div class="status-badge" :class="{ active: task.is_active }">
                      <span class="status-dot"></span>
                      <span class="status-text">{{ task.is_active ? '运行中' : '已暂停' }}</span>
                    </div>
                  </div>
                </div>
                <el-switch
                  v-model="task.is_active"
                  inline-prompt
                  active-text=""
                  inactive-text=""
                  style="--el-switch-on-color: #52c41a; --el-switch-off-color: #d9d9d9"
                  @change="handleStatusChange(task)"
                />
              </div>
            </template>

            <!-- 卡片内容 -->
            <div class="card-content">
              <p class="task-description">{{ task.description }}</p>

              <div class="schedule-info">
                <div class="schedule-icon">
                  <el-icon><Clock /></el-icon>
                </div>
                <div class="schedule-text">
                  <span class="schedule-label">执行频率</span>
                  <span class="schedule-value">{{ formatCronToText(task.cron_expression) }}</span>
                </div>
              </div>
            </div>

            <!-- 卡片底部操作按钮 -->
            <div class="card-footer">
              <el-button
                type="primary"
                link
                @click="openEdit(task)"
                class="action-btn"
              >
                <el-icon class="btn-icon"><Edit /></el-icon>
                修改频率
              </el-button>
              <el-divider direction="vertical" />
              <el-button
                type="primary"
                link
                @click="triggerTask(task)"
                class="action-btn"
              >
                <el-icon class="btn-icon"><VideoPlay /></el-icon>
                立即执行
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 空状态 -->
      <el-empty
        v-if="!loading && tasks.length === 0"
        description="暂无定时任务"
        :image-size="120"
      />
    </div>

    <!-- 修改频率对话框 (人性化表单) -->
    <el-dialog
      v-model="showEditDialog"
      title="修改执行频率"
      width="480px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" class="edit-form">
        <el-form-item label="任务名称">
          <span class="task-name-display">{{ currentTask.name }}</span>
        </el-form-item>

        <el-form-item label="模式选择">
          <el-radio-group v-model="frequencyMode">
            <el-radio-button label="interval">按间隔</el-radio-button>
            <el-radio-button label="time">按时间</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 按间隔模式 -->
        <el-form-item label="执行间隔" v-if="frequencyMode === 'interval'">
          <el-input-number
            v-model="intervalMinutes"
            :min="1"
            :max="1440"
            controls-position="right"
            class="interval-input"
          />
          <span class="interval-unit">分钟</span>
        </el-form-item>

        <!-- 按时间模式 -->
        <el-form-item label="执行时间" v-if="frequencyMode === 'time'">
          <el-time-picker
            v-model="executionTime"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="选择执行时间"
            :clearable="false"
            class="time-picker"
          />
        </el-form-item>

        <!-- 预览 -->
        <el-form-item label="频率预览">
          <span class="preview-text">{{ frequencyPreview }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveFrequency" :loading="saving">
          <el-icon class="mr-1"><Check /></el-icon> 保存并生效
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Timer, Refresh, Edit, VideoPlay, Check, Clock,
  Paperclip, Promotion, Search, RefreshLeft, Document,
  Connection, DataLine, Monitor, Setting
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const API_BASE = `${import.meta.env.VITE_API_BASE_URL}/scheduler`

interface Task {
  id: number
  name: string
  task_key: string
  cron_expression: string
  is_active: boolean
  description: string
}

const tasks = ref<Task[]>([])
const loading = ref(false)
const saving = ref(false)
const showEditDialog = ref(false)
const currentTask = ref<any>({})

// 频率配置模式：interval=按间隔, time=按时间
const frequencyMode = ref<'interval' | 'time'>('interval')
const intervalMinutes = ref(5)
const executionTime = ref('02:00')

// 任务图标映射
const getTaskIcon = (taskKey: string) => {
  const iconMap: Record<string, any> = {
    'publish_articles': Promotion,
    'sync_zhihu': Paperclip,
    'check收录': Search,
    'auto_reply': Document,
    'heartbeat': Connection,
    'analytics': DataLine,
    'monitor': Monitor,
    'cleanup': RefreshLeft,
  }
  return iconMap[taskKey] || Setting
}

// Cron 转自然语言
const formatCronToText = (cron: string): string => {
  if (!cron) return '未配置'

  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return '自定义频率'

  const [minute, hour, day, month, weekday] = parts

  // 按间隔执行：*/N * * * *
  const intervalMatch = minute.match(/^\*\/(\d+)$/)
  if (intervalMatch && hour === '*' && day === '*' && month === '*' && weekday === '*') {
    const n = parseInt(intervalMatch[1])
    if (n === 1) return '每 1 分钟执行一次'
    return `每 ${n} 分钟执行一次`
  }

  // 按小时执行：0 * * * *
  if (minute === '0' && hour === '*' && day === '*' && month === '*' && weekday === '*') {
    return '每小时执行一次'
  }

  // 按时间执行：0 H * * *
  const hourMatch = hour.match(/^(\d+)$/)
  if (minute === '0' && hourMatch && day === '*' && month === '*' && weekday === '*') {
    const h = parseInt(hourMatch[1])
    return `每天 ${h.toString().padStart(2, '0')}:00 执行`
  }

  // 工作日特定时间：0 H * * 1-5
  const workdayMatch = weekday.match(/^1-5$/)
  if (minute === '0' && hourMatch && day === '*' && month === '*' && workdayMatch) {
    const h = parseInt(hourMatch[1])
    return `工作日 ${h.toString().padStart(2, '0')}:00 执行`
  }

  return '自定义频率'
}

// 根据配置生成 Cron
const generateCron = (): string => {
  if (frequencyMode.value === 'interval') {
    return `*/${intervalMinutes.value} * * * *`
  } else {
    const [h, m] = executionTime.value.split(':')
    return `${m} ${h} * * *`
  }
}

// 频率预览
const frequencyPreview = computed(() => {
  return formatCronToText(generateCron())
})

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/jobs`)
    tasks.value = res.data
  } catch (error) {
    ElMessage.error('无法连接到调度中心')
  } finally {
    loading.value = false
  }
}

// 切换开关状态
const handleStatusChange = async (row: Task) => {
  try {
    await updateTaskApi(row)
    ElMessage.success(row.is_active ? `任务 [${row.name}] 已启动` : `任务 [${row.name}] 已暂停`)
  } catch (error) {
    row.is_active = !row.is_active // 失败则回滚UI状态
    ElMessage.error('状态更新失败')
  }
}

// 打开编辑
const openEdit = (row: Task) => {
  currentTask.value = { ...row }

  // 解析现有 Cron，设置初始值
  const parts = row.cron_expression.trim().split(/\s+/)
  if (parts.length === 5) {
    const [minute, hour] = parts

    // 判断是否为间隔模式
    const intervalMatch = minute.match(/^\*\/(\d+)$/)
    if (intervalMatch && hour === '*') {
      frequencyMode.value = 'interval'
      intervalMinutes.value = parseInt(intervalMatch[1])
    } else {
      frequencyMode.value = 'time'
      // 解析时间
      if (minute === '0' && hour.match(/^\d+$/)) {
        const h = parseInt(hour).toString().padStart(2, '0')
        executionTime.value = `${h}:00`
      } else {
        // 尝试解析复杂的时间格式
        const hNum = parseInt(hour) || 0
        const mNum = parseInt(minute) || 0
        executionTime.value = `${hNum.toString().padStart(2, '0')}:${mNum.toString().padStart(2, '0')}`
      }
    }
  }

  showEditDialog.value = true
}

// 立即执行任务
const triggerTask = async (task: Task) => {
  try {
    await ElMessageBox.confirm(
      `确定要立即执行任务 "${task.name}" 吗？`,
      '立即执行',
      {
        confirmButtonText: '执行',
        cancelButtonText: '取消',
        type: 'info',
      }
    )
    loading.value = true
    // 使用 task_key 而不是 id，因为 APScheduler 的 Job ID 是 task_key (字符串)
    await axios.post(`${API_BASE}/jobs/${task.task_key}/run`)
    ElMessage.success('任务已触发执行')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('触发执行失败')
    }
  } finally {
    loading.value = false
  }
}

// 保存频率修改
const saveFrequency = async () => {
  saving.value = true
  try {
    const newCron = generateCron()
    const task = {
      ...currentTask.value,
      cron_expression: newCron
    }
    await updateTaskApi(task)
    ElMessage.success('执行频率已更新，下次执行将按新规则')
    showEditDialog.value = false
    loadTasks() // 刷新列表
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    saving.value = false
  }
}

// 统一更新接口
const updateTaskApi = async (task: Task) => {
  const payload = {
    cron_expression: task.cron_expression,
    is_active: task.is_active
  }
  await axios.put(`${API_BASE}/jobs/${task.id}`, payload)
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped lang="scss">
.scheduler-page {
  padding: 24px;
  background: #f5f7fa;
  min-height: 100vh;
}

/* 头部样式 */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.04);
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    .header-icon {
      width: 52px;
      height: 52px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 26px;
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }

    .page-title {
      margin: 0 0 6px 0;
      font-size: 22px;
      font-weight: 600;
      color: #1a1a2e;
    }

    .page-desc {
      margin: 0;
      font-size: 14px;
      color: #8b9bb4;
    }
  }
}

/* 任务卡片区域 */
.tasks-section {
  min-height: 300px;
}

.task-card {
  height: 100%;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: none;
  border-radius: 12px;

  &:hover {
    transform: translateY(-4px);
  }

  :deep(.el-card__header) {
    padding: 16px 20px;
    border-bottom: 1px solid #f0f0f0;
  }

  :deep(.el-card__body) {
    padding: 20px;
  }
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
  }

  .task-icon {
    width: 42px;
    height: 42px;
    background: #f5f7fa;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #8b9bb4;
    font-size: 20px;
    transition: all 0.3s ease;

    &.active {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      box-shadow: 0 4px 10px rgba(102, 126, 234, 0.25);
    }
  }

  .task-name {
    margin: 0 0 4px 0;
    font-size: 16px;
    font-weight: 600;
    color: #1a1a2e;
  }

  .status-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #8b9bb4;
    transition: all 0.3s ease;

    &.active {
      color: #52c41a;
    }

    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #d9d9d9;
      transition: all 0.3s ease;

      .status-badge.active & {
        background: #52c41a;
        box-shadow: 0 0 8px rgba(82, 196, 26, 0.5);
      }
    }
  }
}

/* 卡片内容 */
.card-content {
  .task-description {
    margin: 0 0 20px 0;
    font-size: 13px;
    color: #8b9bb4;
    line-height: 1.6;
    min-height: 40px;
  }

  .schedule-info {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 16px;
    background: #f8f9fc;
    border-radius: 10px;
    border-left: 3px solid #667eea;

    .schedule-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 18px;
    }

    .schedule-text {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;

      .schedule-label {
        font-size: 11px;
        color: #8b9bb4;
      }

      .schedule-value {
        font-size: 16px;
        font-weight: 600;
        color: #1a1a2e;
      }
    }
  }
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;

  .action-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0;
    font-size: 13px;

    .btn-icon {
      font-size: 15px;
    }
  }

  :deep(.el-divider--vertical) {
    height: 14px;
    margin: 0;
    border-color: #e0e0e0;
  }
}

/* 编辑弹窗样式 */
.edit-form {
  .task-name-display {
    font-size: 15px;
    font-weight: 500;
    color: #1a1a2e;
  }

  .interval-input {
    width: 140px;
  }

  .interval-unit {
    margin-left: 8px;
    color: #8b9bb4;
  }

  .time-picker {
    width: 100%;
  }

  .preview-text {
    font-size: 15px;
    font-weight: 500;
    color: #667eea;
    padding: 8px 12px;
    background: #f8f9fc;
    border-radius: 6px;
    display: inline-block;
  }
}

.mr-1 {
  margin-right: 4px;
}
</style>
