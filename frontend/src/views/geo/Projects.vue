<template>
  <div class="projects-page">
    <!-- 头部 -->
    <header class="page-header">
      <div class="header-content">
        <div class="header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"/>
          </svg>
        </div>
        <div class="header-text">
          <h1 class="page-title">GEO 项目管理</h1>
          <p class="page-desc">智能获客项目全生命周期管理</p>
        </div>
      </div>
      <el-button type="primary" size="large" @click="showCreateDialog = true">
        <svg viewBox="0 0 16 16" fill="currentColor" width="16">
          <path d="M8 4a.5.5 0 01.5.5v3h3a.5.5 0 010 1h-3v3a.5.5 0 01-1 0v-3h-3a.5.5 0 010-1h3v-3A.5.5 0 018 4z"/>
        </svg>
        创建项目
      </el-button>
    </header>

    <!-- 项目网格 -->
    <section class="projects-section">
      <div class="section-header">
        <h2 class="section-title">项目列表</h2>
        <span class="section-count">{{ projects.length }} 个项目</span>
      </div>
      <div v-loading="loading" class="projects-grid">
        <div
          v-for="project in projects"
          :key="project.id"
          class="project-card"
        >
          <div class="card-header">
            <div class="project-badge">{{ getProjectInitial(project.name) }}</div>
            <el-dropdown trigger="click">
              <div class="more-btn">
                <svg viewBox="0 0 16 16" fill="currentColor" width="16">
                  <path d="M3 9.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm5 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm5 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3z"/>
                </svg>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="editProject(project)">
                    <el-icon><Edit /></el-icon>
                    编辑项目
                  </el-dropdown-item>
                  <el-dropdown-item @click="goToKeywords(project)">
                    <el-icon><Key /></el-icon>
                    管理关键词
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="deleteProject(project)">
                    <el-icon><Delete /></el-icon>
                    删除项目
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <div class="card-body">
            <h3 class="project-name">{{ project.name }}</h3>
            <div class="project-company">
              <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                <path d="M8 1a4 4 0 00-4 4v2H2v2h2v6a2 2 0 002 2h4a2 2 0 002-2V9h2V7h-2V5a4 4 0 00-4-4zm0 2a2 2 0 012 2v2H6V5a2 2 0 012-2z"/>
              </svg>
              {{ project.company_name }}
            </div>

            <div v-if="project.domain_keyword" class="keyword-tag">
              <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                <path d="M6.5 2a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1zm3 0a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1z"/>
              </svg>
              {{ project.domain_keyword }}
            </div>

            <div class="card-meta">
              <span v-if="project.industry" class="industry-badge">{{ project.industry }}</span>
              <span class="keyword-count">{{ getKeywordCount(project.id) }} 个关键词</span>
            </div>
          </div>

          <div class="card-footer">
            <button class="action-btn primary" @click="goToKeywords(project)">
              <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                <path d="M8 4a.5.5 0 01.5.5v3h3a.5.5 0 010 1h-3v3a.5.5 0 01-1 0v-3h-3a.5.5 0 010-1h3v-3A.5.5 0 018 4z"/>
              </svg>
              关键词蒸馏
            </button>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!loading && projects.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 3h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
            </svg>
          </div>
          <h3>还没有GEO项目</h3>
          <p>创建第一个项目开始您的获客之旅</p>
          <el-button type="primary" @click="showCreateDialog = true">创建项目</el-button>
        </div>
      </div>
    </section>

    <!-- 创建/编辑项目对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingProject ? '编辑GEO项目' : '创建GEO项目'"
      width="520px"
      :close-on-click-modal="false"
      class="project-dialog"
    >
      <el-form :model="projectForm" label-position="top" @submit.prevent="saveProject">
        <el-form-item label="项目名称" required>
          <el-input
            v-model="projectForm.name"
            placeholder="如：绿阳环保无人机清洗"
            clearable
            size="large"
          />
        </el-form-item>

        <el-form-item label="公司名称" required>
          <el-input
            v-model="projectForm.company_name"
            placeholder="如：绿阳环保科技有限公司"
            clearable
            size="large"
          />
        </el-form-item>

        <el-form-item label="领域关键词" required>
          <el-input
            v-model="projectForm.domain_keyword"
            placeholder="如：无人机清洗"
            clearable
            size="large"
          />
          <div class="form-tip">此关键词将用于AI蒸馏生成用户提问句</div>
        </el-form-item>

        <el-form-item label="所属行业">
          <el-select
            v-model="projectForm.industry"
            placeholder="选择或输入自定义行业"
            allow-create
            filterable
            style="width: 100%"
            size="large"
          >
            <el-option
              v-for="ind in industries"
              :key="ind"
              :label="ind"
              :value="ind"
            />
          </el-select>
          <div class="form-tip">支持自定义输入行业名称</div>
        </el-form-item>

        <el-form-item label="项目描述">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            :rows="3"
            placeholder="简要描述项目背景和目标（可选）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProject">
          {{ editingProject ? '保存修改' : '创建项目' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Key } from '@element-plus/icons-vue'
import { geoKeywordApi } from '@/services/api'

// 行业列表
const industries = [
  'SaaS软件',
  '环保工程',
  '工业清洗',
  '无人机服务',
  '电商',
  '教育培训',
  '金融服务',
  '医疗健康',
  '制造业',
  '房地产',
  '餐饮美食',
  '旅游出行',
  '物流运输',
  '新能源',
  '化工行业',
  '建筑工程',
  '其他',
]

// ==================== 类型定义 ====================
interface Project {
  id: number
  name: string
  company_name: string
  domain_keyword?: string
  description?: string
  industry?: string
  status: number
  created_at: string
}

// ==================== 状态 ====================
const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)
const saving = ref(false)
const showCreateDialog = ref(false)
const editingProject = ref<Project | null>(null)

