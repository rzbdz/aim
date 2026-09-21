import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The dashboard is served by `aimboard serve` from `web/dist`, next to the JSON
// API that feeds it. `base: './'` keeps the built assets path-relative so the
// same bundle works from `/` and from a sub-path.
export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          element: ['element-plus', '@element-plus/icons-vue'],
          charts: ['echarts', 'vue-echarts'],
        },
      },
    },
  },
  server: {
    proxy: {
      // `npm run dev` against a running `aimboard serve`, so the front-end can be
      // edited with hot reload without teaching it a second way to read the fabric.
      '/api': { target: 'http://127.0.0.1:8777', changeOrigin: true },
    },
  },
})
