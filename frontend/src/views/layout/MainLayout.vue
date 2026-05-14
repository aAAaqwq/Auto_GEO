<template>
  <div class="main-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <span class="logo-icon">🚀</span>
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

// 当前激活的菜单key
const activeMenuKey = computed(() => {
  return route.path
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
.main-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  background: var(--bg-primary);
  color: var(--text-primary);
}

// 侧边栏
.sidebar {
  width: 240px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;

  .sidebar-header {
    padding: 20px;
    border-bottom: 1px solid var(--border);

    .logo {
      display: flex;
      align-items: center;
      gap: 12px;

      .logo-icon {
        font-size: 28px;
      }

      .logo-text {
        font-size: 20px;
        font-weight: 600;
        background: linear-gradient(135deg, #4a90e2, #67b26f);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
    }
  }

  .sidebar-nav {
    flex: 1;
    padding: 8px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;

    // 滚动条样式优化
    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;

      &:hover {
        background: rgba(255, 255, 255, 0.2);
      }
    }

    // Element Plus Menu 样式覆盖
    .sidebar-menu {
      border: none;
      background: transparent;

      .el-menu-item,
      .el-sub-menu__title {
        color: var(--text-secondary);
        border-radius: 8px;
        margin: 2px 0;

        &:hover {
          background: rgba(74, 144, 226, 0.1) !important;
          color: var(--text-primary);
        }

        .el-icon {
          font-size: 20px;
        }
      }

      .el-menu-item.is-active {
        background: rgba(74, 144, 226, 0.2) !important;
        color: #4a90e2;
        border-left: 3px solid #4a90e2;
      }

      // 子菜单样式
      .el-sub-menu {
        .el-menu {
          background: transparent;
        }

        .el-menu-item {
          padding-left: 48px !important;
          font-size: 13px;
        }
      }
    }
  }

  // 用户信息区域
  .sidebar-footer {
    padding: 12px;
    border-top: 1px solid var(--border);
  }

  .user-info {
    .user-trigger {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px;
      border-radius: 8px;
      cursor: pointer;
      transition: background-color 0.2s;

      &:hover {
        background: rgba(255, 255, 255, 0.05);
      }
    }

    .user-avatar {
      background: linear-gradient(135deg, #4a90e2, #67b26f);
      color: white;
      font-weight: 600;
    }

    .user-details {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;

      .user-name {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .user-role {
        font-size: 12px;
        color: var(--text-secondary);
      }
    }

    .dropdown-icon {
      color: var(--text-secondary);
      font-size: 12px;
    }
  }
}

// 主内容区
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: 60px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;

  .header-left {
    .page-title {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;

    .el-button {
      color: var(--text-secondary);

      &:hover {
        color: var(--text-primary);
      }
    }
  }
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

// 动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
