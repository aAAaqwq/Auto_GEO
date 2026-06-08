<template>
  <div class="article-edit-page">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <el-button @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <div class="toolbar-center">
        <el-tag v-if="isEdit" type="info">{{ saving ? '保存中...' : (articleId ? '编辑模式' : '新建模式') }}</el-tag>
      </div>
      <div class="toolbar-right">
        <el-button @click="saveDraft" :loading="saving">
          <el-icon><FolderOpened /></el-icon>
          保存草稿
        </el-button>
        <el-button type="success" @click="showPublishDialog = true" :disabled="!canPublish">
          <el-icon><Promotion /></el-icon>
          发布到平台
        </el-button>
      </div>
    </div>

    <!-- 主编辑区 -->
    <div class="editor-layout">
      <div class="editor-main">
        <el-input
          v-model="article.title"
          placeholder="请输入文章标题"
          size="large"
          class="title-input"
        />

        <div class="editor-wrapper">
          <WangEditor
            v-model="article.content"
            height="100%"
            @change="handleContentChange"
          />
        </div>
      </div>

      <!-- 右侧发布面板 -->
      <aside class="publish-panel">
        <div class="panel-section">
          <h4>
            <el-icon><Connection /></el-icon>
            已连接平台账号
          </h4>
          <div v-if="loadingAccounts" class="panel-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            加载账号中...
          </div>
          <div v-else-if="availableAccounts.length === 0" class="panel-empty">
            <el-empty description="暂无可用账号" :image-size="48">
              <el-button size="small" @click="goToAccounts">去添加账号</el-button>
            </el-empty>
          </div>
          <div v-else class="account-list">
            <div
              v-for="acc in availableAccounts"
              :key="acc.id"
              class="account-item"
              :class="{ selected: selectedAccounts.includes(acc.id) }"
              @click="toggleAccount(acc.id)"
            >
              <div class="account-info">
                <el-tag
                  :color="getPlatformColor(acc.platform)"
                  size="small"
                  effect="dark"
                >
                  {{ getPlatformName(acc.platform) }}
                </el-tag>
                <span class="account-name">{{ acc.account_name || acc.username || '未命名' }}</span>
              </div>
              <div class="account-status">
                <span v-if="acc.status === 1" class="status-online" title="已授权">
                  <el-icon><CircleCheck /></el-icon>
                </span>
                <span v-else class="status-offline" title="待授权">
                  <el-icon><WarningFilled /></el-icon>
                </span>
                <el-checkbox
                  :model-value="selectedAccounts.includes(acc.id)"
                  @change="toggleAccount(acc.id)"
                  @click.stop
                />
              </div>
            </div>
          </div>
        </div>

        <div class="panel-section" v-if="selectedAccounts.length > 0">
          <div class="publish-summary">
            <p>
              将发布到
              <strong>{{ selectedAccounts.length }}</strong> 个平台账号
            </p>
          </div>
          <el-button
            type="primary"
            size="large"
            class="publish-btn"
            :loading="publishing"
            @click="publishToSelected"
          >
            <el-icon><Promotion /></el-icon>
            一键发布到平台
          </el-button>
        </div>

        <!-- 最近发布记录 -->
        <div class="panel-section" v-if="publishHistory.length > 0">
          <h4>最近发布记录</h4>
          <div class="history-list">
            <div v-for="record in publishHistory.slice(0, 5)" :key="record.id" class="history-item">
              <el-tag :type="record.status === 'success' ? 'success' : 'danger'" size="small">
                {{ record.status === 'success' ? '成功' : '失败' }}
              </el-tag>
              <span class="history-platform">{{ getPlatformName(record.platform) }}</span>
              <span class="history-time">{{ formatTime(record.created_at) }}</span>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 发布确认对话框 -->
    <el-dialog
      v-model="showPublishDialog"
      title="确认发布到平台"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="publish-dialog">
        <div class="dialog-article-info">
          <h5>文章信息</h5>
          <p><strong>标题：</strong>{{ article.title || '未设置标题' }}</p>
          <p><strong>内容长度：</strong>{{ article.content?.length || 0 }} 字</p>
        </div>

        <el-divider />

        <div class="dialog-accounts">
          <h5>目标平台账号（{{ selectedAccounts.length }} 个）</h5>
          <div class="selected-account-tags">
            <el-tag
              v-for="accId in selectedAccounts"
              :key="accId"
              closable
              @close="toggleAccount(accId)"
              size="large"
            >
              {{ getPlatformName(getAccountById(accId)?.platform) }}
              - {{ getAccountById(accId)?.account_name || '未知' }}
            </el-tag>
          </div>
          <p v-if="selectedAccounts.length === 0" class="no-selection">
            请先在右侧面板中选择目标平台账号
          </p>
        </div>

        <el-alert
          v-if="selectedAccounts.length > 0"
          title="系统将通过浏览器自动化登录平台并发布文章，可能需要几分钟时间。"
          type="info"
          :closable="false"
          show-icon
        />
      </div>

      <template #footer>
        <el-button @click="showPublishDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="publishing"
          :disabled="selectedAccounts.length === 0"
          @click="confirmPublish"
        >
          确认发布
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  FolderOpened,
  Promotion,
  Connection,
  Loading,
  CircleCheck,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useArticleStore } from '@/stores/modules/article'
