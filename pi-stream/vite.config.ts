import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
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