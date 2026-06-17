<template>
  <div class="publish-monitor-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>平台发布监控</h2>
      <div class="header-actions">
        <el-button @click="loadMonitorData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 总体统计 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon" style="background: rgba(74, 144, 226, 0.1)">
          <el-icon size="24" color="#4a90e2"><List /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总任务数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: rgba(103, 178, 111, 0.1)">
          <el-icon size="24" color="#67b26f"><CircleCheck /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.completed }}</div>
          <div class="stat-label">已完成</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: rgba(230, 162, 60, 0.1)">
          <el-icon size="24" color="#e6a23c"><Loading /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.running }}</div>
          <div class="stat-label">执行中</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: rgba(245, 108, 108, 0.1)">
          <el-icon size="24" color="#f56c6c"><CircleClose /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.failed }}</div>
          <div class="stat-label">失败</div>
        </div>
      </div>
    </div>

    <!-- 平台发布状态 -->
    <div v-loading="loading" class="platform-list">
      <div
        v-for="(platformData, platformKey) in platformStats"
        :key="platformKey"
        class="platform-card"
      >
        <div class="platform-header">
          <div class="platform-info">
            <el-tag :color="PLATFORMS[platformKey]?.color" size="large">
              {{ PLATFORMS[platformKey]?.name || platformKey }}
            </el-tag>
            <div class="platform-stats">
              <span class="stat-item">
                <el-icon><CircleCheck /></el-icon>
                {{ platformData.completed }}/{{ platformData.total }}
              </span>
              <span v-if="platformData.failed > 0" class="stat-item error">
                <el-icon><CircleClose /></el-icon>
                {{ platformData.failed }}失败
              </span>
            </div>
          </div>
          <el-progress
            :percentage="getPlatformProgress(platformData)"
            :status="platformData.failed > 0 ? 'exception' : undefined"
            :stroke-width="8"
            style="width: 200px"
          />
        </div>

        <!-- 任务列表 -->
        <div class="task-list">
          <div
            v-for="task in platformData.tasks"
            :key="task.id"
            class="task-item"
            :class="`status-${task.status}`"
          >
            <div class="task-main">
              <div class="task-article">
                <el-icon><Document /></el-icon>
                <span>{{ task.articleTitle || '未知文章' }}</span>
              </div>
              <div class="task-account">
                <el-icon><User /></el-icon>
                <span>{{ task.accountName || '未知账号' }}</span>
              </div>
            </div>
            <div class="task-status">
              <el-tag v-if="task.status === 0" type="warning" size="small">
                <el-icon class="is-loading"><Loading /></el-icon>
                发布中
              </el-tag>
              <el-tag v-else-if="task.status === 1" type="success" size="small">
                <el-icon><CircleCheck /></el-icon>
                成功
              </el-tag>
              <el-tag v-else-if="task.status === 2" type="danger" size="small">
                <el-icon><CircleClose /></el-icon>
                失败
              </el-tag>
              <el-tag v-else type="info" size="small">
                <el-icon><Clock /></el-icon>
                等待中
              </el-tag>
            </div>
            <div class="task-actions">
              <el-button
                v-if="task.status === 2"
                size="small"
                @click="retryTask(task)"
              >
                重试
              </el-button>
              <el-button
                v-if="task.platformUrl"
                size="small"
                type="primary"
                @click="openUrl(task.platformUrl)"
              >
                查看
              </el-button>
            </div>
            <div v-if="task.errorMsg" class="task-error">
              {{ task.errorMsg }}
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="platformData.tasks.length === 0" class="empty-state">
            <el-empty description="暂无任务" :image-size="60" />
          </div>
        </div>
      </div>

      <!-- 全部空状态 -->
      <div v-if="Object.keys(platformStats).length === 0 && !loading" class="empty-state-full">
        <el-empty description="暂无发布任务">
          <el-button type="primary" @click="router.push('/auto-publish')">创建发布任务</el-button>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Refresh,
  List,
  CircleCheck,
  CircleClose,
  Loading,
  Clock,
  Document,
  User
} from '@element-plus/icons-vue'
import { autoPublishApi } from '@/services/api'
import { PLATFORMS } from '@/core/config/platform'
import { useWebSocket } from '@/composables/useWebSocket'

const router = useRouter()
const { connect, disconnect, onPublishProgress } = useWebSocket()

// 数据
const loading = ref(false)
const stats = ref({
  total: 0,
  completed: 0,
  running: 0,
  failed: 0
})
const platformStats = ref<Record<string, any>>({})

