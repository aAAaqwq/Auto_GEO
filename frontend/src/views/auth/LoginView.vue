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
.login-page {
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.login-container {
  display: flex;
  width: 1000px;
  height: 600px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

// 左侧装饰区
.login-decoration {
  flex: 1;
  background: linear-gradient(135deg, rgba(74, 144, 226, 0.3) 0%, rgba(103, 178, 111, 0.2) 100%);
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
    background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
    animation: pulse 4s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.5; }
    50% { transform: scale(1.1); opacity: 0.8; }
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
  gap: 16px;
  margin-bottom: 16px;

  .logo-icon {
    font-size: 48px;
  }

  .logo-text {
    font-size: 36px;
    font-weight: 700;
    background: linear-gradient(135deg, #4a90e2, #67b26f);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
}

.slogan {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 40px;
}

.features {
  display: flex;
  flex-direction: column;
  gap: 16px;
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;

  .el-icon {
    color: #67b26f;
    font-size: 18px;
  }
}

// 右侧登录表单
.login-form-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.login-form-container {
  width: 100%;
  max-width: 360px;
}

.form-title {
  font-size: 28px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 8px 0;
  text-align: center;
}

.form-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 32px 0;
  text-align: center;
}

.login-form {
  .el-input {
    --el-input-bg-color: rgba(255, 255, 255, 0.1);
    --el-input-text-color: #ffffff;
    --el-input-border-color: rgba(255, 255, 255, 0.2);
    --el-input-hover-border-color: rgba(74, 144, 226, 0.8);
    --el-input-focus-border-color: #4a90e2;
    --el-input-placeholder-color: rgba(255, 255, 255, 0.4);

    :deep(.el-input__wrapper) {
      background-color: var(--el-input-bg-color);
      border-radius: 10px;
      box-shadow: none !important;
      border: 1px solid var(--el-input-border-color);
      padding: 4px 16px;
      height: 48px;

      &:hover {
        border-color: var(--el-input-hover-border-color);
      }

      &.is-focus {
        border-color: var(--el-input-focus-border-color);
      }
    }

    :deep(.el-input__inner) {
      color: var(--el-input-text-color);
      font-size: 15px;
    }

    :deep(.el-input__icon) {
      color: rgba(255, 255, 255, 0.5);
    }
  }
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;

  :deep(.el-checkbox__label) {
    color: rgba(255, 255, 255, 0.8);
  }

  :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
    color: #4a90e2;
  }

  :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
    background-color: #4a90e2;
    border-color: #4a90e2;
  }
}

.login-button {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 500;
  border-radius: 10px;
  background: linear-gradient(135deg, #4a90e2, #357abd);
  border: none;
  transition: all 0.3s ease;

  &:hover {
    background: linear-gradient(135deg, #5a9fe2, #4a90e2);
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(74, 144, 226, 0.4);
  }

  &:active {
    transform: translateY(0);
  }
}

.version-info {
  margin-top: 24px;
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}

// 响应式设计
@media (max-width: 900px) {
  .login-container {
    width: 90%;
    height: auto;
    flex-direction: column;
  }

  .login-decoration {
    padding: 30px;
    min-height: 200px;
  }

  .logo-large {
    .logo-icon {
      font-size: 36px;
    }

    .logo-text {
      font-size: 28px;
    }
  }

  .slogan {
    font-size: 16px;
    margin-bottom: 24px;
  }

  .features {
    display: none;
  }

  .login-form-wrapper {
    padding: 30px;
  }
}

@media (max-width: 480px) {
  .login-decoration {
    padding: 20px;
    min-height: 150px;
  }

  .logo-large {
    .logo-icon {
      font-size: 28px;
    }

    .logo-text {
      font-size: 24px;
    }
  }

  .slogan {
    font-size: 14px;
    margin-bottom: 16px;
  }

  .login-form-wrapper {
    padding: 20px;
  }
}
</style>
