import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// El proxy evita tener que abrir CORS para el caso normal, que es la UI y la
// API en la misma máquina. Si sirves el build desde otro sitio, añade su
// origen a CORS_ORIGINS en el .env.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8088',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    // three.js pesa lo suyo; separarlo evita reconstruir el bundle entero en
    // cada cambio de la aplicación.
    rollupOptions: {
      output: {
        manualChunks: { three: ['three'] },
      },
    },
  },
})