const projectForm = ref({
  name: '',
  company_name: '',
  domain_keyword: '',
  industry: '',
  description: '',
})

// ==================== 方法 ====================

// 加载项目列表
const loadProjects = async () => {
  loading.value = true
  try {
    const result: any = await geoKeywordApi.getProjects()
    projects.value = Array.isArray(result) ? result : (result?.data || [])
  } catch (error) {
    console.error('加载项目失败:', error)
    projects.value = [] // 确保始终是数组
  } finally {
    loading.value = false
  }
}

// 获取项目首字母
const getProjectInitial = (name: string) => {
  return name.charAt(0).toUpperCase()
}

// 获取项目关键词数量
const getKeywordCount = (projectId: number) => {
  // TODO: 实际应该从API获取，暂时返回0
  return 0
}

// 查看项目
const viewProject = (project: Project) => {
  goToKeywords(project)
}

// 跳转到关键词管理
const goToKeywords = (project: Project) => {
  router.push({
    name: 'GeoKeywords',
    query: { projectId: project.id }
  })
}

// 编辑项目
const editProject = (project: Project) => {
  editingProject.value = project
  projectForm.value = {
    name: project.name,
    company_name: project.company_name,
    domain_keyword: project.domain_keyword || '',
    industry: project.industry || '',
    description: project.description || '',
  }
  showCreateDialog.value = true
}

