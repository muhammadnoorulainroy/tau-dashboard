import React from 'react';
import {
  HomeIcon,
  UserGroupIcon,
  ClipboardDocumentCheckIcon,
  FolderIcon,
  DocumentTextIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';

const navigation = [
  { name: 'Dashboard', value: 'dashboard', icon: HomeIcon },
  { name: 'Developers', value: 'developers', icon: UserGroupIcon },
  { name: 'Reviewers', value: 'reviewers', icon: ClipboardDocumentCheckIcon },
  { name: 'Domains', value: 'domains', icon: FolderIcon },
  { name: 'Pull Requests', value: 'pull-requests', icon: DocumentTextIcon },
  { name: 'Aggregation', value: 'aggregation', icon: ChartBarIcon },
];

const Sidebar = ({ activeView, setActiveView, isOpen }) => {
  return (
    <div className={`
      fixed inset-y-0 left-0 z-10 w-64 bg-white shadow-lg transform transition-transform duration-300 pt-16
      ${isOpen ? 'translate-x-0' : '-translate-x-full'}
    `}>
      <div className="flex flex-col h-full">
        <nav className="flex-1 px-2 py-4 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.value;
            
            return (
              <button
                key={item.value}
                onClick={() => setActiveView(item.value)}
                className={`
                  w-full flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors
                  ${isActive
                    ? 'bg-primary-100 text-primary-900'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }
                `}
              >
                <Icon className={`mr-3 h-5 w-5 ${isActive ? 'text-primary-600' : 'text-gray-400'}`} />
                {item.name}
              </button>
            );
          })}
        </nav>
        
        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-600"></div>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-gray-700">TAU System</p>
              <p className="text-xs text-gray-500">Version 1.0.0</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;


