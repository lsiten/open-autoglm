import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(() => {
  const isHttps = process.env.VITE_HTTPS === 'true'
  
  return {
    plugins: [vue()],
    server: {
      https: isHttps ? {
        key: fs.readFileSync(path.resolve(__dirname, '../../certs/key.pem')),
        cert: fs.readFileSync(path.resolve(__dirname, '../../certs/cert.pem')),
      } : undefined,
      proxy: {
        '/api': {
          target: isHttps ? 'https://127.0.0.1:8000' : 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
          ws: true
        },
        '/docs': {
          target: isHttps ? 'https://127.0.0.1:8000' : 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false
        },
        '/openapi.json': {
          target: isHttps ? 'https://127.0.0.1:8000' : 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
