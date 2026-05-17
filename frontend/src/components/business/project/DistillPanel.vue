<template>
  <div class="distill-panel">
    <!-- 头部 -->
    <div class="panel-header">
      <div class="header-left">
        <div class="header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div>
          <h3 class="header-title">关键词蒸馏</h3>
          <span v-if="currentProject" class="header-project">{{ currentProject.name }}</span>
          <span v-else class="header-hint">请先选择项目</span>
        </div>
      </div>
      <button
        v-if="results.length > 0"
        class="clear-btn"
        @click="clearResults"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" width="14">
          <path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/>
          <path fill-rule="evenodd" d="M14.5 3a1 1 0 01-1 1H13v9a2 2 0 01-2 2H5a2 2 0 01-2-2V4h-.5a1 1 0 01-1-1V2a1 1 0 011-1H6a1 1 0 011-1h2a1 1 0 011 1h3.5a1 1 0 011 1v1zM4.118 4L4 4.059V13a1 1 0 001 1h6a1 1 0 001-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
        </svg>
        清空
      </button>
    </div>

    <!-- 蒸馏输入区 -->
    <div class="distill-form" :class="{ disabled: !currentProject }">
      <div class="form-row">
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
            <div v-if="isSynced" class="sync-badge" title="已同步项目信息">
              <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
              </svg>
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
              placeholder="自动填充"
              :disabled="!currentProject"
              @keyup.enter="startDistill"
            >
            <div v-if="isSynced" class="sync-badge" title="已同步项目信息">
              <svg viewBox="0 0 16 16" fill="currentColor" width="12">
                <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- 示例提示 -->
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
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          </svg>
        </span>
        <span v-else class="btn-spinner"></span>
        <span class="btn-text">{{ distilling ? '蒸馏中...' : '开始蒸馏' }}</span>
      </button>
    </div>

    <!-- 蒸馏结果区 -->
    <div v-if="hasResults || distilling" class="distill-results">
      <div class="results-header">
        <h4 class="results-title">
          <svg viewBox="0 0 16 16" fill="currentColor" width="16">
            <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
          </svg>
          蒸馏结果
        </h4>
        <button
          v-if="hasUnsaved"
          class="save-all-btn"
          @click="saveAll"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" width="14">
            <path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 01.02-.022z"/>
          </svg>
          全部保存
        </button>
      </div>

      <div class="results-list">
        <!-- 加载骨架屏 -->
        <template v-if="distilling && !hasResults">
          <div v-for="i in 3" :key="'skeleton-' + i" class="result-skeleton">
            <div class="skeleton-number"></div>
            <div class="skeleton-content">
              <div class="skeleton-keyword"></div>
              <div class="skeleton-questions">
                <div class="skeleton-question"></div>
                <div class="skeleton-question"></div>
              </div>
            </div>
          </div>
        </template>

        <!-- 相近关键词区域 -->
        <ResultSection
          v-if="similarKeywords.length > 0"
          title="相近关键词"
          :items="similarKeywords.map(kw => ({ key: kw, label: kw }))"
          :count="similarKeywords.length"
          tag-class="similar-tag"
        >
          <template #icon>
            <svg viewBox="0 0 16 16" fill="currentColor" width="14">
              <path d="M6.5 2a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1zm3 0a.5.5 0 01.5.5v1a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h1z"/>
              <path d="M6 8a6 6 0 1111.96-4.65l3.44 3.44a.5.5 0 01-.7.7l-3.44-3.44A6 6 0 016 8zm0-5a5 5 0 109.95 3.05l-2.44-2.44a.5.5 0 10-.71.71l2.44 2.44A5 5 0 006 3z"/>
            </svg>
          </template>
        </ResultSection>

        <!-- 核心关键词变体区域 -->
        <ResultSection
          v-if="keywordVariants.length > 0"
          title="核心关键词"
          :items="keywordVariants.map(kv => ({ key: kv.keyword, label: kv.keyword }))"
          :count="keywordVariants.length"
          tag-class="variant-tag"
        >
          <template #icon>
            <svg viewBox="0 0 16 16" fill="currentColor" width="14">
              <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm0 14.5a6.5 6.5 0 110-13 6.5 6.5 0 010 13zM6 5.5a1.5 1.5 0 113 0 1.5 1.5 0 01-3 0zM8 10c-1.1 0-2 .4-2.7 1l-1 1.7c-.2.3-.3.7-.3 1 0 .8.7 1.5 1.5 1.5h3c.8 0 1.5-.7 1.5-1.5 0-.3-.1-.7-.3-1l-1-1.7c-.7-.6-1.7-1-2.7-1z"/>
            </svg>
          </template>
        </ResultSection>

        <!-- 高转化搜索短语区域 -->
        <PhraseList
          v-if="conversionPhrases.length > 0"
          title="高转化搜索短语"
          :phrases="conversionPhrases"
          @save="savePhrase"
        />

        <!-- 兼容旧版结果列表 -->
        <TransitionGroup v-if="results.length > 0" name="result">
          <ResultItem
            v-for="(result, index) in results"
            :key="result.id"
            :result="result"
            :index="index"
            @save="saveResult"
          />
        </TransitionGroup>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { geoKeywordApi } from '@/services/api'
