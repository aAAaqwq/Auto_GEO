<template>
  <div class="feishu-bindings-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title">
        <h1>飞书用户绑定管理</h1>
        <p class="subtitle">管理飞书 open_id 到系统用户的绑定关系</p>
      </div>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        创建绑定
      </el-button>
    </div>

    <!-- 自服务绑定：用户输入自己的 ID 获取绑定码 -->
    <el-card class="self-bind-card">
      <template #header>
        <div class="card-header">
          <span>🔗 自服务绑定</span>
          <el-tag type="info">用户自助绑定飞书</el-tag>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="12">
          <div class="bind-step">
            <div class="step-number">1</div>
            <div class="step-content">
              <h4>生成绑定码</h4>
              <p>输入你的系统用户 ID，生成一个临时绑定码</p>
              <div style="display:flex;gap:8px;margin-top:8px">
                <el-input-number v-model="selfUserId" :min="1" placeholder="用户ID" style="width:140px" />
                <el-button type="primary" @click="generateCode" :loading="genLoading">
                  生成绑定码
                </el-button>
                <el-button @click="checkStatus" :loading="checkLoading">
                  检查绑定状态
                </el-button>
              </div>
              <div v-if="generatedCode" class="code-display">
                <div class="code-text">{{ generatedCode }}</div>
                <div class="code-hint">请在飞书中发送：<strong>绑定 {{ generatedCode }}</strong></div>
                <div class="code-expire">有效期至：{{ codeExpiresAt }}</div>
              </div>
              <div v-if="bindStatus !== null" class="status-display">
                <el-alert
                  :title="bindStatus.is_bound ? '✅ 已绑定飞书' : '❌ 未绑定飞书'"
                  :type="bindStatus.is_bound ? 'success' : 'warning'"
                  :closable="false"
                  show-icon
                >
                  <template v-if="bindStatus.is_bound">
                    <p>绑定用户：{{ bindStatus.binding?.username }}</p>
                    <p>飞书 Open ID：{{ bindStatus.binding?.open_id }}</p>
                  </template>
                </el-alert>
              </div>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="bind-step">
            <div class="step-number">2</div>
            <div class="step-content">
              <h4>在飞书中完成绑定</h4>
              <p>打开飞书，向 AutoGEO 机器人发送：</p>
              <el-alert type="info" :closable="false" style="margin-top:8px">
                <template #title>
                  <code style="font-size:16px">绑定 &lt;绑定码&gt;</code>
                </template>
              </el-alert>
              <p style="margin-top:8px;color:#909399">
                例如：<code>绑定 ABC123</code>
              </p>
              <p style="margin-top:4px;color:#909399">
                绑定成功后，你就可以在飞书中直接发送指令生成和发布文章了。
              </p>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 绑定列表 -->
    <el-card class="bindings-table-card">
      <template #header>
        <div class="card-header">
          <span>绑定列表（共 {{ total }} 条）</span>
          <el-button :icon="Refresh" @click="fetchBindings" :loading="loading" circle />
        </div>
      </template>

      <el-table :data="bindings" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="open_id" label="飞书 Open ID" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.open_id" placement="top">
              <span class="mono-text">{{ row.open_id }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="系统用户" width="120" />
        <el-table-column prop="system_user_id" label="用户ID" width="80" />
        <el-table-column prop="default_project_name" label="默认项目" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.default_project_name" type="success" size="small">
              {{ row.default_project_name }}
            </el-tag>
            <span v-else class="text-muted">未设置</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '已绑定' : '已解绑' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="绑定时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editBinding(row)">
              编辑
            </el-button>
            <el-button
              v-if="row.status === 1"
              link
              type="danger"
              size="small"
              @click="deleteBinding(row)"
            >
              解绑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑绑定对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingBinding ? '编辑绑定' : '创建绑定'"
      width="500px"
      @close="resetForm"
    >
      <el-form :model="form" label-width="120px" ref="formRef">
        <el-form-item label="飞书 Open ID" required>
          <el-input
            v-model="form.open_id"
            placeholder="输入飞书用户的 open_id"
            :disabled="!!editingBinding"
          />
        </el-form-item>
        <el-form-item label="系统用户 ID" required>
          <el-input-number
            v-model="form.system_user_id"
            :min="1"
            placeholder="输入系统用户ID"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="默认项目">
          <el-input-number
            v-model="form.default_project_id"
            :min="0"
            placeholder="可选，默认项目ID"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="默认客户">
          <el-input-number
            v-model="form.default_client_id"
            :min="0"
            placeholder="可选，默认客户ID"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingBinding ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

// 状态
const loading = ref(false)
const submitting = ref(false)
const genLoading = ref(false)
const checkLoading = ref(false)
const showCreateDialog = ref(false)
const editingBinding = ref<any>(null)
const bindings = ref<any[]>([])
const total = ref(0)

// 自服务绑定
const selfUserId = ref(1)
const generatedCode = ref('')
const codeExpiresAt = ref('')
const bindStatus = ref<any>(null)

// 表单
const form = reactive({
  open_id: '',
  system_user_id: 1,
  default_project_id: undefined as number | undefined,
  default_client_id: undefined as number | undefined,
})

// API 基础路径
const API_BASE = '/api/feishu'

// 获取绑定列表
async function fetchBindings() {
  loading.value = true
  try {
    const resp = await axios.get(`${API_BASE}/bindings`)
    const data = resp.data?.data || {}
    bindings.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    ElMessage.error('获取绑定列表失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

// 创建/更新绑定
async function submitForm() {
  if (!form.open_id || !form.system_user_id) {
    ElMessage.warning('请填写飞书 Open ID 和系统用户 ID')
    return
  }
  submitting.value = true
  try {
    if (editingBinding.value) {
      // 更新
      await axios.put(`${API_BASE}/bindings/${editingBinding.value.id}`, {
        default_project_id: form.default_project_id || null,
        default_client_id: form.default_client_id || null,
      })
      ElMessage.success('绑定已更新')
    } else {
      // 创建
      await axios.post(`${API_BASE}/bindings`, {
        open_id: form.open_id,
        system_user_id: form.system_user_id,
        default_project_id: form.default_project_id || null,
        default_client_id: form.default_client_id || null,
      })
      ElMessage.success('绑定创建成功')
    }
    showCreateDialog.value = false
    fetchBindings()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

// 编辑绑定
function editBinding(row: any) {
  editingBinding.value = row
  form.open_id = row.open_id
  form.system_user_id = row.system_user_id
  form.default_project_id = row.default_project_id
  form.default_client_id = row.default_client_id
  showCreateDialog.value = true
}

// 删除绑定
async function deleteBinding(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定要解除用户「${row.username || row.open_id}」的飞书绑定吗？解除后该用户将无法通过飞书触发任务。`,
      '确认解绑',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.delete(`${API_BASE}/bindings/${row.id}`)
    ElMessage.success('绑定已解除')
    fetchBindings()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('解绑失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

// 重置表单
function resetForm() {
  editingBinding.value = null
  form.open_id = ''
  form.system_user_id = 1
  form.default_project_id = undefined
  form.default_client_id = undefined
}

// 格式化时间
function formatTime(iso: string | null): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

// 生成绑定码
async function generateCode() {
  if (!selfUserId.value) {
    ElMessage.warning('请输入用户ID')
    return
  }
  genLoading.value = true
  try {
    const resp = await axios.post(`${API_BASE}/bindings/generate-code/${selfUserId.value}`)
    const data = resp.data?.data || {}
    generatedCode.value = data.code
    codeExpiresAt.value = data.expires_at ? new Date(data.expires_at).toLocaleString('zh-CN') : ''
    ElMessage.success(data.message || '绑定码已生成')
  } catch (e: any) {
    ElMessage.error('生成失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    genLoading.value = false
  }
}

// 检查绑定状态
async function checkStatus() {
  if (!selfUserId.value) {
    ElMessage.warning('请输入用户ID')
    return
  }
  checkLoading.value = true
  try {
    const resp = await axios.get(`${API_BASE}/bindings/my-status/${selfUserId.value}`)
    bindStatus.value = resp.data?.data || null
    if (bindStatus.value?.is_bound) {
      ElMessage.success('该用户已绑定飞书')
    } else {
      ElMessage.warning('该用户尚未绑定飞书')
    }
  } catch (e: any) {
    ElMessage.error('查询失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    checkLoading.value = false
  }
}

// 加载
onMounted(() => {
  fetchBindings()
})
</script>

<style scoped>
.feishu-bindings-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-title h1 {
  margin: 0;
  font-size: 22px;
  color: var(--el-text-color-primary);
}

.subtitle {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.bindings-table-card {
  margin-top: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mono-text {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.text-muted {
  color: var(--el-text-color-placeholder);
}

.self-bind-card {
  margin-bottom: 20px;
}

.bind-step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 2px;
}

.step-content h4 {
  margin: 0 0 4px;
  font-size: 15px;
}

.step-content p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.code-display {
  margin-top: 16px;
  padding: 16px;
  background: var(--el-color-success-light-9);
  border-radius: 8px;
  text-align: center;
}

.code-text {
  font-size: 32px;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  color: var(--el-color-success);
  letter-spacing: 8px;
  margin-bottom: 8px;
}

.code-hint {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-bottom: 4px;
}

.code-expire {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.status-display {
  margin-top: 16px;
}
</style>
