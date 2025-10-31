import axios from 'axios';
import { API_BASE_URL, WS_URL } from './api.config';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add authentication token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle authentication errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // If 401 Unauthorized, clear auth and redirect to login
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user');
      // Page will automatically redirect to login due to App.jsx auth check
      window.location.reload();
    }
    
    return Promise.reject(error);
  }
);

// Dashboard Overview
export const getDashboardOverview = () => api.get('/overview');

// Developers
export const getDeveloperMetrics = (params = {}) => 
  api.get('/developers', { params });

export const getDeveloperDetails = (username) => 
  api.get(`/developers/${username}`);

// Reviewers
export const getReviewerMetrics = (params = {}) => 
  api.get('/reviewers', { params });

// Domains
export const getDomainMetrics = () => api.get('/domains');

export const getDomainDetails = (domain) => 
  api.get(`/domains/${domain}`);

// PR States
export const getPRStateDistribution = (domain = null) => 
  api.get('/pr-states', { params: domain ? { domain } : {} });

// Pull Requests
export const getPullRequests = (params = {}) => 
  api.get('/prs', { params });

// Timeline Stats
export const getTimelineStats = (days = 30, domain = null) => 
  api.get('/stats/timeline', { params: { days, ...(domain ? { domain } : {}) } });

// Sync
export const triggerSync = (sinceDays = 60) => 
  api.post('/sync', { since_days: sinceDays });

// Domain Configuration
export const refreshDomains = () => 
  api.post('/domains/config/refresh');

export const getCurrentDomains = () => 
  api.get('/domains/config/current');

// Authentication
export const logout = () => 
  api.post('/auth/logout');

export const getCurrentUser = () => 
  api.get('/auth/me');

// WebSocket connection for real-time updates
export const connectWebSocket = (onMessage) => {
  const ws = new WebSocket(WS_URL);
  
  ws.onopen = () => {
    console.log('WebSocket connected');
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  ws.onclose = () => {
    console.log('WebSocket disconnected');
    // Attempt reconnection after 5 seconds
    setTimeout(() => connectWebSocket(onMessage), 5000);
  };
  
  return ws;
};

export default api;

