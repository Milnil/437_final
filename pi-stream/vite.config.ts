import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/video': 'http://192.168.10.59:8000',
      '/ws': {
        target: 'ws://192.168.10.59:8001',
        ws: true,
      }
    }
  }
});