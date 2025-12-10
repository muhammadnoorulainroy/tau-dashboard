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

// ============================================================================
// V2 API - Task Agent Endpoints (Primary)
// ============================================================================

// Dashboard Overview - Task Agent
export const getDashboardOverview = () => api.get('/v2/overview');

// Tasks
export const getTasks = (params = {}) => api.get('/v2/tasks', { params });
export const getTask = (taskId) => api.get(`/v2/tasks/${taskId}`);
export const getTaskByAgentId = (taskAgentId) => api.get(`/v2/tasks/by-agent-id/${taskAgentId}`);

// Environments/Domains - Task Agent
export const getEnvironments = (activeOnly = true) => 
  api.get('/v2/environments', { params: { active_only: activeOnly } });

export const getEnvironment = (name) => api.get(`/v2/environments/${name}`);

export const getDomainMetrics = () => api.get('/v2/environments');

// Trainers (replaces Developers)
export const getTrainers = (params = {}) => api.get('/v2/trainers', { params });

// Batches
export const getBatches = (params = {}) => api.get('/v2/batches', { params });

// Status Breakdown
export const getStatusBreakdown = (byDomain = false) => 
  api.get('/v2/status-breakdown', { params: { by_domain: byDomain } });

// Sync
export const getSyncStatus = () => api.get('/v2/sync/status');
export const triggerSync = (fetchDetails = true) => 
  api.post('/v2/sync/trigger', null, { params: { fetch_details: fetchDetails } });

// Similarity
export const getTaskSimilarity = (taskId, limit = 10) => 
  api.get(`/v2/similarity/tasks/${taskId}`, { params: { limit } });

export const getActionSimilarity = (taskId, limit = 10) => 
  api.get(`/v2/similarity/actions/${taskId}`, { params: { limit } });

export const searchSimilarTasks = (queryText, options = {}) => 
  api.post('/v2/similarity/search', {
    query_text: queryText,
    domain: options.domain || null,
    search_type: options.searchType || 'instruction',
    limit: options.limit || 10,
    min_similarity: options.minSimilarity || 0.3
  });

// Statistics
export const getStatsByDifficulty = (domain = null) => 
  api.get('/v2/stats/by-difficulty', { params: domain ? { domain } : {} });

export const getStatsByBatch = (domain = null) => 
  api.get('/v2/stats/by-batch', { params: domain ? { domain } : {} });

export const getTimelineStats = (days = 30, domain = null) => 
  api.get('/v2/stats/timeline', { params: { days, ...(domain ? { domain } : {}) } });

// Aggregation - POD Leads, Calibrators, Expert Reviewers
export const getPodLeadAggregation = (domain = null) => 
  api.get('/v2/aggregation/pod-leads', { params: domain ? { domain } : {} });

export const getCalibratorAggregation = (domain = null) => 
  api.get('/v2/aggregation/calibrators', { params: domain ? { domain } : {} });

export const getExpertReviewerAggregation = (domain = null) => 
  api.get('/v2/aggregation/expert-reviewers', { params: domain ? { domain } : {} });

// ============================================================================
// Legacy V1 API (GitHub-based) - Kept for backwards compatibility
// ============================================================================

// Developers (GitHub)
export const getDeveloperMetrics = (params = {}) => 
  api.get('/developers', { params });

export const getDeveloperDetails = (username) => 
  api.get(`/developers/${username}`);

// Reviewers (GitHub)
export const getReviewerMetrics = (params = {}) => 
  api.get('/reviewers', { params });

// PR States (GitHub)
export const getPRStateDistribution = (domain = null) => 
  api.get('/pr-states', { params: domain ? { domain } : {} });

// Pull Requests (GitHub)
export const getPullRequests = (params = {}) => 
  api.get('/prs', { params });

// Domain Configuration
export const refreshDomains = () => 
  api.post('/domains/config/refresh');

export const getCurrentDomains = () => 
  api.get('/domains/config/current');

// ============================================================================
// Authentication
// ============================================================================

export const logout = () => 
  api.post('/auth/logout');

export const getCurrentUser = () => 
  api.get('/auth/me');

// ============================================================================
// WebSocket connection for real-time updates
// ============================================================================

export const connectWebSocket = (onMessage) => {
  const ws = new WebSocket(WS_URL);
  
  ws.onopen = () => {
    // WebSocket connected
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };
  
  ws.onerror = (error) => {
    // WebSocket error occurred
  };
  
  ws.onclose = () => {
    // Attempt reconnection after 5 seconds
    setTimeout(() => connectWebSocket(onMessage), 5000);
  };
  
  return ws;
};

export default api;
