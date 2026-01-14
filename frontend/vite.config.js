import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // IMPORTANT: Build to dist-react/ to avoid overwriting the static landing page in dist/
  // The production UI is the static index.html with raven logo in dist/
  // The React app is for development only
  build: {
    outDir: 'dist-react',
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:9000',
        ws: true,
      },
    },
  },
})

