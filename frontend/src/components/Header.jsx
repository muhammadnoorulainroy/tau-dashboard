import React from 'react';
import { format, formatDistanceToNow } from 'date-fns';
import { 
  Bars3Icon, 
  XMarkIcon, 
  ArrowPathIcon,
  BellIcon,
  ClockIcon,
  InformationCircleIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import { triggerSync, refreshDomains, logout as apiLogout } from '../services/api';
import toast from 'react-hot-toast';

const Header = ({ sidebarOpen, setSidebarOpen, lastUpdate, user, onLogout }) => {
  const [syncing, setSyncing] = React.useState(false);
  const [syncingDomains, setSyncingDomains] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(new Date());
  const [justUpdated, setJustUpdated] = React.useState(false);
  const [showUserMenu, setShowUserMenu] = React.useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = React.useState(false);
  const [isLoggingOut, setIsLoggingOut] = React.useState(false);

  // Auto-sync interval: 1 hour (3600 seconds)
  const AUTO_SYNC_INTERVAL_MS = 3600 * 1000; // 1 hour in milliseconds

  // Calculate remaining time until next auto-sync
  const getRemainingTime = () => {
    const timeSinceLastSync = currentTime - lastUpdate;
    const remainingMs = AUTO_SYNC_INTERVAL_MS - timeSinceLastSync;
    
    if (remainingMs <= 0) return 'Syncing soon...';
    
    const remainingMinutes = Math.floor(remainingMs / 60000);
    const remainingSeconds = Math.floor((remainingMs % 60000) / 1000);
    
    if (remainingMinutes >= 60) {
      return `Next auto-sync in ${Math.floor(remainingMinutes / 60)}h ${remainingMinutes % 60}m`;
    } else if (remainingMinutes > 0) {
      return `Next auto-sync in ${remainingMinutes}m ${remainingSeconds}s`;
    } else {
      return `Next auto-sync in ${remainingSeconds}s`;
    }
  };

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

  const handleLogoutClick = () => {
    setShowUserMenu(false);
    setShowLogoutConfirm(true);
  };

  const handleLogoutConfirm = async () => {
    setIsLoggingOut(true);
    
    try {
      // Call backend logout API
      await apiLogout();
    } catch (error) {
      console.error('Logout API error:', error);
      // Continue with logout even if API call fails
    } finally {
      setIsLoggingOut(false);
      setShowLogoutConfirm(false);
      onLogout();
    }
  };

  const handleLogoutCancel = () => {
    setShowLogoutConfirm(false);
  };

  // Close dropdowns when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event) => {
      if (showUserMenu && !event.target.closest('.user-menu-container')) {
        setShowUserMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showUserMenu]);

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
                  Synced {formatDistanceToNow(lastUpdate, { addSuffix: true })}
                </span>
              </div>
              
              {/* Info icon with tooltip */}
              <div className="relative group">
                <InformationCircleIcon className="h-4 w-4 text-gray-400 hover:text-gray-600 cursor-help" />
                
                {/* Tooltip */}
                <div className="absolute right-0 top-full mt-2 w-48 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                  <div className="flex flex-col space-y-1">
                    <span className="font-medium">{getRemainingTime()}</span>
                    <span className="text-gray-300">Auto-sync runs every hour</span>
                  </div>
                  {/* Arrow */}
                  <div className="absolute right-2 -top-1 w-2 h-2 bg-gray-900 transform rotate-45"></div>
                </div>
              </div>
              
              {justUpdated && (
                <span className="flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
              )}
            </div>
            
            {/* Sync PRs Button - DISABLED FOR NOW */}
            {/* <button
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
            </button> */}

            {/* Sync Domains Button - DISABLED (synced automatically every hour) */}
            {/* <button
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
            </button> */}
            
            {/* User Profile Menu */}
            <div className="relative user-menu-container">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center space-x-2 p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
              >
                {user && user.picture ? (
                  <img 
                    src={user.picture} 
                    alt={user.name} 
                    className="h-8 w-8 rounded-full border-2 border-gray-300"
                  />
                ) : (
                  <UserCircleIcon className="h-8 w-8" />
                )}
              </button>

              {/* User Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-xl border border-gray-200 py-2 z-50">
                  {/* User Info */}
                  <div className="px-4 py-3 border-b border-gray-100">
                    <div className="flex items-center space-x-3">
                      {user && user.picture ? (
                        <img 
                          src={user.picture} 
                          alt={user.name} 
                          className="h-12 w-12 rounded-full border-2 border-blue-500"
                        />
                      ) : (
                        <div className="h-12 w-12 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-lg">
                          {user && user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate">
                          {user && user.name}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {user && user.email}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Menu Items */}
                  <div className="py-1">
                    <button
                      onClick={handleLogoutClick}
                      className="w-full flex items-center px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <ArrowRightOnRectangleIcon className="h-5 w-5 mr-3" />
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            {/* Background overlay */}
            <div 
              className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75"
              onClick={handleLogoutCancel}
            ></div>

            {/* Center modal */}
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen">&#8203;</span>

            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                    <ArrowRightOnRectangleIcon className="h-6 w-6 text-red-600" />
                  </div>
                  <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                    <h3 className="text-lg leading-6 font-medium text-gray-900">
                      Sign Out
                    </h3>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        Are you sure you want to sign out? You'll need to authenticate again to access the dashboard.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  type="button"
                  disabled={isLoggingOut}
                  onClick={handleLogoutConfirm}
                  className={`w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-base font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm ${
                    isLoggingOut 
                      ? 'bg-red-400 cursor-not-allowed' 
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {isLoggingOut ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Signing out...
                    </>
                  ) : (
                    'Yes, sign out'
                  )}
                </button>
                <button
                  type="button"
                  disabled={isLoggingOut}
                  onClick={handleLogoutCancel}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;