import ResultSection from './ResultSection.vue'
import PhraseList from './PhraseList.vue'
import ResultItem from './ResultItem.vue'

// ==================== 类型定义 ====================
interface Project {
  id: number
  name: string
  company_name: string
  domain_keyword?: string
  industry?: string
  description?: string
}

interface DistillResult {
  id: string
  keyword: string
  questions: string[]
  saved: boolean
}

interface KeywordVariant {
  keyword: string
  score?: number
}

interface ConversionPhrase {
  question: string
  keyword?: string
  saved: boolean
}

// ==================== Props ====================
interface Props {
  currentProject: Project | null
}

const props = defineProps<Props>()

// ==================== 状态 ====================
const distilling = ref(false)
const results = ref<DistillResult[]>([])
const similarKeywords = ref<string[]>([])
const keywordVariants = ref<KeywordVariant[]>([])
const conversionPhrases = ref<ConversionPhrase[]>([])

const distillForm = ref({
  keyword: '',
  company: '',
})

// ==================== 计算属性 ====================
const canDistill = computed(() => {
  return props.currentProject &&
    distillForm.value.keyword.trim() &&
    distillForm.value.company.trim()
})

const isSynced = computed(() => {
  if (!props.currentProject) return false
  return distillForm.value.keyword === props.currentProject.domain_keyword &&
    distillForm.value.company === props.currentProject.company_name
})

const hasUnsaved = computed(() => {
  return conversionPhrases.value.some(p => !p.saved) || results.value.some(r => !r.saved)
})

const hasResults = computed(() => {
  return similarKeywords.value.length > 0 ||
    keywordVariants.value.length > 0 ||
    conversionPhrases.value.length > 0 ||
    results.value.length > 0
})

// ==================== 方法 ====================

// 监听项目变化，同步表单
watch(() => props.currentProject, (project) => {
  if (project) {
    distillForm.value.keyword = project.domain_keyword || ''
    distillForm.value.company = project.company_name || ''
    results.value = []
    similarKeywords.value = []
    keywordVariants.value = []
    conversionPhrases.value = []
  } else {
    distillForm.value.keyword = ''
    distillForm.value.company = ''
    results.value = []
    similarKeywords.value = []
    keywordVariants.value = []
    conversionPhrases.value = []
  }
}, { immediate: true })

// 开始蒸馏
const startDistill = async () => {
  if (!canDistill.value) {
    ElMessage.warning('请输入关键词和公司名称')
    return
  }

  // 清空之前的结果
  results.value = []
  similarKeywords.value = []
  keywordVariants.value = []
  conversionPhrases.value = []

  distilling.value = true
  try {
    const result = await geoKeywordApi.distill({
      project_id: props.currentProject!.id,
      core_kw: distillForm.value.keyword,
      target_info: distillForm.value.company,
      company_name: distillForm.value.company,
      industry: props.currentProject?.industry || '',
      description: props.currentProject?.description || '',
      count: 5,
    })

    if (result.success && result.data) {
      const data = result.data

      // 解析相近关键词 (similar_keywords)
      if (data.similar_keywords && Array.isArray(data.similar_keywords)) {
        similarKeywords.value = data.similar_keywords
      }

      // 解析核心关键词变体 (keywords 或 variants)
      const variants = data.keywords || data.variants || []
      if (Array.isArray(variants) && variants.length > 0) {
        keywordVariants.value = variants.map((v: any) =>
          typeof v === 'string' ? { keyword: v } : v
        )
      }

      // 解析高转化搜索短语 (conversion_phrases, questions, 或 high_conversion_phrases)
      const phrases = data.conversion_phrases || data.questions || data.high_conversion_phrases || []
      if (Array.isArray(phrases) && phrases.length > 0) {
        conversionPhrases.value = phrases.map((p: any) => ({
          question: typeof p === 'string' ? p : p.question || p.text || '',
          keyword: typeof p === 'string' ? undefined : p.keyword,
          saved: false
        }))
      }

      // 兜底：如果标准字段都为空，尝试从 raw_response 中解析
      if (
        similarKeywords.value.length === 0 &&
        keywordVariants.value.length === 0 &&
        conversionPhrases.value.length === 0 &&
        data.raw_response
      ) {
        const raw = data.raw_response
        // 从 raw 中提取 keywords 数组
        const rawKw = raw.keywords || []
        if (Array.isArray(rawKw) && rawKw.length > 0) {
          keywordVariants.value = rawKw.map((v: any) =>
            typeof v === 'string' ? { keyword: v } : v
          )
        }
        // 从 raw 中提取 questions 数组
        const rawQ = raw.questions || raw.conversion_phrases || []
        if (Array.isArray(rawQ) && rawQ.length > 0) {
          conversionPhrases.value = rawQ.map((p: any) => ({
            question: typeof p === 'string' ? p : p.question || p.text || '',
            keyword: typeof p === 'string' ? undefined : p.keyword,
            saved: false
          }))
        }
        // 从 raw 中提取 similar_keywords
        const rawSimilar = raw.similar_keywords || raw.related_keywords || []
        if (Array.isArray(rawSimilar) && rawSimilar.length > 0) {
          similarKeywords.value = rawSimilar
        }
      }

      // 触发刷新事件
      emit('refresh')

      ElMessage.success(`蒸馏完成！生成 ${similarKeywords.value.length} 个相近关键词、${keywordVariants.value.length} 个核心变体、${conversionPhrases.value.length} 个高转化短语`)
    } else {
      ElMessage.error(result.message || '蒸馏失败')
    }
  } catch (error) {
    ElMessage.error('蒸馏失败，请稍后重试')
  } finally {
    distilling.value = false
  }
}

