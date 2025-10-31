import React, { useState, useEffect } from 'react';
import { getPullRequests, getDomainMetrics } from '../services/api';
import { format } from 'date-fns';
import {
  FunnelIcon,
  MagnifyingGlassIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  CheckCircleIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';

const PullRequestsView = ({ lastUpdate }) => {
  const [prs, setPRs] = useState([]);
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    state: '',
    domain: '',
    developer: '',
    search: ''
  });
  const [pagination, setPagination] = useState({
    limit: 20,
    offset: 0,
    total: 0
  });

  useEffect(() => {
    fetchDomains();
  }, []);

  useEffect(() => {
    fetchPRs();
  }, [lastUpdate, filters, pagination.offset]);

  const fetchDomains = async () => {
    try {
      const response = await getDomainMetrics();
      setDomains(response.data.map(d => d.domain));
    } catch (error) {
      console.error('Error fetching domains:', error);
    }
  };

  const fetchPRs = async () => {
    setLoading(true);
    try {
      const params = {
        limit: pagination.limit,
        offset: pagination.offset,
        ...(filters.state && { state: filters.state }),
        ...(filters.domain && { domain: filters.domain }),
        ...(filters.developer && { developer: filters.developer })
      };
      
      const response = await getPullRequests(params);
      setPRs(response.data);
      // Note: Total count would need to be returned from API for proper pagination
    } catch (error) {
      console.error('Error fetching PRs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPagination(prev => ({ ...prev, offset: 0 }));
  };

  const handlePageChange = (direction) => {
    if (direction === 'next') {
      setPagination(prev => ({ ...prev, offset: prev.offset + prev.limit }));
    } else if (direction === 'prev' && pagination.offset >= pagination.limit) {
      setPagination(prev => ({ ...prev, offset: prev.offset - prev.limit }));
    }
  };

  const getStateColor = (pr) => {
    if (pr.merged) return 'bg-success-100 text-success-800';
    if (pr.state === 'open') return 'bg-warning-100 text-warning-800';
    return 'bg-gray-100 text-gray-800';
  };

  const getStateIcon = (pr) => {
    if (pr.merged) return <CheckCircleIcon className="h-4 w-4" />;
    if (pr.state === 'open') return <ClockIcon className="h-4 w-4" />;
    return <XMarkIcon className="h-4 w-4" />;
  };

  const getLabelColor = (label) => {
    if (label.includes('expert')) return 'bg-primary-100 text-primary-800';
    if (label.includes('ready')) return 'bg-success-100 text-success-800';
    if (label.includes('pending')) return 'bg-warning-100 text-warning-800';
    if (label.includes('approved')) return 'bg-success-100 text-success-800';
    return 'bg-gray-100 text-gray-700';
  };

  const filteredPRs = prs.filter(pr => {
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return pr.title.toLowerCase().includes(searchLower) ||
             pr.developer_username?.toLowerCase().includes(searchLower) ||
             pr.author_login.toLowerCase().includes(searchLower) ||
             pr.turing_email?.toLowerCase().includes(searchLower);
    }
    return true;
  });

  if (loading && prs.length === 0) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-48"></div>
        <div className="card">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-24 mb-4"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Fixed Header */}
      <div className="flex-shrink-0 space-y-4 mb-4">
        <div className="flex justify-between items-center">
          <h2 className="text-3xl font-bold text-gray-900">Pull Requests</h2>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-500">
              Showing {filteredPRs.length} PRs
            </span>
          </div>
        </div>

        {/* Filters */}
        <div className="card">
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search PRs..."
                  value={filters.search}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                  className="pl-10 pr-3 py-2 border border-gray-300 rounded-md w-full focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            
            <select
              value={filters.state}
              onChange={(e) => handleFilterChange('state', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All States</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
              <option value="merged">Merged</option>
            </select>

            <select
              value={filters.domain}
              onChange={(e) => handleFilterChange('domain', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All Domains</option>
              {domains.map(domain => (
                <option key={domain} value={domain}>{domain}</option>
              ))}
            </select>

            <input
              type="text"
              placeholder="Developer email or username..."
              value={filters.developer}
              onChange={(e) => handleFilterChange('developer', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            />

            <button
              onClick={() => setFilters({ state: '', domain: '', developer: '', search: '' })}
              className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Table Container */}
      <div className="flex-1 card overflow-hidden flex flex-col">
        <div className="flex-1 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  PR
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Developer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Domain
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Labels
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Rework
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Failed Checks
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Task Success
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredPRs.map((pr) => (
                <tr key={pr.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        #{pr.number}
                      </div>
                      <div className="text-sm text-gray-500 max-w-md truncate">
                        {pr.title}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {pr.turing_email ? (
                      <>
                        <div className="text-sm text-gray-900">{pr.turing_email}</div>
                        <div className="text-sm text-gray-500">@{pr.author_login}</div>
                      </>
                    ) : (
                      <>
                        <div className="text-sm text-gray-900">{pr.developer_username || 'N/A'}</div>
                        <div className="text-sm text-gray-500">@{pr.author_login}</div>
                      </>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      {pr.domain || 'N/A'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStateColor(pr)}`}>
                      {getStateIcon(pr)}
                      <span className="ml-1">
                        {pr.merged ? 'Merged' : pr.state}
                      </span>
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {pr.labels.slice(0, 3).map((label, idx) => (
                        <span
                          key={idx}
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getLabelColor(label)}`}
                        >
                          {label}
                        </span>
                      ))}
                      {pr.labels.length > 3 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
                          +{pr.labels.length - 3}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-center">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      pr.rework_count > 2 ? 'bg-danger-100 text-danger-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {pr.rework_count}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {pr.failed_check_names && pr.failed_check_names.length > 0 ? (
                        <>
                          {pr.failed_check_names.slice(0, 3).map((checkName, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800"
                            >
                              {checkName}
                            </span>
                          ))}
                          {pr.failed_check_names.length > 3 && (
                            <span
                              title={pr.failed_check_names.slice(3).join(', ')}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 cursor-help"
                            >
                              +{pr.failed_check_names.length - 3}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          None
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-center">
                    {pr.task_trials_total > 0 ? (
                      <div className="flex flex-col items-center">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          pr.task_success_rate === 100 ? 'bg-green-100 text-green-800' :
                          pr.task_success_rate >= 50 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {pr.task_success_rate}%
                        </span>
                        <span className="text-xs text-gray-500 mt-1">
                          {pr.task_trials_passed}/{pr.task_trials_total}
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">N/A</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {format(new Date(pr.created_at), 'MMM d, yyyy')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Fixed Pagination */}
        <div className="flex-shrink-0 px-6 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handlePageChange('prev')}
              disabled={pagination.offset === 0}
              className={`p-2 rounded-md ${
                pagination.offset === 0 
                  ? 'text-gray-400 cursor-not-allowed' 
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <ChevronLeftIcon className="h-5 w-5" />
            </button>
            <span className="text-sm text-gray-700">
              Page {Math.floor(pagination.offset / pagination.limit) + 1}
            </span>
            <button
              onClick={() => handlePageChange('next')}
              disabled={filteredPRs.length < pagination.limit}
              className={`p-2 rounded-md ${
                filteredPRs.length < pagination.limit
                  ? 'text-gray-400 cursor-not-allowed' 
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <ChevronRightIcon className="h-5 w-5" />
            </button>
          </div>
          <div className="text-sm text-gray-500">
            Showing {pagination.offset + 1} to {pagination.offset + filteredPRs.length}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PullRequestsView;


