import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load .env.dev file (vite looks for .env.{mode} files)
  const env = loadEnv(mode, process.cwd(), '')
  
  const frontendPort = parseInt(env.VITE_FRONTEND_PORT || '3000')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:4000'
  
  return {
    plugins: [react()],
    envPrefix: 'VITE_',
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


