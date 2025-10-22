import React from 'react';
import { format, formatDistanceToNow } from 'date-fns';
import { 
  Bars3Icon, 
  XMarkIcon, 
  ArrowPathIcon,
  BellIcon,
  ClockIcon
} from '@heroicons/react/24/outline';
import { triggerSync, refreshDomains } from '../services/api';
import toast from 'react-hot-toast';

const Header = ({ sidebarOpen, setSidebarOpen, lastUpdate }) => {
  const [syncing, setSyncing] = React.useState(false);
  const [syncingDomains, setSyncingDomains] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(new Date());
  const [justUpdated, setJustUpdated] = React.useState(false);

  // Update current time every second
  React.useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Flash indicator when data updates
  React.useEffect(() => {
    setJustUpdated(true);
    const timer = setTimeout(() => setJustUpdated(false), 2000);
    return () => clearTimeout(timer);
  }, [lastUpdate]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const response = await triggerSync(60);
      const { status, sync_type, description, message } = response.data;
      
      if (status === 'started') {
        // Sync started in background - show initial message
        const syncTypeLabel = sync_type === 'full' ? 'Full sync' : 'Incremental sync';
        toast.loading(`${syncTypeLabel} started...`, {
          duration: 3000,
          id: 'sync-progress'
        });
        console.log(`Sync started: ${description}`);
        
        // Stop spinner after a short delay (sync runs in background)
        setTimeout(() => setSyncing(false), 1000);
      } else {
        // Old format (shouldn't happen, but handle it)
        toast.success('Sync completed!', { duration: 3000 });
        setSyncing(false);
      }
    } catch (error) {
      toast.error('Failed to start sync');
      console.error('Sync error:', error);
      setSyncing(false);
    }
  };

  const handleSyncDomains = async () => {
    setSyncingDomains(true);
    try {
      const response = await refreshDomains();
      const { status, message, count } = response.data;
      
      if (status === 'success') {
        toast.success(`Domains refreshed: ${count} domains discovered`, { duration: 3000 });
        console.log(`Domains synced: ${message}`);
      } else {
        toast.error(message || 'Failed to refresh domains', { duration: 3000 });
      }
    } catch (error) {
      toast.error('Failed to refresh domains');
      console.error('Domain refresh error:', error);
    } finally {
      setSyncingDomains(false);
    }
  };

  return (
    <header className="bg-white shadow-sm border-b border-gray-200 relative z-20">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500"
            >
              {sidebarOpen ? (
                <XMarkIcon className="h-6 w-6" />
              ) : (
                <Bars3Icon className="h-6 w-6" />
              )}
            </button>
            
            <div className="ml-4">
              <h1 className="text-2xl font-bold text-gray-900">
                TAU Dashboard
              </h1>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Live Update Indicator */}
            <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg border transition-all duration-300 ${
              justUpdated 
                ? 'bg-green-50 border-green-300 shadow-sm' 
                : 'bg-gray-50 border-gray-200'
            }`}>
              <ClockIcon className={`h-4 w-4 ${justUpdated ? 'text-green-600' : 'text-gray-500'}`} />
              <div className="flex flex-col">
                <span className={`text-xs font-medium ${justUpdated ? 'text-green-700' : 'text-gray-700'}`}>
                  {format(lastUpdate, 'HH:mm:ss')}
                </span>
                <span className="text-[10px] text-gray-500">
                  {formatDistanceToNow(lastUpdate, { addSuffix: true })}
                </span>
              </div>
              {justUpdated && (
                <span className="flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
              )}
            </div>
            
            <button
              onClick={handleSync}
              disabled={syncing}
              className={`
                inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md
                ${syncing 
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                  : 'text-white bg-success-600 hover:bg-success-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-success-500'
                }
              `}
            >
              <ArrowPathIcon className={`h-4 w-4 mr-1.5 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? 'Syncing...' : 'Sync PRs'}
            </button>

            <button
              onClick={handleSyncDomains}
              disabled={syncingDomains}
              className={`
                inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md
                ${syncingDomains 
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                  : 'text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500'
                }
              `}
            >
              <ArrowPathIcon className={`h-4 w-4 mr-1.5 ${syncingDomains ? 'animate-spin' : ''}`} />
              {syncingDomains ? 'Syncing...' : 'Sync Domains'}
            </button>
            
            <button className="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500">
              <BellIcon className="h-6 w-6" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;

