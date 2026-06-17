<template>
  <div class="keywords-page">
    <!-- 头部 - 项目选择器 -->
    <header class="page-header">
      <div class="header-left">
        <div class="header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
          </svg>
        </div>
        <div class="header-text">
          <h1 class="page-title">关键词蒸馏</h1>
          <p class="page-desc">根据领域关键词智能生成用户提问句</p>
        </div>
      </div>
      <div class="header-right">
        <el-select
          v-model="selectedProjectId"
          placeholder="选择项目"
          size="large"
          style="width: 280px"
          @change="handleProjectChange"
        >
          <el-option
            v-for="project in validProjects"
            :key="project.id"
            :label="`${project.name} - ${project.company_name}`"
            :value="project.id"
          >
            <div class="project-option">
              <span class="option-name">{{ project.name }}</span>
              <span class="option-company">{{ project.company_name }}</span>
            </div>
          </el-option>
          <template #empty>
            <div class="project-empty">
              <p>还没有项目</p>
              <el-button type="primary" link @click="goToProjects">去创建</el-button>
            </div>
          </template>
        </el-select>
      </div>
    </header>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧 - 蒸馏面板 -->
      <aside class="distill-sidebar">
        <div class="sidebar-header">
          <div class="header-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          </div>
          <div>
            <h3 class="sidebar-title">蒸馏面板</h3>
            <span v-if="currentProject" class="sidebar-project">{{ currentProject.name }}</span>
            <span v-else class="sidebar-hint">请先选择项目</span>
          </div>
        </div>

        <!-- 蒸馏输入表单 -->
        <div class="distill-form" :class="{ disabled: !currentProject }">
          <!-- 项目同步状态提示 -->
          <div v-if="currentProject && isProjectSynced" class="sync-notice">
            <svg viewBox="0 0 16 16" fill="currentColor" width="14">
              <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm.93-9.412-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.293.006-.399-.287-.47l-.451-.081.082-.381 2.29-.287zM8 5.5a1 1 0 110-2 1 1 0 010 2z"/>
            </svg>
            <span>已自动从项目「{{ currentProject.name }}」填充信息，可直接修改或开始蒸馏</span>
          </div>

          <!-- 输入区域 -->
          <div class="form-group">
            <label class="form-label">
              <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                <path d="M6.5 2a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1zm3 0a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1z"/>
              </svg>
              领域关键词
            </label>
            <div class="input-wrapper">
              <input
                v-model="distillForm.keyword"
                type="text"
                class="form-input"
                placeholder="如：无人机清洗"
                :disabled="!currentProject"
                @keyup.enter="startDistill"
              >
              <div v-if="isKeywordFromProject" class="auto-fill-tag">
                来自项目
              </div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                <path d="M8 1a4 4 0 00-4 4v2H2v2h2v6a2 2 0 002 2h4a2 2 0 002-2V9h2V7h-2V5a4 4 0 00-4-4zm0 2a2 2 0 012 2v2H6V5a2 2 0 012-2z"/>
              </svg>
              公司名称
            </label>
            <div class="input-wrapper">
              <input
                v-model="distillForm.company"
                type="text"
                class="form-input"
                placeholder="如：绿阳环保科技"
                :disabled="!currentProject"
                @keyup.enter="startDistill"
              >
              <div v-if="isCompanyFromProject" class="auto-fill-tag">
                来自项目
              </div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              用户自定义前缀（可选）
            </label>
            <div class="input-wrapper">
              <input
                v-model="distillForm.prefixes"
                type="text"
                class="form-input"
                placeholder="如：专业 靠谱 知名"
                :disabled="!currentProject"
                @keyup.enter="startDistill"
              >
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              用户自定义后缀（可选）
            </label>
            <div class="input-wrapper">
              <input
                v-model="distillForm.suffixes"
                type="text"
                class="form-input"
                placeholder="如：哪家好 厂家 服务商"
                :disabled="!currentProject"
                @keyup.enter="startDistill"
              >
            </div>
          </div>

          <!-- 示例 -->
          <div v-if="!distilling && results.length === 0" class="example-tip">
            <svg viewBox="0 0 16 16" fill="currentColor" width="16">
              <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm.93-9.412-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.293.006-.399-.287-.47l-.451-.081.082-.381 2.29-.287zM8 5.5a1 1 0 110-2 1 1 0 010 2z"/>
            </svg>
            <span>示例：「无人机清洗」+「绿阳环保」→ 无人机清洗哪家强？无人机清洗推荐？</span>
          </div>

          <!-- 蒸馏按钮 -->
          <button
            class="distill-btn"
            :class="{ loading: distilling, disabled: !canDistill }"
            :disabled="!canDistill"
            @click="startDistill"
          >
            <span v-if="!distilling" class="btn-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </span>
            <span v-else class="btn-spinner"></span>
            <span class="btn-text">{{ distilling ? '蒸馏中...' : '开始蒸馏' }}</span>
          </button>
        </div>

        <!-- 蒸馏结果 -->
        <div v-if="results.length > 0 || distilling" class="distill-results">
          <div class="results-header">
            <h4 class="results-title">
              <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
              </svg>
              蒸馏结果
              <span class="results-count">({{ results.length }})</span>
            </h4>
            <div class="results-actions">
              <button v-if="hasUnsaved" class="action-btn save-all" @click="saveAll">
                <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                  <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
                </svg>
                全部保存
              </button>
              <button class="action-btn clear" @click="clearResults">
                <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                  <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/>
                </svg>
                清空
              </button>
            </div>
          </div>

          <div class="results-list">
            <!-- 骨架屏 -->
            <template v-if="distilling && results.length === 0">
              <div v-for="i in 3" :key="'skeleton-' + i" class="result-skeleton">
                <div class="skeleton-number"></div>
                <div class="skeleton-content">
                  <div class="skeleton-keyword"></div>
                  <div class="skeleton-questions">
                    <div class="skeleton-q"></div>
                    <div class="skeleton-q"></div>
                  </div>
                </div>
              </div>
            </template>

            <!-- 结果列表 -->
            <TransitionGroup name="result">
              <div
                v-for="(result, index) in results"
                :key="result.id"
                class="result-item"
                :class="{ saved: result.saved }"
              >
                <div class="result-number">{{ index + 1 }}</div>
                <div class="result-content">
                  <div class="result-keyword">
                    <span class="keyword-tag">{{ result.keyword }}</span>
                  </div>
                  <div class="result-questions">
                    <div
                      v-for="(q, qIndex) in result.questions"
                      :key="qIndex"
                      class="question-chip"
                    >
                      {{ q }}
                    </div>
                  </div>
                </div>
                <div class="result-action">
                  <button
                    v-if="!result.saved"
                    class="action-btn save"
                    @click="saveResult(result)"
                  >
                    保存
                  </button>
                  <span v-else class="saved-badge">
                    <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                      <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
                    </svg>
                    已保存
                  </span>
                </div>
              </div>
            </TransitionGroup>

          </div>

            <!-- 搜索短语（问题列表）- 独立滚动区域 -->
            <div v-if="distillQuestions.length > 0" class="questions-section-global">
              <div class="questions-section-header">
                <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                  <path d="M2 0a2 2 0 00-2 2v8a2 2 0 002 2h2v2.5a.5.5 0 00.854.354L8.56 12H14a2 2 0 002-2V2a2 2 0 00-2-2H2z"/>
                </svg>
                搜索短语 ({{ distillQuestions.length }})
              </div>
              <div class="questions-list-global">
                <div
                  v-for="(q, index) in distillQuestions"
                  :key="index"
                  class="question-item-global"
                >
                  <span class="q-number">{{ index + 1 }}</span>
                  <span class="q-text">{{ q }}</span>
                </div>
              </div>
            </div>
          </div>
      </aside>

      <!-- 右侧 - 双列布局：核心关键词 + 搜索问题 -->
      <div class="keywords-split-area">
        <!-- 左列 - 核心关键词 -->
        <section class="keywords-column">
          <div class="column-header">
            <div class="column-header-left">
              <div class="column-icon keyword-icon">
                <svg viewBox="0 0 16 16" fill="currentColor" width="16">
                  <path d="M6.5 2a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1zm3 0a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1z"/>
                  <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm.93-9.412-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.293.006-.399-.287-.47l-.451-.081.082-.381 2.29-.287zM8 5.5a1 1 0 110-2 1 1 0 010 2z"/>
                </svg>
              </div>
              <div>
                <h3 class="column-title">核心关键词</h3>
                <span class="column-count">{{ coreKeywords.length }} 个</span>
              </div>
            </div>
            <div class="column-header-right">
              <button
                v-if="keywords.length > 0"
                class="delete-all-btn"
                title="一键清空当前项目的所有关键词"
                @click="deleteAllKeywords"
              >
                <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                  <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/>
                  <path fill-rule="evenodd" d="M14.5 3a1 1 0 01-1 1H13v9a2 2 0 01-2 2H5a2 2 0 01-2-2V4h-.5a1 1 0 01-1-1V2a1 1 0 011-1H6a1 1 0 011-1h2a1 1 0 011 1h3.5a1 1 0 011 1v1zM4.118 4L4 4.059V13a1 1 0 001 1h6a1 1 0 001-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
                </svg>
                一键清空全部
              </button>
            </div>
          </div>
          <div v-loading="loading" class="column-body">
            <div v-if="!loading && coreKeywords.length === 0" class="column-empty">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
              <p>暂无核心关键词</p>
            </div>
            <TransitionGroup v-else name="keyword" tag="div" class="keywords-grid-column">
              <div
                v-for="keyword in coreKeywords"
                :key="keyword.id"
                class="keyword-card"
                @click="viewDetail(keyword)"
              >
                <div class="card-header">
                  <h4 class="keyword-text">{{ keyword.keyword }}</h4>
                  <div v-if="keyword.difficulty_score" class="difficulty-badge" :class="getDifficultyClass(keyword.difficulty_score)">
                    {{ keyword.difficulty_score }}
                  </div>
                </div>
                <div class="card-actions">
                  <button class="action-btn view" @click.stop="viewDetail(keyword)">查看</button>
                  <button class="action-btn delete" @click.stop="deleteKeyword(keyword)">
                    <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                      <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/>
                    </svg>
                  </button>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </section>

        <!-- 右列 - 搜索问题 -->
        <section class="questions-column">
          <div class="column-header">
            <div class="column-header-left">
              <div class="column-icon question-icon">
                <svg viewBox="0 0 16 16" fill="currentColor" width="16">
                  <path d="M2 0a2 2 0 00-2 2v8a2 2 0 002 2h2v2.5a.5.5 0 00.854.354L8.56 12H14a2 2 0 002-2V2a2 2 0 00-2-2H2z"/>
                </svg>
              </div>
              <div>
                <h3 class="column-title">搜索问题</h3>
                <span class="column-count">{{ questionKeywords.length }} 个</span>
              </div>
            </div>
          </div>
          <div v-loading="loading" class="column-body">
            <div v-if="!loading && questionKeywords.length === 0" class="column-empty">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
              <p>暂无搜索问题</p>
            </div>
            <TransitionGroup v-else name="question-card" tag="div" class="questions-grid-column">
              <div
                v-for="q in questionKeywords"
                :key="q.id"
                class="question-card"
              >
                <div class="question-card-body">
                  <span class="question-text">{{ q.keyword }}</span>
                </div>
                <div class="question-card-actions">
                  <button class="action-btn delete" @click.stop="deleteKeyword(q)">
                    <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                      <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/>
                    </svg>
                  </button>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </section>
      </div>
    </div>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="showDetail"
      :title="`关键词详情 - ${currentKeyword?.keyword}`"
      width="520px"
      class="detail-dialog"
    >
      <div v-if="currentKeyword" class="detail-content">
        <div class="detail-meta">
          <div class="meta-item">
            <span class="meta-label">关键词</span>
            <el-tag type="warning">{{ currentKeyword.keyword }}</el-tag>
          </div>
          <div class="meta-item">
            <span class="meta-label">难度评分</span>
            <el-tag v-if="currentKeyword.difficulty_score" :type="getDifficultyType(currentKeyword.difficulty_score)">
              {{ currentKeyword.difficulty_score }}
            </el-tag>
            <span v-else class="meta-empty">未评分</span>
          </div>
        </div>

        <el-divider />

        <div class="questions-section">
          <div class="questions-header">
            <h5>问题变体</h5>
            <el-button
              type="primary"
              size="small"
              :loading="generating"
              @click="generateQuestions"
            >
              <svg viewBox="0 0 16 16" fill="currentColor" width="14">
                <path d="M8 4a.5.5 0 01.5.5v3h3a.5.5 0 010 1h-3v3a.5.5 0 01-1 0v-3h-3a.5.5 0 010-1h3v-3A.5.5 0 018 4z"/>
              </svg>
              生成问题
            </el-button>
          </div>
          <div v-loading="loadingQuestions" class="questions-list">
            <TransitionGroup name="question">
              <div
                v-for="(q, index) in currentQuestions"
                :key="q.id"
                class="question-item"
              >
                <span class="q-number">{{ index + 1 }}</span>
                <span class="q-text">{{ q.question }}</span>
              </div>
            </TransitionGroup>
            <el-empty v-if="currentQuestions.length === 0" description="暂无问题变体，点击上方按钮生成" />
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { geoKeywordApi } from '@/services/api'

