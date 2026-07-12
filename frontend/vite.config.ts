import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
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
  build: { outDir: 'dist', sourcemap: false },
})
