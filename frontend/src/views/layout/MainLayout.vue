<template>
  <div class="main-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <span class="logo-icon" aria-hidden="true">
            <span class="logo-mark-core">G</span>
            <span class="logo-spark logo-spark-a"></span>
            <span class="logo-spark logo-spark-b"></span>
          </span>
          <span class="logo-text">AutoGeo</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <el-menu
          :default-active="activeMenuKey"
          :collapse="false"
          :unique-opened="true"
          class="sidebar-menu"
          router
        >
          <template v-for="route in menuRoutes" :key="route.name">
            <!-- 有子菜单的情况 -->
            <el-sub-menu v-if="route.children && route.children.length > 0" :index="route.path">
              <template #title>
                <el-icon>
                  <component :is="route.meta?.icon" />
                </el-icon>
                <span>{{ route.meta?.title }}</span>
              </template>
              <el-menu-item
                v-for="child in route.children"
                :key="child.name"
                :index="child.path"
              >
                <el-icon>
                  <component :is="child.meta?.icon" />
                </el-icon>
                <span>{{ child.meta?.title }}</span>
              </el-menu-item>
            </el-sub-menu>

            <!-- 无子菜单的情况 -->
            <el-menu-item v-else :index="route.path">
              <el-icon>
                <component :is="route.meta?.icon" />
              </el-icon>
              <span>{{ route.meta?.title }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </nav>

      <!-- 用户信息区域 -->
      <div class="sidebar-footer">
        <div class="user-info">
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-trigger">
              <el-avatar :size="32" class="user-avatar">
                {{ userStore.displayName.charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="user-details">
                <span class="user-name">{{ userStore.displayName }}</span>
                <span class="user-role">{{ userStore.isAdmin ? '管理员' : '普通用户' }}</span>
              </div>
              <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item command="changePassword">
                  <el-icon><Lock /></el-icon>
                  修改密码
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 顶部栏 -->
      <header class="header">
        <div class="header-left">
          <h1 class="page-title">{{ currentPageTitle }}</h1>
        </div>
        <div class="header-right">
          <el-button text @click="minimizeWindow">
            <el-icon><Minus /></el-icon>
          </el-button>
          <el-button text @click="maximizeWindow">
            <el-icon><FullScreen /></el-icon>
          </el-button>
          <el-button text @click="closeWindow">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="page-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="changePasswordDialogVisible"
      title="修改密码"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="changePasswordFormRef"
        :model="changePasswordForm"
        :rules="changePasswordRules"
        label-width="100px"
      >
        <el-form-item label="原密码" prop="oldPassword">
          <el-input
            v-model="changePasswordForm.oldPassword"
            type="password"
            placeholder="请输入原密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="changePasswordForm.newPassword"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="changePasswordForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="changePasswordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  Minus,
  FullScreen,
  Close,
  ArrowDown,
  User,
  Lock,
  SwitchButton,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/modules/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 构建菜单路由结构（支持子菜单）
const menuRoutes = computed(() => {
  const allRoutes = router.getRoutes()
    .filter(r => r.path.startsWith('/') && !r.meta?.hidden && !r.meta?.roles)

  // 分离父路由和子路由
  const parentRoutes = allRoutes.filter(r => !r.meta?.parent)
  const childRoutes = allRoutes.filter(r => r.meta?.parent)

  // 按order排序
  parentRoutes.sort((a, b) => (Number(a.meta?.order ?? 999)) - (Number(b.meta?.order ?? 999)))

  // 构建带子菜单的路由结构
  return parentRoutes.map(parentRoute => {
    // 查找当前路由的子路由
    const children = childRoutes
      .filter(r => r.meta?.parent === parentRoute.name)
      .sort((a, b) => (Number(a.meta?.order ?? 999)) - (Number(b.meta?.order ?? 999)))

    return {
      ...parentRoute,
      children: children.length > 0 ? children : undefined
    }
  })
})

// 当前激活的菜单key —— 去掉开头 / 以匹配 el-menu-item 的 index
const activeMenuKey = computed(() => {
  return route.path.replace(/^\//, '')
})

// 当前页面标题
const currentPageTitle = computed(() => {
  return route.meta?.title || 'AutoGeo'
})

// 窗口控制
const minimizeWindow = () => {
  window.electronAPI?.minimizeWindow()
}

const maximizeWindow = () => {
  window.electronAPI?.maximizeWindow()
}

const closeWindow = () => {
  window.electronAPI?.closeWindow()
}

// 用户下拉菜单命令处理
function handleUserCommand(command: string) {
  switch (command) {
    case 'profile':
      ElMessage.info('个人资料功能开发中')
      break
    case 'changePassword':
      changePasswordDialogVisible.value = true
      break
    case 'logout':
      handleLogout()
      break
  }
}

// 登出处理
async function handleLogout() {
  try {
    await userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } catch {
    ElMessage.error('退出失败')
  }
}

// 修改密码
const changePasswordDialogVisible = ref(false)
const changePasswordFormRef = ref<FormInstance>()
const changingPassword = ref(false)

const changePasswordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value !== changePasswordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const changePasswordRules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应为 6-20 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleChangePassword() {
  if (!changePasswordFormRef.value) return

  await changePasswordFormRef.value.validate(async (valid) => {
    if (!valid) return

    changingPassword.value = true
    try {
      const result = await userStore.changePassword(
        changePasswordForm.oldPassword,
        changePasswordForm.newPassword
      )
      if (result.success) {
        ElMessage.success('密码修改成功')
        changePasswordDialogVisible.value = false
        // 清空表单
        changePasswordFormRef.value?.resetFields()
      } else {
        ElMessage.error(result.message || '密码修改失败')
      }
    } finally {
      changingPassword.value = false
    }
  })
}
</script>

<style scoped lang="scss">
/* ================================================================
   MainLayout — Sidebar + Header + Content
   ================================================================ */

.main-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  background:
    radial-gradient(ellipse at 20% 0%, rgba(212, 168, 83, 0.10), transparent 30%),
    radial-gradient(ellipse at 85% 10%, rgba(110, 184, 214, 0.07), transparent 28%),
    linear-gradient(180deg, rgba(255, 246, 230, 0.03), transparent 50%),
    var(--surface-root);
  color: var(--text-body);
  position: relative;
  isolation: isolate;
}

.main-layout::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: -1;
  opacity: 0.38;
  background-image:
    linear-gradient(rgba(200, 185, 160, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(200, 185, 160, 0.03) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: linear-gradient(90deg, black, transparent 70%);
}

// ---- Sidebar ----
.sidebar {
  width: 248px;
  background:
    radial-gradient(circle at 28px 30px, rgba(212, 168, 83, 0.12), transparent 32px),
    linear-gradient(180deg, rgba(255, 246, 230, 0.05), transparent 210px),
    linear-gradient(90deg, rgba(212, 168, 83, 0.08), transparent 70%),
    rgba(37, 34, 29, 0.94);
  border-right: 1px solid var(--border-thin);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  box-shadow: 14px 0 42px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);

  .sidebar-header {
    padding: 22px 18px 18px;
    border-bottom: 1px solid var(--border-thin);

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;

      .logo-icon {
        width: 38px;
        height: 38px;
        border: 1px solid var(--border-soft);
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background:
          radial-gradient(circle at 72% 24%, rgba(255, 255, 255, 0.82), transparent 0 3px, transparent 4px),
          linear-gradient(135deg, var(--accent-hover), var(--accent-amber) 58%, var(--accent-blue));
        color: var(--accent-ink);
        font-family: var(--font-display);
        font-size: 19px;
        font-weight: 900;
        line-height: 1;
        position: relative;
        box-shadow:
          0 12px 28px rgba(212, 168, 83, 0.20),
          inset 0 1px 0 rgba(255, 255, 255, 0.38);
        overflow: hidden;
      }

      .logo-icon::before {
        content: '';
        position: absolute;
        inset: 7px;
        border: 1px solid rgba(6, 29, 34, 0.34);
        border-radius: 9px;
        transform: rotate(12deg);
      }

      .logo-mark-core {
        position: relative;
        z-index: 1;
      }

      .logo-spark {
        position: absolute;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #fff8d9;
        box-shadow: 0 0 10px #fff8d9;
      }

      .logo-spark-a {
        right: 7px;
        top: 7px;
      }

      .logo-spark-b {
        left: 8px;
        bottom: 8px;
        width: 3px;
        height: 3px;
      }

      .logo-text {
        font-family: var(--font-display);
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.01em;
        background: linear-gradient(135deg, #fef8ec 0%, var(--accent-hover) 50%, var(--accent-amber) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
    }
  }

  .sidebar-nav {
    flex: 1;
    padding: 12px 10px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;

    .sidebar-menu {
      border: none;
      background: transparent;

      .el-menu-item,
      .el-sub-menu__title {
        height: 42px;
        line-height: 42px;
        color: var(--text-muted);
        border-radius: var(--radius-md);
        margin: 3px 0;
        font-size: 13px;
        font-weight: 500;
        letter-spacing: 0.01em;
        transition: all var(--duration-fast) var(--ease-out);

        &:hover {
          background: rgba(255, 255, 255, 0.075) !important;
          color: var(--text-head);
        }

        .el-icon {
          font-size: 18px;
          margin-right: 2px;
          color: rgba(216, 228, 238, 0.76);
          transition: color var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out);
        }

        &:hover .el-icon {
          color: var(--accent-hover);
          transform: translateY(-1px);
        }
      }

      .el-menu-item.is-active {
        background:
          linear-gradient(90deg, rgba(212, 168, 83, 0.20), rgba(110, 184, 214, 0.08)) !important;
        color: var(--accent-hover);
        font-weight: 600;
        box-shadow:
          inset 0 0 0 1px rgba(212, 168, 83, 0.16),
          0 6px 18px rgba(212, 168, 83, 0.08);

        &::before {
          content: '';
          position: absolute;
          left: 0;
          top: 10px;
          bottom: 10px;
          width: 3px;
          background: var(--accent);
          border-radius: 0 3px 3px 0;
        }

        .el-icon {
          color: var(--accent-hover);
        }
      }

      .el-sub-menu {
        .el-menu {
          background: transparent;
        }

        .el-menu-item {
          padding-left: 48px !important;
          font-size: 12px;
          height: 38px;
          line-height: 38px;
        }
      }
    }
  }

  // User area
.sidebar-footer {
    padding: 12px;
    border-top: 1px solid var(--border-thin);
  }

  .user-info {
    .user-trigger {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid transparent;
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: background var(--duration-fast) var(--ease-out);

      &:hover {
        background: var(--surface-hover);
        border-color: var(--border-soft);
      }
    }

    .user-avatar {
      background: linear-gradient(135deg, var(--accent), var(--accent-amber));
      color: var(--accent-ink);
      font-weight: 600;
      flex-shrink: 0;
    }

    .user-details {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;

      .user-name {
        font-size: 13px;
        font-weight: 500;
        color: var(--text-head);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.3;
      }

      .user-role {
        font-size: 11px;
        color: var(--text-muted);
        line-height: 1.3;
      }
    }

    .dropdown-icon {
      color: var(--text-muted);
      font-size: 11px;
      transition: color var(--duration-fast);
    }
  }
}

// ---- Main Content Area ----
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

// ---- Header ----
.header {
  height: 60px;
  background: rgba(28, 25, 21, 0.78);
  border-bottom: 1px solid var(--border-thin);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  flex-shrink: 0;
  backdrop-filter: blur(16px);

  .header-left {
    .page-title {
      margin: 0;
      font-family: var(--font-display);
      font-size: 17px;
      font-weight: 600;
      color: var(--text-head);
      letter-spacing: -0.01em;
    }
  }

  .header-right {
    display: flex;
    gap: 4px;

    .el-button {
      color: var(--text-muted);
      width: 36px;
      height: 36px;
      border-radius: var(--radius-sm);

      &:hover {
        color: var(--text-head);
        background: var(--surface-hover);
      }
    }
  }
}

// ---- Page Content ----
.page-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: transparent;
  padding: 0;
}

// ---- Route Transition ----
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-fast) ease, transform var(--duration-fast) ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
