<template>
  <div class="auth-flow-container">
    <div class="auth-flow-header">
      <h2>AI平台授权</h2>
      <p>通过浏览器扩展将您本地浏览器中的登录状态同步到后端，后端使用您的 Cookie 执行收录检测</p>
    </div>

    <div class="auth-step">
      <div class="extension-sync-banner">
        <div class="banner-header">
          <span class="banner-icon">🔗</span>
          <div>
            <h4>授权方式：浏览器扩展同步</h4>
            <p>不需要后端弹浏览器窗口 — 在您自己的 Chrome 里登录平台，扩展自动捕获 Cookie 传给后端</p>
          </div>
        </div>
        <div class="banner-actions">
          <a :href="downloadUrl" class="btn btn-download btn-sm" target="_blank">
            下载扩展 (.zip)
          </a>
          <button class="btn btn-outline btn-sm" @click="showExtensionGuide = !showExtensionGuide">
            {{ showExtensionGuide ? '收起说明' : '如何操作？' }}
          </button>
          <button class="btn btn-primary btn-sm" @click="checkExtensionSync">
            检查同步状态
          </button>
        </div>
        <div v-if="showExtensionGuide" class="extension-guide">
          <div class="guide-step">
            <span class="step-number">1</span>
            <div>
              <strong>下载并安装扩展</strong>
              <p>点击 <a :href="downloadUrl" target="_blank">下载扩展 (.zip)</a>，解压后，打开 Chrome 访问 <code>chrome://extensions/</code>，开启"开发者模式"，点击"加载已解压的扩展"，选择解压后的 <code>cookie-sync</code> 文件夹</p>
            </div>
          </div>
          <div class="guide-step">
            <span class="step-number">2</span>
            <div>
              <strong>打开平台并登录</strong>
              <p>点击下方各平台的"打开平台"按钮，在新标签页中完成登录（扫码或账号密码）</p>
            </div>
          </div>
          <div class="guide-step">
            <span class="step-number">3</span>
            <div>
              <strong>点击同步</strong>
              <p>登录成功后，点击页面右下角的蓝色悬浮按钮，或点击浏览器工具栏的扩展图标 → "同步"</p>
            </div>
          </div>
        </div>
      </div>

      <h3>平台授权状态</h3>
      <div class="auth-status-list">
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
              <span class="status-badge" :class="platform.status">
                {{ getStatusText(platform.status) }}
              </span>
              <span v-if="platform.age_info" class="age-info">
                {{ getAgeText(platform.age_info) }}
              </span>
            </div>
          </div>
          <div class="platform-actions">
            <button class="btn btn-outline btn-sm" @click="openPlatformUrl(platform)">
              打开平台
            </button>
            <button
              class="btn btn-primary btn-sm"
              @click="checkSinglePlatform(platform.id)"
            >
              检查状态
            </button>
            <button
              v-if="platform.status !== 'invalid'"
              class="btn btn-sm"
              style="color: #dc3545; border-color: #dc3545;"
              @click="deleteSession(platform.id)"
            >
              取消授权
            </button>
          </div>
        </div>
      </div>
      <div class="auth-actions">
        <button class="btn btn-outline" @click="syncAllPlatforms">
          一键同步（打开所有平台触发自动同步）
        </button>
        <button class="btn btn-secondary" @click="refreshStatus">
          刷新状态
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="auth-error">
      <div class="error-icon">!</div>
      <div class="error-content">
        <h4>提示</h4>
        <p>{{ error }}</p>
        <button class="btn btn-sm btn-outline" @click="clearError">
          关闭
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="auth-loading">
      <div class="loading-spinner"></div>
      <p>{{ loadingMessage || '处理中...' }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { get, del } from '@/services/api'

const availablePlatforms = [
  { id: 'doubao', name: '豆包', url: 'https://www.doubao.com', color: '#0066FF' },
  { id: 'deepseek', name: '深度求索', url: 'https://chat.deepseek.com', color: '#4D6BFE' },
  { id: 'qianwen', name: '通义千问', url: 'https://qianwen.com', color: '#FF6A00' }
]

const platformStatuses = ref([])
const loading = ref(false)
const loadingMessage = ref('')
const error = ref('')
const showExtensionGuide = ref(true)

const downloadUrl = import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL.replace('/api', '/static/cookie-sync-extension.zip')
  : 'http://192.168.150.1:8001/static/cookie-sync-extension.zip'

const getStatusText = (status) => {
  const statusMap = {
    'valid': '已授权',
    'expiring': '即将过期',
    'invalid': '未授权',
  }
  return statusMap[status] || status
}

const getAgeText = (ageInfo) => {
  if (!ageInfo) return ''
  if (ageInfo.age_days && ageInfo.age_days >= 1) {
    return `${ageInfo.age_days}天前授权`
  } else if (ageInfo.age_hours && ageInfo.age_hours >= 1) {
    return `${ageInfo.age_hours}小时前授权`
  } else {
    return '刚刚授权'
  }
}

const clearError = () => { error.value = '' }

const openPlatformUrl = (platform) => {
  window.open(platform.url, '_blank')
}

const deleteSession = async (platformId) => {
  const platform = platformStatuses.value.find(p => p.id === platformId)
  if (!confirm(`确定要取消 ${platform?.name || platformId} 的授权吗？`)) return

  try {
    await del('/auth/session', {
      user_id: 1,
      project_id: 1,
      platform: platformId,
    })
    // 刷新状态
    const idx = platformStatuses.value.findIndex(p => p.id === platformId)
    if (idx > -1) {
      platformStatuses.value[idx].status = 'invalid'
      platformStatuses.value[idx].age_info = null
    }
    error.value = `已取消 ${platform?.name || platformId} 的授权`
    setTimeout(() => { error.value = '' }, 3000)
  } catch (err) {
    error.value = `取消失败: ${err.message || '未知错误'}`
  }
}

const loadPlatformStatuses = async () => {
  loading.value = true
  loadingMessage.value = '加载授权状态...'
  error.value = ''

  const user_id = 1
  const project_id = 1

  try {
    const response = await get('/auth/sessions', { user_id, project_id })

    if (response.success) {
      const sessions = response.data.sessions || []
      const sessionMap = {}
      sessions.forEach(s => { sessionMap[s.platform] = s })

      const statuses = availablePlatforms.map(platform => {
        const session = sessionMap[platform.id]
        return {
          ...platform,
          status: session ? 'valid' : 'invalid',
          age_info: session?.age_info
        }
      })

      for (const st of statuses) {
        try {
          const res = await get('/auth/session/status', {
            user_id, project_id, platform: st.id
          })
          if (res.success) {
            st.status = res.data.status
            st.age_info = res.data.age_info
          }
        } catch (e) { /* ignore */ }
      }

      platformStatuses.value = statuses
    }
  } catch (err) {
    error.value = `加载失败: ${err.message || '未知错误'}`
  } finally {
    loading.value = false
    loadingMessage.value = ''
  }
}

const refreshStatus = async () => {
  loading.value = true
  loadingMessage.value = '正在请求扩展同步Cookie...'

  // 通知后端：前端需要同步
  try {
    await get('/auth/request-sync')
  } catch (e) { /* ignore */ }

  // 等扩展轮询到请求并完成同步（扩展每5秒轮询一次）
  await new Promise(r => setTimeout(r, 6000))

  loadingMessage.value = '正在检查授权状态...'
  await loadPlatformStatuses()
  loading.value = false
  loadingMessage.value = ''
}

const syncAllPlatforms = () => {
  const invalidPlatforms = platformStatuses.value.filter(p => p.status !== 'valid')
  if (invalidPlatforms.length === 0) {
    error.value = '所有平台已授权'
    setTimeout(() => { error.value = '' }, 3000)
    return
  }
  for (const p of invalidPlatforms) {
    window.open(p.url, '_blank')
  }
  error.value = `已打开 ${invalidPlatforms.length} 个平台，登录后自动同步`
  setTimeout(() => { error.value = '' }, 5000)
}

const checkExtensionSync = async () => {
  loading.value = true
  loadingMessage.value = '检查同步状态...'

  try {
    await loadPlatformStatuses()
    const synced = platformStatuses.value.filter(p => p.status === 'valid')
    if (synced.length > 0) {
      error.value = `${synced.map(p => p.name).join('、')} 已授权`
    } else {
      error.value = '尚未同步，请在浏览器中登录平台后点击扩展的同步按钮'
    }
    setTimeout(() => { error.value = '' }, 5000)
  } catch (err) {
    error.value = `检查失败: ${err.message}`
  } finally {
    loading.value = false
    loadingMessage.value = ''
  }
}

const checkSinglePlatform = async (platformId) => {
  loading.value = true
  loadingMessage.value = `检查 ${platformId} 状态...`

  try {
    const res = await get('/auth/session/status', {
      user_id: 1, project_id: 1, platform: platformId
    })
    if (res.success) {
      const idx = platformStatuses.value.findIndex(p => p.id === platformId)
      if (idx > -1) {
        platformStatuses.value[idx].status = res.data.status
        platformStatuses.value[idx].age_info = res.data.age_info
      }
      error.value = `${platformId}: ${getStatusText(res.data.status)}`
    }
    setTimeout(() => { error.value = '' }, 3000)
  } catch (err) {
    error.value = `检查失败: ${err.message}`
  } finally {
    loading.value = false
    loadingMessage.value = ''
  }
}

onMounted(() => { loadPlatformStatuses() })
</script>

<style scoped>
/* ================================================================
   AuthFlow — Unified Dark Theme
   ================================================================ */

.auth-flow-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
  background: var(--surface-raised);
  border: 1px solid var(--border-thin);
  border-radius: var(--radius-lg);
}

