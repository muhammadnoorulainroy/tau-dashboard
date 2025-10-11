// API configuration that works both locally and in Docker

const getApiBaseUrl = () => {
  // If running in production/Docker with VITE_API_URL set
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // Default to proxying through Vite dev server
  return '';
};

const getWebSocketUrl = () => {
  // If running in production/Docker
  if (import.meta.env.VITE_API_URL) {
    const wsUrl = import.meta.env.VITE_API_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    return `${wsUrl}/ws`;
  }
  
  // Default for local development
  return `ws://localhost:8000/ws`;
};

export const API_BASE_URL = getApiBaseUrl() + '/api';
export const WS_URL = getWebSocketUrl();

