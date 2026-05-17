<template>
  <div class="knowledge-page">
    <!-- 头部 -->
    <header class="page-header">
      <div class="header-left">
        <div class="header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
          </svg>
        </div>
        <div class="header-text">
          <h1 class="page-title">知识库管理</h1>
          <p class="page-desc">RAGFlow 智能知识库，支持文档解析、存储与语义检索</p>
        </div>
      </div>
      <div class="header-actions">
        <!-- RAGFlow 状态指示 -->
        <div class="ragflow-status" :class="{ connected: ragflowConnected }">
          <span class="status-dot"></span>
          <span class="status-text">{{ ragflowConnected ? 'RAGFlow 已连接' : 'RAGFlow 未连接' }}</span>
        </div>

        <el-button type="primary" size="large" @click="createDataset">
          <svg viewBox="0 0 16 16" fill="currentColor" width="16">
            <path d="M8 4a.5.5 0 01.5.5v3h3a.5.5 0 010 1h-3v3a.5.5 0 01-1 0v-3h-3a.5.5 0 010-1h3v-3A.5.5 0 018 4z"/>
          </svg>
          新建知识库
        </el-button>
      </div>
    </header>

    <!-- RAGFlow 知识库 -->
    <section class="ragflow-section">
      <div class="section-header">
        <h2 class="section-title">知识库列表</h2>
        <div class="section-actions">
          <el-input
            v-model="datasetSearch"
            placeholder="搜索知识库..."
            style="width: 260px"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button @click="loadDatasets">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>

      <div v-loading="datasetsLoading" class="datasets-grid">
        <div
          v-for="dataset in filteredDatasets"
          :key="dataset.id"
          class="dataset-card"
          @click="viewDataset(dataset)"
        >
          <div class="dataset-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
            </svg>
          </div>
          <div class="dataset-info">
            <h3 class="dataset-name">{{ dataset.name }}</h3>
            <p class="dataset-desc">{{ dataset.description || '暂无描述' }}</p>
            <div class="dataset-stats">
              <span class="stat-badge">
                <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                  <path d="M4 1a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V2a1 1 0 00-1-1H4zm0 1h8v12H4V2z"/>
                </svg>
                {{ dataset.document_count }} 文档
              </span>
              <span class="stat-badge">
                <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                  <path d="M2 3h12v2H2V3zm2 4h8v2H4V7zm2 4h6v2H6v-2z"/>
                </svg>
                {{ dataset.chunk_count }} 块
              </span>
            </div>
          </div>
          <el-dropdown trigger="click" @click.stop>
            <span class="dataset-more">···</span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="openUploadDialog(dataset)">
                  <el-icon><Upload /></el-icon>
                  上传文档
                </el-dropdown-item>
                <el-dropdown-item @click="deleteDataset(dataset)">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <el-empty v-if="!datasetsLoading && filteredDatasets.length === 0" description="暂无知识库，点击右上角新建" />
      </div>
    </section>

    <!-- RAGFlow 文档抽屉 -->
    <el-drawer
      v-model="showDocDrawer"
      :title="`知识库: ${activeDataset?.name || ''}`"
      size="680px"
      :close-on-click-modal="false"
    >
      <div class="doc-header">
        <el-input
          v-model="docSearch"
          placeholder="搜索文档..."
          clearable
          style="width: 240px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="openUploadDialog(activeDataset!)">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>

      <div v-loading="docsLoading" class="doc-list">
        <div
          v-for="doc in filteredDocs"
          :key="doc.id"
          class="doc-item"
        >
          <div class="doc-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14,2 14,8 20,8"/>
            </svg>
          </div>
          <div class="doc-info">
            <h4 class="doc-name">{{ doc.name }}</h4>
            <div class="doc-meta">
              <el-tag :type="getDocStatusType(doc.run_status)" size="small">
                {{ getDocStatusLabel(doc.run_status) }}
              </el-tag>
              <span class="doc-size">{{ formatFileSize(doc.size) }}</span>
              <span class="doc-type">{{ doc.type.toUpperCase() }}</span>
            </div>
          </div>
          <el-dropdown trigger="click" @click.stop>
            <span class="doc-more">···</span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="previewDocument(doc)">
                  <el-icon><Document /></el-icon>
                  预览
                </el-dropdown-item>
                <el-dropdown-item @click="parseDocument(doc)">
                  <el-icon><Refresh /></el-icon>
                  重新解析
                </el-dropdown-item>
                <el-dropdown-item divided @click="deleteDocument(doc)">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <el-empty v-if="!docsLoading && filteredDocs.length === 0" description="暂无文档" />
      </div>
    </el-drawer>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传文档"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-upload
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :on-change="handleUploadChange"
        :file-list="uploadFiles"
        accept=".pdf,.doc,.docx,.txt,.md,.ppt,.pptx,.xls,.xlsx"
      >
        <div class="upload-content">
          <el-icon class="upload-icon"><Upload /></el-icon>
          <div class="upload-text">
            <span>将文件拖到此处，或</span>
            <em>点击上传</em>
          </div>
          <div class="upload-tip">支持 PDF、Word、Excel、PPT、TXT 等格式</div>
        </div>
      </el-upload>

      <el-checkbox v-model="autoParse" style="margin-top: 16px">
        上传后自动解析文档
      </el-checkbox>

      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 文档预览对话框 -->
    <el-dialog
      v-model="showPreview"
      :title="`预览: ${previewDoc?.name || ''}`"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="previewDoc" class="document-preview">
        <div class="preview-info">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="文件名">{{ previewDoc.name }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ previewDoc.type.toUpperCase() }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatFileSize(previewDoc.size) }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getDocStatusType(previewDoc.run_status)" size="small">
                {{ getDocStatusLabel(previewDoc.run_status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="分块方式">{{ previewDoc.chunk_method }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ previewDoc.created_at }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-if="previewDoc.run_status === 'DONE' || previewDoc.run_status === 'COMPLETE' || previewDoc.run_status === '3'" class="preview-chunks">
          <h4>文档块</h4>
          <el-empty description="预览功能开发中，可前往 RAGFlow 管理后台查看完整内容" />
        </div>
        <div v-else class="preview-not-ready">
          <el-alert type="info" :closable="false">
            文档正在处理中，请在解析完成后查看预览
          </el-alert>
        </div>
      </div>
      <template #footer>
        <el-button @click="showPreview = false">关闭</el-button>
        <el-button v-if="previewDoc?.run_status !== 'DONE' && previewDoc?.run_status !== 'COMPLETE' && previewDoc?.run_status !== '3'" type="primary" @click="parseDocument(previewDoc!)">
          重新解析
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Search, Upload, Refresh } from '@element-plus/icons-vue'
import { api } from '@/services/api'

// ==================== 类型 ====================
interface RAGFlowDataset {
  id: string
  name: string
  description?: string
  document_count: number
  chunk_count: number
  created_at: string
  updated_at: string
}

interface RAGFlowDocument {
  id: string
  name: string
  type: string
  size: number
  run_status: string
  chunk_method: string
  created_at: string
  updated_at: string
}

// ==================== 状态 ====================
const ragflowConnected = ref(false)
const datasetsLoading = ref(false)
const docsLoading = ref(false)
const uploadLoading = ref(false)

const datasets = ref<RAGFlowDataset[]>([])
const documents = ref<RAGFlowDocument[]>([])
const activeDataset = ref<RAGFlowDataset | null>(null)
const previewDoc = ref<RAGFlowDocument | null>(null)

const datasetSearch = ref('')
const docSearch = ref('')

const showDocDrawer = ref(false)
const showUploadDialog = ref(false)
const showPreview = ref(false)

const uploadFiles = ref<any[]>([])
const uploadDatasetId = ref('')
const autoParse = ref(true)

// ==================== 计算属性 ====================
const filteredDatasets = computed(() => {
  if (!datasetSearch.value) return datasets.value
  const kw = datasetSearch.value.toLowerCase()
  return datasets.value.filter(d =>
    d.name.toLowerCase().includes(kw) ||
    d.description?.toLowerCase().includes(kw)
  )
})

const filteredDocs = computed(() => {
  if (!docSearch.value) return documents.value
  const kw = docSearch.value.toLowerCase()
  return documents.value.filter(d => d.name.toLowerCase().includes(kw))
})

// ==================== 数据集操作 ====================
const loadRAGFlowStatus = async () => {
  try {
    const res = await api.knowledge.getRAGFlowStatus()
    if (res.success && res.data) {
      ragflowConnected.value = res.data.connected
    }
  } catch {
    ragflowConnected.value = false
  }
}

const loadDatasets = async () => {
  datasetsLoading.value = true
  try {
    const res = await api.knowledge.getRAGFlowDatasets({ page: 1, limit: 50 })
    if (res.success && res.data) {
      datasets.value = res.data.items || []
    }
  } catch {
    ElMessage.error('加载数据集失败')
  } finally {
    datasetsLoading.value = false
  }
}

const createDataset = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入知识库名称:', '创建知识库', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPlaceholder: '如：产品文档',
    })
    if (!value?.trim()) {
      ElMessage.warning('请输入名称')
      return
    }
    const res = await api.knowledge.createRAGFlowDataset({ name: value.trim() })
    if (res.success) {
      ElMessage.success('创建成功')
      await loadDatasets()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('创建失败')
    }
  }
}