.auth-flow-header { text-align: center; margin-bottom: 32px; }
.auth-flow-header h2 { font-family: var(--font-display); font-size: 24px; font-weight: 600; color: var(--text-head); margin-bottom: 8px; }
.auth-flow-header p { font-size: 14px; color: var(--text-muted); }

.auth-step { margin-bottom: 32px; }
.auth-step h3 { font-size: 18px; font-weight: 600; color: var(--text-head); margin-bottom: 20px; }

/* Extension sync banner */
.extension-sync-banner {
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-bottom: 28px;
}
.extension-sync-banner .banner-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.extension-sync-banner .banner-icon { font-size: 28px; flex-shrink: 0; }
.extension-sync-banner h4 { font-size: 15px; font-weight: 600; color: var(--text-head); margin-bottom: 4px; }
.extension-sync-banner p { font-size: 13px; color: var(--text-muted); margin: 0; }
.banner-actions { display: flex; gap: 10px; justify-content: flex-end; }
.extension-guide { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-soft); }
.guide-step { display: flex; gap: 12px; margin-bottom: 14px; align-items: flex-start; }
.guide-step:last-child { margin-bottom: 0; }
.step-number {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--accent); color: #fff; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px;
}
.guide-step strong { display: block; font-size: 13px; color: var(--text-head); margin-bottom: 2px; }
.guide-step p { font-size: 12px; color: var(--text-muted); margin: 0; }
.guide-step code { background: var(--surface-field); padding: 1px 6px; border-radius: 3px; font-size: 11px; color: var(--text-body); }
.guide-step a { color: var(--accent); text-decoration: underline; font-weight: 500; }

