import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
// Mode: VITE_APP_MODE env var (for Docker builds) > default 'admin'
// vite.user.config.js overrides this to 'user' for dev server
const appMode = process.env.VITE_APP_MODE || 'admin'

export default defineConfig({
  plugins: [react()],
  define: {
    // Set import.meta.env.VITE_APP_MODE at build time
    'import.meta.env.VITE_APP_MODE': JSON.stringify(appMode),
  },
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      }
    }
  }
})