// 保存单个结果
const saveResult = async (result: DistillResult) => {
  try {
    result.saved = true
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 保存单个短语
const savePhrase = async (phrase: ConversionPhrase) => {
  try {
    phrase.saved = true
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 全部保存
const saveAll = async () => {
  for (const result of results.value) {
    if (!result.saved) {
      await saveResult(result)
    }
  }
  for (const phrase of conversionPhrases.value) {
    if (!phrase.saved) {
      await savePhrase(phrase)
    }
  }
}

// 清空结果
const clearResults = () => {
  results.value = []
  similarKeywords.value = []
  keywordVariants.value = []
  conversionPhrases.value = []
}

// ==================== Emits ====================
const emit = defineEmits<{
  refresh: []
}>()
</script>

<style scoped lang="scss">
.distill-panel {
  display: flex;
  flex-direction: column;
  background: #f8f9fc;
  border-radius: 12px;
  overflow: hidden;
}

// 头部
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: white;
  border-bottom: 1px solid #e8ecf1;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .header-icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;

      svg {
        width: 18px;
        height: 18px;
      }
    }

    .header-title {
      margin: 0;
      font-size: 14px;
      font-weight: 600;
      color: #1a1f36;
    }

    .header-project {
      font-size: 12px;
      color: #4a90e2;
    }

    .header-hint {
      font-size: 12px;
      color: #9ca3af;
    }
  }

  .clear-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    background: #fef2f2;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    color: #ef4444;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: #fee2e2;
    }
  }
}

// 蒸馏表单
.distill-form {
  padding: 16px;
  background: white;
  margin: 12px;
  border-radius: 12px;

  &.disabled {
    opacity: 0.6;
    pointer-events: none;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }

  .form-group {
    .form-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
      color: #374151;
      margin-bottom: 6px;
    }

    .input-wrapper {
      position: relative;

      .form-input {
        width: 100%;
        padding: 10px 40px 10px 12px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        font-size: 13px;
        color: #1a1f36;
      }

      .sync-badge {
        position: absolute;
        right: 10px;
        top: 50%;
        transform: translateY(-50%);
        width: 18px;
        height: 18px;
        background: #d1fae5;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #059669;
      }
    }
  }

  .example-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: linear-gradient(135deg, rgba(74, 144, 226, 0.08) 0%, rgba(74, 144, 226, 0.04) 100%);
    border-radius: 8px;
    margin-bottom: 12px;
    font-size: 12px;
    color: #6b7280;

    svg {
      color: #4a90e2;
      flex-shrink: 0;
    }
  }

  .distill-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 24px;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 500;
    color: white;
    cursor: pointer;
    transition: all 0.3s ease;

    &:hover:not(.disabled) {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }

    &.disabled {
      background: #e5e7eb;
      cursor: not-allowed;
    }

    &.loading {
      background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
    }

    .btn-icon svg {
      width: 18px;
      height: 18px;
    }

    .btn-spinner {
      width: 18px;
      height: 18px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: white;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
  }
}

// 蒸馏结果
.distill-results {
  margin: 0 12px 12px;
  background: white;
  border-radius: 12px;
  overflow: hidden;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #e8ecf1;

  .results-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    color: #1a1f36;

    svg {
      color: #10b981;
    }

    .results-count {
      font-weight: normal;
      color: #9ca3af;
    }
  }

  .save-all-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background: #4a90e2;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    color: white;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: #357abd;
    }
  }
}

.results-list {
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

// 骨架屏
.result-skeleton {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 10px;
  margin-bottom: 8px;

  .skeleton-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
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
      background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      margin-bottom: 8px;
    }

    .skeleton-questions {
      display: flex;
      gap: 6px;

      .skeleton-question {
        width: 120px;
        height: 24px;
        border-radius: 6px;
        background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
      }
    }
  }
}

// 滚动条样式
.results-list::-webkit-scrollbar {
  width: 4px;
}

.results-list::-webkit-scrollbar-track {
  background: transparent;
}

.results-list::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}

// 动画
@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

// 列表过渡动画
.result-enter-active {
  transition: all 0.3s ease;
}

.result-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.result-enter-to {
  opacity: 1;
  transform: translateX(0);
}

// 动画

</style>
