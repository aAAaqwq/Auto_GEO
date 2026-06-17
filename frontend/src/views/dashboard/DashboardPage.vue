<template>
  <div class="dashboard-page">
    <section class="command-hero">
      <div class="hero-copy">
        <div class="hero-kicker">
          <span></span>
          AutoGeo Control Room
        </div>
        <h2>内容增长作战台</h2>
        <p>把客户、知识库、关键词、文章生成和发布任务收拢到同一张工作桌上，优先处理最影响增长的动作。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" @click="goTo('/geo/articles')">
          <el-icon><EditPen /></el-icon>
          生成文章
        </el-button>
        <el-button size="large" @click="goTo('/auto-publish')">
          <el-icon><List /></el-icon>
          发布任务
        </el-button>
      </div>
      <div class="hero-signal">
        <div class="signal-value">{{ stats.todayPublished }}</div>
        <div class="signal-label">今日发布</div>
      </div>
    </section>
    <!-- 系统状态概览 -->
    <div class="section">
      <h2 class="section-title">
        <el-icon><DataAnalysis /></el-icon>
        系统状态概览
      </h2>
      <div class="stats-grid">
        <div class="stat-card" @click="goTo('/clients')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)">
            <el-icon><UserFilled /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.clients }}</div>
            <div class="stat-label">客户总数</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/knowledge')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%)">
            <el-icon><Reading /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.knowledgeFiles }}</div>
            <div class="stat-label">知识库文件</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/geo/keywords')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)">
            <el-icon><MagicStick /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.keywords }}</div>
            <div class="stat-label">关键词数量</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/geo/articles')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)">
            <el-icon><Document /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.articles }}</div>
            <div class="stat-label">生成文章</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/accounts')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%)">
            <el-icon><User /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.accounts }}</div>
            <div class="stat-label">授权账号</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/auto-publish')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #30cfd0 0%, #330867 100%)">
            <el-icon><List /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.publishTasks }}</div>
            <div class="stat-label">发布任务</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/geo/monitor')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.indexed }}</div>
            <div class="stat-label">已收录</div>
          </div>
        </div>
        <div class="stat-card" @click="goTo('/data-report')">
          <div class="stat-icon" style="background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.todayPublished }}</div>
            <div class="stat-label">今日发布</div>
          </div>
        </div>
      </div>
    </div>

    <!-- GEO业务流程 -->
    <div class="section">
      <h2 class="section-title">
        <el-icon><Operation /></el-icon>
        GEO 业务流程
        <span class="section-subtitle">点击卡片跳转到对应功能</span>
      </h2>
      <div class="process-flow">
        <div
          v-for="(step, index) in processSteps"
          :key="step.path"
          class="process-step"
          :class="{ active: step.active }"
          @click="goTo(step.path)"
        >
          <div class="step-number">{{ index + 1 }}</div>
          <div class="step-icon">
            <el-icon>
              <component :is="step.icon" />
            </el-icon>
          </div>
          <div class="step-content">
            <div class="step-title">{{ step.title }}</div>
            <div class="step-desc">{{ step.desc }}</div>
          </div>
          <div class="step-arrow" v-if="index < processSteps.length - 1">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- 待办事项 & 快速操作 -->
    <div class="two-columns">
      <!-- 待办事项 -->
      <div class="section">
        <h2 class="section-title">
          <el-icon><Bell /></el-icon>
          待办事项
        </h2>
        <div class="todo-list">
          <div v-if="todos.length === 0" class="empty-todo">
            <el-icon><CircleCheck /></el-icon>
            <span>暂无待办事项</span>
          </div>
          <div v-else class="todo-item" v-for="todo in todos" :key="todo.id" @click="goTo(todo.path)">
            <div class="todo-icon" :class="`todo-${todo.type}`">
              <el-icon><component :is="todo.icon" /></el-icon>
            </div>
            <div class="todo-content">
              <div class="todo-title">{{ todo.title }}</div>
              <div class="todo-desc">{{ todo.desc }}</div>
            </div>
            <div class="todo-count">{{ todo.count }}</div>
          </div>
        </div>
      </div>

      <!-- 快速操作 -->
      <div class="section">
        <h2 class="section-title">
          <el-icon><Lightning /></el-icon>
          快速操作
        </h2>
        <div class="quick-actions">
          <el-button type="primary" size="large" @click="goTo('/clients')">
            <el-icon><Plus /></el-icon>
            新建客户
          </el-button>
          <el-button type="success" size="large" @click="goTo('/accounts/add')">
            <el-icon><User /></el-icon>
            添加账号
          </el-button>
          <el-button type="warning" size="large" @click="goTo('/geo/articles')">
            <el-icon><EditPen /></el-icon>
            生成文章
          </el-button>
          <el-button type="danger" size="large" @click="goTo('/publish')">
            <el-icon><Monitor /></el-icon>
            平台发布监控
          </el-button>
        </div>
      </div>
    </div>

    <!-- 最近活动 -->
    <div class="section">
      <h2 class="section-title">
        <el-icon><Clock /></el-icon>
        最近活动
      </h2>
      <el-table :data="recentActivities" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getActivityTypeColor(row.type)">{{ row.typeText }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="platform" label="平台" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.platform" :color="getPlatformColor(row.platform)" effect="dark">
              {{ getPlatformName(row.platform) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.statusText }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="时间" width="180" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  DataAnalysis, UserFilled, Reading, MagicStick, Document, User, List,
  Monitor, TrendCharts, Operation, ArrowRight, Bell, CircleCheck,
  Lightning, Plus, EditPen, Promotion, Clock, House, Platform,
  Key, FolderOpened, Timer, Setting
} from '@element-plus/icons-vue'
import { clientApi, knowledgeApi, reportsApi, accountApi, autoPublishApi } from '@/services/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)

