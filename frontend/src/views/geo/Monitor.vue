<template>
  <div class="monitor-page" v-if="initialized">
    <!-- 1. 统计卡片 -->
    <div class="stats-grid">
      <div v-for="item in statConfigs" :key="item.label" :class="['stat-card', item.class]">
        <div class="stat-value">{{ item.value }}{{ item.unit }}</div>
        <div class="stat-label">{{ item.label }}</div>
      </div>
    </div>

    <!-- 平台授权状态 -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">AI平台授权状态</h2>
        <el-button @click="refreshPlatformStatuses">
          <el-icon><Refresh /></el-icon>
          刷新状态
        </el-button>
      </div>
      
      <div v-loading="platformStatusesLoading" class="platform-status-list">
        <div 
          v-for="platform in platformStatuses" 
          :key="platform.id"
          class="platform-status-card"
          :class="platform.status"
        >
          <div class="platform-icon" :style="{ backgroundColor: platform.color + '20' }">
            <span :style="{ color: platform.color }">{{ platform.name.charAt(0) }}</span>
          </div>
          <div class="platform-info">
            <h4>{{ platform.name }}</h4>
            <p>{{ platform.url }}</p>
            <div class="status-info">
              <el-tag :type="getStatusType(platform.status)">
                {{ getStatusText(platform.status) }}
              </el-tag>
            </div>
          </div>
          <div class="platform-actions">
            <el-button 
              type="primary"
              size="small"
              @click="startPlatformAuthFlow(platform.id)"
            >
              开启新的授权
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <!-- 检测操作区 -->
        <div class="section">
          <div class="section-header">
            <h2 class="section-title">收录检测</h2>
            <el-button @click="refreshAllData" size="small" type="primary" plain>
              <el-icon><Refresh /></el-icon>
              刷新数据
            </el-button>
          </div>
          <el-form :inline="true" :model="checkForm" class="check-form">
            <el-form-item label="选择项目">
              <el-select
                v-model="checkForm.projectId"
                placeholder="请选择项目"
                style="width: 200px"
                @change="onProjectChange"
              >
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="选择关键词">
              <el-select
                v-model="checkForm.keywordId"
                placeholder="请选择关键词"
                style="width: 200px"
                :disabled="!checkForm.projectId"
              >
                <el-option
                  v-for="keyword in keywords"
                  :key="keyword.id"
                  :label="keyword.keyword"
                  :value="keyword.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="检测平台">
              <el-select v-model="checkForm.platforms" multiple style="width: 250px">
                <el-option label="豆包" value="doubao" />
                <el-option label="通义千问" value="qianwen" />
                <el-option label="DeepSeek" value="deepseek" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="checking"
                :disabled="!checkForm.keywordId"
                @click="runCheck"
              >
                <el-icon><Search /></el-icon>
                开始检测
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <!-- 检测结果表格 -->
        <div class="section">
          <div class="section-header">
            <h2 class="section-title">检测记录</h2>
            <div class="header-actions">
              <el-button 
                type="danger" 
                :disabled="selectedRecords.length === 0"
                @click="batchDelete"
              >
                <el-icon><Delete /></el-icon>
                批量删除
              </el-button>
              <el-button @click="loadRecords">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </div>

          <!-- 筛选工具栏 -->
          <div class="filter-toolbar">
            <el-form :inline="true" :model="filterForm" class="filter-form">
              <el-form-item label="平台">
                <el-select v-model="filterForm.platform" placeholder="全部平台" clearable style="width: 140px">
                  <el-option label="全部" value="" />
                  <el-option label="豆包" value="doubao" />
                  <el-option label="通义千问" value="qianwen" />
                  <el-option label="DeepSeek" value="deepseek" />
                </el-select>
              </el-form-item>
              <el-form-item label="命中状态">
                <el-select v-model="filterForm.hitStatus" placeholder="全部状态" clearable style="width: 140px">
                  <el-option label="全部" value="" />
                  <el-option label="关键词命中" value="keyword_found" />
                  <el-option label="公司名命中" value="company_found" />
                </el-select>
              </el-form-item>
              <el-form-item label="时间范围">
                <el-select v-model="filterForm.timeRange" placeholder="全部时间" clearable style="width: 140px">
                  <el-option label="全部" value="" />
                  <el-option label="近三天" value="3days" />
                  <el-option label="本周" value="week" />
                  <el-option label="本月" value="month" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-input
                  v-model="filterForm.question"
                  placeholder="搜索检测问题"
                  prefix-icon="Search"
                  clearable
                  style="width: 200px"
                  @keyup.enter="handleFilter"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleFilter">筛选</el-button>
                <el-button @click="resetFilter">重置</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table
            v-loading="recordsLoading"
            :data="records"
            stripe
            style="width: 100%"
            @selection-change="handleSelectionChange"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="question" label="检测问题" min-width="250" show-overflow-tooltip />
            <el-table-column prop="platform" label="平台" width="120">
              <template #default="{ row }">
                <el-tag :type="getPlatformType(row.platform)">
                  {{ getPlatformName(row.platform) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关键词命中" width="120">
              <template #default="{ row }">
                <el-tag :type="row.keyword_found ? 'success' : 'danger'">
                  {{ row.keyword_found ? '命中' : '未命中' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="公司名命中" width="120">
              <template #default="{ row }">
                <el-tag :type="row.company_found ? 'success' : 'danger'">
                  {{ row.company_found ? '命中' : '未命中' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="check_time" label="检测时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.check_time) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" size="small" link @click="viewAnswer(row)">
                  查看
                </el-button>
                <el-popconfirm
                  title="确定要删除这条记录吗？"
                  @confirm="deleteRecord(row)"
                >
                  <template #reference>
                    <el-button type="danger" size="small" link>
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="pagination-container">
            <el-pagination
              v-model:current-page="pagination.currentPage"
              v-model:page-size="pagination.pageSize"
              :page-sizes="[15, 30, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              :total="pagination.total"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </div>

        <!-- 命中率趋势图表 -->
        <div class="section">
          <div class="section-header">
            <h2 class="section-title">命中率趋势</h2>
            <el-select 
              v-model="trendPlatform" 
              placeholder="全平台" 
              style="width: 150px"
              @change="loadTrendChart"
            >
              <el-option label="全平台" value="" />
              <el-option label="豆包" value="doubao" />
              <el-option label="通义千问" value="qianwen" />
              <el-option label="DeepSeek" value="deepseek" />
            </el-select>
          </div>
          <div ref="chartRef" class="chart-container" />
        </div>
      </el-col>

      <!-- 实时日志 -->
      <el-col :span="8">
        <div class="section log-section">
          <div class="section-header">
            <h2 class="section-title">流水线实时日志</h2>
            <el-tag :type="wsStatus === 'connected' ? 'success' : 'danger'" size="small">{{ wsStatus }}</el-tag>
          </div>
          <div class="log-console" ref="logRef">
            <div v-for="(log, index) in logs" :key="index" :class="['log-line', log.level]">
              <span class="log-time">{{ log.time }}</span>
              <span class="log-msg">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 回答详情对话框 -->
    <el-dialog
      v-model="showAnswerDialog"
      title="AI回答内容"
      width="600px"
    >
      <div v-if="currentRecord" class="answer-content">
        <div class="answer-question">
          <strong>检测问题：</strong>{{ currentRecord.question }}
        </div>
        <div class="answer-body">
          <strong>AI回答：</strong>
          <p>{{ currentRecord.answer }}</p>
        </div>
        <div class="answer-result">
          <el-tag :type="currentRecord.keyword_found ? 'success' : 'danger'">
            关键词{{ currentRecord.keyword_found ? '命中' : '未命中' }}
          </el-tag>
          <el-tag :type="currentRecord.company_found ? 'success' : 'danger'">
            公司名{{ currentRecord.company_found ? '命中' : '未命中' }}
          </el-tag>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  Refresh,
  Delete
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { geoKeywordApi, indexCheckApi, reportsApi } from '@/services/api'
import { get, post } from '@/services/api'

// ==================== 类型定义 ====================
interface Project {
  id: number
  name: string
  company_name: string
}

interface Keyword {
  id: number
  keyword: string
}

interface CheckRecord {
  id: number
  keyword_id: number
  platform: string
  question: string
  answer?: string
  keyword_found?: boolean
  company_found?: boolean
  check_time: string
}

// ==================== 状态 ====================
const initialized = ref(false)
const projects = ref<Project[]>([])
const keywords = ref<Keyword[]>([])
const records = ref<CheckRecord[]>([])
const selectedRecords = ref<CheckRecord[]>([])
const stats = ref({
  total_keywords: 0,
  keyword_found: 0,
  company_found: 0,
  overall_hit_rate: 0,
})

const recordsLoading = ref(false)
const checking = ref(false)
const logs = ref<any[]>([])
const wsStatus = ref('disconnected')
const logRef = ref<HTMLElement | null>(null)

const currentRecord = ref<CheckRecord | null>(null)

// 分页配置
const pagination = reactive({
  currentPage: 1,
  pageSize: 15,
  total: 0
})

// 筛选表单
const filterForm = reactive({
  platform: '',
  hitStatus: '',
  timeRange: '',
  question: ''
})

// 对话框状态
const showAnswerDialog = ref(false)
const trendPlatform = ref('')

// 检测表单
const checkForm = ref({
  projectId: null as number | null,
  keywordId: null as number | null,
  platforms: ['doubao', 'qianwen', 'deepseek'],
})

// 平台授权状态相关
interface Platform {
  id: string
  name: string
  url: string
  color: string
  status?: string
}

const platformStatuses = ref<Platform[]>([])
const platformStatusesLoading = ref(false)
const availablePlatforms = ref<Platform[]>([
  { id: 'doubao', name: '豆包', url: 'https://www.doubao.com', color: '#FF6A00' },
  { id: 'deepseek', name: '深度求索', url: 'https://chat.deepseek.com', color: '#FF6A00' },
  { id: 'qianwen', name: '通义千问', url: 'https://qianwen.com', color: '#FF6A00' }
])

// 图表相关
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let socket: WebSocket | null = null

// 统计配置
const statConfigs = computed(() => [
  { label: '监测关键词', value: stats.value.total_keywords || 0, unit: '', class: 'stat-blue' },
  { label: '关键词命中', value: stats.value.keyword_found || 0, unit: '', class: 'stat-green' },
  { label: '公司名命中', value: stats.value.company_found || 0, unit: '', class: 'stat-orange' },
  { label: '总体命中率', value: stats.value.overall_hit_rate || 0, unit: '%', class: 'stat-purple' }
])

// 加载项目列表函数已移除，未使用

// 项目变化时加载关键词
const onProjectChange = async () => {
  checkForm.value.keywordId = null
  if (checkForm.value.projectId) {
    try {
      const result = await geoKeywordApi.getProjectKeywords(checkForm.value.projectId)
      keywords.value = result || []
    } catch (error) {
      console.error('加载关键词失败:', error)
    }
  }
}

// 加载检测记录
const loadRecords = async () => {
  recordsLoading.value = true
  try {
    // 处理日期范围
    let startDate: string | undefined
    let endDate: string | undefined
    
    if (filterForm.timeRange) {
      const now = new Date()
      const end = new Date()
      let start = new Date()
      
      if (filterForm.timeRange === '3days') {
        start.setDate(now.getDate() - 3)
      } else if (filterForm.timeRange === 'week') {
        start.setDate(now.getDate() - 7)
      } else if (filterForm.timeRange === 'month') {
        start.setMonth(now.getMonth() - 1)
      }
      
      startDate = start.toISOString().split('T')[0]
      endDate = end.toISOString().split('T')[0]
    }

    const result = await indexCheckApi.getRecords({
      limit: pagination.pageSize,
      skip: (pagination.currentPage - 1) * pagination.pageSize,
      platform: filterForm.platform || undefined,
      keyword_found: filterForm.hitStatus === 'keyword_found' ? true : undefined,
      company_found: filterForm.hitStatus === 'company_found' ? true : undefined,
      start_date: startDate,
      end_date: endDate,
      question: filterForm.question || undefined
    })
    
    // 兼容后端返回格式 (可能返回数组或带分页信息的对象)
    if (Array.isArray(result)) {
      records.value = result
      // 如果后端只返回数组，无法得知总数，暂时用当前数量代替（或者需要后端调整）
      // 这里假设后端已调整，返回 { total, items }
    } else if (result && result.items) {
      records.value = result.items
      pagination.total = result.total
    } else {
      records.value = []
      pagination.total = 0
    }
  } catch (error) {
    console.error('加载记录失败:', error)
    records.value = []
  } finally {
    recordsLoading.value = false
  }
}

// 筛选操作
const handleFilter = () => {
  pagination.currentPage = 1
  loadRecords()
}

const resetFilter = () => {
  filterForm.platform = ''
  filterForm.hitStatus = ''
  filterForm.timeRange = ''
  filterForm.question = ''
  handleFilter()
}

// 分页操作
const handleSizeChange = (val: number) => {
  pagination.pageSize = val
  loadRecords()
}

const handleCurrentChange = (val: number) => {
  pagination.currentPage = val
  loadRecords()
}

// 选择操作
const handleSelectionChange = (val: CheckRecord[]) => {
  selectedRecords.value = val
}

// 删除单条记录
const deleteRecord = async (row: CheckRecord) => {
  try {
    await indexCheckApi.deleteRecord(row.id)
    ElMessage.success('删除成功')
    loadRecords()
  } catch (error) {
    console.error('删除失败:', error)
    ElMessage.error('删除失败')
  }
}

// 批量删除
const batchDelete = async () => {
  if (selectedRecords.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRecords.value.length} 条记录吗？此操作不可恢复。`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    const ids = selectedRecords.value.map(item => item.id)
    await indexCheckApi.batchDeleteRecords(ids)
    
    ElMessage.success('批量删除成功')
    selectedRecords.value = [] // 清空选择
    loadRecords()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败')
    }
  }
}

// 加载统计数据
const loadStats = async () => {
  try {
    const res = await reportsApi.getOverview()
    stats.value = res.data || res || {}
  } catch (e) { console.error("加载卡片失败", e) }
}

// 执行检测
const runCheck = async () => {
  if (!checkForm.value.keywordId) {
    ElMessage.warning('请选择关键词')
    return
  }

  const project = projects.value.find(p => p.id === checkForm.value.projectId)
  if (!project) {
    ElMessage.warning('请选择项目')
    return
  }

  if (!checkForm.value.platforms || checkForm.value.platforms.length === 0) {
    ElMessage.warning('请选择至少一个检测平台')
    return
  }

  checking.value = true
  try {
    const result = await indexCheckApi.checkKeyword({
      keyword_id: checkForm.value.keywordId,
      company_name: project.company_name,
      platforms: checkForm.value.platforms,
    })

    if (result.success) {
      ElMessage.success('监测任务已提交，请等待日志更新')
      // 8秒后自动刷新数据
      setTimeout(refreshAllData, 8000)
    } else {
      ElMessage.error(result.message || '检测失败')
    }
  } catch (error) {
    console.error('检测失败:', error)
    ElMessage.error('检测失败')
  } finally {
    checking.value = false
  }
}

// 查看回答
const viewAnswer = (record: CheckRecord) => {
  currentRecord.value = record
  showAnswerDialog.value = true
}

// 获取平台名称
const getPlatformName = (platform: string) => {
  const names: Record<string, string> = {
    doubao: '豆包',
    qianwen: '通义千问',
    deepseek: 'DeepSeek',
  }
  return names[platform] || platform
}

// 获取平台标签类型
const getPlatformType = (platform: string) => {
  const types: Record<string, string> = {
    doubao: 'primary',
    qianwen: 'warning',
    deepseek: 'success',
  }
  return (types[platform] || 'info') as 'primary' | 'success' | 'warning' | 'danger' | 'info'
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  // 后端现在直接返回北京时间字符串，例如 "2026-02-02 23:39:00"
  // 我们直接解析并显示，不再做时区转换
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

// 加载趋势数据
const loadTrendData = async () => {
  try {
    const result = await reportsApi.getIndexTrend({ 
      days: 30,
      platform: trendPlatform.value || undefined
    })
    return result || []
  } catch (error) {
    console.error('加载趋势数据失败:', error)
    return []
  }
}

// 渲染图表
const renderChart = (data: any[]) => {
  if (!chartInstance) return

  // 处理空数据
  const safeData = Array.isArray(data) ? data : []
  
  const dates = safeData.map(d => d.date || '')
  
  // 计算命中率，如果总检测数为0，则命中率为null（断开连接）
  const totalChecks = safeData.map(d => d.total_checks || 0)
  
  const keywordRates = safeData.map(d => {
    const total = d.total_checks || 0
    if (total === 0) return null
    return parseFloat(((d.keyword_found_count || 0) / total * 100).toFixed(1))
  })
  
  const companyRates = safeData.map(d => {
    const total = d.total_checks || 0
    if (total === 0) return null
    return parseFloat(((d.company_found_count || 0) / total * 100).toFixed(1))
  })

  const option = {
        tooltip: {
          trigger: 'axis',
          formatter: function(params: any) {
            let result = params[0].name + '<br/>'
            params.forEach((item: any) => {
              let value = item.value
              if (value === null || value === undefined) value = '-'
              else if (item.seriesName.includes('率')) value += '%'
              else value += ' 次'
              
              result += item.marker + item.seriesName + ': ' + value + '<br/>'
            })
            return result
          },
          backgroundColor: 'rgba(45, 45, 45, 0.8)',
          borderColor: '#3a3a3a',
          textStyle: {
            color: '#dcdfe6'
          }
        },
        legend: {
          data: ['总检测数', '关键词命中率', '公司名命中率'],
          textStyle: {
            color: '#dcdfe6',
          },
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true,
          backgroundColor: 'transparent'
        },
        xAxis: {
          type: 'category',
          boundaryGap: true, // 柱状图需要true
          data: dates.length > 0 ? dates : ['无数据'],
          axisLabel: {
            color: '#dcdfe6',
          },
          axisLine: {
            lineStyle: {
              color: '#3a3a3a'
            }
          },
          splitLine: {
            show: false
          }
        },
        yAxis: [
          {
            type: 'value',
            name: '数量 (次)',
            position: 'left',
            axisLine: { 
              show: true,
              lineStyle: {
                color: '#3a3a3a'
              }
            },
            axisLabel: {
              color: '#dcdfe6',
              formatter: '{value}'
            },
            splitLine: {
              show: true,
              lineStyle: {
                type: 'dashed',
                color: '#3a3a3a'
              }
            }
          },
          {
            type: 'value',
            name: '命中率 (%)',
            position: 'right',
            min: 0,
            max: 100,
            axisLine: { 
              show: true,
              lineStyle: {
                color: '#3a3a3a'
              }
            },
            axisLabel: {
              color: '#dcdfe6',
              formatter: '{value} %'
            },
            splitLine: { show: false }
          }
        ],
        series: [
          {
            name: '总检测数',
            type: 'bar',
            yAxisIndex: 0,
            data: totalChecks.length > 0 ? totalChecks : [0],
            itemStyle: { 
              color: 'rgba(230, 162, 60, 0.6)',
              borderRadius: [4, 4, 0, 0]
            },
            barMaxWidth: 30
          },
          {
            name: '关键词命中率',
            type: 'line',
            yAxisIndex: 1,
            data: keywordRates.length > 0 ? keywordRates : [null],
            smooth: true,
            connectNulls: false, // 关键：断开空数据
            itemStyle: { color: '#67c23a' },
            lineStyle: { width: 3 },
            symbol: 'circle',
            symbolSize: 6
          },
          {
            name: '公司名命中率',
            type: 'line',
            yAxisIndex: 1,
            data: companyRates.length > 0 ? companyRates : [null],
            smooth: true,
            connectNulls: false, // 关键：断开空数据
            itemStyle: { color: '#409eff' },
            lineStyle: { width: 3 },
            symbol: 'circle',
            symbolSize: 6
          }
        ],
      }

  chartInstance.setOption(option)
}

// 加载并刷新图表
const loadTrendChart = async () => {
  const trendData = await loadTrendData()
  renderChart(trendData)
}

// 初始化图表
const initChart = async () => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  await loadTrendChart()
}

// 窗口大小变化时重绘图表
const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

// ==================== 平台授权状态相关方法 ====================

// 加载平台授权状态
const loadPlatformStatuses = async (forceRefresh = false) => {
  // 总是显示加载状态，确保用户知道正在刷新
  platformStatusesLoading.value = true
  
  try {
    // 这里应该从当前登录用户获取user_id，从路由参数或store获取project_id
    // 暂时使用固定值，实际应用中需要从上下文中获取
    const user_id = 1 // 示例值
    const project_id = 1 // 示例值

    // 构建基本平台状态列表，使用默认状态
    const initialStatuses = availablePlatforms.value.map(platform => ({
      ...platform,
      status: 'invalid'
    }))
    
    // 立即显示初始状态，减少用户等待时间
    if (platformStatuses.value.length === 0) {
      platformStatuses.value = initialStatuses
    }

    // 并行执行所有请求，提高效率
    const [, ...statusResponses] = await Promise.all([
      // 获取所有会话状态
      get('/auth/sessions', { user_id, project_id }).catch((err: any) => {
        console.error('获取会话列表失败:', err)
        return { success: false, data: { sessions: [] } }
      }),
      // 并行获取每个平台的状态
      ...availablePlatforms.value.map(platform => 
        get('/auth/session/status', {
          user_id,
          project_id,
          platform: platform.id,
          fast: !forceRefresh // 默认使用快速检查，只有点击刷新时才进行完整检查
        }).catch((err: any) => {
          console.error(`获取${platform.name}状态失败:`, err)
          return { success: false, data: { status: 'invalid' } }
        })
      )
    ])

    // 更新平台状态
    const updatedStatuses = availablePlatforms.value.map((platform, index) => {
      let status = 'invalid'

      // 从平台状态响应中获取更详细的状态（优先使用这个，因为包含心跳检测结果）
      const statusResponse = statusResponses[index]
      if (statusResponse.success && statusResponse.data) {
        status = statusResponse.data.status
      }

      return {
        ...platform,
        status
      }
    })

    platformStatuses.value = updatedStatuses
  } catch (err: any) {
    console.error('加载平台状态失败:', err)
    // 出错时不显示错误提示，避免影响用户体验
  } finally {
    platformStatusesLoading.value = false
  }
}

// 刷新平台授权状态
const refreshPlatformStatuses = () => {
  loadPlatformStatuses(true) // 传递 true 表示强制刷新（完整检查）
}

// 开始平台授权流程
const startPlatformAuthFlow = async (platformId: string) => {
  try {
    // 从实际上下文获取用户ID和项目ID
    const user_id = parseInt(localStorage.getItem('current_user_id') || '1')
    const project_id = parseInt(String(checkForm.value.projectId) || '1')

    // 开始授权流程，只授权指定平台
    const platforms = [platformId]
    
    // 调用后端API开始授权流程
    const response = await post('/auth/start-flow', {
      user_id,
      project_id,
      platforms
    })

    if (response.success) {
      const authSessionId = response.auth_session_id
      
      if (authSessionId) {
        const platformName = availablePlatforms.value.find(p => p.id === platformId)?.name
        ElMessage.success(`${platformName}平台授权流程已开始，请检查浏览器弹出的窗口`)
        
        // 开始该平台的授权
        await startSinglePlatformAuth(authSessionId, platformId)
      } else {
        ElMessage.error('开始授权流程失败：未返回授权会话ID')
      }
    } else {
      ElMessage.error(response.error || '开始授权流程失败')
    }
  } catch (err: any) {
    ElMessage.error(`请求失败: ${err.message || '未知错误'}`)
  }
}

// 开始单个平台的授权
const startSinglePlatformAuth = async (authSessionId: string, platform: string) => {
  try {
    // 调用后端API开始单个平台的授权
    const response = await post(`/auth/start-platform/${authSessionId}`, {}, {
      params: { platform }
    })

    if (response.success) {
      // 后端现在直接打开授权窗口，不需要前端打开窗口
      ElMessage.success(`授权窗口已打开，请完成登录操作`)
      
      // 不自动检查授权状态，让用户手动刷新
      // 这样可以避免浏览器窗口被过早关闭
    } else {
      ElMessage.error(response.error || '开始平台授权失败')
    }
  } catch (err: any) {
    ElMessage.error(`请求失败: ${err.message || '未知错误'}`)
  }
}

// 检查平台授权状态函数已移除，根据设计不自动检查授权状态，用户可通过手动刷新查看状态

// 获取状态文本
const getStatusText = (status: string | undefined) => {
  const statusMap: Record<string, string> = {
    'valid': '已授权',
    'expiring': '已授权', // 即将过期也视为已授权
    'invalid': '未授权',
    'error': '错误'
  }
  return statusMap[status || ''] || '未知'
}

// 获取状态标签类型
const getStatusType = (status: string | undefined) => {
  const typeMap: Record<string, string> = {
    'valid': 'success',
    'expiring': 'success', // 即将过期也使用成功标签
    'invalid': 'danger',
    'error': 'danger'
  }
  return (typeMap[status || ''] || 'info') as 'primary' | 'success' | 'warning' | 'danger' | 'info'
}

// 统一刷新方法
const refreshAllData = async () => {
  await loadStats()
  await loadRecords()
  await loadPlatformStatuses()
  await loadTrendChart()
}

// WebSocket (保持连接)
const initWebSocket = () => {
  const wsBaseUrl = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8001/ws'
  socket = new WebSocket(`${wsBaseUrl}?client_id=mon_${Math.random().toString(36).slice(-5)}`)
  socket.onopen = () => { wsStatus.value = 'connected' }
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data && data.message) {
        logs.value.push({ time: data.time || '', level: data.level || 'INFO', message: data.message })
        if (logs.value.length > 50) logs.value.shift()
        nextTick(() => { if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight })
      }
    } catch (e) {}
  }
  socket.onclose = () => { wsStatus.value = 'disconnected'; setTimeout(initWebSocket, 5000) }
}

// ==================== 生命周期 ====================
onMounted(async () => {
  const pRes = await geoKeywordApi.getProjects()
  projects.value = Array.isArray(pRes) ? pRes : (pRes as any)?.data || []
  await loadStats()
  await loadRecords()
  await loadPlatformStatuses()
  initialized.value = true // 显示页面
  nextTick(() => {
    initChart()
    initWebSocket()
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (socket) socket.close()
  if (chartInstance) chartInstance.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.monitor-page { padding: 20px; background: #1a1a1a; min-height: 100vh; color: #dcdfe6; }

/* 统计卡片 */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }
.stat-card { padding: 20px; border-radius: 12px; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
.stat-blue { background: linear-gradient(135deg, #409eff, #79bbff); }
.stat-green { background: linear-gradient(135deg, #67c23a, #95d475); }
.stat-orange { background: linear-gradient(135deg, #e6a23c, #eebe77); }
.stat-purple { background: linear-gradient(135deg, #909399, #b1b3b8); }
.stat-value { font-size: 28px; font-weight: bold; margin-bottom: 5px; }
.stat-label { font-size: 14px; opacity: 0.9; }

/* 通用 section 样式 */
.section { background: #252525; padding: 20px; border-radius: 8px; border: 1px solid #3a3a3a; margin-bottom: 20px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.section-title { font-size: 16px; font-weight: bold; margin: 0; color: #dcdfe6; }
.header-actions { display: flex; gap: 12px; }

/* 检测表单 */
.check-form { display: flex; flex-wrap: wrap; gap: 12px; }

/* 筛选工具栏样式 */
.filter-toolbar { margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #3a3a3a; }
.filter-form { display: flex; flex-wrap: wrap; gap: 8px; }
.filter-form .el-form-item { margin-bottom: 8px; margin-right: 12px; }
.filter-form .el-form-item__label { color: #dcdfe6; }
.filter-form .el-input__wrapper { background-color: #3a3a3a; border-color: #4a4a4a; }
.filter-form .el-input__input { color: #dcdfe6; }
.filter-form .el-select__wrapper { background-color: #3a3a3a; border-color: #4a4a4a; }
.filter-form .el-select__input { color: #dcdfe6; }
.filter-form .el-select__placeholder { color: #909399; }

/* 表格样式 */
.pagination-container { display: flex; justify-content: flex-end; margin-top: 16px; }
.el-table { background-color: #252525; border-color: #3a3a3a; }
.el-table th { background-color: #2d2d2d; color: #dcdfe6; border-color: #3a3a3a; }
.el-table td { background-color: #252525; color: #dcdfe6; border-color: #3a3a3a; }
.el-table tr:hover > td { background-color: #2d2d2d; }
.el-table__empty-text { color: #909399; }

/* 图表容器 */
.chart-container { width: 100%; height: 350px; }

/* 回答详情对话框 */
.answer-content { display: flex; flex-direction: column; gap: 16px; }
.answer-question { padding: 12px; background: #2d2d2d; border-radius: 8px; color: #dcdfe6; }
.answer-body strong { display: block; margin-bottom: 8px; color: #dcdfe6; }
.answer-body p { margin: 0; line-height: 1.8; color: #dcdfe6; white-space: pre-wrap; word-break: break-word; }
.answer-result { display: flex; gap: 12px; }

/* 平台授权状态样式 */
.platform-status-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(450px, 1fr)); gap: 20px; margin-bottom: 24px; }
.platform-status-card { display: flex; align-items: flex-start; padding: 20px; border: 1px solid #3a3a3a; border-radius: 8px; transition: all 0.3s ease; background: #fff; }
.platform-status-card:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
.platform-status-card.valid { border-color: #e6a23c; background-color: #fdf6ec; }
.platform-status-card.expiring { border-color: #e6a23c; background-color: #fdf6ec; }
.platform-status-card.invalid { border-color: #f56c6c; background-color: #fef0f0; }
.platform-icon { width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 16px; flex-shrink: 0; }
.platform-icon span { font-size: 20px; font-weight: 600; }
.platform-info { flex: 1; min-width: 0; }
.platform-info h4 { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 4px; }
.platform-info p { font-size: 12px; color: #606266; margin-bottom: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.status-info { display: flex; align-items: center; gap: 12px; }
.platform-actions { display: flex; flex-direction: column; gap: 8px; }

/* 实时日志 */
.log-section { height: fit-content; }
.log-console { height: 420px; background: #1a1a1a; color: #dcdfe6; padding: 10px; overflow-y: auto; font-family: 'Courier New', Courier, monospace; font-size: 12px; border-radius: 4px; }
.log-line { margin-bottom: 4px; border-bottom: 1px solid #2d2d2d; padding-bottom: 2px; }
.log-time { color: #888; margin-right: 8px; }
.log-line.SUCCESS { color: #67c23a; }
.log-line.ERROR { color: #f56c6c; }

/* 响应式设计 */
@media (max-width: 1200px) {
  .platform-status-list { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: 1fr; }
  
  .platform-status-card {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .platform-icon {
    margin-bottom: 12px;
  }
  
  .platform-info {
    margin-bottom: 16px;
  }
  
  .platform-actions {
    width: 100%;
    flex-direction: row;
  }
  
  .platform-actions .el-button {
    flex: 1;
  }
  
  .check-form {
    flex-direction: column;
  }
  
  .filter-form {
    flex-direction: column;
  }
}
</style>