import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import './index.css'
import App from './App.tsx'
import ToastProvider from './components/ToastProvider'
import ScrollToTop from './components/ScrollToTop'
import SessionExpiredHandler from './components/SessionExpiredHandler'
import ErrorBoundary from './components/ErrorBoundary'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HelmetProvider>
      <BrowserRouter>
        <ScrollToTop />
        <ToastProvider>
          <ErrorBoundary>
            <SessionExpiredHandler />
            <App />
          </ErrorBoundary>
        </ToastProvider>
      </BrowserRouter>
    </HelmetProvider>
  </StrictMode>,
)
