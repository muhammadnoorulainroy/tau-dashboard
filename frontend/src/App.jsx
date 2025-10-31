import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import toast, { Toaster } from 'react-hot-toast';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Dashboard from './components/Dashboard';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import DeveloperView from './components/DeveloperView';
import ReviewerView from './components/ReviewerView';
import DomainView from './components/DomainView';
import PullRequestsView from './components/PullRequestsView';
import InterfaceView from './components/InterfaceView';
import AggregationView from './components/AggregationView';
import Login from './components/Login';
import ProtectedRoute from './components/ProtectedRoute';
import { connectWebSocket, getDashboardOverview } from './services/api';

// Google OAuth Client ID from environment variable
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// Main Layout Component (for authenticated routes)
function MainLayout({ children, sidebarOpen, setSidebarOpen, lastUpdate, user, onLogout }) {
  const location = useLocation();
  
  // Determine if current route should have full page scroll or not
  const fullScrollRoutes = ['/dashboard', '/domains', '/interfaces'];
  const isFullScroll = fullScrollRoutes.includes(location.pathname);
  
  return (
    <>
      <Header 
        sidebarOpen={sidebarOpen} 
        setSidebarOpen={setSidebarOpen}
        lastUpdate={lastUpdate}
        user={user}
        onLogout={onLogout}
      />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isOpen={sidebarOpen} />
        
        <main className={`flex-1 transition-all duration-300 ${
          isFullScroll ? 'overflow-auto' : 'overflow-hidden'
        } ${sidebarOpen ? 'ml-64' : 'ml-0'}`}>
          <div className={`p-6 ${isFullScroll ? '' : 'h-full overflow-hidden'}`}>
            {children}
          </div>
        </main>
      </div>
    </>
  );
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('auth_token');
      const storedUser = localStorage.getItem('user');
      
      if (token && storedUser) {
        try {
          const parsedUser = JSON.parse(storedUser);
          setUser(parsedUser);
          setIsAuthenticated(true);
        } catch (error) {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user');
        }
      }
      
      setIsCheckingAuth(false);
    };
    
    checkAuth();
  }, []);

  // Fetch data and connect WebSocket only when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    
    // Fetch initial last sync time from backend
    const fetchLastSyncTime = async () => {
      try {
        const response = await getDashboardOverview();
        if (response.data.last_sync_time) {
          setLastUpdate(new Date(response.data.last_sync_time));
        }
      } catch (error) {
        // If 401, token might be expired
        if (error.response && error.response.status === 401) {
          handleLogout();
        }
      }
    };
    
    fetchLastSyncTime();
    
    // Connect to WebSocket for real-time updates
    const ws = connectWebSocket((data) => {
      if (data.type === 'data_updated' || data.type === 'sync_complete') {
        setLastUpdate(new Date());
        
        // If sync complete, show success message
        if (data.type === 'sync_complete' && data.data) {
          const { synced_count, sync_type } = data.data;
          // Dismiss loading toast and show success
          toast.dismiss('sync-progress');
          
          if (sync_type === 'full') {
            toast.success(`Full sync complete! Synced ${synced_count} PRs`, {
              duration: 4000,
            });
          } else {
            toast.success(`Sync complete! Updated ${synced_count} PRs`, {
              duration: 3000,
            });
          }
        }
      }
    });

    return () => {
      ws.close();
    };
  }, [isAuthenticated]);
  
  const handleLoginSuccess = (data) => {
    setUser(data.user);
    setIsAuthenticated(true);
  };
  
  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setUser(null);
    setIsAuthenticated(false);
    toast.success('Logged out successfully', {
      duration: 2000,
    });
  };

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <Router>
        <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
          <Toaster 
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#363636',
                color: '#fff',
              },
              success: {
                style: {
                  background: '#2ecc71',
                },
              },
              error: {
                style: {
                  background: '#e74c3c',
                },
              },
            }}
          />
          
          {/* Show loading spinner while checking authentication */}
          {isCheckingAuth ? (
            <div className="h-screen flex items-center justify-center bg-gray-50">
              <div className="text-center">
                <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
                <p className="mt-4 text-gray-600 font-medium">Checking authentication...</p>
              </div>
            </div>
          ) : !isAuthenticated ? (
            // Not authenticated - show only login route
            <Routes>
              <Route path="*" element={<Login onLoginSuccess={handleLoginSuccess} />} />
            </Routes>
          ) : (
          // Authenticated - show all protected routes
          <Routes>
            {/* Protected Routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <Dashboard lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/developers"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <DeveloperView lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/reviewers"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <ReviewerView lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/domains"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <DomainView lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/pull-requests"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <PullRequestsView lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/interfaces"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <InterfaceView lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/aggregation"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated}>
                  <MainLayout
                    sidebarOpen={sidebarOpen}
                    setSidebarOpen={setSidebarOpen}
                    lastUpdate={lastUpdate}
                    user={user}
                    onLogout={handleLogout}
                  >
                    <AggregationView lastUpdate={lastUpdate} />
                  </MainLayout>
                </ProtectedRoute>
              }
            />
            
            {/* Default Redirect */}
            <Route 
              path="/" 
              element={<Navigate to="/dashboard" replace />} 
            />
            
            {/* Catch all - redirect to dashboard */}
            <Route 
              path="*" 
              element={<Navigate to="/dashboard" replace />} 
            />
          </Routes>
          )}
        </div>
      </Router>
    </GoogleOAuthProvider>
  );
}

export default App;