// ==================== 类型定义 ====================
interface Project {
  id: number
  name: string
  company_name: string
  domain_keyword?: string
  industry?: string
  description?: string
}

interface Keyword {
  id: number
  keyword: string
  difficulty_score?: number
  status: string
  keyword_type?: string  // "keyword" or "question"
}

interface QuestionVariant {
  id: number
  keyword_id: number
  question: string
}

interface DistillResult {
  id: string
  keyword: string
  questions: string[]
  saved: boolean
}

// ==================== 状态 ====================
const router = useRouter()
const projects = ref<Project[]>([])
const keywords = ref<Keyword[]>([])
const keywordQuestions = ref<Record<number, QuestionVariant[]>>({})

const loading = ref(false)
const distilling = ref(false)
const loadingQuestions = ref(false)
const generating = ref(false)

const selectedProjectId = ref<number | null>(null)
const viewMode = ref<'grid' | 'list'>('grid')
const showDetail = ref(false)
const currentKeyword = ref<Keyword | null>(null)

const distillForm = ref({
  keyword: '',
  company: '',
  prefixes: '',
  suffixes: '',
})

const results = ref<DistillResult[]>([])
const distillQuestions = ref<string[]>([])

// ==================== 计算属性 ====================
// 🌟 有效项目列表（过滤掉没有 id 的项目，防止 el-option 报错）
const validProjects = computed(() => {
  return (projects.value || []).filter(p => p?.id !== undefined && p?.id !== null)
})

