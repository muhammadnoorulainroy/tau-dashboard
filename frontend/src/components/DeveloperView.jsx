import React, { useState, useEffect } from 'react';
import { getDeveloperMetrics } from '../services/api';
import { 
  UserIcon, 
  DocumentTextIcon, 
  ArrowPathIcon,
  CheckCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';

const DeveloperView = ({ lastUpdate }) => {
  const [developers, setDevelopers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('total_prs');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    fetchDevelopers();
  }, [lastUpdate, sortBy]);

  const fetchDevelopers = async () => {
    setLoading(true);
    try {
      const response = await getDeveloperMetrics({ sort_by: sortBy });
      setDevelopers(response.data.data);  // Updated: response.data.data
      setTotal(response.data.total);      // New: get total count
    } catch (error) {
      console.error('Error fetching developers:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-48"></div>
        <div className="card">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-16 mb-4"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Developers</h2>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            Total: {total} developers
          </span>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Developer
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('total_prs')}
                >
                  <div className="flex items-center justify-center">
                    Total PRs
                    {sortBy === 'total_prs' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('open_prs')}
                >
                  <div className="flex items-center justify-center">
                    Open PRs
                    {sortBy === 'open_prs' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('merged_prs')}
                >
                  <div className="flex items-center justify-center">
                    Merged PRs
                    {sortBy === 'merged_prs' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('total_rework')}
                >
                  <div className="flex items-center justify-center">
                    Total Rework
                    {sortBy === 'total_rework' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Domains
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Performance
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {developers.map((dev) => {
                const mergeRate = dev.total_prs > 0 ? ((dev.merged_prs / dev.total_prs) * 100).toFixed(1) : 0;
                const reworkRate = dev.total_prs > 0 ? (dev.total_rework / dev.total_prs).toFixed(2) : 0;
                
                return (
                  <tr key={dev.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white font-semibold">
                            {dev.username.charAt(0).toUpperCase()}
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">
                            {dev.username}
                          </div>
                          <div className="text-sm text-gray-500">
                            @{dev.github_login || 'N/A'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="text-lg font-semibold text-gray-900">{dev.total_prs}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
                        {dev.open_prs}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-800">
                        {dev.merged_prs}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        dev.total_rework > 5 ? 'bg-danger-100 text-danger-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {dev.total_rework}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {dev.metrics?.domains && Object.keys(dev.metrics.domains).slice(0, 3).map(domain => (
                          <span key={domain} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                            {domain}
                          </span>
                        ))}
                        {dev.metrics?.domains && Object.keys(dev.metrics.domains).length > 3 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
                            +{Object.keys(dev.metrics.domains).length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="space-y-1">
                        <div className="flex items-center">
                          <span className="text-xs text-gray-500 w-20">Merge Rate:</span>
                          <div className="flex-1 bg-gray-200 rounded-full h-2 ml-2">
                            <div 
                              className="bg-success-500 h-2 rounded-full"
                              style={{ width: `${mergeRate}%` }}
                            ></div>
                          </div>
                          <span className="text-xs font-medium text-gray-700 ml-2">{mergeRate}%</span>
                        </div>
                        <div className="flex items-center">
                          <span className="text-xs text-gray-500 w-20">Rework Avg:</span>
                          <span className={`text-xs font-medium ml-2 ${reworkRate > 2 ? 'text-danger-600' : 'text-gray-700'}`}>
                            {reworkRate}
                          </span>
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DeveloperView;


