/**
 * AutoGeo Vue 应用入口
 * 我用这个来启动整个前端！
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/modules/user'
import './assets/styles/index.scss'

// 创建应用实例
const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 使用插件
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { zIndex: 3000 })

// 初始化用户状态（在挂载前完成）
const userStore = useUserStore()
userStore.initUser()

// 挂载应用
app.mount('#app')

// 暗色主题
document.documentElement.classList.add('dark')
