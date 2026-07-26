import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [vue(), Components({ resolvers: [ElementPlusResolver({ importStyle: 'css' })] })],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        timeout: 300000,
        proxyTimeout: 300000,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/echarts/') || id.includes('zrender')) return 'charts'
          if (id.includes('/vue/') || id.includes('vue-router') || id.includes('/pinia/')) return 'vue-core'
          return undefined
        },
      },
    },
  },
})