/* Platform status cards */
.auth-status-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; margin-bottom: 32px; }
.platform-status-card { display: flex; align-items: flex-start; padding: 20px; border: 1px solid var(--border-soft); border-radius: var(--radius-md); transition: all var(--duration-fast); background: var(--surface-field); }
.platform-status-card:hover { border-color: var(--border-hover); }
.platform-status-card.valid { border-color: var(--success); background: var(--success-soft); }
.platform-status-card.expiring { border-color: var(--warning); background: var(--warning-soft); }
.platform-status-card.invalid { border-color: var(--danger); background: var(--danger-soft); }

.platform-icon { width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 16px; flex-shrink: 0; }
.platform-icon span { font-size: 20px; font-weight: 600; }

.platform-info { flex: 1; }
.platform-info h4 { font-size: 16px; font-weight: 600; color: var(--text-head); margin-bottom: 4px; }
.platform-info p { font-size: 12px; color: var(--text-muted); margin: 0; }

.status-info { display: flex; align-items: center; gap: 12px; }
.age-info { font-size: 12px; color: var(--text-muted); }
.platform-actions { display: flex; flex-direction: column; gap: 8px; }

/* Status badges */
.status-badge { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.status-badge.valid { background: var(--success-soft); color: var(--success); }
.status-badge.expiring { background: var(--warning-soft); color: var(--warning); }
.status-badge.invalid { background: var(--danger-soft); color: var(--danger); }

/* Buttons */
.auth-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px; }
.btn { padding: 10px 20px; border: none; border-radius: var(--radius-sm); font-size: 14px; font-weight: 500; cursor: pointer; transition: all var(--duration-fast); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-primary:disabled { background: var(--surface-field); color: var(--text-disabled); cursor: not-allowed; }
.btn-secondary { background: var(--surface-field); color: var(--text-body); border: 1px solid var(--border-soft); }
.btn-secondary:hover { background: var(--surface-hover); }
.btn-outline { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
.btn-outline:hover { background: var(--accent); color: #fff; }
.btn-download { background: var(--success); color: #fff; text-decoration: none; display: inline-block; }
.btn-download:hover { background: #3da870; }
.btn-sm { padding: 6px 12px; font-size: 12px; }

/* Error */
.auth-error { display: flex; align-items: flex-start; padding: 16px; background: var(--danger-soft); border: 1px solid var(--danger); border-radius: var(--radius-sm); margin-bottom: 20px; }
.auth-error .error-icon { font-size: 18px; font-weight: 600; color: var(--danger); margin-right: 12px; flex-shrink: 0; }
.auth-error .error-content { flex: 1; }
.auth-error h4 { font-size: 14px; font-weight: 600; color: var(--danger); margin-bottom: 4px; }
.auth-error p { font-size: 14px; color: var(--text-body); margin-bottom: 12px; }

/* Loading */
.auth-loading {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(8, 12, 20, 0.85);
  display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 1000;
}
.loading-spinner { width: 40px; height: 40px; border: 3px solid var(--border-soft); border-top: 3px solid var(--accent); border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 16px; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.auth-loading p { font-size: 14px; color: #666; }

/* 响应式 */
@media (max-width: 768px) {
  .auth-flow-container { padding: 16px; margin: 16px; }
  .auth-status-list { grid-template-columns: 1fr; }
  .platform-status-card { flex-direction: column; align-items: flex-start; }
  .platform-icon { margin-bottom: 12px; }
  .platform-info { margin-bottom: 16px; }
  .platform-actions { width: 100%; flex-direction: row; }
  .platform-actions .btn { flex: 1; }
  .auth-actions { flex-direction: column; }
  .auth-actions .btn { width: 100%; }
}
</style>