const currentProject = computed(() => {
  if (!selectedProjectId.value) return null
  return projects.value.find(p => p.id === selectedProjectId.value) || null
})

// 检查关键词是否来自项目
const isKeywordFromProject = computed(() => {
  return currentProject.value &&
    distillForm.value.keyword === currentProject.value.domain_keyword &&
    currentProject.value.domain_keyword
})

// 检查公司名是否来自项目
const isCompanyFromProject = computed(() => {
  return currentProject.value &&
    distillForm.value.company === currentProject.value.company_name &&
    currentProject.value.company_name
})

// 检查是否有任何信息来自项目
const isProjectSynced = computed(() => {
  return isKeywordFromProject.value || isCompanyFromProject.value
})

const canDistill = computed(() => {
  return currentProject.value &&
    distillForm.value.keyword.trim() &&
    distillForm.value.company.trim()
})

const hasUnsaved = computed(() => {
  return results.value.some(r => !r.saved)
})

// 按 keyword_type 拆分关键词和搜索问题
const coreKeywords = computed(() => {
  return keywords.value.filter(k => k.keyword_type !== 'question')
})

const questionKeywords = computed(() => {
  return keywords.value.filter(k => k.keyword_type === 'question')
})

const currentQuestions = computed(() => {
  if (!currentKeyword.value) return []
  return keywordQuestions.value[currentKeyword.value.id] || []
})

