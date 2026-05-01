import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 6300,
    proxy: {
      '/api': {
        target: 'http://localhost:8606',
        changeOrigin: true
      },
      '/v1': {
        target: 'http://localhost:8606',
        changeOrigin: true
      }
    }
  }
})
