import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': {
        target: 'ws://localhost:5002',
        ws: true,
      },
      '/audio': {
        target: 'ws://localhost:5001',
        ws: true,
      }
    }
  }
});