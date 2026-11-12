// Primeiro: copia as chaves antigas do localStorage antes de qualquer
// modulo ler as preferencias (ver o proprio arquivo).
import './armazenamento/migrarChaves'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './estilos/base.css'
import App from './App.tsx'
import { iniciarTema } from './tema/useTema'
import { iniciarIdioma } from './i18n/idioma'

iniciarTema()
iniciarIdioma()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
