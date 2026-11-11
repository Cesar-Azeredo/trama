import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './estilos/base.css'
import App from './App.tsx'
import { iniciarTema } from './tema/useTema'

iniciarTema()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