// 系统统计数据
const stats = ref({
  clients: 0,
  knowledgeFiles: 0,
  keywords: 0,
  articles: 0,
  accounts: 0,
  publishTasks: 0,
  indexed: 0,
  todayPublished: 0
})

// GEO业务流程步骤
const processSteps = ref([
  { title: '客户管理', desc: '创建和管理客户', icon: 'UserFilled', path: '/clients', active: true },
  { title: '知识库管理', desc: '上传和管理知识文档', icon: 'Reading', path: '/knowledge', active: true },
  { title: '智能建站', desc: '配置和生成站点', icon: 'Platform', path: '/site-builder', active: true },
  { title: '关键词蒸馏', desc: 'AI提取优质关键词', icon: 'MagicStick', path: '/geo/keywords', active: true },
  { title: '文章生成', desc: 'AI生成GEO文章', icon: 'EditPen', path: '/geo/articles', active: true },
  { title: '文章管理', desc: '管理和编辑文章', icon: 'Document', path: '/articles', active: true },
  { title: '账号管理', desc: '管理发布账号', icon: 'User', path: '/accounts', active: true },
  { title: '发布任务', desc: '创建和管理发布任务', icon: 'List', path: '/auto-publish', active: true },
  { title: '平台发布监控', desc: '实时监控发布进度', icon: 'Monitor', path: '/publish', active: true },
  { title: '收录监控', desc: '监控文章收录情况', icon: 'DataAnalysis', path: '/geo/monitor', active: true },
  { title: '数据报表', desc: '查看数据分析', icon: 'TrendCharts', path: '/data-report', active: true },
  { title: '定时任务', desc: '配置定时任务', icon: 'Timer', path: '/scheduler', active: true },
  { title: '系统设置', desc: '系统参数配置', icon: 'Setting', path: '/settings', active: true }
])

// 待办事项
const todos = ref<any[]>([])

// 最近活动
const recentActivities = ref([
  {
    type: 'publish',
    typeText: '发布',
    title: '示例文章已发布到知乎',
    platform: 'zhihu',
    status: 'success',
    statusText: '成功',
    time: '2025-01-08 12:00'
  }
])

// 加载系统统计数据
const loadStats = async () => {
  try {
    const results = await Promise.allSettled([
      clientApi.getStats(),
      knowledgeApi.getCategories({ limit: 100 }),
      reportsApi.getOverview(),
      reportsApi.getArticleStats(),
      accountApi.getList({ limit: 1 }),
      autoPublishApi.getTasks({ limit: 1 }),
      reportsApi.getStats({ days: 1 }),
    ])

    const [clientRes, knowledgeRes, overviewRes, articleRes, accountRes, taskRes, todayRes] = results

    if (clientRes.status === 'fulfilled') {
      stats.value.clients = clientRes.value.data?.total || 0
    }

    if (knowledgeRes.status === 'fulfilled') {
      const items = knowledgeRes.value.items || []
      stats.value.knowledgeFiles = items.reduce((sum: number, cat: any) => sum + (cat.knowledge_count || 0), 0)
    }

    if (overviewRes.status === 'fulfilled') {
      stats.value.keywords = overviewRes.value.total_keywords || 0
      stats.value.indexed = overviewRes.value.keyword_found || 0
    }

    if (articleRes.status === 'fulfilled') {
      stats.value.articles = articleRes.value.total || 0
    }

    if (accountRes.status === 'fulfilled') {
      stats.value.accounts = accountRes.value.total || 0
    }

    if (taskRes.status === 'fulfilled') {
      stats.value.publishTasks = taskRes.value.data?.total || 0
    }

    if (todayRes.status === 'fulfilled') {
      stats.value.todayPublished = todayRes.value.publish_success_count || 0
    }
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

// 加载待办事项
const loadTodos = async () => {
  // 这里可以从后端API获取实际的待办事项
  todos.value = [
    {
      id: 1,
      type: 'warning',
      icon: 'Document',
      title: '待发布文章',
      desc: '有文章等待发布',
      count: 5,
      path: '/articles'
    },
    {
      id: 2,
      type: 'danger',
      icon: 'User',
      title: '账号待授权',
      desc: '有账号需要重新授权',
      count: 2,
      path: '/accounts'
    }
  ]
}

// 页面跳转
const goTo = (path: string) => {
  router.push(path)
}

// 工具方法
const getActivityTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    publish: 'success',
    generate: 'warning',
    auth: 'danger'
  }
  return colors[type] || 'info'
}

