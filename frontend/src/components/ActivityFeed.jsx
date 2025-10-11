import React from 'react';
import { format } from 'date-fns';
import { 
  CheckCircleIcon, 
  ClockIcon, 
  XCircleIcon,
  UserCircleIcon,
  ArrowPathIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';

const ActivityFeed = ({ activities }) => {
  if (!activities || activities.length === 0) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-900">Recent Activity</h3>
          <SparklesIcon className="h-5 w-5 text-primary-500" />
        </div>
        <div className="text-center py-12">
          <ClockIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No recent activity to display</p>
          <p className="text-sm text-gray-400 mt-1">Click "Sync" to fetch latest data</p>
        </div>
      </div>
    );
  }

  const getStatusIcon = (state) => {
    if (state === 'merged') {
      return <CheckCircleIcon className="h-6 w-6 text-success-600" />;
    } else if (state === 'open') {
      return <ClockIcon className="h-6 w-6 text-warning-600" />;
    } else if (state === 'closed') {
      return <XCircleIcon className="h-6 w-6 text-gray-600" />;
    }
    return <ArrowPathIcon className="h-6 w-6 text-primary-600" />;
  };

  const getStatusBadge = (state) => {
    const badges = {
      open: 'bg-warning-100 text-warning-800 border-warning-200',
      merged: 'bg-success-100 text-success-800 border-success-200',
      closed: 'bg-gray-100 text-gray-800 border-gray-200'
    };
    return badges[state] || badges.open;
  };

  const getActivityGradient = (state) => {
    if (state === 'merged') return 'from-success-50 to-success-100/50';
    if (state === 'open') return 'from-warning-50 to-warning-100/50';
    if (state === 'closed') return 'from-gray-50 to-gray-100/50';
    return 'from-primary-50 to-primary-100/50';
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-gray-900">Recent Activity</h3>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-500">{activities.length} recent PRs</span>
          <SparklesIcon className="h-5 w-5 text-primary-500" />
        </div>
      </div>
      
      <div className="flow-root">
        <ul className="-mb-8 space-y-4">
          {activities.map((activity, idx) => (
            <li key={idx} className="relative">
              {idx !== activities.length - 1 && (
                <span
                  className="absolute top-10 left-5 -ml-px h-full w-0.5 bg-gradient-to-b from-gray-200 to-transparent"
                  aria-hidden="true"
                />
              )}
              
              <div className={`relative group`}>
                <div className={`bg-gradient-to-r ${getActivityGradient(activity.state)} rounded-xl border border-gray-200 p-4 transition-all duration-200 hover:shadow-md hover:scale-[1.01] cursor-pointer`}>
                  <div className="flex items-start space-x-4">
                    {/* Icon */}
                    <div className="flex-shrink-0">
                      <div className="h-10 w-10 rounded-full bg-white shadow-sm flex items-center justify-center ring-2 ring-white">
                        {getStatusIcon(activity.state)}
                      </div>
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      {/* Title */}
                      <div className="flex items-start justify-between">
                        <p className="text-sm font-semibold text-gray-900 truncate pr-2">
                          {activity.title}
                        </p>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusBadge(activity.state)}`}>
                          {activity.state}
                        </span>
                      </div>
                      
                      {/* Developer Info */}
                      <div className="mt-2 flex items-center text-sm text-gray-600">
                        <UserCircleIcon className="h-4 w-4 mr-1.5 text-gray-400" />
                        <span className="font-medium">{activity.developer || 'Unknown Developer'}</span>
                      </div>
                      
                      {/* Timestamp */}
                      {activity.created_at && (
                        <div className="mt-2 flex items-center text-xs text-gray-500">
                          <ClockIcon className="h-3.5 w-3.5 mr-1" />
                          <time dateTime={activity.created_at}>
                            {format(new Date(activity.created_at), 'MMM d, yyyy • HH:mm')}
                          </time>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
      
      {/* Footer */}
      {activities.length >= 10 && (
        <div className="mt-6 pt-4 border-t border-gray-200">
          <p className="text-center text-sm text-gray-500">
            Showing {activities.length} most recent activities
          </p>
        </div>
      )}
    </div>
  );
};

export default ActivityFeed;