// ==================== 方法 ====================

// 加载项目列表
const loadProjects = async () => {
  try {
    const result: any = await geoKeywordApi.getProjects()
    projects.value = Array.isArray(result) ? result : (result?.data || [])
  } catch (error) {
    console.error('加载项目失败:', error)
    projects.value = [] // 确保始终是数组
  }
}

// 加载项目关键词
const loadProjectKeywords = async () => {
  if (!selectedProjectId.value) return

  loading.value = true
  try {
    const result = await geoKeywordApi.getProjectKeywords(selectedProjectId.value)
    keywords.value = result || []
  } catch (error) {
    console.error('加载关键词失败:', error)
  } finally {
    loading.value = false
  }
}

// 项目变化处理 - 填充表单并加载关键词
const handleProjectChange = () => {
  const project = projects.value.find(p => p.id === selectedProjectId.value)
  if (project) {
    distillForm.value.keyword = project.domain_keyword || ''
    distillForm.value.company = project.company_name || ''
    distillForm.value.prefixes = ''
    distillForm.value.suffixes = ''
  } else {
    distillForm.value.keyword = ''
    distillForm.value.company = ''
    distillForm.value.prefixes = ''
    distillForm.value.suffixes = ''
  }
  results.value = []
  distillQuestions.value = []
  loadProjectKeywords()
}

// 跳转到项目管理
const goToProjects = () => {
  router.push({ name: 'GeoProjects' })
}

