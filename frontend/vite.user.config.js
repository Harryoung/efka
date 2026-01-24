import { defineConfig, mergeConfig } from 'vite'
import baseConfig from './vite.config.js'

export default mergeConfig(
  baseConfig,
  defineConfig({
    define: {
      // Override to 'user' mode for User UI
      'import.meta.env.VITE_APP_MODE': JSON.stringify('user'),
    },
    server: {
      port: 3001,
      strictPort: true,
    },
  })
)
