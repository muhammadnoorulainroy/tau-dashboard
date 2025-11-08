// API configuration that works both locally and in Docker

const getApiBaseUrl = () => {
  // In production (when served via nginx), use relative paths
  if (import.meta.env.PROD) {
    return '';  // Empty string means relative path
  }
  
  // Use VITE_BACKEND_URL from environment
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  
  // Fallback for development
  return 'http://localhost:4000';
};

const getWebSocketUrl = () => {
  // In production, construct WebSocket URL from current hostname
  if (import.meta.env.PROD) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws`;
  }
  
  // Use VITE_WS_URL from environment
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  
  // Fallback for development
  return 'ws://localhost:4000/ws';
};

export const API_BASE_URL = getApiBaseUrl() + '/api';
export const WS_URL = getWebSocketUrl();