// 开始蒸馏
const startDistill = async () => {
  if (!canDistill.value) {
    ElMessage.warning('请输入关键词和公司名称')
    return
  }

  distilling.value = true
  try {
    const result = await geoKeywordApi.distill({
      project_id: selectedProjectId.value!,
      core_kw: distillForm.value.keyword,
      target_info: distillForm.value.company,
      prefixes: distillForm.value.prefixes,
      suffixes: distillForm.value.suffixes,
      company_name: distillForm.value.company,
      industry: currentProject.value?.industry || '',
      description: currentProject.value?.description || '',
      count: 5,
    })

    if (result.success && result.data?.keywords) {
      const kwList = result.data.keywords

      // 展示关键词
      for (const kw of kwList) {
        results.value.push({
          id: kw.id.toString(),
          keyword: kw.keyword,
          questions: [],
          saved: true,
        })
      }

      // 展示 n8n 返回的搜索短语（问题列表）
      distillQuestions.value = result.data.conversion_phrases || []

      await loadProjectKeywords()
      ElMessage.success(`蒸馏完成，生成 ${kwList.length} 个关键词、${distillQuestions.value.length} 个搜索短语`)
    } else {
      ElMessage.error(result.message || '蒸馏失败')
    }
  } catch (error) {
    console.error('蒸馏失败:', error)
    ElMessage.error('蒸馏失败，请稍后重试')
  } finally {
    distilling.value = false
  }
}

// 保存单个结果
const saveResult = async (result: DistillResult) => {
  result.saved = true
  ElMessage.success('保存成功')
}

// 全部保存
const saveAll = async () => {
  for (const result of results.value) {
    if (!result.saved) {
      await saveResult(result)
    }
  }
}

// 清空结果
const clearResults = () => {
  results.value = []
  distillQuestions.value = []
}

// 获取问题数量
const getQuestionCount = (keywordId: number) => {
  return (keywordQuestions.value[keywordId] || []).length
}

// 获取难度样式类
const getDifficultyClass = (score: number) => {
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
}

// 获取难度标签类型
const getDifficultyType = (score: number) => {
  if (score >= 80) return 'danger'
  if (score >= 60) return 'warning'
  return 'success'
}

// 查看详情
const viewDetail = async (keyword: Keyword) => {
  currentKeyword.value = keyword
  showDetail.value = true
  await loadKeywordQuestions(keyword.id)
}

// 加载关键词问题
const loadKeywordQuestions = async (keywordId: number) => {
  loadingQuestions.value = true
  try {
    const result = await geoKeywordApi.getKeywordQuestions(keywordId)
    keywordQuestions.value[keywordId] = result || []
  } catch (error) {
    console.error('加载问题失败:', error)
  } finally {
    loadingQuestions.value = false
  }
}

// 生成问题
const generateQuestions = async () => {
  if (!currentKeyword.value) return

  generating.value = true
  try {
    const result = await geoKeywordApi.generateQuestions({
      keyword_id: currentKeyword.value.id,
      count: 3,
    })

    if (result.success) {
      await loadKeywordQuestions(currentKeyword.value.id)
      ElMessage.success(result.message || '问题生成成功')
    }
  } catch (error) {
    console.error('生成问题失败:', error)
    ElMessage.error('生成问题失败')
  } finally {
    generating.value = false
  }
}

// 删除单个关键词
const deleteKeyword = async (keyword: Keyword) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除关键词"${keyword.keyword}"吗？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )

    await geoKeywordApi.deleteKeyword(keyword.id)
    keywords.value = keywords.value.filter(k => k.id !== keyword.id)
    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

// 一键删除所有关键词
const deleteAllKeywords = async () => {
  if (!selectedProjectId.value) return

  try {
    await ElMessageBox.confirm(
      `确定要删除当前项目下的<b>所有关键词</b>（包含核心关键词和搜索问题）吗？<br/><br/>此操作不可恢复，请谨慎操作！`,
      '一键清空确认',
      {
        type: 'warning',
        confirmButtonText: '确定清空全部',
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: true,
        confirmButtonClass: 'el-button--danger',
      }
    )

    await geoKeywordApi.deleteAllKeywords(selectedProjectId.value)
    keywords.value = []
    ElMessage.success('所有关键词已清空')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空关键词失败:', error)
      ElMessage.error('清空失败，请稍后重试')
    }
  }
}

// ==================== 生命周期 ====================
onMounted(async () => {
  await loadProjects()

  // 处理路由参数 - 自动选中项目
  const route = router.currentRoute.value
  const projectIdFromQuery = route.query.projectId
  if (projectIdFromQuery && projects.value.length > 0) {
    const projectId = Number(projectIdFromQuery)
    const project = projects.value.find(p => p.id === projectId)
    if (project) {
      selectedProjectId.value = projectId
      await loadProjectKeywords()
    }
  }
})
</script>

