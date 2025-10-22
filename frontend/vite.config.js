import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')
  
  const frontendPort = parseInt(env.VITE_FRONTEND_PORT || '3000')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:4000'
  
  return {
    plugins: [react()],
    server: {
      port: frontendPort,
      host: true,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        '/ws': {
          target: backendUrl.replace('http', 'ws'),
          ws: true,
          changeOrigin: true,
        },
      },
    },
  }
})


