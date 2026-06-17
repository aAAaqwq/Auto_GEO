<template>
  <div class="client-page">
    <!-- 顶部统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card">
        <div class="stat-icon" style="background: #6366f1">
          <el-icon><OfficeBuilding /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">总客户</div>
          <div class="stat-value">{{ stats.total }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #22c55e">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">活跃客户</div>
          <div class="stat-value">{{ stats.active }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #f59e0b">
          <el-icon><Warning /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">停用客户</div>
          <div class="stat-value">{{ stats.inactive }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #8b5cf6">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">行业数</div>
          <div class="stat-value">{{ Object.keys(stats.industry_distribution || {}).length }}</div>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索客户名称或公司"
          clearable
          style="width: 200px"
          @change="loadClients"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 120px" @change="loadClients">
          <el-option label="全部" :value="null" />
          <el-option label="活跃" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>

        <el-select v-model="filterIndustry" placeholder="行业" clearable style="width: 150px" @change="loadClients">
          <el-option label="全部" :value="null" />
          <el-option v-for="ind in industries" :key="ind" :label="ind" :value="ind" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建客户
        </el-button>
      </div>
    </div>

    <!-- 客户表格 -->
    <div class="table-container">
      <el-table
        :data="clients"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="客户名称" min-width="150" />
        <el-table-column prop="company_name" label="公司名称" min-width="150" />
        <el-table-column prop="contact_person" label="联系人" width="120" />
        <el-table-column prop="phone" label="电话" width="140" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="industry" label="行业" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.industry" size="small">{{ row.industry }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="project_count" label="项目数" width="80" align="center">
          <template #default="{ row }">
            <el-badge :value="row.project_count || 0" type="primary" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click="viewProjects(row)"
            >
              查看项目
            </el-button>
            <el-button
              type="success"
              size="small"
              @click="uploadKnowledge(row)"
            >
              <el-icon><Upload /></el-icon>
              上传资料
            </el-button>
            <el-dropdown @command="(cmd) => handleCommand(cmd, row)">
              <el-button size="small">
                更多<el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="delete" style="color: #f56c6c">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadClients"
          @current-change="loadClients"
        />
      </div>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑客户' : '新建客户'"
      width="600px"
    >
      <el-form :model="clientForm" label-width="100px">
        <el-form-item label="客户名称" required>
          <el-input v-model="clientForm.name" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="公司名称">
          <el-input v-model="clientForm.company_name" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="clientForm.contact_person" placeholder="请输入联系人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="clientForm.phone" placeholder="请输入联系电话" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="clientForm.email" placeholder="请输入邮箱地址" />
        </el-form-item>
        <el-form-item label="所属行业">
          <el-select v-model="clientForm.industry" placeholder="请选择行业" style="width: 100%">
            <el-option label="互联网" value="互联网" />
            <el-option label="金融" value="金融" />
            <el-option label="教育" value="教育" />
            <el-option label="医疗" value="医疗" />
            <el-option label="制造业" value="制造业" />
            <el-option label="零售" value="零售" />
            <el-option label="房地产" value="房地产" />
            <el-option label="物流" value="物流" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="clientForm.address" placeholder="请输入地址" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="clientForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入客户描述或备注"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="clientForm.status">
            <el-radio :value="1">活跃</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveClient">确定</el-button>
      </template>
    </el-dialog>

    <!-- 项目列表对话框 -->
    <el-dialog
      v-model="projectsDialogVisible"
      title="客户项目"
      width="900px"
    >
      <div class="projects-header">
        <h4>{{ currentClient?.name }} 的项目列表</h4>
        <el-button type="primary" size="small" @click="showProjectForm(null)">
          <el-icon><Plus /></el-icon>
          新建项目
        </el-button>
      </div>
      <el-table :data="clientProjects" v-loading="loadingProjects" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="项目名称" min-width="120" />
        <el-table-column prop="company_name" label="公司名称" min-width="120" />
        <el-table-column prop="domain_keyword" label="领域关键词" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="showProjectForm(row)">编辑</el-button>
            <el-button type="danger" size="small" link @click="deleteProjectItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loadingProjects && clientProjects.length === 0" description="暂无项目" />
    </el-dialog>

    <!-- 项目新建/编辑对话框 -->
    <el-dialog
      v-model="projectFormVisible"
      :title="editingProject ? '编辑项目' : '新建项目'"
      width="520px"
      append-to-body
    >
      <el-form :model="projectForm" label-width="100px">
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="公司名称" required>
          <el-input v-model="projectForm.company_name" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="领域关键词" required>
          <el-input v-model="projectForm.domain_keyword" placeholder="用于AI蒸馏生成用户提问句" />
        </el-form-item>
        <el-form-item label="所属行业">
          <el-select v-model="projectForm.industry" placeholder="选择行业" allow-create filterable style="width: 100%">
            <el-option v-for="ind in projectIndustries" :key="ind" :label="ind" :value="ind" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="projectForm.description" type="textarea" :rows="3" placeholder="简要描述项目（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="projectFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingProject" @click="saveProjectItem">
          {{ editingProject ? '保存修改' : '创建项目' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 知识库上传对话框 -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传资料到知识库"
      width="600px"
    >
      <div class="upload-content">
        <el-alert
          title="资料上传说明"
          type="info"
          :closable="false"
          style="margin-bottom: 16px"
        >
          <p>支持的文件格式：PDF、Word、TXT、Markdown</p>
          <p>单个文件大小限制：10MB</p>
        </el-alert>

        <el-form :model="uploadForm" label-width="100px">
          <el-form-item label="客户名称">
            <el-input :value="currentClient?.name" disabled />
          </el-form-item>
          <el-form-item label="资料分类">
            <el-select v-model="uploadForm.category" placeholder="选择分类" style="width: 100%">
              <el-option label="公司资料" value="company" />
              <el-option label="产品文档" value="product" />
              <el-option label="行业报告" value="industry" />
              <el-option label="技术文档" value="technical" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="文件上传">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="5"
              :on-change="handleFileChange"
              :on-exceed="handleExceed"
              :file-list="fileList"
              drag
              multiple
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                将文件拖到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持扩展名：.pdf .doc .docx .txt .md
                </div>
              </template>
            </el-upload>
          </el-form-item>
          <el-form-item label="备注说明">
            <el-input
              v-model="uploadForm.description"
              type="textarea"
              :rows="3"
              placeholder="请输入资料备注说明（可选）"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="confirmUpload">
          <el-icon><Upload /></el-icon>
          确认上传
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  OfficeBuilding, CircleCheck, Warning, TrendCharts, Search, Plus,
  Upload, ArrowDown, UploadFilled
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadInstance, UploadUserFile } from 'element-plus'
import { clientApi, geoKeywordApi } from '@/services/api'

// 状态
const loading = ref(false)
const loadingProjects = ref(false)
const clients = ref<any[]>([])
const clientProjects = ref<any[]>([])
const industries = ref<string[]>([])

// 筛选
const searchKeyword = ref('')
const filterStatus = ref<number | null>(null)
const filterIndustry = ref<string | null>(null)

// 分页
const pagination = ref({
  page: 1,
  limit: 20,
  total: 0
})

// 统计
const stats = ref({
  total: 0,
  active: 0,
  inactive: 0,
  industry_distribution: {}
})

// 对话框
const dialogVisible = ref(false)
const projectsDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const isEdit = ref(false)
const currentClient = ref<any>(null)

// 知识库上传
const uploadRef = ref<UploadInstance>()
const uploading = ref(false)
const fileList = ref<UploadUserFile[]>([])
const uploadForm = ref({
  category: '',
  description: ''
})
const clientForm = ref({
  id: null as number | null,
  name: '',
  company_name: '',
  contact_person: '',
  phone: '',
  email: '',
  industry: '',
  address: '',
  description: '',
  status: 1
})

// 项目管理
const projectFormVisible = ref(false)
const editingProject = ref<any>(null)
const savingProject = ref(false)
const projectForm = ref({
  name: '',
  company_name: '',
  domain_keyword: '',
  industry: '',
  description: '',
})
const projectIndustries = [
  'SaaS软件', '环保工程', '工业清洗', '无人机服务', '电商',
  '教育培训', '金融服务', '医疗健康', '制造业', '房地产',
  '餐饮美食', '旅游出行', '物流运输', '新能源', '化工行业',
  '建筑工程', '其他',
]

// 加载客户列表
const loadClients = async () => {
  loading.value = true
  try {
    const data = await clientApi.getList({
      page: pagination.value.page,
      limit: pagination.value.limit,
      status: filterStatus.value ?? undefined,
      keyword: searchKeyword.value || undefined,
      industry: filterIndustry.value || undefined
    })

    clients.value = data.items || []
    pagination.value.total = data.total || 0
  } catch (e: any) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// 加载统计数据
const loadStats = async () => {
  try {
    const data = await clientApi.getStats()
    stats.value = data.data || { total: 0, active: 0, inactive: 0, industry_distribution: {} }
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

// 加载行业列表
const loadIndustries = async () => {
  try {
    const data = await clientApi.getIndustries()
    industries.value = data.data || []
  } catch (e) {
    console.error('加载行业列表失败', e)
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  isEdit.value = false
  clientForm.value = {
    id: null,
    name: '',
    company_name: '',
    contact_person: '',
    phone: '',
    email: '',
    industry: '',
    address: '',
    description: '',
    status: 1
  }
  dialogVisible.value = true
}

// 编辑客户
const editClient = (client: any) => {
  isEdit.value = true
  clientForm.value = {
    id: client.id,
    name: client.name,
    company_name: client.company_name || '',
    contact_person: client.contact_person || '',
    phone: client.phone || '',
    email: client.email || '',
    industry: client.industry || '',
    address: client.address || '',
    description: client.description || '',
    status: client.status
  }
  dialogVisible.value = true
}

// 保存客户
const saveClient = async () => {
  if (!clientForm.value.name) {
    ElMessage.warning('请输入客户名称')
    return
  }

  try {
    const payload = {
      name: clientForm.value.name,
      company_name: clientForm.value.company_name,
      contact_person: clientForm.value.contact_person,
      phone: clientForm.value.phone,
      email: clientForm.value.email,
      industry: clientForm.value.industry,
      address: clientForm.value.address,
      description: clientForm.value.description,
      status: clientForm.value.status
    }

    if (isEdit.value) {
      await clientApi.update(clientForm.value.id!, payload)
      ElMessage.success('更新成功')
    } else {
      await clientApi.create(payload)
      ElMessage.success('创建成功')
    }

    dialogVisible.value = false
    loadClients()
    loadStats()
    loadIndustries()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + e.message)
  }
}

// 删除客户
const deleteClient = async (id: number) => {
  try {
    await clientApi.delete(id)
    ElMessage.success('删除成功')
    loadClients()
    loadStats()
  } catch (e: any) {
    ElMessage.error('删除失败: ' + e.message)
  }
}

// 查看项目
const viewProjects = async (client: any) => {
  currentClient.value = client
  loadingProjects.value = true
  projectsDialogVisible.value = true

  try {
    const data = await clientApi.getProjects(client.id)
    clientProjects.value = data.data || []
  } catch (e: any) {
    ElMessage.error('加载项目失败: ' + e.message)
  } finally {
    loadingProjects.value = false
  }
}

// 显示项目表单（新建或编辑）
const showProjectForm = (project: any) => {
  if (project) {
    editingProject.value = project
    projectForm.value = {
      name: project.name || '',
      company_name: project.company_name || '',
      domain_keyword: project.domain_keyword || '',
      industry: project.industry || '',
      description: project.description || '',
    }
  } else {
    editingProject.value = null
    projectForm.value = {
      name: '',
      company_name: currentClient.value?.company_name || '',
      domain_keyword: '',
      industry: currentClient.value?.industry || '',
      description: '',
    }
  }
  projectFormVisible.value = true
}

// 保存项目（新建或编辑）
const saveProjectItem = async () => {
  if (!projectForm.value.name?.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  if (!projectForm.value.company_name?.trim()) {
    ElMessage.warning('请输入公司名称')
    return
  }
  if (!projectForm.value.domain_keyword?.trim()) {
    ElMessage.warning('请输入领域关键词')
    return
  }

  savingProject.value = true
  try {
    if (editingProject.value) {
      await geoKeywordApi.updateProject(editingProject.value.id, {
        client_id: currentClient.value?.id,
        ...projectForm.value,
      })
      ElMessage.success('项目已更新')
    } else {
      await geoKeywordApi.createProject({
        client_id: currentClient.value?.id,
        ...projectForm.value,
      })
      ElMessage.success('项目创建成功')
    }
    projectFormVisible.value = false
    // 刷新项目列表
    if (currentClient.value) {
      viewProjects(currentClient.value)
    }
    loadClients()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.message || '未知错误'))
  } finally {
    savingProject.value = false
  }
}

// 删除项目
const deleteProjectItem = async (project: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目"${project.name}"吗？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await geoKeywordApi.deleteProject(project.id)
    ElMessage.success('项目已删除')
    if (currentClient.value) {
      viewProjects(currentClient.value)
    }
    loadClients()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// ==================== 知识库上传相关方法 ====================

// 打开知识库上传对话框
const uploadKnowledge = (client: any) => {
  currentClient.value = client
  uploadForm.value = {
    category: '',
    description: ''
  }
  fileList.value = []
  uploadDialogVisible.value = true
}

// 处理文件选择
const handleFileChange = (file: UploadFile, uploadFiles: UploadUserFile[]) => {
  // 验证文件类型
  const allowedTypes = ['pdf', 'doc', 'docx', 'txt', 'md']
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !allowedTypes.includes(ext)) {
    ElMessage.error('不支持的文件格式，请上传 PDF、Word、TXT 或 Markdown 文件')
    fileList.value = uploadFiles.filter(item => item.uid !== file.uid)
    return false
  }

  // 验证文件大小 (10MB)
  if ((file.size || 0) > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    fileList.value = uploadFiles.filter(item => item.uid !== file.uid)
    return false
  }

  fileList.value = uploadFiles
  return true
}

// 处理文件超出限制
const handleExceed = () => {
  ElMessage.warning('最多只能上传 5 个文件')
}

// 确认上传
const confirmUpload = async () => {
  if (!currentClient.value) return

  if (fileList.value.length === 0) {
    ElMessage.warning('请至少选择一个文件')
    return
  }

  if (!uploadForm.value.category) {
    ElMessage.warning('请选择资料分类')
    return
  }

  uploading.value = true

  try {
    const formData = new FormData()
    formData.append('client_id', String(currentClient.value.id))
    formData.append('category', uploadForm.value.category)
    formData.append('description', uploadForm.value.description)

    // 添加所有文件
    fileList.value.forEach((file: any) => {
      formData.append('files', file.raw)
    })

    const response = await clientApi.uploadFiles(formData)
    const result = response.data || {}

    if (response.success) {
      const successCount = result.success_count ?? result.uploaded?.length ?? fileList.value.length
      const failedCount = result.failed_count ?? result.failed?.length ?? 0
      if (failedCount > 0) {
        ElMessage.warning(`上传完成：成功 ${successCount} 个，失败 ${failedCount} 个`)
        if (Array.isArray(result.failed) && result.failed.length > 0) {
          const failedText = result.failed
            .map((item: any) => `${item.name || '未知文件'}：${item.error || '未知错误'}`)
            .join('\n')
          ElMessageBox.alert(failedText, '上传失败详情', {
            confirmButtonText: '知道了',
            type: 'warning'
          })
        }
      } else {
        ElMessage.success(`成功上传 ${successCount} 个文件`)
      }

      if (successCount === 0) {
        return
      }

      uploadDialogVisible.value = false
      fileList.value = []
      uploadRef.value?.clearFiles()
      uploadForm.value = { category: '', description: '' }

      // 如果从文档中提取到了客户信息，自动填充编辑表单
      if (result.extracted_info && Object.keys(result.extracted_info).length > 0) {
        const info = result.extracted_info
        clientForm.value = {
          id: currentClient.value.id,
          name: info.company_name || currentClient.value.name,
          company_name: info.company_name || currentClient.value.company_name || '',
          contact_person: info.contact_person || currentClient.value.contact_person || '',
          phone: info.phone || currentClient.value.phone || '',
          email: info.email || currentClient.value.email || '',
          industry: info.industry || currentClient.value.industry || '',
          address: info.address || currentClient.value.address || '',
          description: info.description || currentClient.value.description || '',
          status: currentClient.value.status ?? 1
        }
        isEdit.value = true
        dialogVisible.value = true
        ElMessage.info('已从文档中提取客户信息，请确认并保存')
      }
    } else {
      ElMessage.error(response.message || '上传失败')
    }
  } catch (e: any) {
    ElMessage.error('上传失败: ' + e.message)
  } finally {
    uploading.value = false
  }
}

// 下拉菜单命令处理
const handleCommand = (cmd: string, client: any) => {
  if (cmd === 'edit') {
    editClient(client)
  } else if (cmd === 'delete') {
    deleteClient(client.id)
  }
}

onMounted(() => {
  loadClients()
  loadStats()
  loadIndustries()
})
</script>

<style scoped lang="scss">
.client-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;

  .stat-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    background: var(--bg-secondary);
    border-radius: 12px;

    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 24px;
    }

    .stat-content {
      .stat-label {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 4px;
      }

      .stat-value {
        font-size: 24px;
        font-weight: 600;
        color: var(--text-primary);
      }
    }
  }
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .toolbar-left {
    display: flex;
    gap: 12px;
  }
}

.table-container {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px;

  .pagination {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}

.projects-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h4 {
    margin: 0;
    font-size: 16px;
    font-weight: 500;
  }
}
</style>
