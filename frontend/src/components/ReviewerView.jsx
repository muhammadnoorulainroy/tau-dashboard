import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../services/api.config';
import { 
  ClipboardDocumentCheckIcon,
  CheckIcon,
  XMarkIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline';

const ReviewerView = ({ lastUpdate }) => {
  const [reviewers, setReviewers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isFiltering, setIsFiltering] = useState(false);
  const [sortBy, setSortBy] = useState('total_reviews');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [domains, setDomains] = useState([]);

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
    fetchReviewers();
  }, [lastUpdate, sortBy, debouncedSearchTerm, selectedDomain]);

  const fetchDomains = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/domains/list`);
      setDomains(response.data.domains || []);
    } catch (error) {
      console.error('Error fetching domains:', error);
    }
  };

  const fetchReviewers = async () => {
    // Only show full loading on initial load, use subtle indicator for filtering
    if (reviewers.length === 0) {
      setLoading(true);
    } else {
      setIsFiltering(true);
    }
    
    try {
      const params = { sort_by: sortBy };
      if (debouncedSearchTerm) params.search = debouncedSearchTerm;
      if (selectedDomain) params.domain = selectedDomain;
      
      const response = await axios.get(`${API_BASE_URL}/reviewers`, { params });
      setReviewers(response.data.data);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Error fetching reviewers:', error);
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
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Reviewers</h2>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            Showing: {reviewers.length} / {total} reviewers
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
              placeholder="Search by reviewer name..."
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

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reviewer
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('total_reviews')}
                >
                  <div className="flex items-center justify-center">
                    Total Reviews
                    {sortBy === 'total_reviews' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('approved_reviews')}
                >
                  <div className="flex items-center justify-center">
                    Approved
                    {sortBy === 'approved_reviews' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('changes_requested')}
                >
                  <div className="flex items-center justify-center">
                    Changes Requested
                    {sortBy === 'changes_requested' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Approval Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Domains
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Recent Activity
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {reviewers.map((reviewer) => {
                const approvalRate = reviewer.total_reviews > 0 
                  ? ((reviewer.approved_reviews / reviewer.total_reviews) * 100).toFixed(1) 
                  : 0;
                
                return (
                  <tr key={reviewer.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-success-400 to-success-600 flex items-center justify-center text-white">
                            <ClipboardDocumentCheckIcon className="h-6 w-6" />
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">
                            {reviewer.username}
                          </div>
                          <div className="text-sm text-gray-500">
                            Reviewer
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="text-lg font-semibold text-gray-900">{reviewer.total_reviews}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-800">
                        <CheckIcon className="h-3 w-3 mr-1" />
                        {reviewer.approved_reviews}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
                        <XMarkIcon className="h-3 w-3 mr-1" />
                        {reviewer.changes_requested}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-[100px]">
                          <div 
                            className={`h-2 rounded-full ${
                              approvalRate > 70 ? 'bg-success-500' : 
                              approvalRate > 40 ? 'bg-warning-500' : 'bg-danger-500'
                            }`}
                            style={{ width: `${approvalRate}%` }}
                          ></div>
                        </div>
                        <span className="text-xs font-medium text-gray-700 ml-2">{approvalRate}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {reviewer.metrics?.domains && Object.keys(reviewer.metrics.domains).slice(0, 3).map(domain => (
                          <span key={domain} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                            {domain} ({reviewer.metrics.domains[domain]})
                          </span>
                        ))}
                        {reviewer.metrics?.domains && Object.keys(reviewer.metrics.domains).length > 3 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
                            +{Object.keys(reviewer.metrics.domains).length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {reviewer.metrics?.recent_reviews && reviewer.metrics.recent_reviews.length > 0 ? (
                        <div className="text-xs">
                          <div className="text-gray-900 truncate max-w-xs">
                            {reviewer.metrics.recent_reviews[0].pr_title}
                          </div>
                          <div className={`mt-1 ${
                            reviewer.metrics.recent_reviews[0].state === 'APPROVED' ? 'text-success-600' : 'text-warning-600'
                          }`}>
                            {reviewer.metrics.recent_reviews[0].state}
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-500">No recent activity</span>
                      )}
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

export default ReviewerView;


