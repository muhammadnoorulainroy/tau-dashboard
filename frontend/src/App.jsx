import React, { useState, useEffect } from 'react';
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
import { connectWebSocket, getDashboardOverview } from './services/api';

// Google OAuth Client ID from environment variable
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

function App() {
  const [activeView, setActiveView] = useState('dashboard');
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
          setUser(JSON.parse(storedUser));
          setIsAuthenticated(true);
        } catch (error) {
          console.error('Failed to parse stored user:', error);
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
        console.error('Failed to fetch last sync time:', error);
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
            toast.success(`✅ Full sync complete! Synced ${synced_count} PRs`, {
              duration: 4000,
            });
          } else {
            toast.success(`✨ Sync complete! Updated ${synced_count} PRs`, {
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
    setActiveView('dashboard');
    toast.success('Logged out successfully', {
      duration: 2000,
    });
  };

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <Dashboard lastUpdate={lastUpdate} />;
      case 'developers':
        return <DeveloperView lastUpdate={lastUpdate} />;
      case 'reviewers':
        return <ReviewerView lastUpdate={lastUpdate} />;
      case 'domains':
        return <DomainView lastUpdate={lastUpdate} />;
      case 'pull-requests':
        return <PullRequestsView lastUpdate={lastUpdate} />;
      case 'interfaces':
        return <InterfaceView lastUpdate={lastUpdate} />;
      case 'aggregation':
        return <AggregationView lastUpdate={lastUpdate} />;
      default:
        return <Dashboard lastUpdate={lastUpdate} />;
    }
  };

  // Show loading spinner while checking authentication
  if (isCheckingAuth) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 font-medium">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
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
        
        {/* Show Login if not authenticated */}
        {!isAuthenticated ? (
          <Login onLoginSuccess={handleLoginSuccess} />
        ) : (
          <>
            {/* Fixed Header */}
            <Header 
              sidebarOpen={sidebarOpen} 
              setSidebarOpen={setSidebarOpen}
              lastUpdate={lastUpdate}
              user={user}
              onLogout={handleLogout}
            />
            
            {/* Flex container for sidebar and main content */}
            <div className="flex flex-1 overflow-hidden">
              <Sidebar 
                activeView={activeView} 
                setActiveView={setActiveView}
                isOpen={sidebarOpen}
              />
              
              <main className={`flex-1 transition-all duration-300 ${
                ['interfaces', 'domains', 'dashboard'].includes(activeView) ? 'overflow-auto' : 'overflow-hidden'
              } ${sidebarOpen ? 'ml-64' : 'ml-0'}`}>
                <div className={`p-6 ${
                  ['interfaces', 'domains', 'dashboard'].includes(activeView) ? '' : 'h-full overflow-hidden'
                }`}>
                  {renderView()}
                </div>
              </main>
            </div>
          </>
        )}
      </div>
    </GoogleOAuthProvider>
  );
}

export default App;