<style scoped lang="scss">
/* ================================================================
   Keywords — Warm Studio Design
   Uses global tokens for consistency.
   ================================================================ */

.keywords-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px;
  background: transparent;
}

// ---- Header ----
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background:
    linear-gradient(135deg, rgba(125, 190, 138, 0.04), transparent 60%),
    var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
  margin-bottom: 20px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    .header-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--success), #5a9e68);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;

      svg { width: 24px; height: 24px; }
    }

    .page-title {
      margin: 0 0 4px 0;
      font-family: var(--font-display);
      font-size: 20px;
      font-weight: 600;
      color: var(--text-head);
    }

    .page-desc {
      margin: 0;
      font-size: 13px;
      color: var(--text-muted);
    }
  }

  .project-option {
    display: flex;
    flex-direction: column;
    gap: 2px;

    .option-name { font-size: 14px; color: var(--text-head); }
    .option-company { font-size: 12px; color: var(--text-muted); }
  }

  .project-empty {
    text-align: center;
    padding: 10px;

    p { margin: 0 0 4px 0; font-size: 13px; color: var(--text-muted); }
  }
}

// ---- Main Content ----
.main-content {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

// ---- Distill Sidebar ----
.distill-sidebar {
  width: 380px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  .sidebar-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    background:
      linear-gradient(135deg, rgba(125, 190, 138, 0.05), transparent),
      var(--surface-raised);
    border: 1px solid var(--border-thin);
    border-radius: var(--radius-lg);

    .header-icon {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--success), #5a9e68);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;

      svg { width: 20px; height: 20px; }
    }

    .sidebar-title {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: var(--text-head);
    }

    .sidebar-project { display: block; font-size: 12px; color: var(--success); font-weight: 500; }
    .sidebar-hint { display: block; font-size: 12px; color: var(--text-muted); }
  }
}

// ---- Distill Form ----
.distill-form {
  padding: 20px;
  background: var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);

  .sync-notice {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: var(--success-soft);
    border: 1px solid rgba(125, 190, 138, 0.18);
    border-radius: var(--radius-md);
    margin-bottom: 16px;
    font-size: 13px;
    color: var(--success);

    svg { flex-shrink: 0; color: var(--success); }
  }

  &.disabled { opacity: 0.5; pointer-events: none; }

  .form-group {
    margin-bottom: 16px;

    .form-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      margin-bottom: 8px;
    }

    .input-wrapper {
      position: relative;

      .form-input {
        width: 100%;
        padding: 12px 90px 12px 14px;
        border: 1px solid var(--border-soft);
        border-radius: var(--radius-sm);
        font-size: 14px;
        background: var(--surface-field);
        color: var(--text-body);
        transition: all var(--duration-fast);

        &::placeholder { color: var(--text-disabled); }

        &:focus {
          outline: none;
          border-color: var(--success);
          box-shadow: 0 0 0 3px var(--success-soft);
        }

        &:disabled {
          background: rgba(200, 185, 160, 0.04);
          color: var(--text-disabled);
          cursor: not-allowed;
        }
      }

      .auto-fill-tag {
        position: absolute;
        right: 12px;
        top: 50%;
        transform: translateY(-50%);
        padding: 4px 10px;
        background: var(--success-soft);
        border-radius: var(--radius-sm);
        font-size: 12px;
        color: var(--success);
        font-weight: 500;
        pointer-events: none;
      }
    }
  }

  .example-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    margin-bottom: 16px;
    font-size: 12px;
    color: var(--text-muted);
    background: rgba(200, 185, 160, 0.03);
    border-radius: var(--radius-sm);
    svg { color: var(--text-muted); flex-shrink: 0; }
  }

  .distill-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 14px 24px;
    background: linear-gradient(135deg, var(--success), #5a9e68);
    border: none;
    border-radius: var(--radius-md);
    font-size: 15px;
    font-weight: 600;
    color: #fff;
    cursor: pointer;
    transition: all var(--duration-normal) var(--ease-out);
    letter-spacing: 0.02em;

    &:hover:not(.disabled) {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(125, 190, 138, 0.32);
    }

    &.disabled {
      background: var(--surface-field);
      color: var(--text-disabled);
      cursor: not-allowed;
    }

    &.loading { opacity: 0.8; }

    .btn-icon svg { width: 18px; height: 18px; }

    .btn-spinner {
      width: 18px;
      height: 18px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
  }
}