import { accountApi, publishApi } from '@/services/api'
import { PLATFORMS } from '@/core/config/platform'
import WangEditor from '@/components/business/editor/WangEditor.vue'

const router = useRouter()
const route = useRoute()
const articleStore = useArticleStore()

// === 文章状态 ===
const articleId = ref<string>('')
const article = ref({ title: '', content: '', tags: '', category: '' })
const saving = ref(false)

const isEdit = computed(() => articleId.value && articleId.value !== 'add')
const canPublish = computed(() => article.value.title.trim() && article.value.content.trim())

// === 平台账号 ===
const availableAccounts = ref<any[]>([])
const selectedAccounts = ref<number[]>([])
const loadingAccounts = ref(false)

// === 发布状态 ===
const publishing = ref(false)
const showPublishDialog = ref(false)
const publishHistory = ref<any[]>([])

// === 初始化 ===
onMounted(async () => {
  const id = route.params.id as string
  articleId.value = id

  // 加载文章详情（编辑模式）
  if (id && id !== 'add') {
    const result = await articleStore.loadArticleDetail(Number(id))
    if (result.success && articleStore.currentArticle.id) {
      article.value = {
        title: articleStore.currentArticle.title || '',
        content: articleStore.currentArticle.content || '',
        tags: articleStore.currentArticle.tags || '',
        category: articleStore.currentArticle.category || '',
      }
    }
  }

  // 加载可用平台账号
  await loadAccounts()
})

// === 加载平台账号 ===
const loadAccounts = async () => {
  loadingAccounts.value = true
  try {
    const res: any = await accountApi.getList({ status: 1 })
    availableAccounts.value = Array.isArray(res) ? res : (res?.data || res?.items || [])
  } catch (e) {
    console.error('加载账号失败:', e)
  } finally {
    loadingAccounts.value = false
  }
}

// === 账号操作 ===
const toggleAccount = (accountId: number) => {
  const idx = selectedAccounts.value.indexOf(accountId)
  if (idx === -1) {
    selectedAccounts.value.push(accountId)
  } else {
    selectedAccounts.value.splice(idx, 1)
  }
}

const getAccountById = (accId: number) => {
  return availableAccounts.value.find((a: any) => a.id === accId)
}

const getPlatformName = (platform: string) => {
  return PLATFORMS[platform]?.name || platform
}

const getPlatformColor = (platform: string) => {
  return PLATFORMS[platform]?.color || '#666'
}

const goToAccounts = () => {
  router.push('/accounts')
}

