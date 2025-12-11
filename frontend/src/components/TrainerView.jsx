import React, { useState, useEffect } from 'react';
import { getTrainers, getEnvironments } from '../services/api';
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

const TrainerView = ({ lastUpdate }) => {
  const [trainers, setTrainers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isFiltering, setIsFiltering] = useState(false);
  const [isSorting, setIsSorting] = useState(false);
  const [sortBy, setSortBy] = useState('total_tasks');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [domains, setDomains] = useState([]);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const perPageOptions = [10, 25, 50, 100];

  useEffect(() => {
    fetchDomains();
  }, []);

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    setTrainers([]);
    setIsFiltering(true);
    fetchTrainers();
  }, [lastUpdate, sortBy, sortOrder, debouncedSearchTerm, selectedDomain, page, perPage]);
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [sortBy, sortOrder, debouncedSearchTerm, selectedDomain]);

  const fetchDomains = async () => {
    try {
      const response = await getEnvironments();
      setDomains((response.data || []).map(e => e.name));
    } catch (error) {
      console.error('Error fetching domains:', error);
    }
  };

  const fetchTrainers = async () => {
    if (trainers.length === 0 && !isFiltering) {
      setLoading(true);
    }
    
    try {
      const params = { 
        sort_by: sortBy,
        sort_order: sortOrder,
        page: page,
        per_page: perPage
      };
      if (debouncedSearchTerm) params.search = debouncedSearchTerm;
      if (selectedDomain) params.domain = selectedDomain;
      
      const response = await getTrainers(params);
      setTrainers(response.data.data || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      setTrainers([]);
      setTotal(0);
      console.error('Error fetching trainers:', error);
    } finally {
      setLoading(false);
      setIsFiltering(false);
      setIsSorting(false);
    }
  };

  const handleSort = (field) => {
    setIsSorting(true);
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return null;
    return sortOrder === 'desc' ? 
      <ChevronDownIcon className="h-4 w-4 ml-1" /> : 
      <ChevronUpIcon className="h-4 w-4 ml-1" />;
  };

  const totalPages = Math.ceil(total / perPage);

  if (loading && trainers.length === 0) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-48"></div>
        <div className="card">
          <div className="skeleton h-[600px]"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Trainers</h2>
        <span className="text-sm text-gray-500">
          Total: {total} trainers
        </span>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search trainers..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input pl-10 w-full"
              />
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <FunnelIcon className="h-5 w-5 text-gray-400" />
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="input"
            >
              <option value="">All Domains</option>
              {domains.map(domain => (
                <option key={domain} value={domain}>{domain.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden relative">
        {/* Sorting overlay */}
        {isSorting && (
          <div className="absolute inset-0 bg-white/70 z-10 flex items-center justify-center">
            <div className="flex items-center gap-2 text-gray-600">
              <ArrowPathIcon className="h-5 w-5 animate-spin" />
              <span className="text-sm font-medium">Sorting...</span>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left">
                  <button 
                    onClick={() => handleSort('trainer_name')}
                    className="flex items-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700"
                  >
                    Trainer
                    <SortIcon field="trainer_name" />
                  </button>
                </th>
                <th className="px-6 py-3 text-center">
                  <button 
                    onClick={() => handleSort('total_tasks')}
                    className="flex items-center justify-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700 mx-auto"
                  >
                    Total
                    <SortIcon field="total_tasks" />
                  </button>
                </th>
                <th className="px-6 py-3 text-center">
                  <button 
                    onClick={() => handleSort('approved_count')}
                    className="flex items-center justify-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700 mx-auto"
                  >
                    Approved
                    <SortIcon field="approved_count" />
                  </button>
                </th>
                <th className="px-6 py-3 text-center">
                  <button 
                    onClick={() => handleSort('rework_count')}
                    className="flex items-center justify-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700 mx-auto"
                  >
                    Rework
                    <SortIcon field="rework_count" />
                  </button>
                </th>
                <th className="px-6 py-3 text-center">
                  <button 
                    onClick={() => handleSort('in_review_count')}
                    className="flex items-center justify-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700 mx-auto"
                  >
                    In Review
                    <SortIcon field="in_review_count" />
                  </button>
                </th>
                <th className="px-6 py-3 text-center">
                  <button 
                    onClick={() => handleSort('approval_rate')}
                    className="flex items-center justify-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700 mx-auto"
                  >
                    Approval Rate
                    <SortIcon field="approval_rate" />
                  </button>
                </th>
                <th className="px-6 py-3 text-center">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Difficulty
                  </span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {trainers.map((trainer, index) => (
                <tr key={trainer.trainer_email} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center">
                      <div className="h-10 w-10 flex-shrink-0 bg-primary-100 rounded-full flex items-center justify-center">
                        <UserIcon className="h-5 w-5 text-primary-600" />
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">
                          {trainer.trainer_name || 'Unknown'}
                        </div>
                        <div className="text-sm text-gray-500">
                          {trainer.trainer_email}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <div className="flex items-center justify-center">
                      <DocumentTextIcon className="h-4 w-4 text-gray-400 mr-1" />
                      <span className="text-sm font-medium text-gray-900">{trainer.total_tasks}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <div className="flex items-center justify-center">
                      <CheckCircleIcon className="h-4 w-4 text-success-500 mr-1" />
                      <span className="text-sm font-medium text-success-600">{trainer.approved_count}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <div className="flex items-center justify-center">
                      <ArrowPathIcon className="h-4 w-4 text-danger-500 mr-1" />
                      <span className="text-sm font-medium text-danger-600">{trainer.rework_count}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className="text-sm text-gray-600">{trainer.in_review_count}</span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      trainer.approval_rate >= 0.7 ? 'bg-success-100 text-success-800' :
                      trainer.approval_rate >= 0.4 ? 'bg-warning-100 text-warning-800' :
                      'bg-danger-100 text-danger-800'
                    }`}>
                      {(trainer.approval_rate * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex justify-center gap-1">
                      {trainer.expert_count > 0 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                          E:{trainer.expert_count}
                        </span>
                      )}
                      {trainer.hard_count > 0 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                          H:{trainer.hard_count}
                        </span>
                      )}
                      {trainer.medium_count > 0 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                          M:{trainer.medium_count}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Show</span>
              <select
                value={perPage}
                onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}
                className="input text-sm py-1 px-2"
              >
                {perPageOptions.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
              <span className="text-sm text-gray-500">per page</span>
            </div>
            <div className="text-sm text-gray-500">
              Showing {((page - 1) * perPage) + 1} to {Math.min(page * perPage, total)} of {total} trainers
            </div>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn btn-secondary btn-sm"
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <span className="text-sm text-gray-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn btn-secondary btn-sm"
              >
                <ChevronRightIcon className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TrainerView;

