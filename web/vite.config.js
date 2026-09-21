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
        // a function, not a map: the bundler in use here wants to see the id
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'charts'
          if (id.includes('element-plus')) return 'element'
          if (id.includes('/vue') || id.includes('pinia') || id.includes('vue-router')) return 'vendor'
          return undefined
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