// === 保存草稿 ===
const saveDraft = async () => {
  if (!article.value.title) {
    ElMessage.warning('请输入标题')
    return
  }
  saving.value = true
  try {
    const result = isEdit.value
      ? await articleStore.updateArticle(Number(articleId.value), { ...article.value, status: 0 })
      : await articleStore.createArticle({ ...article.value, status: 0 })

    if (result.success) {
      ElMessage.success(isEdit.value ? '草稿已更新' : '草稿已保存')
      if (!isEdit.value && result.data?.id) {
        articleId.value = String(result.data.id)
        router.replace(`/articles/edit/${result.data.id}`)
      }
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

// === 发布到平台 ===
const publishToSelected = () => {
  if (selectedAccounts.value.length === 0) {
    ElMessage.warning('请至少选择一个平台账号')
    return
  }
  showPublishDialog.value = true
}

const confirmPublish = async () => {
  if (!article.value.title || !article.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  if (selectedAccounts.value.length === 0) {
    ElMessage.warning('请选择目标平台账号')
    return
  }

  publishing.value = true
  try {
    // 1. 如果是新建文章，先保存
    let targetArticleId = Number(articleId.value)
    if (!isEdit.value || !targetArticleId) {
      const saveResult = await articleStore.createArticle({ ...article.value, status: 1 })
      if (!saveResult.success || !saveResult.data?.id) {
        ElMessage.error('保存文章失败，无法发布')
        return
      }
      targetArticleId = saveResult.data.id
      articleId.value = String(targetArticleId)
      router.replace(`/articles/edit/${targetArticleId}`)
    } else {
      // 编辑模式：先更新文章
      await articleStore.updateArticle(targetArticleId, { ...article.value, status: 1 })
    }

    // 2. 触发平台发布（使用 /publish/create 接口，不限制文章状态）
    const result = await publishApi.create({
      article_ids: [targetArticleId],
      account_ids: selectedAccounts.value,
    })

    if (result && (result as any).success !== false) {
      const taskId = (result as any).data?.task_id || (result as any).task_id
      ElMessage.success(`发布任务已启动！正在通过 ${selectedAccounts.value.length} 个平台账号发布文章`)
      showPublishDialog.value = false

      // 3. 跳转到监控页查看进度
      setTimeout(() => {
        router.push('/publish')
      }, 1500)
    } else {
      ElMessage.error((result as any)?.message || '发布失败，请重试')
    }
  } catch (e: any) {
    console.error('发布失败:', e)
    ElMessage.error(e?.response?.data?.detail || e.message || '发布失败，请检查网络连接')
  } finally {
    publishing.value = false
  }
}

// === 内容变更 ===
const handleContentChange = (value: string) => {
  article.value.content = value
}

// === 工具函数 ===
const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped lang="scss">
.article-edit-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
  flex-shrink: 0;

  .toolbar-center {
    display: flex;
    align-items: center;
  }

  .toolbar-right {
    display: flex;
    gap: 10px;
  }
}

.editor-layout {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 16px;

  .title-input {
    :deep(.el-input__wrapper) {
      background: transparent;
      border: none;
      border-bottom: 2px solid var(--border);
      border-radius: 0;
      padding: 12px 0;

      input {
        font-size: 24px;
        font-weight: 500;
      }
    }
  }

  .editor-wrapper {
    flex: 1;
    min-height: 0;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
}

// === 右侧发布面板 ===
.publish-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;

  .panel-section {
    background: var(--bg-secondary, #2a2a2a);
    border-radius: 12px;
    padding: 16px;

    h4 {
      margin: 0 0 12px 0;
      font-size: 14px;
      color: var(--text-secondary, #aaa);
      display: flex;
      align-items: center;
      gap: 6px;
    }
  }

  .panel-loading,
  .panel-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px 0;
    color: var(--text-secondary, #aaa);
    font-size: 13px;
    gap: 8px;
  }
}

.account-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.account-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1.5px solid transparent;
  background: var(--bg-tertiary, #3a3a3a);

  &:hover {
    background: var(--bg-hover, #444);
  }

  &.selected {
    border-color: var(--primary, #4a90e2);
    background: rgba(74, 144, 226, 0.08);
  }

  .account-info {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;

    .account-name {
      font-size: 13px;
      color: var(--text-primary, #fff);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .account-status {
    display: flex;
    align-items: center;
    gap: 6px;

    .status-online {
      color: #67c23a;
      font-size: 14px;
    }

    .status-offline {
      color: #e6a23c;
      font-size: 14px;
    }
  }
}

.publish-summary {
  text-align: center;
  margin-bottom: 12px;
  color: var(--text-secondary, #aaa);
  font-size: 14px;

  strong {
    color: var(--primary, #4a90e2);
    font-size: 16px;
  }
}

.publish-btn {
  width: 100%;
}

// 历史记录
.history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary, #aaa);

  .history-platform {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .history-time {
    color: var(--text-secondary, #666);
  }
}

// === 对话框样式 ===
.publish-dialog {
  .dialog-article-info {
    p {
      margin: 4px 0;
      font-size: 14px;
      color: var(--text-primary, #fff);
    }
    strong {
      color: var(--text-secondary, #aaa);
    }
  }

  .dialog-accounts {
    .selected-account-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }

    .no-selection {
      color: var(--text-secondary, #aaa);
      text-align: center;
      padding: 16px 0;
    }
  }
}
</style>
