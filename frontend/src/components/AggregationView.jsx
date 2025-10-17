import React, { useState, useEffect } from 'react';
import { 
  BuildingOfficeIcon, 
  UserGroupIcon,
  TrophyIcon,
  ShieldCheckIcon,
  ArrowPathIcon,
  ChevronLeftIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';
import { API_BASE_URL } from '../services/api.config';

const AggregationView = () => {
  const [activeTab, setActiveTab] = useState('domains');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [domains, setDomains] = useState([]);
  const [selectedDomain, setSelectedDomain] = useState('');
  const [statuses, setStatuses] = useState([]);
  const [selectedStatus, setSelectedStatus] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [pagination, setPagination] = useState({
    page: 1,
    rowsPerPage: 20
  });

  const tabs = [
    { id: 'domains', label: 'Domain wise', icon: BuildingOfficeIcon, endpoint: '/aggregation/domains' },
    { id: 'trainers', label: 'Trainer wise', icon: UserGroupIcon, endpoint: '/aggregation/trainers' },
    { id: 'pod-leads', label: 'POD Leads wise', icon: TrophyIcon, endpoint: '/aggregation/pod-leads' },
    { id: 'calibrators', label: 'Calibrators wise', icon: ShieldCheckIcon, endpoint: '/aggregation/calibrators' },
  ];

  // Fetch domains and statuses list on mount
  useEffect(() => {
    fetchDomains();
    fetchStatuses();
  }, []);

  // Fetch data when tab, domain, or status filter changes
  useEffect(() => {
    fetchData();
  }, [activeTab, selectedDomain, selectedStatus]);

  const fetchDomains = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/domains/list`);
      setDomains(response.data);
    } catch (err) {
      console.error('Failed to fetch domains:', err);
    }
  };

  const fetchStatuses = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/statuses/list`);
      setStatuses(response.data);
    } catch (err) {
      console.error('Failed to fetch statuses:', err);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = tabs.find(t => t.id === activeTab)?.endpoint;
      let url = `${API_BASE_URL}${endpoint}`;
      
      // Add filters for trainers, pod-leads, and calibrators tabs
      if (['trainers', 'pod-leads', 'calibrators'].includes(activeTab)) {
        const params = new URLSearchParams();
        if (selectedDomain) params.append('domain', selectedDomain);
        if (selectedStatus) params.append('status', selectedStatus);
        const queryString = params.toString();
        if (queryString) url += `?${queryString}`;
      }
      
      const response = await axios.get(url);
      setData(response.data);
    } catch (err) {
      setError('Failed to load data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setPagination({ page: 1, rowsPerPage: pagination.rowsPerPage }); // Reset to first page
    // Reset filters when switching to domains tab
    if (tabId === 'domains') {
      setSelectedDomain('');
      setSelectedStatus('');
    }
  };

  const handlePageChange = (newPage) => {
    setPagination({ ...pagination, page: newPage });
  };

  const handleRowsPerPageChange = (e) => {
    setPagination({ page: 1, rowsPerPage: parseInt(e.target.value) });
  };

  const syncGoogleSheets = async () => {
    setSyncing(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/google-sheets/sync`);
      alert(`✅ ${response.data.message}`);
      await fetchData();
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Failed to sync Google Sheets. Check console.';
      alert(`❌ ${errorMsg}`);
      console.error('Sync error:', err);
    } finally {
      setSyncing(false);
    }
  };

  const currentTab = tabs.find(t => t.id === activeTab);
  const Icon = currentTab?.icon;

  // Client-side pagination
  const totalItems = data.length;
  const totalPages = Math.ceil(totalItems / pagination.rowsPerPage);
  const startIndex = (pagination.page - 1) * pagination.rowsPerPage;
  const endIndex = startIndex + pagination.rowsPerPage;
  const paginatedData = data.slice(startIndex, endIndex);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">Aggregation Metrics</h1>
          <p className="text-gray-600 mt-1">Task metrics by Domain, Developer, POD Lead, and Calibrator</p>
        </div>
        <button
          onClick={syncGoogleSheets}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
        >
          <ArrowPathIcon className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Syncing...' : 'Sync Google Sheets'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200 overflow-x-auto">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center gap-2 px-6 py-3 font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'border-b-2 border-orange-500 text-orange-600'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              <TabIcon className="w-5 h-5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Filters for Trainers, POD Leads, and Calibrators */}
      {['trainers', 'pod-leads', 'calibrators'].includes(activeTab) && (
        <div className="flex flex-wrap items-center gap-4 bg-gray-50 rounded-lg p-4">
          {/* Domain Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="domain-filter" className="text-sm font-medium text-gray-700">
              Domain:
            </label>
            <select
              id="domain-filter"
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
            >
              <option value="">All Domains</option>
              {domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="status-filter" className="text-sm font-medium text-gray-700">
              Status:
            </label>
            <select
              id="status-filter"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            >
              <option value="">All Statuses</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>

          {/* Clear Filters Button */}
          {(selectedDomain || selectedStatus) && (
            <button
              onClick={() => {
                setSelectedDomain('');
                setSelectedStatus('');
              }}
              className="text-sm text-orange-600 hover:text-orange-700 font-medium"
            >
              Clear All Filters
            </button>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Summary Statistics - Moved to Top */}
      {data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-gray-500">
            <div className="text-sm text-gray-600">Total Tasks</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">
              {data.reduce((sum, item) => sum + item.total_tasks, 0)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
            <div className="text-sm text-gray-600">Completed</div>
            <div className="text-2xl font-bold text-green-600 mt-1">
              {data.reduce((sum, item) => sum + item.completed_tasks, 0)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-yellow-500">
            <div className="text-sm text-gray-600">Avg Rework %</div>
            <div className="text-2xl font-bold text-yellow-600 mt-1">
              {(data.reduce((sum, item) => sum + item.rework_percentage, 0) / data.length).toFixed(1)}%
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500">
            <div className="text-sm text-gray-600">Total Rejected</div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              {data.reduce((sum, item) => sum + item.rejected_count, 0)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
            <div className="text-sm text-gray-600">Delivery Ready</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {data.reduce((sum, item) => sum + item.delivery_ready_tasks, 0)}
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
              {Icon && <Icon className="w-6 h-6" />}
              {currentTab?.label} ({totalItems} total)
            </h2>
            {['trainers', 'pod-leads', 'calibrators'].includes(activeTab) && (selectedDomain || selectedStatus) && (
              <div className="flex gap-2">
                {selectedDomain && (
                  <span className="text-sm text-orange-600 font-medium bg-orange-50 px-3 py-1 rounded-full">
                    Domain: {selectedDomain}
                  </span>
                )}
                {selectedStatus && (
                  <span className="text-sm text-blue-600 font-medium bg-blue-50 px-3 py-1 rounded-full">
                    Status: {selectedStatus}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-500">Loading...</div>
          </div>
        ) : data.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-500">
            <p>No data available</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    {activeTab === 'domains' ? 'Domain' : 
                     activeTab === 'trainers' ? 'Developer' :
                     activeTab === 'pod-leads' ? 'POD Lead' :
                     activeTab === 'calibrators' ? 'Calibrator' : 'Name'}
                  </th>
                  {(activeTab === 'trainers' || activeTab === 'pod-leads' || activeTab === 'calibrators') && (
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                  )}
                  {activeTab === 'pod-leads' && (
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                      <div className="flex flex-col items-center">
                        <span>Trainers</span>
                        <span className="text-xs font-normal text-gray-400">(Count)</span>
                      </div>
                    </th>
                  )}
                  {activeTab === 'calibrators' && (
                    <>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                        <div className="flex flex-col items-center">
                          <span>POD Leads</span>
                          <span className="text-xs font-normal text-gray-400">(Count)</span>
                        </div>
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                        <div className="flex flex-col items-center">
                          <span>Trainers</span>
                          <span className="text-xs font-normal text-gray-400">(Count)</span>
                        </div>
                      </th>
                    </>
                  )}
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Total Tasks</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Completed</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Rework %</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Rejected</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Delivery Ready</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {paginatedData.map((item, idx) => (
                  <tr key={startIndex + idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900">{item.name}</div>
                      {activeTab === 'trainers' && (
                        <div className="text-xs text-gray-500 mt-0.5">@{item.name}</div>
                      )}
                    </td>
                    {(activeTab === 'trainers' || activeTab === 'pod-leads' || activeTab === 'calibrators') && (
                      <td className="px-6 py-4">
                        {item.email ? (
                          <div className="text-sm text-gray-700">{item.email}</div>
                        ) : (
                          <div className="text-xs text-gray-400 italic">No email available</div>
                        )}
                      </td>
                    )}
                    {activeTab === 'pod-leads' && (
                      <td className="px-6 py-4 text-center">
                        <div className="text-sm font-semibold text-blue-600 bg-blue-50 rounded-full py-1 px-3 inline-block">
                          {item.trainer_count || 0}
                        </div>
                      </td>
                    )}
                    {activeTab === 'calibrators' && (
                      <>
                        <td className="px-6 py-4 text-center">
                          <div className="text-sm font-semibold text-purple-600 bg-purple-50 rounded-full py-1 px-3 inline-block">
                            {item.pod_lead_count || 0}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="text-sm font-semibold text-blue-600 bg-blue-50 rounded-full py-1 px-3 inline-block">
                            {item.trainer_count || 0}
                          </div>
                        </td>
                      </>
                    )}
                    <td className="px-6 py-4 text-center">
                      <div className="text-sm font-semibold text-gray-900">{item.total_tasks}</div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <div className="text-sm text-green-600 font-medium">{item.completed_tasks}</div>
                      <div className="text-xs text-gray-500">
                        {item.total_tasks > 0 ? `${((item.completed_tasks / item.total_tasks) * 100).toFixed(1)}%` : '0%'}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <div className={`text-sm font-medium ${
                        item.rework_percentage > 30 ? 'text-red-600' : 
                        item.rework_percentage > 15 ? 'text-yellow-600' : 'text-green-600'
                      }`}>
                        {item.rework_percentage}%
                      </div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <div className="text-sm text-red-600 font-medium">{item.rejected_count}</div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <div className="text-sm text-blue-600 font-medium">{item.delivery_ready_tasks}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!loading && data.length > 0 && (
          <div className="px-6 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {/* Rows per page selector */}
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-700">Rows per page:</span>
                <select
                  value={pagination.rowsPerPage}
                  onChange={handleRowsPerPageChange}
                  className="border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>

              {/* Page navigation */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handlePageChange(pagination.page - 1)}
                  disabled={pagination.page === 1}
                  className={`p-2 rounded-md ${
                    pagination.page === 1 
                      ? 'text-gray-400 cursor-not-allowed' 
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                  aria-label="Previous page"
                >
                  <ChevronLeftIcon className="h-5 w-5" />
                </button>
                <span className="text-sm text-gray-700">
                  Page {pagination.page} of {totalPages}
                </span>
                <button
                  onClick={() => handlePageChange(pagination.page + 1)}
                  disabled={pagination.page === totalPages}
                  className={`p-2 rounded-md ${
                    pagination.page === totalPages
                      ? 'text-gray-400 cursor-not-allowed' 
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                  aria-label="Next page"
                >
                  <ChevronRightIcon className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Items count */}
            <div className="text-sm text-gray-500">
              Showing {startIndex + 1} to {Math.min(endIndex, totalItems)} of {totalItems} items
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AggregationView;