// ---- Distill Results ----
.distill-results {
  background: var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-thin);

  .results-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-head);

    svg { color: var(--success); }
    .results-count { font-weight: normal; color: var(--text-muted); }
  }

  .results-actions {
    display: flex;
    gap: 8px;

    .action-btn {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 6px 12px;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all var(--duration-fast);

      &.save-all {
        background: var(--accent);
        color: var(--accent-ink);
        &:hover { background: var(--accent-hover); }
      }

      &.clear {
        background: var(--danger-soft);
        color: var(--danger);
        &:hover { background: rgba(224, 115, 99, 0.22); }
      }
    }
  }
}

.results-list {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  background: var(--surface-field);
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  border-left: 3px solid transparent;
  transition: all var(--duration-fast);

  &:hover { background: var(--surface-hover); }

  &.saved {
    border-left-color: var(--success);
    background: linear-gradient(90deg, rgba(125, 190, 138, 0.08) 0%, transparent 100%);
  }

  .result-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--success), #5a9e68);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .result-content {
    flex: 1;
    min-width: 0;

    .result-keyword {
      margin-bottom: 10px;
      .keyword-tag {
        display: inline-flex;
        align-items: center;
        padding: 5px 12px;
        background: var(--warning-soft);
        border-radius: var(--radius-sm);
        font-size: 13px;
        font-weight: 500;
        color: var(--warning);
      }
    }

    .result-questions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;

      .question-chip {
        padding: 5px 10px;
        background: rgba(200, 185, 160, 0.06);
        border: 1px solid var(--border-soft);
        border-radius: var(--radius-sm);
        font-size: 12px;
        color: var(--text-muted);
        transition: all var(--duration-fast);
        &:hover { border-color: var(--border-hover); color: var(--text-body); }
      }
    }
  }

  .result-action {
    flex-shrink: 0;

    .action-btn {
      padding: 6px 12px;
      background: var(--accent);
      border: none;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 500;
      color: var(--accent-ink);
      cursor: pointer;
      &:hover { background: var(--accent-hover); }
    }

    .saved-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      background: var(--success-soft);
      border-radius: var(--radius-sm);
      font-size: 11px;
      color: var(--success);
      font-weight: 500;
    }
  }
}

// ---- Skeleton ----
.result-skeleton {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  background: var(--surface-field);
  border-radius: var(--radius-md);
  margin-bottom: 10px;

  .skeleton-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: linear-gradient(90deg, rgba(200,185,160,0.08) 25%, rgba(200,185,160,0.14) 50%, rgba(200,185,160,0.08) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    flex-shrink: 0;
  }

  .skeleton-content {
    flex: 1;
    .skeleton-keyword {
      width: 80px;
      height: 28px;
      border-radius: 6px;
      background: linear-gradient(90deg, rgba(200,185,160,0.08) 25%, rgba(200,185,160,0.14) 50%, rgba(200,185,160,0.08) 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      margin-bottom: 10px;
    }
    .skeleton-questions {
      display: flex;
      gap: 6px;
      .skeleton-q {
        width: 100px;
        height: 24px;
        border-radius: 6px;
        background: linear-gradient(90deg, rgba(200,185,160,0.08) 25%, rgba(200,185,160,0.14) 50%, rgba(200,185,160,0.08) 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
      }
    }
  }
}

// ---- Right Split Area ----
.keywords-split-area {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.keywords-column,
.questions-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-width: 0;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-thin);
  flex-shrink: 0;
  background: rgba(200, 185, 160, 0.02);
}

.column-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.delete-all-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  background: var(--danger-soft);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--danger);
  cursor: pointer;
  transition: all var(--duration-fast);
  white-space: nowrap;

  svg { flex-shrink: 0; }

  &:hover {
    background: rgba(224, 115, 99, 0.22);
    border-color: var(--danger);
  }
}

.column-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.column-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  svg { width: 16px; height: 16px; }
}

.keyword-icon { background: linear-gradient(135deg, var(--warning), #b8861e); }
.question-icon { background: linear-gradient(135deg, #7b9ec7, #5a7db0); }

.column-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-head);
}

.column-count { font-size: 11px; color: var(--text-muted); font-weight: 500; }

.column-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.column-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: var(--text-muted);

  svg { width: 48px; height: 48px; margin-bottom: 12px; opacity: 0.25; }
  p { margin: 0; font-size: 13px; }
}

// ---- Keywords Grid ----
.keywords-grid-column {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

// ---- Question Cards ----
.questions-grid-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.question-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--surface-field);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast);

  &:hover {
    background: var(--surface-hover);
    border-color: var(--border-soft);
  }

  .question-card-body {
    flex: 1;
    min-width: 0;
    .question-text {
      font-size: 13px;
      color: var(--text-body);
      line-height: 1.5;
      word-break: break-all;
    }
  }

  .question-card-actions {
    flex-shrink: 0;
    margin-left: 10px;

    .action-btn.delete {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      background: transparent;
      border: none;
      border-radius: var(--radius-sm);
      color: var(--text-muted);
      cursor: pointer;
      transition: all var(--duration-fast);

      &:hover { background: var(--danger-soft); color: var(--danger); }
    }
  }
}

