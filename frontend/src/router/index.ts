/**
 * 路由配置
 * 定义应用所有路由和侧边栏菜单结构
 */

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/modules/user'
import { ElMessage } from 'element-plus'

// 路由定义
const routes: RouteRecordRaw[] = [
  // 登录页（独立路由，不使用 MainLayout）
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录', hidden: true, public: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册', hidden: true, public: true },
  },
  {
    path: '/',
    component: () => import('@/views/layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      // 侧边栏菜单按业务流程排序：
      // 首页、客户管理、知识库管理、智能建站、关键词蒸馏、GEO文章生成、文章管理、账号管理、发布任务管理、批量发布、收录监控、数据报表、定时任务、系统设置

      // 1. 首页
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardPage.vue'),
        meta: { title: '首页', icon: 'House', order: 1 },
      },

      // 2. 客户管理
      {
        path: 'clients',
        name: 'Clients',
        component: () => import('@/views/client/ClientPage.vue'),
        meta: { title: '客户管理', icon: 'UserFilled', order: 2 },
      },

      // 3. GEO项目管理
      {
        path: 'clients/projects',
        name: 'GeoProjects',
        component: () => import('@/views/geo/Projects.vue'),
        meta: { title: 'GEO项目管理', icon: 'Grid', order: 3 },
      },

      // 4. 知识库管理
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/KnowledgePage.vue'),
        meta: { title: '知识库管理', icon: 'Reading', order: 4 },
      },

      // 5. 智能建站
      {
        path: 'site-builder',
        name: 'SiteBuilder',
        component: () => import('@/views/site-builder/ConfigWizard.vue'),
        meta: { title: '智能建站', icon: 'Platform', order: 5 },
      },

      // 6. 关键词蒸馏
      {
        path: 'geo/keywords',
        name: 'GeoKeywords',
        component: () => import('@/views/geo/Keywords.vue'),
        meta: { title: '关键词蒸馏', icon: 'MagicStick', order: 6 },
      },

      // 7. 文章生成
      {
        path: 'geo/articles',
        name: 'GeoArticles',
        component: () => import('@/views/geo/Articles.vue'),
        meta: { title: 'GEO文章生成', icon: 'EditPen', order: 7 },
      },

      // 8. 文章管理
      {
        path: 'articles',
        name: 'Articles',
        component: () => import('@/views/article/ArticleList.vue'),
        meta: { title: '文章管理', icon: 'Document', order: 8 },
      },
      {
        path: 'articles/add',
        name: 'ArticleAdd',
        component: () => import('@/views/article/ArticleEdit.vue'),
        meta: { title: '新建文章', hidden: true },
      },
      {
        path: 'articles/edit/:id',
        name: 'ArticleEdit',
        component: () => import('@/views/article/ArticleEdit.vue'),
        meta: { title: '编辑文章', hidden: true },
      },

      // 9. 账号管理
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('@/views/account/AccountList.vue'),
        meta: { title: '账号管理', icon: 'User', order: 9 },
      },
      {
        path: 'accounts/add',
        name: 'AccountAdd',
        component: () => import('@/views/account/AccountAdd.vue'),
        meta: { title: '添加账号', hidden: true },
      },

      // 10. 发布任务管理
      {
        path: 'auto-publish',
        name: 'AutoPublish',
        component: () => import('@/views/publish/AutoPublishPage.vue'),
        meta: { title: '发布任务管理', icon: 'List', order: 10 },
      },

      // 11. 批量发布
      {
        path: 'publish',
        name: 'Publish',
        component: () => import('@/views/publish/PublishPage.vue'),
        meta: { title: '平台发布监控', icon: 'Monitor', order: 11 },
      },

      // 12. 收录监控
      {
        path: 'geo/monitor',
        name: 'GeoMonitor',
        component: () => import('@/views/geo/Monitor.vue'),
        meta: { title: '收录监控', icon: 'Monitor', order: 12 },
      },

      // 13. 数据报表
      {
        path: 'data-report',
        name: 'DataReport',
        component: () => import('@/views/report/DataReport.vue'),
        meta: { title: '数据报表', icon: 'DataAnalysis', order: 13 },
      },

      // 14. 定时任务
      {
        path: 'scheduler',
        name: 'Scheduler',
        component: () => import('@/views/scheduler/SchedulerPage.vue'),
        meta: { title: '定时任务', icon: 'Timer', order: 14 },
      },

      // 15. 系统设置
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/SettingsPage.vue'),
        meta: { title: '系统设置', icon: 'Setting', order: 15 },
      },

      // 16. 后台管理（仅管理员）
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/admin/AdminView.vue'),
        meta: { title: '后台管理', icon: 'Tools', order: 16, roles: ['admin'] },
      },

      // ========== 以下是不在侧边栏显示的辅助路由 ==========
      // GEO数据概览（已废弃，保留路由以免报错）
      {
        path: 'geo/dashboard',
        name: 'GeoDashboard',
        component: () => import('@/views/geo/Dashboard.vue'),
        meta: { title: '数据概览', icon: 'PieChart', hidden: true },
      },
    ],
  },
]

// 创建路由实例
const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  // 设置页面标题
  if (to.meta?.title) {
    document.title = `${to.meta.title} - AutoGeo`
  }

  // 获取用户 store
  const userStore = useUserStore()

  // 初始化用户状态（从本地存储恢复）
  if (!userStore.user) {
    userStore.initUser()
  }

  // 公开页面（如登录页）直接放行
  if (to.meta?.public || to.meta?.hidden) {
    // 如果已登录且访问登录页，重定向到首页
    if (userStore.isLoggedIn && to.path === '/login') {
      next('/dashboard')
      return
    }
    next()
    return
  }

  // 检查是否已登录
  if (!userStore.isLoggedIn) {
    // 尝试从服务器获取当前用户信息（token 可能还有效）
    const isValid = await userStore.fetchCurrentUser()
    if (!isValid) {
      ElMessage.warning('请先登录')
      next({
        path: '/login',
        query: { redirect: to.fullPath },
      })
      return
    }
  }

  // 检查角色权限
  const requiredRoles = to.meta?.roles as string[] | undefined
  if (requiredRoles && requiredRoles.length > 0) {
    if (!requiredRoles.includes(userStore.user?.role || '')) {
      ElMessage.error('您没有权限访问此页面')
      next('/dashboard')
      return
    }
  }

  next()
})

export default router