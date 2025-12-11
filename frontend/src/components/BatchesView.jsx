import React, { useState, useEffect } from 'react';
import { getBatches } from '../services/api';
import { 
  ArchiveBoxIcon, 
  LockClosedIcon,
  LockOpenIcon,
  CheckCircleIcon,
  ClockIcon,
  ChevronUpDownIcon
} from '@heroicons/react/24/outline';

const STATUS_COLORS = {
  'inprogress': 'bg-amber-100 text-amber-800',
  'delivered': 'bg-green-100 text-green-800',
  'closed': 'bg-gray-100 text-gray-800'
};

const SORT_OPTIONS = [
  { value: 'task_count_desc', label: 'Tasks (High to Low)' },
  { value: 'task_count_asc', label: 'Tasks (Low to High)' },
  { value: 'date_opened_desc', label: 'Newest First' },
  { value: 'date_opened_asc', label: 'Oldest First' },
  { value: 'batch_name_asc', label: 'Name (A-Z)' },
  { value: 'batch_name_desc', label: 'Name (Z-A)' },
];

const BatchesView = ({ lastUpdate }) => {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStatus, setSelectedStatus] = useState('');
  const [sortOption, setSortOption] = useState('task_count_desc');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const perPageOptions = [10, 25, 50, 100];

  const sortBatches = (data) => {
    const [field, order] = sortOption.split('_').reduce((acc, part, idx, arr) => {
      if (idx === arr.length - 1) {
        return [acc.join('_'), part];
      }
      return [[...acc, part].join('_')];
    }, [[]]);
    
    // Simpler parsing
    const isDesc = sortOption.endsWith('_desc');
    const sortField = sortOption.replace('_desc', '').replace('_asc', '');
    
    return [...data].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      
      // Handle dates
      if (sortField === 'date_opened' || sortField === 'date_closed') {
        aVal = aVal ? new Date(aVal).getTime() : 0;
        bVal = bVal ? new Date(bVal).getTime() : 0;
      }
      
      // Handle strings
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal?.toLowerCase() || '';
      }
      
      // Handle nulls
      if (aVal == null) aVal = 0;
      if (bVal == null) bVal = 0;
      
      if (isDesc) {
        return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
      }
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
    });
  };

  useEffect(() => {
    fetchBatches();
  }, [lastUpdate, selectedStatus]);

  const fetchBatches = async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedStatus) params.status = selectedStatus;
      
      const response = await getBatches(params);
      setBatches(response.data || []);
    } catch (error) {
      setBatches([]);
      console.error('Error fetching batches:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-48"></div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card skeleton h-48"></div>
          ))}
        </div>
      </div>
    );
  }

  // Sort and pagination calculations
  const sortedBatches = sortBatches(batches);
  const totalPages = Math.ceil(sortedBatches.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedBatches = sortedBatches.slice(startIndex, startIndex + itemsPerPage);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Batches</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <ChevronUpDownIcon className="h-5 w-5 text-gray-400" />
            <select
              value={sortOption}
              onChange={(e) => { setSortOption(e.target.value); setCurrentPage(1); }}
              className="input"
            >
              {SORT_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <select
            value={selectedStatus}
            onChange={(e) => { setSelectedStatus(e.target.value); setCurrentPage(1); }}
            className="input"
          >
            <option value="">All Statuses</option>
            <option value="inprogress">In Progress</option>
            <option value="delivered">Delivered</option>
          </select>
          <span className="text-sm text-gray-500">
            Total: {batches.length} batches
          </span>
        </div>
      </div>

      {/* Batch Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {paginatedBatches.map((batch) => (
          <div 
            key={batch.id}
            className="card hover:shadow-md transition-shadow"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <ArchiveBoxIcon className="h-5 w-5 text-primary-600 mr-2" />
                <h3 className="text-sm font-semibold text-gray-900 truncate max-w-[200px]" title={batch.batch_name}>
                  {batch.batch_name}
                </h3>
              </div>
              {batch.is_locked ? (
                <LockClosedIcon className="h-5 w-5 text-red-500" title="Locked" />
              ) : (
                <LockOpenIcon className="h-5 w-5 text-green-500" title="Open" />
              )}
            </div>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Environment</span>
                <span className="text-sm font-medium text-gray-900">
                  {batch.environment?.replace(/_/g, ' ') || 'N/A'}
                </span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Status</span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[batch.status] || 'bg-gray-100 text-gray-800'}`}>
                  {batch.status === 'inprogress' ? 'In Progress' : batch.status}
                </span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Tasks</span>
                <span className="text-sm font-bold text-primary-600">{batch.task_count}</span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Author</span>
                <span className="text-sm text-gray-900">{batch.author || 'Unknown'}</span>
              </div>
              
              <div className="border-t pt-3 mt-3">
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <div className="flex items-center">
                    <ClockIcon className="h-4 w-4 mr-1" />
                    Opened: {batch.date_opened ? new Date(batch.date_opened).toLocaleDateString() : 'N/A'}
                  </div>
                  {batch.date_closed && (
                    <div className="flex items-center">
                      <CheckCircleIcon className="h-4 w-4 mr-1" />
                      Closed: {new Date(batch.date_closed).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex gap-2 mt-2">
                {batch.is_exported && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                    Exported
                  </span>
                )}
                {batch.is_locked && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                    Locked
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {batches.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No batches found
        </div>
      )}

      {/* Pagination */}
      {batches.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Show</span>
                <select
                  value={itemsPerPage}
                  onChange={(e) => { setItemsPerPage(Number(e.target.value)); setCurrentPage(1); }}
                  className="px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {perPageOptions.map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
                <span className="text-sm text-gray-500">per page</span>
              </div>
              <div className="text-sm text-gray-700">
                Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, sortedBatches.length)} of {sortedBatches.length} batches
              </div>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className={`px-3 py-2 text-sm font-medium rounded-md ${
                    currentPage === 1
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                  }`}
                >
                  Previous
                </button>
                <span className="text-sm text-gray-700">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className={`px-3 py-2 text-sm font-medium rounded-md ${
                    currentPage === totalPages
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                  }`}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default BatchesView;