// ---- Keyword Card ----
.keyword-card {
  background: var(--surface-field);
  border-radius: var(--radius-md);
  padding: 16px;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  border: 1px solid transparent;

  &:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 16px rgba(212, 168, 83, 0.08);
    transform: translateY(-2px);
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 12px;

    .keyword-text {
      margin: 0;
      font-size: 14px;
      font-weight: 600;
      color: var(--text-head);
      word-break: break-word;
    }

    .difficulty-badge {
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      font-size: 11px;
      font-weight: 600;
      flex-shrink: 0;

      &.high { background: var(--danger-soft); color: var(--danger); }
      &.medium { background: var(--warning-soft); color: var(--warning); }
      &.low { background: var(--success-soft); color: var(--success); }
    }
  }

  .card-actions {
    display: flex;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px solid var(--border-thin);

    .action-btn {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 6px;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all var(--duration-fast);

      &.view {
        background: rgba(200, 185, 160, 0.06);
        color: var(--text-muted);
        &:hover { background: rgba(200, 185, 160, 0.12); color: var(--text-head); }
      }

      &.delete {
        background: var(--danger-soft);
        color: var(--danger);
        &:hover { background: rgba(224, 115, 99, 0.22); }
      }
    }
  }
}

// ---- Detail Dialog ----
.detail-content {
  .detail-meta {
    display: flex;
    gap: 24px;
    .meta-item {
      display: flex; align-items: center; gap: 8px;
      .meta-label { font-size: 13px; color: var(--text-muted); }
      .meta-empty { font-size: 13px; color: var(--text-muted); }
    }
  }

  .questions-section {
    .questions-header {
      display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;
      h5 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text-head); }
    }

    .questions-list {
      display: flex; flex-direction: column; gap: 10px; min-height: 100px;

      .question-item {
        display: flex; gap: 12px; padding: 12px 14px;
        background: var(--surface-field); border-radius: var(--radius-sm);
        border: 1px solid var(--border-thin);

        .q-number {
          width: 24px; height: 24px; border-radius: 50%;
          background: var(--accent); color: var(--accent-ink);
          display: flex; align-items: center; justify-content: center;
          font-size: 12px; font-weight: 600; flex-shrink: 0;
        }
        .q-text { flex: 1; font-size: 13px; color: var(--text-body); }
      }
    }
  }
}

// ---- Global Questions Section ----
.questions-section-global {
  margin-top: 12px;
  padding: 14px 18px;
  border-top: 1px solid var(--border-thin);
  background: var(--surface-field);

  .questions-section-header {
    display: flex; align-items: center; gap: 6px;
    font-size: 13px; font-weight: 600; color: var(--text-head);
    margin-bottom: 10px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border-thin);

    svg { color: #7b9ec7; }
  }

  .questions-list-global {
    display: flex; flex-direction: column; gap: 6px;
    max-height: 300px; overflow-y: auto;
  }

  .question-item-global {
    display: flex; gap: 10px; padding: 8px 10px;
    background: rgba(200, 185, 160, 0.03);
    border: 1px solid var(--border-thin);
    border-radius: var(--radius-sm);
    transition: background var(--duration-fast);

    &:hover { background: rgba(200, 185, 160, 0.06); }

    .q-number {
      width: 22px; height: 22px; border-radius: 50%;
      background: linear-gradient(135deg, #7b9ec7, #5a7db0);
      color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 500; flex-shrink: 0;
    }
    .q-text { flex: 1; font-size: 13px; color: var(--text-body); line-height: 1.5; }
  }
}

// ---- Animations ----
@keyframes spin { to { transform: rotate(360deg); } }

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.result-enter-active,
.keyword-enter-active {
  transition: all 0.3s ease;
}
.result-enter-from,
.keyword-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.question-enter-active { transition: all 0.2s ease; }
.question-enter-from { opacity: 0; transform: translateX(-10px); }
</style>
