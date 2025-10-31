import React, { useState, useEffect } from 'react';
import { getDomainMetrics, getPRStateDistribution } from '../services/api';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { FolderIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

const COLORS = {
  'expert_review_pending': '#f39c12',
  'calibrator_review_pending': '#e67e22',
  'expert_approved': '#27ae60',
  'ready_to_merge': '#2ecc71',
  'merged': '#229954',
  'other': '#95a5a6'
};

const DomainView = ({ lastUpdate }) => {
  const [domains, setDomains] = useState([]);
  const [selectedDomain, setSelectedDomain] = useState(null);
  const [domainStats, setDomainStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDomains();
  }, [lastUpdate]);

  useEffect(() => {
    if (selectedDomain) {
      fetchDomainStats(selectedDomain);
    }
  }, [selectedDomain]);

  const fetchDomains = async () => {
    setLoading(true);
    try {
      const response = await getDomainMetrics();
      setDomains(response.data);
      if (response.data.length > 0 && !selectedDomain) {
        setSelectedDomain(response.data[0].domain);
      }
    } catch (error) {
      // Error fetching domains
    } finally {
      setLoading(false);
    }
  };

  const fetchDomainStats = async (domain) => {
    try {
      const response = await getPRStateDistribution(domain);
      const data = Object.entries(response.data.distribution)
        .filter(([_, value]) => value > 0)
        .map(([key, value]) => ({
          name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          value,
          color: COLORS[key] || '#95a5a6'
        }));
      setDomainStats(data);
    } catch (error) {
      // Error fetching domain stats
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

  const selectedDomainData = domains.find(d => d.domain === selectedDomain);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Domains</h2>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            Total: {domains.length} domains
          </span>
        </div>
      </div>

      {/* Domain Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {domains.map((domain) => (
          <div 
            key={domain.id}
            onClick={() => setSelectedDomain(domain.domain)}
            className={`card cursor-pointer transition-all duration-200 ${
              selectedDomain === domain.domain 
                ? 'ring-2 ring-primary-500 shadow-md' 
                : 'hover:shadow-md'
            }`}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <FolderIcon className="h-5 w-5 text-primary-600 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">
                  {domain.domain}
                </h3>
              </div>
              <ChevronRightIcon className="h-5 w-5 text-gray-400" />
            </div>
            
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-xs text-gray-500">Total Tasks</p>
                <p className="text-xl font-bold text-gray-900">{domain.total_tasks}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Merged</p>
                <p className="text-xl font-bold text-success-600">{domain.merged}</p>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Progress</span>
                <span className="text-xs font-medium text-gray-700">
                  {domain.total_tasks > 0 ? ((domain.merged / domain.total_tasks) * 100).toFixed(1) : 0}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-primary-400 to-primary-600 h-2 rounded-full"
                  style={{ width: `${domain.total_tasks > 0 ? (domain.merged / domain.total_tasks) * 100 : 0}%` }}
                ></div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {domain.expert_review_pending > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-warning-100 text-warning-800">
                  Expert Review: {domain.expert_review_pending}
                </span>
              )}
              {domain.ready_to_merge > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-success-100 text-success-800">
                  Ready: {domain.ready_to_merge}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Selected Domain Details */}
      {selectedDomainData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {selectedDomain} - Task Distribution
            </h3>
            {domainStats && (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={domainStats}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry) => `${entry.value}`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {domainStats.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {selectedDomain} - Details
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Expert Tasks</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedDomainData.expert_count}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Hard Tasks</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedDomainData.hard_count}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Medium Tasks</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedDomainData.medium_count}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Completion Rate</p>
                  <p className="text-2xl font-bold text-success-600">
                    {selectedDomainData.total_tasks > 0 
                      ? ((selectedDomainData.merged / selectedDomainData.total_tasks) * 100).toFixed(1) 
                      : 0}%
                  </p>
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Status Breakdown</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Expert Review Pending</span>
                    <span className="font-medium">{selectedDomainData.expert_review_pending}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Calibrator Review Pending</span>
                    <span className="font-medium">{selectedDomainData.calibrator_review_pending}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Expert Approved</span>
                    <span className="font-medium">{selectedDomainData.expert_approved}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Ready to Merge</span>
                    <span className="font-medium">{selectedDomainData.ready_to_merge}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Merged</span>
                    <span className="font-medium text-success-600">{selectedDomainData.merged}</span>
                  </div>
                </div>
              </div>

              {selectedDomainData.detailed_metrics?.developers && (
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Top Contributors</h4>
                  <div className="space-y-2">
                    {Object.entries(selectedDomainData.detailed_metrics.developers)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 5)
                      .map(([dev, count]) => (
                        <div key={dev} className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">{dev}</span>
                          <span className="font-medium">{count} PRs</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DomainView;