const getPlatformColor = (platform: string) => {
  const colors: Record<string, string> = {
    zhihu: '#0084FF',
    baijiahao: '#E53935',
    sohu: '#FF6B00',
    toutiao: '#333333'
  }
  return colors[platform] || '#666'
}

const getPlatformName = (platform: string) => {
  const names: Record<string, string> = {
    zhihu: '知乎',
    baijiahao: '百家号',
    sohu: '搜狐号',
    toutiao: '头条号'
  }
  return names[platform] || platform
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    success: 'success',
    pending: 'warning',
    failed: 'danger'
  }
  return types[status] || 'info'
}

onMounted(() => {
  loadStats()
  loadTodos()
})
</script>

<style scoped lang="scss">
/* ================================================================
   Dashboard — Unified Dark Theme
   ================================================================ */

.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
  animation: dashboardIn 360ms var(--ease-out);
}

.command-hero {
  min-height: 178px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 160px;
  align-items: center;
  gap: 24px;
  padding: 28px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at 84% 18%, rgba(255, 200, 87, 0.22), transparent 24%),
    radial-gradient(circle at 16% 12%, rgba(98, 168, 255, 0.22), transparent 28%),
    linear-gradient(115deg, rgba(68, 210, 190, 0.24), transparent 42%),
    repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.045) 0 1px, transparent 1px 16px),
    var(--surface-raised);
  box-shadow:
    var(--shadow-md),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  overflow: hidden;
  position: relative;

  &::after {
    content: '';
    position: absolute;
    inset: auto 28px 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent-hover), var(--accent-amber), transparent);
    opacity: 0.82;
  }

  .hero-copy {
    min-width: 0;
  }

  .hero-kicker {
    display: flex;
    align-items: center;
    gap: 9px;
    color: var(--accent-hover);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0;
    text-transform: uppercase;

    span {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 16px var(--accent-glow);
    }
  }

  h2 {
    margin: 10px 0 8px;
    color: var(--text-head);
    font-family: var(--font-display);
    font-size: 34px;
    line-height: 1.18;
    font-weight: 800;
  }

  p {
    max-width: 690px;
    color: #b9c9d8;
    font-size: 14px;
    line-height: 1.75;
  }

  .hero-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .hero-signal {
    min-height: 112px;
    border-left: 1px solid rgba(202, 230, 255, 0.16);
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding-left: 26px;
  }

  .signal-value {
    color: #ffffff;
    font-family: var(--font-display);
    font-size: 48px;
    line-height: 1;
  }

  .signal-label {
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 12px;
  }

  @media (max-width: 1180px) {
    grid-template-columns: 1fr;

    .hero-actions {
      justify-content: flex-start;
    }

    .hero-signal {
      min-height: auto;
      border-left: 0;
      border-top: 1px solid var(--border-soft);
      padding: 16px 0 0;
    }
  }
}

// ---- Section Cards ----
.section {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.055), transparent 130px),
    var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
  padding: 22px;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.18);
  transition: border-color var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out);

  &:hover {
    border-color: var(--border-soft);
    transform: translateY(-1px);
  }

  .section-title {
    margin: 0 0 18px 0;
    font-family: var(--font-display);
    font-size: 17px;
    font-weight: 600;
    color: var(--text-head);
    display: flex;
    align-items: center;
    gap: 8px;

    .section-subtitle {
      font-size: 12px;
      font-weight: 400;
      color: var(--text-muted);
      margin-left: 6px;
    }
  }
}

