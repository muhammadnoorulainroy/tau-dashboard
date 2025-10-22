import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../services/api.config';
import { 
  UserIcon, 
  DocumentTextIcon, 
  ArrowPathIcon,
  CheckCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

const DeveloperView = ({ lastUpdate }) => {
  const [developers, setDevelopers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isFiltering, setIsFiltering] = useState(false);
  const [sortBy, setSortBy] = useState('total_prs');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [domains, setDomains] = useState([]);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    fetchDomains();
  }, []);

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300); // Wait 300ms after user stops typing

    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    // Clear data when filters change to prevent stale/mixed data
    setDevelopers([]);
    setIsFiltering(true);
    fetchDevelopers();
  }, [lastUpdate, sortBy, debouncedSearchTerm, selectedDomain, page, limit]);
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [sortBy, debouncedSearchTerm, selectedDomain]);

  const fetchDomains = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/domains/list`);
      setDomains(response.data.domains || []);
    } catch (error) {
      console.error('Error fetching domains:', error);
    }
  };

  const fetchDevelopers = async () => {
    // Only show full loading on initial load
    if (developers.length === 0 && !isFiltering) {
      setLoading(true);
    }
    
    try {
      const offset = (page - 1) * limit;
      const params = { 
        sort_by: sortBy,
        limit: limit,
        offset: offset
      };
      if (debouncedSearchTerm) params.search = debouncedSearchTerm;
      if (selectedDomain) params.domain = selectedDomain;
      
      const response = await axios.get(`${API_BASE_URL}/developers`, { params });
      // Always replace data, never append
      setDevelopers(response.data.data || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      console.error('Error fetching developers:', error);
      setDevelopers([]);
      setTotal(0);
    } finally {
      setLoading(false);
      setIsFiltering(false);
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
    <div className="flex flex-col h-full">
      {/* Fixed Header */}
      <div className="flex-shrink-0 space-y-4 mb-4">
        <div className="flex justify-between items-center">
          <h2 className="text-3xl font-bold text-gray-900">Developers</h2>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">
              Showing: {developers.length} / {total} developers
              {isFiltering && (
                <svg className="inline-block animate-spin h-3 w-3 ml-2 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
            </span>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="card">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Search Bar */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                placeholder="Search by developer name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>

            {/* Domain Filter */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FunnelIcon className="h-5 w-5 text-gray-400" />
              </div>
              <select
                value={selectedDomain}
                onChange={(e) => setSelectedDomain(e.target.value)}
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value="">All Domains</option>
                {domains.map((domain) => (
                  <option key={domain.id} value={domain.name}>
                    {domain.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Scrollable Table Container */}
      <div className="flex-1 card overflow-hidden flex flex-col">
        <div className="flex-1 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-56">
                  Developer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-52">
                  Email
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-32"
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
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-28"
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
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-32"
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
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-32"
                  onClick={() => handleSort('closed_prs')}
                >
                  <div className="flex items-center justify-center">
                    Closed PRs
                    {sortBy === 'closed_prs' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-32"
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
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        {dev.email || 'N/A'}
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
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        {dev.closed_prs || 0}
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
                        {dev.metrics?.domains && Array.isArray(dev.metrics.domains) && dev.metrics.domains.slice(0, 3).map(domain => (
                          <span key={domain} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                            {domain}
                          </span>
                        ))}
                        {dev.metrics?.domains && Array.isArray(dev.metrics.domains) && dev.metrics.domains.length > 3 && (
                          <span 
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500 cursor-help"
                            title={dev.metrics.domains.slice(3).join(', ')}
                          >
                            +{dev.metrics.domains.length - 3}
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
        
        {/* Pagination Controls */}
        <div className="flex-shrink-0 px-6 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {/* Rows per page */}
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-700">Rows per page:</span>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>
            
            {/* Page navigation */}
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className={`p-2 rounded-md ${
                  page === 1 
                    ? 'text-gray-400 cursor-not-allowed' 
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <ChevronLeftIcon className="h-5 w-5" />
              </button>
              <span className="text-sm text-gray-700">
                Page {page} of {Math.ceil(total / limit)}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= Math.ceil(total / limit)}
                className={`p-2 rounded-md ${
                  page >= Math.ceil(total / limit)
                    ? 'text-gray-400 cursor-not-allowed' 
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <ChevronRightIcon className="h-5 w-5" />
              </button>
            </div>
          </div>
          
          {/* Items count */}
          <div className="text-sm text-gray-500">
            Showing {((page - 1) * limit) + 1} to {Math.min(page * limit, total)} of {total} developers
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeveloperView;


