import React, { useState, useEffect } from 'react';
import { 
  BuildingOfficeIcon, 
  UserGroupIcon
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

  const tabs = [
    { id: 'domains', label: 'Domain wise', icon: BuildingOfficeIcon, endpoint: '/aggregation/domains' },
    { id: 'trainers', label: 'Trainer wise', icon: UserGroupIcon, endpoint: '/aggregation/trainers' },
  ];

  // Fetch domains list on mount
  useEffect(() => {
    fetchDomains();
  }, []);

  // Fetch data when tab or domain filter changes
  useEffect(() => {
    fetchData();
  }, [activeTab, selectedDomain]);

  const fetchDomains = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/domains/list`);
      setDomains(response.data);
    } catch (err) {
      console.error('Failed to fetch domains:', err);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const endpoint = tabs.find(t => t.id === activeTab)?.endpoint;
      let url = `${API_BASE_URL}${endpoint}`;
      
      // Add domain filter for trainers tab
      if (activeTab === 'trainers' && selectedDomain) {
        url += `?domain=${encodeURIComponent(selectedDomain)}`;
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
    // Reset domain filter when switching tabs
    if (tabId !== 'trainers') {
      setSelectedDomain('');
    }
  };

  const currentTab = tabs.find(t => t.id === activeTab);
  const Icon = currentTab?.icon;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">Aggregation Metrics</h1>
          <p className="text-gray-600 mt-1">Task metrics by Domain and Developer</p>
        </div>
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

      {/* Domain Filter for Trainers */}
      {activeTab === 'trainers' && (
        <div className="flex items-center gap-4 bg-gray-50 rounded-lg p-4">
          <label htmlFor="domain-filter" className="text-sm font-medium text-gray-700">
            Filter by Domain:
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
          {selectedDomain && (
            <button
              onClick={() => setSelectedDomain('')}
              className="text-sm text-orange-600 hover:text-orange-700 font-medium"
            >
              Clear Filter
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

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
              {Icon && <Icon className="w-6 h-6" />}
              {currentTab?.label} ({data.length})
            </h2>
            {activeTab === 'trainers' && selectedDomain && (
              <span className="text-sm text-orange-600 font-medium bg-orange-50 px-3 py-1 rounded-full">
                Filtered: {selectedDomain}
              </span>
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
                    {activeTab === 'domains' ? 'Domain' : activeTab === 'trainers' ? 'Developer' : 'Name'}
                  </th>
                  {activeTab === 'trainers' && (
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                  )}
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Total Tasks</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Completed</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Rework %</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Rejected</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Delivery Ready</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.map((item, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900">{item.name}</div>
                      {activeTab === 'trainers' && (
                        <div className="text-xs text-gray-500 mt-0.5">@{item.name}</div>
                      )}
                    </td>
                    {activeTab === 'trainers' && (
                      <td className="px-6 py-4">
                        {item.email ? (
                          <div className="text-sm text-gray-700">{item.email}</div>
                        ) : (
                          <div className="text-xs text-gray-400 italic">No email available</div>
                        )}
                      </td>
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
      </div>

      {/* Summary */}
      {data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm text-gray-600">Total Tasks</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">
              {data.reduce((sum, item) => sum + item.total_tasks, 0)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm text-gray-600">Completed</div>
            <div className="text-2xl font-bold text-green-600 mt-1">
              {data.reduce((sum, item) => sum + item.completed_tasks, 0)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm text-gray-600">Avg Rework %</div>
            <div className="text-2xl font-bold text-yellow-600 mt-1">
              {(data.reduce((sum, item) => sum + item.rework_percentage, 0) / data.length).toFixed(1)}%
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm text-gray-600">Total Rejected</div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              {data.reduce((sum, item) => sum + item.rejected_count, 0)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm text-gray-600">Delivery Ready</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {data.reduce((sum, item) => sum + item.delivery_ready_tasks, 0)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AggregationView;