// ---- Stats Grid ----
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;

  @media (max-width: 1400px) { grid-template-columns: repeat(3, 1fr); }
  @media (max-width: 1024px) { grid-template-columns: repeat(2, 1fr); }

  .stat-card {
    min-height: 112px;
    background:
      radial-gradient(circle at 12% 0%, rgba(255, 255, 255, 0.10), transparent 34%),
      linear-gradient(135deg, rgba(255, 255, 255, 0.055), transparent),
      var(--surface-field);
    border: 1px solid var(--border-thin);
    border-radius: var(--radius-md);
    padding: 18px;
    display: flex;
    align-items: center;
    gap: 16px;
    cursor: pointer;
    transition: all var(--duration-normal) var(--ease-out);

    &:hover {
      transform: translateY(-2px);
      border-color: var(--border-accent);
      box-shadow:
        0 14px 30px rgba(0, 0, 0, 0.28),
        0 0 0 1px rgba(255, 255, 255, 0.03);
    }

    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      color: white;
      flex-shrink: 0;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
    }

    &:nth-child(3n + 1) .stat-icon {
      background: linear-gradient(135deg, var(--accent-hover), #1aa898) !important;
    }

    &:nth-child(3n + 2) .stat-icon {
      background: linear-gradient(135deg, var(--accent-amber), #e48f2f) !important;
    }

    &:nth-child(3n) .stat-icon {
      background: linear-gradient(135deg, #8ab7ff, #446ee7) !important;
    }

    &:nth-child(4n) .stat-icon {
      background: linear-gradient(135deg, var(--accent-lime), #25b97a) !important;
    }

    .stat-content {
      flex: 1;
      min-width: 0;

      .stat-value {
        font-size: 26px;
        font-weight: 700;
        color: var(--text-head);
        line-height: 1.15;
        font-family: var(--font-display);
      }

      .stat-label {
        font-size: 12px;
        color: var(--text-muted);
        margin-top: 3px;
      }
    }
  }
}

// ---- Process Flow ----
.process-flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  gap: 10px;

  .process-step {
    min-width: 0;
    max-width: none;
    background:
      linear-gradient(180deg, rgba(68, 210, 190, 0.09), transparent),
      var(--surface-field);
    border: 1px solid var(--border-thin);
    border-radius: var(--radius-md);
    padding: 16px 12px 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: all var(--duration-normal) var(--ease-out);
    position: relative;

    &:hover {
      transform: translateY(-3px);
      border-color: var(--accent);
      box-shadow: 0 12px 26px rgba(68, 210, 190, 0.15);
    }

    .step-number {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--accent);
      color: var(--accent-ink);
      font-size: 11px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .step-icon {
      width: 44px;
      height: 44px;
      border-radius: var(--radius-md);
      background:
        radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.24), transparent 34%),
        var(--accent-soft);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      color: var(--accent);
    }

    .step-content {
      text-align: center;

      .step-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-head);
        margin-bottom: 3px;
      }

      .step-desc {
        font-size: 11px;
        color: var(--text-muted);
        line-height: 1.4;
      }
    }

    .step-arrow {
      display: none;
    }
  }
}

// ---- Two Columns ----
.two-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;

  @media (max-width: 768px) { grid-template-columns: 1fr; }
}

// ---- Todo List ----
.todo-list {
  .empty-todo {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 40px 20px;
    color: var(--text-muted);

    .el-icon { font-size: 48px; color: var(--success); }
  }

  .todo-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    border-radius: var(--radius-sm);
    background: var(--surface-field);
    cursor: pointer;
    transition: all var(--duration-fast) var(--ease-out);
    margin-bottom: 8px;

    &:hover { background: var(--accent-soft); }

    .todo-icon {
      width: 38px;
      height: 38px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 17px;

      &.todo-warning { background: var(--warning-soft); color: var(--warning); }
      &.todo-danger { background: var(--danger-soft); color: var(--danger); }
    }

    .todo-content {
      flex: 1;
      .todo-title { font-size: 13px; font-weight: 500; color: var(--text-head); }
      .todo-desc { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
    }

    .todo-count {
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: var(--accent);
      color: white;
      font-size: 11px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
}

// ---- Quick Actions ----
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;

  .el-button {
    width: 100%;
    justify-content: flex-start;
    padding: 14px 18px;
    border-radius: var(--radius-sm);
    min-height: 46px;
    background:
      linear-gradient(135deg, rgba(255, 255, 255, 0.055), transparent),
      var(--surface-field);

    .el-icon { font-size: 17px; }
  }
}

@keyframes dashboardIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
