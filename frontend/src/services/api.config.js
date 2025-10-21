// API configuration that works both locally and in Docker

const getApiBaseUrl = () => {
  // Use VITE_BACKEND_URL from environment
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  
  // Fallback for development
  return 'http://localhost:4000';
};

const getWebSocketUrl = () => {
  // Use VITE_WS_URL from environment
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  
  // Fallback for development
  return 'ws://localhost:4000/ws';
};

export const API_BASE_URL = getApiBaseUrl() + '/api';
export const WS_URL = getWebSocketUrl();

