import axios from 'axios';
import { API_BASE_URL, WS_URL } from './api.config';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

