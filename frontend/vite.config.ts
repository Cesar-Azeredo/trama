import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Servidor FastAPI roda em 127.0.0.1:8000 (ADR 0004). O proxy evita
    // precisar de CORS no servidor - ele continua casca fina, sem saber
    // de onde o navegador esta rodando.
    // TRAMA_PORTA: a mesma variavel que o servidor le - as capturas
    // (ferramentas/capturas.mjs) sobem um servidor de demonstracao noutra
    // porta para nao colidir com um Trama de verdade na 8000.
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.TRAMA_PORTA ?? '8000'}`,
        changeOrigin: true,
      },
    },
  },
})
