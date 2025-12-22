import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(() => {
  const isHttps = process.env.VITE_HTTPS === 'true'
  
  let httpsConfig = undefined
  if (isHttps) {
    const keyPath = path.resolve(__dirname, '../../certs/key.pem')
    const certPath = path.resolve(__dirname, '../../certs/cert.pem')
    console.log('HTTPS enabled, loading certificates from:', { keyPath, certPath })
    try {
      httpsConfig = {
        key: fs.readFileSync(keyPath),
        cert: fs.readFileSync(certPath),
      }
      console.log('Certificates loaded successfully')
    } catch (error) {
      console.error('Failed to load certificates:', error)
      throw error
    }
  }
  
  return {
    plugins: [vue()],
    server: {
      https: httpsConfig,
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