const deleteDataset = async (dataset: RAGFlowDataset) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除知识库"${dataset.name}"吗？删除后无法恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const res = await api.knowledge.deleteRAGFlowDataset(dataset.id)
    if (res.success) {
      ElMessage.success('删除成功')
      await loadDatasets()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const viewDataset = async (dataset: RAGFlowDataset) => {
  activeDataset.value = dataset
  showDocDrawer.value = true
  await loadDocuments(dataset.id)
}

// ==================== 文档操作 ====================
const loadDocuments = async (datasetId: string) => {
  docsLoading.value = true
  try {
    const res = await api.knowledge.getRAGFlowDocuments(datasetId, { page: 1, limit: 100 })
    if (res.success && res.data) {
      documents.value = res.data.items || []
    }
  } catch {
    ElMessage.error('加载文档失败')
  } finally {
    docsLoading.value = false
  }
}

const deleteDocument = async (doc: RAGFlowDocument) => {
  if (!activeDataset.value) return
  try {
    await ElMessageBox.confirm(`确定要删除文档"${doc.name}"吗？`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    const res = await api.knowledge.deleteRAGFlowDocument(activeDataset.value.id, doc.id)
    if (res.success) {
      ElMessage.success('删除成功')
      await loadDocuments(activeDataset.value.id)
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const parseDocument = async (doc: RAGFlowDocument) => {
  if (!activeDataset.value) return
  try {
    await ElMessageBox.confirm(
      `确定要重新解析文档"${doc.name}"吗？这将重新分块文档内容。`,
      '确认解析',
      { type: 'warning', confirmButtonText: '解析', cancelButtonText: '取消' }
    )
    const res = await api.knowledge.parseRAGFlowDocument(activeDataset.value.id, doc.id)
    if (res.success) {
      ElMessage.success('解析任务已提交')
      await loadDocuments(activeDataset.value.id)
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('解析失败')
    }
  }
}

const previewDocument = (doc: RAGFlowDocument) => {
  previewDoc.value = doc
  showPreview.value = true
}

// ==================== 上传 ====================
const openUploadDialog = (dataset: RAGFlowDataset) => {
  uploadDatasetId.value = dataset.id
  uploadFiles.value = []
  showUploadDialog.value = true
}

const handleUploadChange = async (uploadOptions: any) => {
  const { file } = uploadOptions
  uploadLoading.value = true

  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    formData.append('title', file.name)

    await api.knowledge.uploadRAGFlowDocument(uploadDatasetId.value, formData)
    ElMessage.success(`文件 "${file.name}" 上传成功`)
    showUploadDialog.value = false

    // 刷新文档列表
    if (activeDataset.value && activeDataset.value.id === uploadDatasetId.value) {
      await loadDocuments(uploadDatasetId.value)
    }
    // 刷新数据集列表（更新文档计数）
    await loadDatasets()
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploadLoading.value = false
    uploadFiles.value = []
  }
}

// ==================== 工具函数 ====================
const getDocStatusLabel = (status: string): string => {
  const map: Record<string, string> = {
    'UNSTART': '等待中', '0': '等待中',
    'RUNNING': '解析中', '2': '解析中',
    'DONE': '已完成', '3': '已完成', 'COMPLETE': '已完成',
    'CANCEL': '已取消',
    'FAIL': '失败', '4': '失败',
  }
  return map[status] || '未知'
}

const getDocStatusType = (status: string): string => {
  const map: Record<string, string> = {
    'UNSTART': 'info', '0': 'info',
    'RUNNING': 'warning', '2': 'warning',
    'DONE': 'success', '3': 'success', 'COMPLETE': 'success',
    'CANCEL': 'info',
    'FAIL': 'danger', '4': 'danger',
  }
  return map[status] || 'info'
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadRAGFlowStatus()
  loadDatasets()
})
</script>

<style scoped lang="scss">
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
  padding: 24px;
  background: linear-gradient(135deg, #f8f9fc 0%, #f0f2f8 100%);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    .header-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;

      svg { width: 26px; height: 26px; }
    }

    .page-title {
      margin: 0 0 4px 0;
      font-size: 22px;
      font-weight: 600;
      color: #1a1f36;
    }

    .page-desc {
      margin: 0;
      font-size: 13px;
      color: #9ca3af;
    }
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
}

.ragflow-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #fef2f2;
  border-radius: 8px;
  font-size: 13px;
  color: #dc2626;

  &.connected {
    background: #f0fdf4;
    color: #16a34a;

    .status-dot { background: #16a34a; }
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #dc2626;
  }
}

.ragflow-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 16px;
  padding: 24px 28px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    .section-title {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: #1a1f36;
    }

    .section-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
  }
}

