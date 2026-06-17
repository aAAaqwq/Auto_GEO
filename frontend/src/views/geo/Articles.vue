<template>
  <div class="articles-page">
    <!-- ========== 页面头部 ========== -->
    <div class="page-hero">
      <div class="hero-content">
        <span class="hero-badge">Content Studio</span>
        <h1 class="hero-title">文章生成</h1>
        <p class="hero-desc">AI 驱动的多平台内容创作与分发引擎</p>
      </div>
      <div class="hero-stats">
        <div class="hero-stat">
          <span class="hero-stat-value">{{ articles.length }}</span>
          <span class="hero-stat-label">文章总数</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-value">{{ articles.filter(function(a) { return a.publish_status === 'published' }).length }}</span>
          <span class="hero-stat-label">已发布</span>
        </div>
      </div>
    </div>

    <!-- 选择区域 -->
    <div class="section">
      <h2 class="section-title">生成文章</h2>
      <el-form :inline="true" :model="generateForm" class="generate-form">
        <el-form-item label="选择项目">
          <el-select
            v-model="generateForm.projectId"
            placeholder="请选择项目"
            style="width: 180px"
            @change="onProjectChange"
          >
            <el-option
              v-for="project in validProjects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="选择关键词">
          <el-select
            v-model="generateForm.keywordId"
            placeholder="请选择关键词"
            style="width: 180px"
            :disabled="!generateForm.projectId"
          >
            <el-option
              v-for="keyword in keywords"
              :key="keyword.id"
              :label="keyword.keyword || keyword.name"
              :value="keyword.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="发布平台">
          <el-select
            v-model="generateForm.targetPlatforms"
            placeholder="请选择发布平台"
            multiple
            style="width: 220px"
            clearable
          >
            <el-option
              v-for="platform in PLATFORM_OPTIONS"
              :key="platform.value"
              :label="platform.label"
              :value="platform.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="发布策略">
          <el-radio-group v-model="generateForm.publishStrategy" size="small">
            <el-radio label="draft">仅生成草稿</el-radio>
            <el-radio label="immediate">生成后立即发布</el-radio>
            <el-radio label="scheduled">定时发布</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="generateForm.publishStrategy === 'scheduled'" label="发布时间">
          <el-date-picker
            v-model="generateForm.scheduledAt"
            type="datetime"
            placeholder="选择发布时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            :disabled-date="disabledDate"
            :disabled-hours="disabledHours"
            :disabled-minutes="disabledMinutes"
            style="width: 220px"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="generating"
            :disabled="!generateForm.keywordId"
            @click="generateArticle"
          >
            <el-icon><MagicStick /></el-icon>
            生成文章
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 文章列表 -->
    <div class="section section-list">
      <div class="section-header">
        <div class="header-left">
          <h2 class="section-title">文章列表</h2>
          <el-select
            v-model="filterProjectId"
            placeholder="全部项目"
            clearable
            style="width: 150px; margin-left: 16px;"
            size="small"
          >
            <el-option label="全部项目" :value="null" />
            <el-option
              v-for="p in validProjects"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>

          <el-select
            v-model="filterPublishStatus"
            placeholder="全部状态"
            clearable
            style="width: 140px; margin-left: 12px;"
            size="small"
          >
            <el-option label="全部状态" :value="null" />
            <el-option label="已生成/待分发" value="completed" />
            <el-option label="已配置定时" value="scheduled" />
            <el-option label="生成中" value="generating" />
            <el-option label="失败" value="failed" />
            <el-option label="发布中" value="publishing" />
            <el-option label="已发布" value="published" />
          </el-select>
        </div>
        <el-button @click="loadArticles" size="small" type="primary" plain>
          <el-icon><Refresh /></el-icon>
          刷新列表
        </el-button>
      </div>

      <el-table
        v-loading="articlesLoading"
        :data="filteredArticles"
        stripe
        style="width: 100%"
        height="500"
      >
        <el-table-column prop="title" label="标题" min-width="180">
          <template #default="{ row }">
            <div class="title-cell">
              <span class="title-text">{{ row.title || '（内容生成中...）' }}</span>
              <el-tag v-if="isGenerating(row)" type="warning" size="small" style="margin-left: 8px;">
                生成中
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="生成状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getGenerateStatusType(row.publish_status)" size="small">
              {{ getArticleStatusText(row) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="发布策略" width="120">
          <template #default="{ row }">
            <span class="text-muted" style="font-size: 12px;">
              {{ getStrategyDisplay(row) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="评分" width="70">
          <template #default="{ row }">
            <span v-if="row.quality_score" :class="getScoreClass(row.quality_score)">
              {{ row.quality_score }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            <span class="text-muted">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="previewArticle(row)">预览</el-button>
            <el-button
              type="success"
              size="small"
              link
              :disabled="isGenerating(row)"
              @click="handleCheckQuality(row)"
            >质检</el-button>
            <el-button
              v-if="isGenerated(row)"
              type="info"
              size="small"
              link
              :disabled="row.publish_status === 'publishing'"
              @click="openPublishDialog(row)"
            >去发布</el-button>
            <el-button type="danger" size="small" link @click="deleteArticle(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 文章预览对话框 -->
    <el-dialog
      v-model="showPreviewDialog"
      :title="currentArticle?.title || '文章预览'"
      width="800px"
      destroy-on-close
    >
      <div v-if="currentArticle" class="article-preview-scroll">
        <div class="markdown-body" v-html="renderMarkdown(currentArticle.content)"></div>
      </div>
    </el-dialog>

    <!-- 发布配置对话框 -->
    <el-dialog
      v-model="showPublishDialog"
      title="发布文章"
      width="560px"
      destroy-on-close
    >
      <div v-if="publishArticle" class="publish-summary">
        <div class="publish-title">{{ publishArticle.title || '未命名文章' }}</div>
        <div class="text-muted">选择发布账号后即可提交发布任务</div>
      </div>

      <el-form :model="publishForm" label-width="90px" class="publish-form">
        <el-form-item label="发布方式">
          <el-radio-group v-model="publishForm.mode">
            <el-radio label="immediate">立即发布</el-radio>
            <el-radio label="scheduled">定时发布</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="发布平台">
          <el-select
            v-model="publishForm.platform"
            placeholder="请选择平台"
            style="width: 100%"
            @change="onPublishPlatformChange"
          >
            <el-option
              v-for="platform in PLATFORM_OPTIONS"
              :key="platform.value"
              :label="platform.label"
              :value="platform.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="发布账号">
          <el-select
            v-model="publishForm.accountId"
            placeholder="请选择已授权账号"
            style="width: 100%"
            :loading="accountsLoading"
            :disabled="!publishForm.platform"
          >
            <el-option
              v-for="account in availablePublishAccounts"
              :key="account.id"
              :label="account.account_name || account.username || `账号 ${account.id}`"
              :value="account.id"
            >
              <div class="account-option">
                <span>{{ account.account_name || account.username || `账号 ${account.id}` }}</span>
                <el-tag size="small" type="success">可用</el-tag>
              </div>
            </el-option>
          </el-select>
          <div v-if="publishForm.platform && availablePublishAccounts.length === 0" class="form-tip">
            当前平台暂无可用账号，请先在账号管理中完成授权。
          </div>
        </el-form-item>

        <el-form-item v-if="publishForm.mode === 'scheduled'" label="发布时间">
          <el-date-picker
            v-model="publishForm.scheduledTime"
            type="datetime"
            placeholder="选择发布时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            :disabled-date="disabledDate"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showPublishDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingPublish" @click="submitPublish">
          {{ publishForm.mode === 'scheduled' ? '配置定时发布' : '立即发布' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Refresh } from '@element-plus/icons-vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { accountApi, geoKeywordApi, geoArticleApi, publishApi } from '@/services/api'
import { getEnabledPlatforms } from '@/core/config/platform'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: true, linkify: true })
const renderMarkdown = (content: string) => content ? md.render(content) : '暂无内容'

// 状态
const projects = ref<any[]>([])
const keywords = ref<any[]>([])
const articles = ref<any[]>([])
const articlesLoading = ref(false)
const generating = ref(false)
const showPreviewDialog = ref(false)
const showPublishDialog = ref(false)
const currentArticle = ref<any>(null)
const publishArticle = ref<any>(null)
const filterProjectId = ref<number | null>(null)
const filterPublishStatus = ref<string | null>(null)
const accounts = ref<any[]>([])
const accountsLoading = ref(false)
const submittingPublish = ref(false)

// 发布平台选项
const PLATFORM_OPTIONS = getEnabledPlatforms()
  .filter(platform => platform.features?.article)
  .map(platform => ({ label: platform.name, value: platform.id }))

const generateForm = ref({
  projectId: null as number | null,
  keywordId: null as number | null,
  targetPlatforms: [] as string[],
  publishStrategy: 'draft' as 'draft' | 'immediate' | 'scheduled',
  scheduledAt: '' as string
})

const publishForm = ref({
  mode: 'immediate' as 'immediate' | 'scheduled',
  platform: '',
  accountId: null as number | null,
  scheduledTime: ''
})

// 🌟 有效项目列表（过滤掉没有 id 的项目，防止 el-option 报错）
const validProjects = computed(() => {
  return (projects.value || []).filter(p => p?.id !== undefined && p?.id !== null)
})

// 过滤后的文章
const filteredArticles = computed(() => {
  let result = articles.value

  // 按项目过滤
  if (filterProjectId.value !== null) {
    result = result.filter(a => {
      const keyword = keywords.value.find(k => k.id === a.keyword_id)
      return keyword && keyword.project_id === filterProjectId.value
    })
  }

  // 按发布状态过滤
  if (filterPublishStatus.value !== null) {
    result = result.filter(a => a.publish_status === filterPublishStatus.value)
  }

  return result
})

const availablePublishAccounts = computed(() => {
  if (!publishForm.value.platform) return []
  return accounts.value.filter(account => {
    const status = Number(account.status)
    return account.platform === publishForm.value.platform && status === 1
  })
})

// 状态判断辅助函数
const isGenerating = (row: any) => row.publish_status === 'generating'
const hasGeneratedContent = (row: any) => {
  return !!row?.title && !!row?.content && !String(row.title).includes('创作中') && !String(row.content).includes('正在努力写作')
}
const isGenerated = (row: any) => {
  return ['completed', 'scheduled', 'published', 'publishing'].includes(row.publish_status) ||
    (row.publish_status === 'failed' && hasGeneratedContent(row))
}

// 数据加载
const loadProjects = async () => {
  try {
    const res: any = await geoKeywordApi.getProjects()
    projects.value = Array.isArray(res) ? res : (res?.data || [])
  } catch (error) { console.error(error) }
}

const onProjectChange = async () => {
  generateForm.value.keywordId = null
  keywords.value = []
  if (generateForm.value.projectId) {
    try {
      const res: any = await geoKeywordApi.getProjectKeywords(generateForm.value.projectId)
      keywords.value = Array.isArray(res) ? res : (res?.data || [])
    } catch (error) { console.error(error) }
  }
}

const loadArticles = async () => {
  articlesLoading.value = true
  try {
    const res: any = await geoArticleApi.getArticles()
    articles.value = Array.isArray(res) ? res : (res?.data || [])

    // 加载所有项目用于过滤
    if (projects.value.length === 0) {
      await loadProjects()
    }

    // 加载所有关键词用于过滤
    for (const article of articles.value) {
      const keyword = keywords.value.find(k => k.id === article.keyword_id)
      if (keyword && !keywords.value.find(k => k.id === keyword.id)) {
        keywords.value.push(keyword)
      }
    }
  } catch (error) {
    console.error('加载文章失败:', error)
  } finally {
    articlesLoading.value = false
  }
}

const normalizeListResponse = (res: any) => {
  if (Array.isArray(res)) return res
  if (Array.isArray(res?.data)) return res.data
  if (Array.isArray(res?.data?.items)) return res.data.items
  if (Array.isArray(res?.items)) return res.items
  return []
}

const loadAccounts = async () => {
  accountsLoading.value = true
  try {
    const res: any = await accountApi.getList({ status: 1 })
    accounts.value = normalizeListResponse(res)
  } catch (error) {
    console.error('加载账号失败:', error)
  } finally {
    accountsLoading.value = false
  }
}

// 操作
const generateArticle = async () => {
  if (!generateForm.value.keywordId) return
  const project = projects.value.find(p => p.id === generateForm.value.projectId)

  generating.value = true
  try {
    const res = await geoArticleApi.generate({
      keyword_id: generateForm.value.keywordId as number,
      company_name: project?.company_name || '默认公司',
      // 新增：发布策略相关参数
      target_platforms: generateForm.value.targetPlatforms,
      publish_strategy: generateForm.value.publishStrategy,
      scheduled_at: generateForm.value.publishStrategy === 'scheduled' ? generateForm.value.scheduledAt : undefined
    })
    if (res.success) {
      const strategyText = {
        draft: '仅生成草稿',
        immediate: '立即发布',
        scheduled: '定时发布'
      }
      ElMessage.success(`任务提交成功，策略：${strategyText[generateForm.value.publishStrategy]}`)
      // 立即刷新列表以显示 generating 状态
      await loadArticles()

      // 启动轮询等待生成完成
      pollArticleGeneration()
    }
  } finally { generating.value = false }
}

// 轮询文章生成状态
const pollArticleGeneration = async () => {
  let pollCount = 0
  const maxPolls = 30 // 最多轮询 5 分钟

  const poll = async () => {
    if (pollCount >= maxPolls) {
      console.log('轮询超时，停止')
      return
    }

    pollCount++
    await loadArticles()

    // 检查是否有刚刚生成的文章变为 completed 状态
    const updatedArticle = articles.value.find(a => a.keyword_id === generateForm.value.keywordId)
    if (updatedArticle && updatedArticle.publish_status === 'completed') {
      console.log('文章生成完成')
      ElMessage.success('文章生成完成')
      return
    }

    // 如果文章状态为 failed，也停止
    if (updatedArticle && updatedArticle.publish_status === 'failed') {
      const failedText = hasGeneratedContent(updatedArticle) ? '发布失败' : '文章生成失败'
      console.log(failedText)
      ElMessage.error(updatedArticle.error_msg || failedText)
      return
    }

    // 1 秒后继续轮询
    setTimeout(poll, 2000)
  }

  await poll()
}

const handleCheckQuality = async (row: any) => {
  try {
    const res = await geoArticleApi.checkQuality(row.id)
    if (res.success) {
      ElMessage.success('质检评分已更新')
      await loadArticles()
    }
  } catch (e) { console.error(e) }
}

const deleteArticle = async (article: any) => {
  try {
    await ElMessageBox.confirm('确定要删除吗？', '警告', { type: 'warning' })
    await geoArticleApi.delete(article.id)
    ElMessage.success('已删除')
    await loadArticles()
  } catch (error) { }
}

const previewArticle = (article: any) => {
  currentArticle.value = article
  showPreviewDialog.value = true
}

const getDefaultPlatform = (article: any) => {
  if (article.platform) return article.platform
  if (Array.isArray(article.target_platforms) && article.target_platforms.length > 0) {
    return article.target_platforms[0]
  }
  if (generateForm.value.targetPlatforms[0]) return generateForm.value.targetPlatforms[0]
  const firstAvailableAccount = accounts.value.find(account => Number(account.status) === 1)
  return firstAvailableAccount?.platform || PLATFORM_OPTIONS[0]?.value || ''
}

const openPublishDialog = async (article: any) => {
  publishArticle.value = article
  if (accounts.value.length === 0) {
    await loadAccounts()
  }
  publishForm.value = {
    mode: article.publish_status === 'scheduled' ? 'scheduled' : 'immediate',
    platform: getDefaultPlatform(article),
    accountId: article.account_id || null,
    scheduledTime: article.scheduled_at || ''
  }
  showPublishDialog.value = true
  onPublishPlatformChange()
}

const onPublishPlatformChange = () => {
  const hasSelectedAccount = availablePublishAccounts.value.some(account => account.id === publishForm.value.accountId)
  if (!hasSelectedAccount) {
    publishForm.value.accountId = availablePublishAccounts.value[0]?.id || null
  }
}

const submitPublish = async () => {
  if (!publishArticle.value) return
  if (!publishForm.value.platform) {
    ElMessage.warning('请选择发布平台')
    return
  }
  if (!publishForm.value.accountId) {
    ElMessage.warning('请选择发布账号')
    return
  }
  if (publishForm.value.mode === 'scheduled' && !publishForm.value.scheduledTime) {
    ElMessage.warning('请选择发布时间')
    return
  }

  const accountId = publishForm.value.accountId
  if (!accountId) return

  submittingPublish.value = true
  try {
    const payload = {
      article_ids: [publishArticle.value.id],
      account_ids: [accountId]
    }
    if (publishForm.value.mode === 'scheduled') {
      await publishApi.schedule({
        ...payload,
        scheduled_time: publishForm.value.scheduledTime
      })
      ElMessage.success('定时发布已配置')
    } else {
      await publishApi.start(payload)
      ElMessage.success('发布任务已启动')
    }
    showPublishDialog.value = false
    await loadArticles()
  } catch (error) {
    console.error('提交发布失败:', error)
  } finally {
    submittingPublish.value = false
  }
}

// 渲染工具
const getGenerateStatusType = (s: string) => {
  const statusMap: Record<string, string> = {
    generating: 'warning',     // 生成中
    completed: 'success',      // 已生成/待分发
    scheduled: 'primary',      // 已配置定时发布
    failed: 'danger',          // 生成失败
    publishing: 'primary',     // 发布中
    published: 'success',      // 已发布
    draft: 'info'             // 草稿
  }
  return statusMap[s] || 'info'
}

const isPublishFailure = (article: any) => {
  if (!article || article.publish_status !== 'failed') return false
  if (article.platform || article.account_id) return true
  const message = article.error_msg || ''
  return /发布|授权|Session|账号|频率|平台/.test(message)
}

const getArticleStatusText = (article: any) => {
  if (article?.publish_status === 'failed') {
    return isPublishFailure(article) ? '发布失败' : '生成失败'
  }
  return getGenerateStatusText(article?.publish_status)
}

const getGenerateStatusText = (s: string) => {
  const textMap = {
    generating: '生成中',
    completed: '已生成/待分发',
    scheduled: '已配置定时发布',
    failed: '失败',
    publishing: '发布中',
    published: '已发布',
    draft: '草稿'
  }
  return textMap[s] || s
}

const getScoreClass = (s: number) => s >= 80 ? 'text-success' : (s >= 60 ? 'text-warning' : 'text-danger')
const formatDate = (d?: string) => d ? new Date(d).toLocaleString() : '-'

// 日期选择器辅助方法 - 禁用过去日期
const disabledDate = (time: Date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return time.getTime() < today.getTime()
}

// 日期选择器辅助方法 - 禁用过去的小时
const disabledHours = (hour: number) => {
  const now = new Date()
  const selectedDate = generateForm.value.scheduledAt ? new Date(generateForm.value.scheduledAt) : now
  if (selectedDate.toDateString() === now.toDateString()) {
    return hour < now.getHours()
  }
  return []
}

// 日期选择器辅助方法 - 禁用过去的分钟
const disabledMinutes = (hour: number, minute: number) => {
  const now = new Date()
  const selectedDate = generateForm.value.scheduledAt ? new Date(generateForm.value.scheduledAt) : now
  if (selectedDate.toDateString() === now.toDateString() && hour === now.getHours()) {
    return minute < now.getMinutes()
  }
  return []
}

// 获取发布策略显示文本
const getStrategyDisplay = (article: any) => {
  if (!article.publish_strategy || article.publish_strategy === 'draft') {
    return '仅草稿'
  }
  if (article.publish_strategy === 'immediate') {
    return '立即发布'
  }
  if (article.publish_strategy === 'scheduled' && article.scheduled_at) {
    const date = new Date(article.scheduled_at)
    return `定时: ${date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`
  }
  return article.publish_strategy || '未知'
}

onMounted(() => {
  loadProjects()
  loadArticles()

  // 🌟 连接 WebSocket 监听发布进度
  const { connect, disconnect, onPublishProgress } = useWebSocket()
  connect()

  // 监听发布进度事件，实时更新文章状态
  onPublishProgress((message: any) => {
    const progressData = message?.data || message
    if (progressData.article_id && progressData.publish_status) {
      const articleIndex = articles.value.findIndex(a => a.id === progressData.article_id)
      if (articleIndex !== -1) {
        const oldStatus = articles.value[articleIndex].publish_status
        articles.value[articleIndex].publish_status = progressData.publish_status

        // 如果有 platform_url，也更新
        if (progressData.platform_url) {
          articles.value[articleIndex].platform_url = progressData.platform_url
        }

        // 如果有 error_msg，也更新
        if (progressData.error_msg) {
          articles.value[articleIndex].error_msg = progressData.error_msg
        }

        console.log(`[Articles] 文章状态已同步: article_id=${progressData.article_id}, ${oldStatus} -> ${progressData.publish_status}`)

        // 发布成功时显示提示
        if (progressData.status === 2 && oldStatus !== 'published') {
          const article = articles.value[articleIndex]
          ElMessage.success(`《${article.title?.substring(0, 20)}...》已成功发布`)
        }
      }
    }
  })

  // 保存 disconnect 函数用于清理
  ;(window as any).__wsDisconnect = disconnect
})

// 组件卸载时断开 WebSocket
onUnmounted(() => {
  if ((window as any).__wsDisconnect) {
    (window as any).__wsDisconnect()
    delete (window as any).__wsDisconnect
  }
})
</script>

<style scoped lang="scss">
/* ==============================================
   Articles Page — Warm Studio
   Uses global design tokens; overrides only
   where page-specific styling is needed.
   ============================================== */

.articles-page {
  padding: 24px 28px;
  min-height: 100%;
  background: transparent;
}

// ---------- Page Hero ----------
.page-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 28px 32px;
  margin-bottom: 24px;
  background:
    linear-gradient(135deg, rgba(212, 168, 83, 0.06) 0%, transparent 50%),
    var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
  position: relative;
  overflow: hidden;

  &::after {
    content: '';
    position: absolute;
    top: -60px;
    right: -40px;
    width: 280px;
    height: 280px;
    background: radial-gradient(circle, rgba(212, 168, 83, 0.10) 0%, transparent 70%);
    pointer-events: none;
  }
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--accent);
  padding: 4px 12px;
  background: var(--accent-soft);
  border: 1px solid rgba(212, 168, 83, 0.18);
  border-radius: 4px;
  margin-bottom: 10px;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--text-head);
  margin: 0 0 6px;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.hero-desc {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

.hero-stats {
  display: flex;
  gap: 32px;
  position: relative;
  z-index: 1;
}

.hero-stat {
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hero-stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-head);
  line-height: 1;
  font-family: var(--font-display);
}

.hero-stat-label {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

// ---------- Section Cards ----------
.section {
  background: var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
  padding: 24px 28px;
  margin-bottom: 20px;
  transition: border-color var(--duration-fast) var(--ease-out);

  &:hover {
    border-color: var(--border-soft);
  }

  &.section-list {
    padding-bottom: 20px;
  }
}

.section-title {
  color: var(--text-head);
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .section-title {
    margin-bottom: 0;
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

// ---------- Generate Form ----------
.generate-form {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: flex-end;

  :deep(.el-form-item) {
    margin-bottom: 0;
    margin-right: 8px;
  }

  :deep(.el-form-item__label) {
    color: var(--text-muted);
    font-weight: 500;
    font-size: 13px;
  }
}

// ---------- Typography ----------
.text-muted {
  color: var(--text-muted);
  font-size: 13px;
}

.text-success {
  color: var(--success);
  font-weight: 700;
}

.text-warning {
  color: var(--warning);
  font-weight: 700;
}

.text-danger {
  color: var(--danger);
  font-weight: 700;
}

// ---------- Title Cell ----------
.title-cell {
  display: flex;
  align-items: center;

  .title-text {
    flex: 1;
    color: var(--text-body);
    font-weight: 500;
  }
}

// ---------- Preview Scroll ----------
.article-preview-scroll {
  max-height: 70vh;
  overflow-y: auto;
  padding: 24px;
  background: #f5f0e7;
  color: #2d2418;
  border-radius: var(--radius-md);
  border: 1px solid rgba(180, 160, 130, 0.2);

  .markdown-body {
    line-height: 1.85;
    font-size: 15px;
    color: #2d2418;

    :deep(img) {
      max-width: 100%;
      border-radius: 8px;
      margin: 10px 0;
    }

    :deep(h1), :deep(h2), :deep(h3) {
      font-family: var(--font-display);
      color: #1a1208;
      margin-top: 1.4em;
      margin-bottom: 0.5em;
    }

    :deep(code) {
      background: #e8dfd0;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
      color: #5c3d1e;
    }

    :deep(pre) {
      background: #2d2418;
      color: #e6dccb;
      padding: 16px 20px;
      border-radius: var(--radius-md);
      overflow-x: auto;

      code {
        background: transparent;
        color: inherit;
      }
    }

    :deep(blockquote) {
      border-left: 3px solid var(--accent);
      padding-left: 16px;
      color: #6b5d48;
      margin: 14px 0;
    }

    :deep(a) {
      color: #b8861e;
      text-decoration: none;
      &:hover { text-decoration: underline; }
    }
  }
}

// ---------- Publish Dialog ----------
.publish-summary {
  padding: 16px 20px;
  margin-bottom: 20px;
  background: var(--surface-base);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
}

.publish-title {
  color: var(--text-head);
  font-weight: 600;
  font-size: 15px;
  line-height: 1.5;
  margin-bottom: 6px;
}

.publish-form {
  :deep(.el-form-item__label) {
    color: var(--text-muted);
    font-weight: 500;
  }
}

.account-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.form-tip {
  color: var(--warning);
  font-size: 12px;
  line-height: 1.5;
  margin-top: 6px;
}

// ==============================================
//   Element Plus Page-Level Overrides
//   (global overrides handle most; these are
//    Articles-page-specific refinements)
// ==============================================

// Table — page-specific refinements
:deep(.el-table) {
  .el-table__header-wrapper th {
    background: rgba(200, 185, 160, 0.04) !important;
    border-bottom: 1px solid var(--border-thin) !important;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 14px 0;
  }

  .el-table__body-wrapper td {
    border-bottom: 1px solid rgba(200, 185, 160, 0.04);
    padding: 14px 0;
    color: var(--text-body);
    font-size: 13px;
  }

  .el-table__row:hover td {
    background: rgba(212, 168, 83, 0.05) !important;
  }
}

// Tags — rounded pill style
:deep(.el-tag) {
  border-radius: 20px;
  font-weight: 500;
  letter-spacing: 0.02em;
  padding: 0 10px;
}

// Generate button — prominent gold
.generate-form :deep(.el-button--primary) {
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 10px 24px;
  transition: all var(--duration-normal) var(--ease-out);

  &:not(:disabled):hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(212, 168, 83, 0.32);
  }
}

// Refresh button
.section-header :deep(.el-button--primary.is-plain) {
  border-color: var(--border-soft);
  color: var(--text-muted);

  &:hover {
    border-color: var(--accent);
    color: var(--accent);
  }
}
</style>