// 删除项目
const deleteProject = async (project: Project) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目"${project.name}"吗？删除后关联的关键词和文章也将被删除！`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )

    await geoKeywordApi.deleteProject(project.id)
    projects.value = projects.value.filter(p => p.id !== project.id)
    ElMessage.success('项目已删除')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除项目失败:', error)
      ElMessage.error('删除项目失败')
    }
  }
}

// 保存项目
const saveProject = async () => {
  // 验证表单
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

  saving.value = true
  try {
    if (editingProject.value) {
      // 更新项目 - 也要传递 domain_keyword
      await geoKeywordApi.updateProject(editingProject.value.id, {
        name: projectForm.value.name,
        company_name: projectForm.value.company_name,
        domain_keyword: projectForm.value.domain_keyword,
        industry: projectForm.value.industry,
        description: projectForm.value.description,
      })
      const index = projects.value.findIndex(p => p.id === editingProject.value!.id)
      if (index !== -1) {
        projects.value[index] = {
          ...projects.value[index],
          name: projectForm.value.name,
          company_name: projectForm.value.company_name,
          domain_keyword: projectForm.value.domain_keyword,
          industry: projectForm.value.industry,
          description: projectForm.value.description,
        }
      }
      ElMessage.success('项目已更新')
    } else {
      // 创建项目 - 传递 domain_keyword
      const result = await geoKeywordApi.createProject({
        name: projectForm.value.name,
        company_name: projectForm.value.company_name,
        domain_keyword: projectForm.value.domain_keyword,
        industry: projectForm.value.industry,
        description: projectForm.value.description,
      })
      projects.value.unshift(result)
      ElMessage.success('项目创建成功')
    }

    showCreateDialog.value = false
    resetForm()
  } catch (error) {
    console.error('保存项目失败:', error)
    ElMessage.error('保存项目失败')
  } finally {
    saving.value = false
  }
}

// 重置表单
const resetForm = () => {
  editingProject.value = null
  projectForm.value = {
    name: '',
    company_name: '',
    domain_keyword: '',
    industry: '',
    description: '',
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadProjects()
})
</script>

<style scoped lang="scss">
/* ================================================================
   Projects — Warm Studio
   ================================================================ */

.projects-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
  padding: 24px 28px;
  background: transparent;
}

// ---- Header ----
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px;
  background:
    linear-gradient(135deg, rgba(110, 184, 214, 0.05), transparent 60%),
    var(--surface-raised);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-thin);

  .header-content {
    display: flex;
    align-items: center;
    gap: 16px;

    .header-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      background: linear-gradient(135deg, #7b9ec7, #5a7db0);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;

      svg { width: 26px; height: 26px; }
    }

    .page-title {
      margin: 0 0 4px 0;
      font-family: var(--font-display);
      font-size: 22px;
      font-weight: 600;
      color: var(--text-head);
    }

    .page-desc {
      margin: 0;
      font-size: 13px;
      color: var(--text-muted);
    }
  }
}

// ---- Section ----
.projects-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface-raised);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-thin);
  padding: 24px 28px;

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;

    .section-title {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--text-head);
    }

    .section-count {
      font-size: 12px;
      color: var(--text-muted);
      padding: 4px 12px;
      background: rgba(200, 185, 160, 0.06);
      border-radius: 20px;
      font-weight: 500;
    }
  }
}

// ---- Project Grid ----
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

// ---- Project Card ----
.project-card {
  background: var(--surface-field);
  border-radius: var(--radius-lg);
  padding: 22px;
  border: 1px solid var(--border-thin);
  display: flex;
  flex-direction: column;
  transition: all var(--duration-normal) var(--ease-out);

  &:hover {
    border-color: rgba(123, 158, 199, 0.30);
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 14px;

    .project-badge {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: linear-gradient(135deg, #7b9ec7, #5a7db0);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 16px;
      color: #fff;
    }

    .more-btn {
      width: 32px;
      height: 32px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-muted);
      cursor: pointer;
      transition: all var(--duration-fast);

      &:hover { background: var(--surface-hover); color: var(--text-head); }
    }
  }

  .card-body {
    flex: 1;

    .project-name {
      margin: 0 0 8px 0;
      font-size: 15px;
      font-weight: 600;
      color: var(--text-head);
    }

    .project-company {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 12px;
    }

    .keyword-tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      background: var(--warning-soft);
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 500;
      color: var(--warning);
      margin-bottom: 12px;
    }

    .card-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;

      .industry-badge {
        padding: 3px 10px;
        background: rgba(200, 185, 160, 0.06);
        border-radius: var(--radius-sm);
        font-size: 11px;
        color: var(--text-muted);
      }

      .keyword-count { font-size: 11px; color: var(--text-disabled); }
    }
  }

  .card-footer {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid var(--border-thin);

    .action-btn {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 20px;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all var(--duration-fast) var(--ease-out);
      letter-spacing: 0.01em;

      &.primary {
        background: linear-gradient(135deg, #7b9ec7, #5a7db0);
        color: #fff;

        &:hover { box-shadow: 0 4px 16px rgba(123, 158, 199, 0.35); transform: translateY(-1px); }
      }
    }
  }
}

// ---- Empty State ----
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;

  .empty-icon {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    background: rgba(123, 158, 199, 0.10);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;

    svg { width: 32px; height: 32px; color: #7b9ec7; }
  }

  h3 { margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: var(--text-head); }
  p { margin: 0 0 20px 0; font-size: 13px; color: var(--text-muted); }
}

// ---- Form Tip ----
.form-tip { margin-top: 6px; font-size: 12px; color: var(--text-muted); }
</style>