// 加载监控数据
const loadMonitorData = async () => {
  loading.value = true
  try {
    // 获取所有正在运行或最近完成的任务
    // 分别获取 pending 和 running 状态的任务再合并
    const [pendingRes, runningRes]: any[] = await Promise.all([
      autoPublishApi.getTasks({ status: 'pending', limit: 100 }),
      autoPublishApi.getTasks({ status: 'running', limit: 100 }),
    ])
    const tasks = pendingRes.data?.items || []
    const runningTasks = runningRes.data?.items || []

    // 获取已完成任务的记录
    const completedRes: any = await autoPublishApi.getTasks({
      status: ['completed', 'failed'],
      limit: 50
    })
    const completedTasks = completedRes.data?.items || []

    // 合并任务数据（pending + running + completed）
    const allTasks = [...tasks, ...runningTasks, ...completedTasks]

    // 按平台分组统计
    const platforms: Record<string, any> = {}
    let totalCount = 0
    let completedCount = 0
    let runningCount = 0
    let failedCount = 0

    allTasks.forEach((task: any) => {
      totalCount++

      // 获取任务的平台信息
      if (task.platform) {
        const platform = task.platform
        if (!platforms[platform]) {
          platforms[platform] = {
            total: 0,
            completed: 0,
            running: 0,
            failed: 0,
            tasks: []
          }
        }

        platforms[platform].total++

        if (task.status === 'completed') {
          platforms[platform].completed++
          completedCount++
        } else if (task.status === 'running') {
          platforms[platform].running++
          runningCount++
        } else if (task.status === 'failed') {
          platforms[platform].failed++
          failedCount++
        }

        // 获取任务的详细记录
        if (task.records && task.records.length > 0) {
          platforms[platform].tasks.push(...task.records.map((record: any) => ({
            ...record,
            taskId: task.id,
            taskName: task.name,
            platform: platform
          })))
        }
      }
    })

    platformStats.value = platforms
    stats.value = {
      total: totalCount,
      completed: completedCount,
      running: runningCount,
      failed: failedCount
    }
  } catch (e) {
    console.error('加载监控数据失败:', e)
  } finally {
    loading.value = false
  }
}

// 计算平台进度
const getPlatformProgress = (platformData: any) => {
  if (platformData.total === 0) return 0
  return Math.round((platformData.completed / platformData.total) * 100)
}

// 重试任务
const retryTask = async (task: any) => {
  try {
    await autoPublishApi.retry(task.taskId)
    ElMessage.success('任务已重新启动')
    await loadMonitorData()
  } catch (e) {
    console.error('重试任务失败:', e)
    ElMessage.error('重试失败')
  }
}

// 打开链接
const openUrl = (url: string) => {
  window.open(url, '_blank')
}

// WebSocket 监听
const setupWebSocket = () => {
  connect()
  onPublishProgress(() => {
    // 有进度更新时刷新数据
    loadMonitorData()
  })
}

onMounted(() => {
  loadMonitorData()
  setupWebSocket()
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped lang="scss">
.publish-monitor-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #1e1e1e);
  padding: 24px;
  gap: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h2 {
    margin: 0;
    color: var(--text-primary, #fff);
  }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-secondary, #2a2a2a);
  border-radius: 12px;

  .stat-icon {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
  }

  .stat-content {
    .stat-value {
      font-size: 24px;
      font-weight: 600;
      color: var(--text-primary, #fff);
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary, #6b7280);
      margin-top: 4px;
    }
  }
}

.platform-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.platform-card {
  background: var(--bg-secondary, #2a2a2a);
  border-radius: 12px;
  padding: 20px;
  border-left: 4px solid transparent;
  transition: all 0.3s;

  &:hover {
    background: var(--bg-tertiary, #3a3a3a);
  }
}

.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .platform-info {
    display: flex;
    align-items: center;
    gap: 16px;

    .platform-stats {
      display: flex;
      gap: 12px;

      .stat-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 14px;
        color: var(--text-secondary, #6b7280);

        &.error {
          color: #f56c6c;
        }
      }
    }
  }
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background: var(--bg-tertiary, #3a3a3a);
  border-radius: 8px;
  gap: 12px;

  &.status-1 {
    border-left: 3px solid #67c23a;
  }

  &.status-2 {
    border-left: 3px solid #f56c6c;
  }

  .task-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;

    .task-article,
    .task-account {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: var(--text-primary, #fff);
    }
  }

  .task-status {
    flex-shrink: 0;
  }

  .task-actions {
    flex-shrink: 0;
    display: flex;
    gap: 8px;
  }

  .task-error {
    width: 100%;
    padding: 8px;
    background: rgba(245, 108, 108, 0.1);
    border-radius: 4px;
    font-size: 12px;
    color: #f56c6c;
  }
}

.empty-state,
.empty-state-full {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.empty-state-full {
  flex: 1;
}
</style>
