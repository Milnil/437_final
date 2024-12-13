import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {
        target: 'ws://localhost:6002',
        ws: true,
      },
      '/audio': {
        target: 'ws://localhost:6001',
        ws: true,
      }
    }
  }
});