<template>
  <div class="login-page">
    <div class="login-container">
      <!-- 左侧装饰区 -->
      <div class="login-decoration">
        <div class="decoration-content">
          <div class="logo-large">
            <span class="logo-icon">🚀</span>
            <span class="logo-text">AutoGeo</span>
          </div>
          <p class="slogan">智能多平台文章发布助手</p>
          <div class="features">
            <div class="feature-item">
              <el-icon><Check /></el-icon>
              <span>智能 GEO 文章生成</span>
            </div>
            <div class="feature-item">
              <el-icon><Check /></el-icon>
              <span>多平台一键发布</span>
            </div>
            <div class="feature-item">
              <el-icon><Check /></el-icon>
              <span>收录状态实时监控</span>
            </div>
            <div class="feature-item">
              <el-icon><Check /></el-icon>
              <span>定时任务自动执行</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧登录表单 -->
      <div class="login-form-wrapper">
        <div class="login-form-container">
          <h2 class="form-title">欢迎登录</h2>
          <p class="form-subtitle">请使用您的账号密码登录系统</p>

          <el-form
            ref="formRef"
            :model="formData"
            :rules="formRules"
            class="login-form"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="formData.username"
                placeholder="请输入用户名"
                size="large"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="formData.password"
                type="password"
                placeholder="请输入密码"
                size="large"
                :prefix-icon="Lock"
                show-password
                clearable
              />
            </el-form-item>

            <el-form-item>
              <div class="form-options">
                <el-checkbox v-model="formData.remember">记住密码</el-checkbox>
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="showForgotPassword"
                >
                  忘记密码？
                </el-button>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                class="login-button"
                :loading="userStore.loading"
                @click="handleLogin"
              >
                {{ userStore.loading ? '登录中...' : '登 录' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <span class="no-account">还没有账号？</span>
            <el-button type="primary" link @click="router.push('/register')">
              去注册
            </el-button>
          </div>

          <div class="version-info">
            <span>Version 1.0.0</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 忘记密码对话框 -->
    <el-dialog
      v-model="forgotPasswordVisible"
      title="忘记密码"
      width="400px"
      :close-on-click-modal="false"
    >
      <p>请联系系统管理员重置密码</p>
      <template #footer>
        <el-button @click="forgotPasswordVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { User, Lock, Check } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/modules/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 表单引用
const formRef = ref<FormInstance>()

// 忘记密码对话框
const forgotPasswordVisible = ref(false)

// 表单数据
const formData = reactive({
  username: '',
  password: '',
  remember: false,
})

// 表单验证规则
const formRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应为 3-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应为 6-20 个字符', trigger: 'blur' },
  ],
}

// 加载本地保存的用户名
onMounted(() => {
  const rememberedUser = localStorage.getItem('autogeo_remember_username')
  if (rememberedUser) {
    formData.username = rememberedUser
    formData.remember = true
  }
})

/**
 * 处理登录
 */
async function handleLogin() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    const result = await userStore.login({
      username: formData.username,
      password: formData.password,
      remember: formData.remember,
    })

    if (result.success) {
      ElMessage.success('登录成功')

      // 如果记住密码，保存用户名
      if (formData.remember) {
        localStorage.setItem('autogeo_remember_username', formData.username)
      } else {
        localStorage.removeItem('autogeo_remember_username')
      }

      // 跳转到首页或重定向地址
      const redirect = route.query.redirect as string
      router.push(redirect || '/dashboard')
    } else {
      ElMessage.error(result.message || '登录失败')
    }
  })
}

/**
 * 显示忘记密码对话框
 */
function showForgotPassword() {
  forgotPasswordVisible.value = true
}
</script>

<style scoped lang="scss">
/* ================================================================
   Login — Refined Dark Theme
   ================================================================ */

.login-page {
  width: 100vw;
  height: 100vh;
  background: var(--surface-root);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.login-container {
  display: flex;
  width: 960px;
  height: 580px;
  background: var(--surface-raised);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--border-thin);
}

// ---- Left Decorative Panel ----
.login-decoration {
  flex: 1;
  background: linear-gradient(135deg, rgba(94, 163, 240, 0.15) 0%, rgba(67, 185, 127, 0.08) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(94, 163, 240, 0.06) 0%, transparent 70%);
    animation: pulse 6s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.4; }
    50% { transform: scale(1.08); opacity: 0.7; }
  }
}

.decoration-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.logo-large {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: 14px;

  .logo-icon { font-size: 44px; }

  .logo-text {
    font-family: var(--font-display);
    font-size: 34px;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, var(--accent), var(--success));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.slogan {
  font-size: 16px;
  color: var(--text-muted);
  margin-bottom: 36px;
}

.features {
  display: flex;
  flex-direction: column;
  gap: 14px;
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-body);
  font-size: 13px;

  .el-icon { color: var(--success); font-size: 17px; }
}

// ---- Right Form Panel ----
.login-form-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.login-form-container {
  width: 100%;
  max-width: 340px;
}

.form-title {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 700;
  color: var(--text-head);
  margin: 0 0 6px 0;
  text-align: center;
  letter-spacing: -0.01em;
}

.form-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 32px 0;
  text-align: center;
}

.login-form {
  .el-input {
    :deep(.el-input__wrapper) {
      background: var(--surface-field) !important;
      border-radius: var(--radius-sm);
      box-shadow: none !important;
      border: 1px solid var(--border-soft) !important;
      padding: 4px 16px;
      height: 48px;
      transition: all var(--duration-fast) var(--ease-out);

      &:hover { border-color: var(--border-hover) !important; }

      &.is-focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-soft) !important;
      }
    }

    :deep(.el-input__inner) { color: var(--text-body); font-size: 15px; }
    :deep(.el-input__icon) { color: var(--text-muted); }
  }
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;

  :deep(.el-checkbox__label) { color: var(--text-muted); font-size: 13px; }
  :deep(.el-checkbox__input.is-checked + .el-checkbox__label) { color: var(--accent); }
  :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
    background-color: var(--accent);
    border-color: var(--accent);
  }
}

.login-button {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  background: var(--accent);
  border: none;
  letter-spacing: 0.04em;
  transition: all var(--duration-normal) var(--ease-out);

  &:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow);
  }

  &:active { transform: translateY(0); }
}

.form-footer {
  text-align: center;
  margin-top: 20px;

  .no-account {
    color: var(--text-muted);
    font-size: 13px;
    margin-right: 4px;
  }
}

.version-info {
  margin-top: 28px;
  text-align: center;
  color: var(--text-disabled);
  font-size: 11px;
}

// ---- Responsive ----
@media (max-width: 900px) {
  .login-container {
    width: 90%;
    height: auto;
    flex-direction: column;
  }

  .login-decoration { padding: 28px; min-height: 180px; }

  .logo-large {
    .logo-icon { font-size: 34px; }
    .logo-text { font-size: 26px; }
  }

  .slogan { font-size: 14px; margin-bottom: 20px; }
  .features { display: none; }

  .login-form-wrapper { padding: 28px; }
}

@media (max-width: 480px) {
  .login-decoration { padding: 18px; min-height: 130px; }

  .logo-large {
    .logo-icon { font-size: 26px; }
    .logo-text { font-size: 22px; }
  }

  .slogan { font-size: 12px; margin-bottom: 12px; }
  .login-form-wrapper { padding: 18px; }
}
</style>
