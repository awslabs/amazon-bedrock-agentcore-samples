import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    basicSsl()  // Enable HTTPS with self-signed cert
  ],
  server: {
    https: true,
    port: 9000,
    host: 'vcas.local.com',  // Visa whitelisted domain
    // Proxy removed - now using Lambda API Gateway directly via VITE_VISA_PROXY_URL
    // proxy: {
    //   '/api/visa': {
    //     target: 'https://localhost:5001',
    //     changeOrigin: true,
    //     secure: false  // Ignore self-signed cert
    //   }
    // }
  }
})
