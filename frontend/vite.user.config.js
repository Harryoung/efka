import { defineConfig, mergeConfig } from 'vite'
import baseConfig from './vite.config.js'

export default mergeConfig(
  baseConfig,
  defineConfig({
    define: {
      'globalThis.__EFKA_APP_MODE__': JSON.stringify('user'),
    },
    server: {
      port: 3001,
      strictPort: true,
    },
  })
)