.datasets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.dataset-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: #f9fafb;
  border-radius: 14px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    border-color: #8b5cf6;
    box-shadow: 0 6px 20px rgba(139, 92, 246, 0.12);
    transform: translateY(-2px);
  }

  .dataset-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;

    svg { width: 24px; height: 24px; }
  }

  .dataset-info {
    flex: 1;
    min-width: 0;

    .dataset-name {
      margin: 0 0 6px 0;
      font-size: 16px;
      font-weight: 600;
      color: #1a1f36;
    }

    .dataset-desc {
      margin: 0 0 12px 0;
      font-size: 13px;
      color: #9ca3af;
      line-height: 1.4;
    }

    .dataset-stats {
      display: flex;
      gap: 12px;
    }
  }

  .dataset-more {
    font-size: 18px;
    color: #9ca3af;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;

    &:hover { background: #e5e7eb; color: #6b7280; }
  }
}

.stat-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: white;
  border-radius: 6px;
  font-size: 12px;
  color: #6b7280;

  svg { color: #9ca3af; }
}

// 文档抽屉
.doc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 12px;
  transition: all 0.2s;

  &:hover { background: #f3f4f6; }

  .doc-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6b7280;
    flex-shrink: 0;

    svg { width: 20px; height: 20px; }
  }

  .doc-info {
    flex: 1;
    min-width: 0;

    .doc-name {
      margin: 0 0 6px 0;
      font-size: 14px;
      font-weight: 500;
      color: #1a1f36;
    }

    .doc-meta {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .doc-size, .doc-type {
      font-size: 12px;
      color: #9ca3af;
    }
  }

  .doc-more {
    font-size: 18px;
    color: #9ca3af;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;

    &:hover { background: #d1d5db; color: #6b7280; }
  }
}

// 上传
.upload-area {
  :deep(.el-upload-dragger) {
    padding: 40px 20px;
    border-radius: 12px;
    border: 2px dashed #d1d5db;
    background: #f9fafb;

    &:hover { border-color: #8b5cf6; }
  }

  .upload-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;

    .upload-icon { font-size: 48px; color: #9ca3af; }

    .upload-text {
      font-size: 14px;
      color: #6b7280;

      em { color: #8b5cf6; font-style: normal; }
    }

    .upload-tip { font-size: 12px; color: #9ca3af; }
  }
}

// 文档预览
.document-preview {
  .preview-info { margin-bottom: 20px; }

  .preview-chunks {
    margin-top: 20px;

    h4 { margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: #1a1f36; }
  }

  .preview-not-ready { margin-top: 20px; }
}

// 滚动条
.datasets-grid::-webkit-scrollbar,
.doc-list::-webkit-scrollbar {
  width: 6px;
}

.datasets-grid::-webkit-scrollbar-track,
.doc-list::-webkit-scrollbar-track {
  background: transparent;
}

.datasets-grid::-webkit-scrollbar-thumb,
.doc-list::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;

  &:hover { background: #9ca3af; }
}
</style>
