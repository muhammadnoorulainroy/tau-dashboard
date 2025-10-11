import React, { useState, useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import Dashboard from './components/Dashboard';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import DeveloperView from './components/DeveloperView';
import ReviewerView from './components/ReviewerView';
import DomainView from './components/DomainView';
import PullRequestsView from './components/PullRequestsView';
import { connectWebSocket, getDashboardOverview } from './services/api';

function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    // Fetch initial last sync time from backend
    const fetchLastSyncTime = async () => {
      try {
        const response = await getDashboardOverview();
        if (response.data.last_sync_time) {
          setLastUpdate(new Date(response.data.last_sync_time));
        }
      } catch (error) {
        console.error('Failed to fetch last sync time:', error);
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
          const toast = require('react-hot-toast').default;
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
  }, []);

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
      default:
        return <Dashboard lastUpdate={lastUpdate} />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
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
      
      <Header 
        sidebarOpen={sidebarOpen} 
        setSidebarOpen={setSidebarOpen}
        lastUpdate={lastUpdate}
      />
      
      <div className="flex">
        <Sidebar 
          activeView={activeView} 
          setActiveView={setActiveView}
          isOpen={sidebarOpen}
        />
        
        <main className={`flex-1 transition-all duration-300 ${sidebarOpen ? 'ml-64' : 'ml-0'}`}>
          <div className="p-6">
            {renderView()}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;


