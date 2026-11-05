import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { AppProviders } from './app/providers';
import './styles/global.css';

const root = document.getElementById('root');
if (!root) throw new Error('Missing application root element');

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </StrictMode>,
);
