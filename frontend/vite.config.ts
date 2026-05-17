import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isH5 = mode === 'h5'

  return {
    // 使用相对路径，避免Electron打包后资源加载失败导致黑屏
    base: './',
    plugins: [
      vue(),
      AutoImport({
        resolvers: [ElementPlusResolver()],
        imports: ['vue', 'vue-router', 'pinia'],
        dts: 'src/types/auto-imports.d.ts',
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        dts: 'src/types/components.d.ts',
      }),
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8001',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api/, '/api'),
          timeout: 600000,
          proxyTimeout: 600000,
        },
        '/ws': {
          target: 'ws://127.0.0.1:8001',
          ws: true,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: isH5 ? 'dist-h5' : 'out/renderer',
      emptyOutDir: true,
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        input: isH5
          ? {
              main: resolve(__dirname, 'index-h5.html'),
            }
          : {
              main: resolve(__dirname, 'index.html'),
            },
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('vue') || id.includes('vue-router') || id.includes('pinia')) {
                return 'vue-vendor'
              }
              if (id.includes('element-plus')) {
                return 'element-plus'
              }
              if (id.includes('vant')) {
                return 'vant'
              }
              if (id.includes('echarts')) {
                return 'echarts'
              }
              if (id.includes('@wangeditor') || id.includes('markdown-it')) {
                return 'editor'
              }
            }
          },
        },
      },
    },
  }
})
