<template>
  <div class="admin-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title">
        <h1>系统管理</h1>
        <p class="subtitle">管理系统配置、用户和服务状态</p>
      </div>
    </div>

    <!-- 管理员标签页 -->
    <el-tabs v-model="activeTab" type="border-card" class="admin-tabs">
      <!-- 系统配置 -->
      <el-tab-pane label="系统配置" name="config">
        <template #label>
          <span class="tab-label">
            <el-icon><Setting /></el-icon>
            系统配置
          </span>
        </template>

        <div class="tab-content">
          <el-card class="config-card">
            <template #header>
              <div class="card-header">
                <span>数据库配置</span>
                <el-tag :type="dbStatus.type">{{ dbStatus.text }}</el-tag>
              </div>
            </template>

            <el-form
              ref="configFormRef"
              :model="configForm"
              :rules="configRules"
              label-position="top"
            >
              <el-form-item label="数据库连接字符串" prop="database_url">
                <el-input
                  v-model="configForm.database_url"
                  placeholder="请输入数据库连接字符串"
                  type="textarea"
                  :rows="3"
                />
              </el-form-item>

              <el-form-item>
                <el-button
                  type="primary"
                  :loading="testingDb"
                  @click="testDatabaseConnection"
                >
                  <el-icon><Connection /></el-icon>
                  测试连接
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card class="config-card">
            <template #header>
              <div class="card-header">
                <span>服务端口配置</span>
              </div>
            </template>

            <el-form :model="configForm" label-position="top">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="API 服务端口">
                    <el-input-number
                      v-model="configForm.api_port"
                      :min="1024"
                      :max="65535"
                      controls-position="right"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="WebSocket 服务端口">
                    <el-input-number
                      v-model="configForm.ws_port"
                      :min="1024"
                      :max="65535"
                      controls-position="right"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card class="config-card">
            <template #header>
              <div class="card-header">
                <span>其他配置</span>
              </div>
            </template>

            <el-form :model="configForm" label-position="top">
              <el-form-item label="日志级别">
                <el-select v-model="configForm.log_level" style="width: 100%">
                  <el-option label="DEBUG" value="debug" />
                  <el-option label="INFO" value="info" />
                  <el-option label="WARNING" value="warning" />
                  <el-option label="ERROR" value="error" />
                </el-select>
              </el-form-item>

              <el-form-item label="最大上传文件大小 (MB)">
                <el-input-number
                  v-model="configForm.max_upload_size"
                  :min="1"
                  :max="1000"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </el-form>
          </el-card>

          <div class="form-actions">
            <el-button
              type="primary"
              size="large"
              :loading="savingConfig"
              @click="saveConfig"
            >
              <el-icon><Check /></el-icon>
              保存配置
            </el-button>
            <el-button
              size="large"
              @click="resetConfig"
            >
              <el-icon><RefreshRight /></el-icon>
              重置
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <template #label>
          <span class="tab-label">
            <el-icon><User /></el-icon>
            用户管理
          </span>
        </template>

        <div class="tab-content">
          <div class="toolbar">
            <el-input
              v-model="userSearchKeyword"
              placeholder="搜索用户名/昵称/邮箱"
              clearable
              style="width: 300px"
              @keyup.enter="searchUsers"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>

            <el-select
              v-model="userRoleFilter"
              placeholder="角色筛选"
              clearable
              style="width: 120px"
              @change="searchUsers"
            >
              <el-option label="全部" value="" />
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>

            <el-select
              v-model="userStatusFilter"
              placeholder="状态筛选"
              clearable
              style="width: 120px"
              @change="searchUsers"
            >
              <el-option label="全部" value="" />
              <el-option label="启用" :value="1" />
              <el-option label="禁用" :value="0" />
            </el-select>

            <el-button type="primary" @click="showCreateUserDialog">
              <el-icon><Plus /></el-icon>
              新增用户
            </el-button>
          </div>

          <el-table
            :data="userList"
            v-loading="loadingUsers"
            stripe
            border
            class="user-table"
          >
            <el-table-column type="index" width="60" align="center" />
            <el-table-column prop="username" label="用户名" width="120" />
            <el-table-column prop="nickname" label="昵称" width="120">
              <template #default="{ row }">
                {{ row.nickname || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="180">
              <template #default="{ row }">
                {{ row.email || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : ''">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'danger'">
                  {{ row.status === 1 ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="editUser(row)"
                >
                  编辑
                </el-button>
                <el-button
                  :type="row.status === 1 ? 'warning' : 'success'"
                  link
                  size="small"
                  @click="toggleUserStatus(row)"
                >
                  {{ row.status === 1 ? '禁用' : '启用' }}
                </el-button>
                <el-button
                  type="danger"
                  link
                  size="small"
                  @click="deleteUser(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="userPage"
              v-model:page-size="userPageSize"
              :total="userTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @size-change="searchUsers"
              @current-change="searchUsers"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- 服务监控 -->
      <el-tab-pane label="服务监控" name="monitor">
        <template #label>
          <span class="tab-label">
            <el-icon><Monitor /></el-icon>
            服务监控
          </span>
        </template>

        <div class="tab-content">
          <!-- 服务状态卡片 -->
          <el-row :gutter="20" class="status-cards">
            <el-col :span="6">
              <el-card class="status-card" :class="{ 'status-running': serviceStatus.status === 'running' }">
                <div class="status-icon">
                  <el-icon :size="40" :color="serviceStatus.status === 'running' ? '#67c23a' : '#f56c6c'">
                    <CircleCheck v-if="serviceStatus.status === 'running'" />
                    <CircleClose v-else />
                  </el-icon>
                </div>
                <div class="status-info">
                  <div class="status-title">服务状态</div>
                  <div class="status-value" :class="serviceStatus.status">
                    {{ serviceStatus.status === 'running' ? '运行中' : serviceStatus.status === 'stopped' ? '已停止' : '异常' }}
                  </div>
                </div>
              </el-card>
            </el-col>

            <el-col :span="6">
              <el-card class="status-card">
                <div class="status-icon">
                  <el-icon :size="40" color="#409eff"><Timer /></el-icon>
                </div>
                <div class="status-info">
                  <div class="status-title">运行时间</div>
                  <div class="status-value">{{ formatUptime(serviceStatus.uptime) }}</div>
                </div>
              </el-card>
            </el-col>

            <el-col :span="6">
              <el-card class="status-card">
                <div class="status-icon">
                  <el-icon :size="40" color="#e6a23c"><Cpu /></el-icon>
                </div>
                <div class="status-info">
                  <div class="status-title">CPU 使用率</div>
                  <div class="status-value">{{ serviceStatus.cpu_usage.toFixed(1) }}%</div>
                </div>
              </el-card>
            </el-col>

            <el-col :span="6">
              <el-card class="status-card">
                <div class="status-icon">
                  <el-icon :size="40" color="#67c23a"><DataAnalysis /></el-icon>
                </div>
                <div class="status-info">
                  <div class="status-title">内存使用</div>
                  <div class="status-value">{{ formatMemory(serviceStatus.memory_usage) }}</div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 服务控制按钮 -->
          <el-card class="control-card">
            <template #header>
              <div class="card-header">
                <span>服务控制</span>
              </div>
            </template>

            <div class="control-buttons">
              <el-button
                type="danger"
                size="large"
                :loading="restarting"
                :disabled="serviceStatus.status !== 'running'"
                @click="restartService"
              >
                <el-icon><Refresh /></el-icon>
                重启服务
              </el-button>

              <el-button
                type="warning"
                size="large"
                :disabled="serviceStatus.status !== 'running'"
                @click="stopService"
              >
                <el-icon><VideoPause /></el-icon>
                停止服务
              </el-button>

              <el-button
                type="success"
                size="large"
                :disabled="serviceStatus.status === 'running'"
                @click="startService"
              >
                <el-icon><VideoPlay /></el-icon>
                启动服务
              </el-button>
            </div>

            <div class="version-info">
              <span>版本: {{ serviceStatus.version }}</span>
              <span>进程ID: {{ serviceStatus.pid }}</span>
            </div>
          </el-card>

          <!-- 系统日志 -->
          <el-card class="logs-card">
            <template #header>
              <div class="card-header">
                <span>系统日志</span>
                <el-button type="danger" link @click="clearLogs">
                  <el-icon><Delete /></el-icon>
                  清空日志
                </el-button>
              </div>
            </template>

            <div class="logs-toolbar">
              <el-select v-model="logLevel" placeholder="日志级别" clearable style="width: 120px">
                <el-option label="全部" value="" />
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARNING" value="warning" />
                <el-option label="ERROR" value="error" />
              </el-select>

              <el-button type="primary" @click="loadLogs">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>

            <div class="logs-content" v-loading="loadingLogs">
              <div
                v-for="(log, index) in logs"
                :key="index"
                class="log-item"
                :class="log.level"
              >
                <span class="log-time">{{ formatDate(log.timestamp) }}</span>
                <span class="log-level" :class="log.level">{{ log.level.toUpperCase() }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>

              <el-empty v-if="logs.length === 0" description="暂无日志" />
            </div>

            <div class="pagination-wrapper">
              <el-pagination
                v-model:current-page="logPage"
                v-model:page-size="logPageSize"
                :total="logTotal"
                :page-sizes="[50, 100, 200, 500]"
                layout="total, sizes, prev, pager, next"
                @size-change="loadLogs"
                @current-change="loadLogs"
              />
            </div>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑用户对话框 -->
    <el-dialog
      v-model="userDialogVisible"
      :title="editingUser ? '编辑用户' : '创建用户'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="userFormRef"
        :model="userForm"
        :rules="userFormRules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="userForm.username"
            placeholder="请输入用户名"
            :disabled="!!editingUser"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password" v-if="!editingUser">
          <el-input
            v-model="userForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>

        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="userForm.nickname" placeholder="请输入昵称" />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="userForm.role">
            <el-radio label="admin">管理员</el-radio>
            <el-radio label="user">普通用户</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="userForm.status">
            <el-radio :label="1">启用</el-radio>
            <el-radio :label="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="saveUser">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  Setting,
  User,
  Monitor,
  CircleCheck,
  CircleClose,
  Timer,
  Cpu,
  DataAnalysis,
  Refresh,
  VideoPause,
  VideoPlay,
  Delete,
  Search,
  Plus,
  Connection,
  Check,
  RefreshRight,
} from '@element-plus/icons-vue'
import {
  getSystemConfig,
  updateSystemConfig,
  testDatabaseConnection as testDbApi,
  getUserList,
  createUser,
  updateUser,
  deleteUser as deleteUserApi,
  toggleUserStatus as toggleUserStatusApi,
  getServiceStatus,
  restartService as restartServiceApi,
  stopService as stopServiceApi,
  startService as startServiceApi,
  getSystemLogs,
  clearSystemLogs as clearLogsApi,
} from '@/services/userApi'

// ==================== 标签页 ====================
const activeTab = ref('config')

// ==================== 系统配置 ====================
const configFormRef = ref<FormInstance>()
const configForm = reactive({
  database_url: '',
  api_port: 8001,
  ws_port: 8002,
  log_level: 'info',
  max_upload_size: 100,
})

const configRules: FormRules = {
  database_url: [
    { required: true, message: '请输入数据库连接字符串', trigger: 'blur' },
  ],
}

const dbStatus = reactive({
  type: 'info' as 'success' | 'warning' | 'info' | 'danger',
  text: '未检测',
})

const testingDb = ref(false)
const savingConfig = ref(false)

// 加载配置
async function loadConfig() {
  try {
    const result = await getSystemConfig()
    if (result.success && result.data) {
      Object.assign(configForm, result.data)
      dbStatus.type = 'success'
      dbStatus.text = '已连接'
    }
  } catch (error) {
    ElMessage.error('加载配置失败')
  }
}

// 测试数据库连接
async function testDatabaseConnection() {
  if (!configForm.database_url) {
    ElMessage.warning('请输入数据库连接字符串')
    return
  }

  testingDb.value = true
  try {
    const result = await testDbApi({ database_url: configForm.database_url })
    if (result.success) {
      dbStatus.type = 'success'
      dbStatus.text = '连接成功'
      ElMessage.success('数据库连接成功')
    } else {
      dbStatus.type = 'danger'
      dbStatus.text = '连接失败'
      ElMessage.error(result.message || '连接失败')
    }
  } finally {
    testingDb.value = false
  }
}

// 保存配置
async function saveConfig() {
  if (!configFormRef.value) return

  await configFormRef.value.validate(async (valid) => {
    if (!valid) return

    savingConfig.value = true
    try {
      const result = await updateSystemConfig(configForm)
      if (result.success) {
        ElMessage.success('配置保存成功')
      } else {
        ElMessage.error(result.message || '保存失败')
      }
    } finally {
      savingConfig.value = false
    }
  })
}

// 重置配置
function resetConfig() {
  loadConfig()
}

// ==================== 用户管理 ====================
const userSearchKeyword = ref('')
const userRoleFilter = ref('')
const userStatusFilter = ref<number | ''>('')
const userPage = ref(1)
const userPageSize = ref(20)
const userTotal = ref(0)
const userList = ref<any[]>([])
const loadingUsers = ref(false)

// 用户对话框
const userDialogVisible = ref(false)
const userFormRef = ref<FormInstance>()
const editingUser = ref<any>(null)
const savingUser = ref(false)

const userForm = reactive({
  username: '',
  password: '',
  nickname: '',
  email: '',
  role: 'user' as 'admin' | 'user',
  status: 1,
})

const userFormRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应为 3-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: !editingUser.value, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应为 6-20 个字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
}

// 搜索用户
async function searchUsers() {
  loadingUsers.value = true
  try {
    const result = await getUserList({
      page: userPage.value,
      pageSize: userPageSize.value,
      keyword: userSearchKeyword.value,
      role: userRoleFilter.value,
      status: userStatusFilter.value === '' ? undefined : userStatusFilter.value,
    })
    if (result.success && result.data) {
      userList.value = result.data.items
      userTotal.value = result.data.total
    }
  } finally {
    loadingUsers.value = false
  }
}

// 显示创建用户对话框
function showCreateUserDialog() {
  editingUser.value = null
  Object.assign(userForm, {
    username: '',
    password: '',
    nickname: '',
    email: '',
    role: 'user',
    status: 1,
  })
  userDialogVisible.value = true
}

// 编辑用户
function editUser(user: any) {
  editingUser.value = user
  Object.assign(userForm, {
    username: user.username,
    password: '',
    nickname: user.nickname || '',
    email: user.email || '',
    role: user.role,
    status: user.status,
  })
  userDialogVisible.value = true
}

// 保存用户
async function saveUser() {
  if (!userFormRef.value) return

  await userFormRef.value.validate(async (valid) => {
    if (!valid) return

    savingUser.value = true
    try {
      if (editingUser.value) {
        // 更新用户
        const result = await updateUser(editingUser.value.id, {
          nickname: userForm.nickname,
          email: userForm.email,
          role: userForm.role,
          status: userForm.status,
        })
        if (result.success) {
          ElMessage.success('用户更新成功')
          userDialogVisible.value = false
          searchUsers()
        } else {
          ElMessage.error(result.message || '更新失败')
        }
      } else {
        // 创建用户
        const result = await createUser(userForm)
        if (result.success) {
          ElMessage.success('用户创建成功')
          userDialogVisible.value = false
          searchUsers()
        } else {
          ElMessage.error(result.message || '创建失败')
        }
      }
    } finally {
      savingUser.value = false
    }
  })
}

// 切换用户状态
async function toggleUserStatus(user: any) {
  try {
    await ElMessageBox.confirm(
      `确定要${user.status === 1 ? '禁用' : '启用'}用户 "${user.username}" 吗？`,
      '确认操作',
      { type: 'warning' }
    )

    const result = await toggleUserStatusApi(user.id, user.status === 1 ? 0 : 1)
    if (result.success) {
      ElMessage.success('操作成功')
      searchUsers()
    } else {
      ElMessage.error(result.message || '操作失败')
    }
  } catch {
    // 用户取消
  }
}

// 删除用户
async function deleteUser(user: any) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？此操作不可恢复！`,
      '确认删除',
      { type: 'danger' }
    )

    const result = await deleteUserApi(user.id)
    if (result.success) {
      ElMessage.success('删除成功')
      searchUsers()
    } else {
      ElMessage.error(result.message || '删除失败')
    }
  } catch {
    // 用户取消
  }
}

// ==================== 服务监控 ====================
const serviceStatus = reactive({
  status: 'stopped' as 'running' | 'stopped' | 'error',
  uptime: 0,
  version: '1.0.0',
  pid: 0,
  memory_usage: 0,
  cpu_usage: 0,
})

const restarting = ref(false)

// 加载服务状态
async function loadServiceStatus() {
  try {
    const result = await getServiceStatus()
    if (result.success && result.data) {
      Object.assign(serviceStatus, result.data)
    }
  } catch (error) {
    serviceStatus.status = 'error'
  }
}

// 重启服务
async function restartService() {
  restarting.value = true
  try {
    const result = await restartServiceApi()
    if (result.success) {
      ElMessage.success('服务重启成功')
      setTimeout(loadServiceStatus, 2000)
    } else {
      ElMessage.error(result.message || '重启失败')
    }
  } finally {
    restarting.value = false
  }
}

// 停止服务
async function stopService() {
  try {
    await ElMessageBox.confirm('确定要停止服务吗？', '确认操作', { type: 'warning' })
    const result = await stopServiceApi()
    if (result.success) {
      ElMessage.success('服务已停止')
      loadServiceStatus()
    } else {
      ElMessage.error(result.message || '操作失败')
    }
  } catch {
    // 用户取消
  }
}

// 启动服务
async function startService() {
  const result = await startServiceApi()
  if (result.success) {
    ElMessage.success('服务已启动')
    setTimeout(loadServiceStatus, 2000)
  } else {
    ElMessage.error(result.message || '启动失败')
  }
}

// ==================== 系统日志 ====================
const logs = ref<any[]>([])
const logLevel = ref('')
const logPage = ref(1)
const logPageSize = ref(50)
const logTotal = ref(0)
const loadingLogs = ref(false)

// 加载日志
async function loadLogs() {
  loadingLogs.value = true
  try {
    const result = await getSystemLogs({
      level: logLevel.value,
      limit: logPageSize.value,
      offset: (logPage.value - 1) * logPageSize.value,
    })
    if (result.success && result.data) {
      logs.value = result.data.items
      logTotal.value = result.data.total
    }
  } finally {
    loadingLogs.value = false
  }
}

// 清空日志
async function clearLogs() {
  try {
    await ElMessageBox.confirm('确定要清空所有日志吗？', '确认操作', { type: 'warning' })
    const result = await clearLogsApi()
    if (result.success) {
      ElMessage.success('日志已清空')
      loadLogs()
    } else {
      ElMessage.error(result.message || '清空失败')
    }
  } catch {
    // 用户取消
  }
}

// ==================== 工具函数 ====================
function formatDate(date: string) {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

function formatUptime(seconds: number) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) return `${days}天 ${hours}小时`
  if (hours > 0) return `${hours}小时 ${minutes}分钟`
  return `${minutes}分钟`
}

function formatMemory(bytes: number) {
  const mb = bytes / 1024 / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  return `${(mb / 1024).toFixed(2)} GB`
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadConfig()
  searchUsers()
  loadServiceStatus()
  loadLogs()
})
</script>

<style scoped lang="scss">
.admin-page {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;

  h1 {
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 8px 0;
    color: var(--text-primary);
  }

  .subtitle {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
  }
}

.admin-tabs {
  background: transparent;
  border: none;

  :deep(.el-tabs__header) {
    background: var(--bg-secondary);
    border-radius: 8px 8px 0 0;
    border: 1px solid var(--border);
    border-bottom: none;
    margin: 0;
  }

  :deep(.el-tabs__content) {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-top: none;
    border-radius: 0 0 8px 8px;
    padding: 24px;
  }
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// 配置卡片
.config-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);

  :deep(.el-card__header) {
    background: rgba(74, 144, 226, 0.1);
    border-bottom: 1px solid var(--border);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    span {
      font-weight: 500;
      color: var(--text-primary);
    }
  }
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-start;
  margin-top: 8px;
}

// 用户管理
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.user-table {
  :deep(th) {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    font-weight: 500;
  }

  :deep(td) {
    color: var(--text-secondary);
  }
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

// 服务监控
.status-cards {
  margin-bottom: 20px;
}

.status-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 20px;
  gap: 16px;

  &.status-running {
    border-color: rgba(103, 194, 58, 0.3);
    background: rgba(103, 194, 58, 0.05);
  }
}

.status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-info {
  flex: 1;
}

.status-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.status-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);

  &.running {
    color: #67c23a;
  }

  &.stopped {
    color: #909399;
  }

  &.error {
    color: #f56c6c;
  }
}

.control-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  margin-bottom: 20px;

  :deep(.el-card__header) {
    background: rgba(74, 144, 226, 0.1);
    border-bottom: 1px solid var(--border);
  }
}

.control-buttons {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.version-info {
  display: flex;
  gap: 24px;
  color: var(--text-secondary);
  font-size: 14px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

// 日志
.logs-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);

  :deep(.el-card__header) {
    background: rgba(74, 144, 226, 0.1);
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.logs-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.logs-content {
  background: #1a1a1a;
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.log-item {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);

  &:last-child {
    border-bottom: none;
  }

  .log-time {
    color: #888;
    flex-shrink: 0;
    min-width: 150px;
  }

  .log-level {
    flex-shrink: 0;
    min-width: 60px;
    font-weight: bold;

    &.debug {
      color: #909399;
    }

    &.info {
      color: #409eff;
    }

    &.warning {
      color: #e6a23c;
    }

    &.error {
      color: #f56c6c;
    }
  }

  .log-message {
    color: #ccc;
    flex: 1;
  }
}

// 响应式
@media (max-width: 1200px) {
  .status-cards .el-col {
    width: 50%;
    margin-bottom: 20px;
  }
}

@media (max-width: 768px) {
  .status-cards .el-col {
    width: 100%;
  }

  .toolbar {
    flex-wrap: wrap;
  }

  .control-buttons {
    flex-wrap: wrap;
  }
}
</style>
