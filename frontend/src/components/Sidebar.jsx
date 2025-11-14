import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  HomeIcon,
  UserGroupIcon,
  ClipboardDocumentCheckIcon,
  FolderIcon,
  DocumentTextIcon,
  ChartBarIcon,
  CubeIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';

const navigation = [
  { name: 'Dashboard', path: '/dashboard', icon: HomeIcon },
  { name: 'Interfaces', path: '/interfaces', icon: CubeIcon },
  { name: 'Task Similarity', path: '/task-similarity', icon: SparklesIcon },
  { name: 'Developers', path: '/developers', icon: UserGroupIcon },
  { name: 'Reviewers', path: '/reviewers', icon: ClipboardDocumentCheckIcon },
  { name: 'Domains', path: '/domains', icon: FolderIcon },
  { name: 'Pull Requests', path: '/pull-requests', icon: DocumentTextIcon },
  { name: 'Aggregation', path: '/aggregation', icon: ChartBarIcon },
];

const Sidebar = ({ isOpen }) => {
  return (
    <div className={`
      fixed inset-y-0 left-0 z-10 w-64 bg-white shadow-lg transform transition-transform duration-300 pt-16
      ${isOpen ? 'translate-x-0' : '-translate-x-full'}
    `}>
      <div className="flex flex-col h-full">
        <nav className="flex-1 px-2 py-4 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;
            
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) => `
                  w-full flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors
                  ${isActive
                    ? 'bg-primary-100 text-primary-900'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }
                `}
              >
                {({ isActive }) => (
                  <>
                    <Icon className={`mr-3 h-5 w-5 ${isActive ? 'text-primary-600' : 'text-gray-400'}`} />
                    {item.name}
                  </>
                )}
              </NavLink>
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


