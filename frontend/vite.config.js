import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    allowedHosts: ['aboral-rogelio-plumbless.ngrok-free.dev'],
    proxy: {
      '/api/ppt': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/knowledge_bases': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/upload': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/jobs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/documents': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/search': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ppt': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
