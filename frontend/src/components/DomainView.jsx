import React, { useState, useEffect } from 'react';
import { getEnvironments } from '../services/api';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { FolderIcon, ChevronRightIcon, CheckCircleIcon, ClockIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

const STATUS_COLORS = {
  'draft': '#9ca3af',
  'pending_review': '#f59e0b',
  'in_expert_review': '#f97316',
  'pending_calibrator_review': '#8b5cf6',
  'in_calibrator_review': '#6366f1',
  'in_pod_lead_review': '#3b82f6',
  'rework': '#ef4444',
  'approved': '#22c55e'
};

const STATUS_LABELS = {
  'draft': 'Draft',
  'pending_review': 'Pending Review',
  'in_expert_review': 'Expert Review',
  'pending_calibrator_review': 'Pending Calibrator',
  'in_calibrator_review': 'Calibrator Review',
  'in_pod_lead_review': 'Pod Lead Review',
  'rework': 'Rework',
  'approved': 'Approved'
};

const DomainView = ({ lastUpdate }) => {
  const [environments, setEnvironments] = useState([]);
  const [selectedEnv, setSelectedEnv] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEnvironments();
  }, [lastUpdate]);

  const fetchEnvironments = async () => {
    setLoading(true);
    try {
      const response = await getEnvironments();
      // Sort by total_tasks descending
      const sorted = (response.data || []).sort((a, b) => b.total_tasks - a.total_tasks);
      setEnvironments(sorted);
      if (sorted.length > 0 && !selectedEnv) {
        setSelectedEnv(sorted[0].name);
      }
    } catch (error) {
      console.error('Error fetching environments:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusPieData = (env) => {
    const data = [
      { name: 'Draft', value: env.draft_count, color: STATUS_COLORS.draft },
      { name: 'Pending Review', value: env.pending_review_count, color: STATUS_COLORS.pending_review },
      { name: 'Expert Review', value: env.in_expert_review_count, color: STATUS_COLORS.in_expert_review },
      { name: 'Pending Calibrator', value: env.pending_calibrator_review_count, color: STATUS_COLORS.pending_calibrator_review },
      { name: 'Calibrator Review', value: env.in_calibrator_review_count, color: STATUS_COLORS.in_calibrator_review },
      { name: 'Pod Lead Review', value: env.in_pod_lead_review_count, color: STATUS_COLORS.in_pod_lead_review },
      { name: 'Rework', value: env.rework_count, color: STATUS_COLORS.rework },
      { name: 'Approved', value: env.approved_count, color: STATUS_COLORS.approved }
    ].filter(d => d.value > 0);
    return data;
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

  const selectedEnvData = environments.find(e => e.name === selectedEnv);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Environments</h2>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            Total: {environments.length} environments
          </span>
        </div>
      </div>

      {/* Environment Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {environments.map((env) => (
          <div 
            key={env.id}
            onClick={() => setSelectedEnv(env.name)}
            className={`card cursor-pointer transition-all duration-200 ${
              selectedEnv === env.name 
                ? 'ring-2 ring-primary-500 shadow-md' 
                : 'hover:shadow-md'
            }`}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <FolderIcon className="h-5 w-5 text-primary-600 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">
                  {env.name.replace(/_/g, ' ')}
                </h3>
              </div>
              <ChevronRightIcon className="h-5 w-5 text-gray-400" />
            </div>
            
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <p className="text-xs text-gray-500">Total</p>
                <p className="text-xl font-bold text-gray-900">{env.total_tasks}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Approved</p>
                <p className="text-xl font-bold text-success-600">{env.approved_count}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Rework</p>
                <p className="text-xl font-bold text-danger-600">{env.rework_count}</p>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Approval Rate</span>
                <span className="text-xs font-medium text-gray-700">
                  {env.total_tasks > 0 ? ((env.approved_count / env.total_tasks) * 100).toFixed(1) : 0}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-success-400 to-success-600 h-2 rounded-full"
                  style={{ width: `${env.total_tasks > 0 ? (env.approved_count / env.total_tasks) * 100 : 0}%` }}
                ></div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {env.pending_review_count > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                  <ClockIcon className="h-3 w-3 mr-1" />
                  Review: {env.pending_review_count + env.in_expert_review_count + env.in_pod_lead_review_count}
                </span>
              )}
              {env.rework_count > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                  <ArrowPathIcon className="h-3 w-3 mr-1" />
                  Rework: {env.rework_count}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Selected Environment Details */}
      {selectedEnvData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {selectedEnv.replace(/_/g, ' ')} - Status Distribution
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={getStatusPieData(selectedEnvData)}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => entry.value > 0 ? entry.value : ''}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {getStatusPieData(selectedEnvData).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {selectedEnv.replace(/_/g, ' ')} - Details
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Expert Tasks</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedEnvData.total_expert}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Hard Tasks</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedEnvData.total_hard}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Medium Tasks</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedEnvData.total_medium}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Approval Rate</p>
                  <p className="text-2xl font-bold text-success-600">
                    {selectedEnvData.total_tasks > 0 
                      ? ((selectedEnvData.approved_count / selectedEnvData.total_tasks) * 100).toFixed(1) 
                      : 0}%
                  </p>
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Status Breakdown</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.draft }}></span>
                      Draft
                    </span>
                    <span className="font-medium">{selectedEnvData.draft_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.pending_review }}></span>
                      Pending Review
                    </span>
                    <span className="font-medium">{selectedEnvData.pending_review_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.in_expert_review }}></span>
                      Expert Review
                    </span>
                    <span className="font-medium">{selectedEnvData.in_expert_review_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.pending_calibrator_review }}></span>
                      Pending Calibrator
                    </span>
                    <span className="font-medium">{selectedEnvData.pending_calibrator_review_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.in_calibrator_review }}></span>
                      Calibrator Review
                    </span>
                    <span className="font-medium">{selectedEnvData.in_calibrator_review_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.in_pod_lead_review }}></span>
                      Pod Lead Review
                    </span>
                    <span className="font-medium">{selectedEnvData.in_pod_lead_review_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.rework }}></span>
                      Rework
                    </span>
                    <span className="font-medium text-danger-600">{selectedEnvData.rework_count}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 flex items-center">
                      <span className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: STATUS_COLORS.approved }}></span>
                      Approved
                    </span>
                    <span className="font-medium text-success-600">{selectedEnvData.approved_count}</span>
                  </div>
                </div>
              </div>

              {/* Approved by Difficulty */}
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Approved by Difficulty</h4>
                <div className="flex gap-4">
                  <div className="flex-1 text-center p-2 bg-purple-50 rounded">
                    <p className="text-lg font-bold text-purple-600">{selectedEnvData.approved_expert}</p>
                    <p className="text-xs text-gray-500">Expert</p>
                  </div>
                  <div className="flex-1 text-center p-2 bg-orange-50 rounded">
                    <p className="text-lg font-bold text-orange-600">{selectedEnvData.approved_hard}</p>
                    <p className="text-xs text-gray-500">Hard</p>
                  </div>
                  <div className="flex-1 text-center p-2 bg-blue-50 rounded">
                    <p className="text-lg font-bold text-blue-600">{selectedEnvData.approved_medium}</p>
                    <p className="text-xs text-gray-500">Medium</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DomainView;
