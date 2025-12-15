import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  envPrefix: ['VITE_', 'REACT_APP_'],  // REACT_APP_ 환경 변수도 인식
  server: {
    host: '0.0.0.0',  // 외부 접속 허용
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // 또는 백엔드 서버 IP
        changeOrigin: true,
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 3000
  }
})
