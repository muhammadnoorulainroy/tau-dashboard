import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  CubeIcon,
  ChartBarIcon,
  DocumentTextIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  FunnelIcon
} from '@heroicons/react/24/outline';

const InterfaceView = ({ lastUpdate }) => {
  const [interfaces, setInterfaces] = useState([]);
  const [summary, setSummary] = useState(null);
  const [statusBreakdown, setStatusBreakdown] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('summary'); // 'summary', 'detail'
  
  // Available filter options
  const [weeks, setWeeks] = useState([]);
  const [domains, setDomains] = useState([]);
  const [trainers, setTrainers] = useState([]);
  
  // Active filters
  const [activeFilters, setActiveFilters] = useState({
    week_id: null,
    domain_id: null,
    trainer_id: null,
    status: null
  });

  useEffect(() => {
    initializeFilters();
  }, []);
  
  useEffect(() => {
    if (activeFilters.week_id !== null && activeFilters.domain_id !== null) {
      fetchFilteredData();
    }
  }, [activeFilters, lastUpdate]);

  const initializeFilters = async () => {
    try {
      // Fetch weeks, domains, and trainers
      const [weeksRes, domainsRes, trainersRes] = await Promise.all([
        axios.get('http://localhost:8000/api/weeks'),
        axios.get('http://localhost:8000/api/domains/list'),
        axios.get('http://localhost:8000/api/trainers')
      ]);
      
      const weeksList = weeksRes.data.weeks || [];
      const domainsList = domainsRes.data.domains || [];
      const trainersList = trainersRes.data.trainers || [];
      
      setWeeks(weeksList);
      setDomains(domainsList);
      setTrainers(trainersList);
      
      // Set default filters: Use a week with data and default to hr_experts
      if (weeksList.length > 0 && domainsList.length > 0) {
        // Use second week if available (skip the very latest which might be incomplete)
        const defaultWeekId = weeksList.length > 1 ? weeksList[1].id : weeksList[0].id;
        
        // Default to hr_experts
        const hrExpertsDomain = domainsList.find(d => d.name === 'hr_experts');
        const defaultDomainId = hrExpertsDomain ? hrExpertsDomain.id : domainsList[0].id;
        
        setActiveFilters({
          week_id: defaultWeekId,
          domain_id: defaultDomainId,
          trainer_id: null,
          status: null
        });
      }
    } catch (error) {
      console.error('Error initializing filters:', error);
    }
  };

  const fetchFilteredData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (activeFilters.week_id) params.week_id = activeFilters.week_id;
      if (activeFilters.domain_id) params.domain_id = activeFilters.domain_id;
      if (activeFilters.trainer_id) params.trainer_id = activeFilters.trainer_id;
      if (activeFilters.status) params.status = activeFilters.status;
      
      // Fetch both interface data and status breakdown
      const [interfacesRes, statusRes] = await Promise.all([
        axios.get('http://localhost:8000/api/interfaces/filtered', { params }),
        axios.get('http://localhost:8000/api/pr-status-breakdown', { params: { week_id: activeFilters.week_id, domain_id: activeFilters.domain_id } })
      ]);
      
      setInterfaces(interfacesRes.data.interfaces);
      setSummary(interfacesRes.data.summary);
      setStatusBreakdown(statusRes.data);
    } catch (error) {
      console.error('Error fetching filtered interface data:', error);
    } finally {
      setLoading(false);
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
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Interface Metrics</h2>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center mb-4">
          <FunnelIcon className="h-5 w-5 text-gray-500 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Week Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Week <span className="text-red-500">*</span>
            </label>
            <select
              value={activeFilters.week_id || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, week_id: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {weeks.map((week) => (
                <option key={week.id} value={week.id}>
                  {week.week_name}
                </option>
              ))}
            </select>
          </div>

          {/* Domain Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Domain <span className="text-red-500">*</span>
            </label>
            <select
              value={activeFilters.domain_id || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, domain_id: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {domains.map((domain) => (
                <option key={domain.id} value={domain.id}>
                  {domain.name}
                </option>
              ))}
            </select>
          </div>

          {/* Trainer Filter (Optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Trainer
            </label>
            <select
              value={activeFilters.trainer_id || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, trainer_id: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Trainers</option>
              {trainers.map((trainer) => (
                <option key={trainer.id} value={trainer.id}>
                  {trainer.username}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter (Optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              PR Status
            </label>
            <select
              value={activeFilters.status || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, status: e.target.value || null })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="merged">Merged</option>
              <option value="open">Open</option>
            </select>
          </div>
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex space-x-2">
        <button
          onClick={() => setView('summary')}
          className={`px-4 py-2 rounded-lg ${
            view === 'summary' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
          }`}
        >
          Summary
        </button>
        <button
          onClick={() => setView('detail')}
          className={`px-4 py-2 rounded-lg ${
            view === 'detail' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
          }`}
        >
          Details
        </button>
      </div>

      {/* Summary View */}
      {view === 'summary' && summary && (
        <div className="space-y-6">
          {/* Overall Statistics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Interfaces</p>
                  <p className="text-3xl font-bold text-gray-900">{interfaces.length}</p>
                </div>
                <CubeIcon className="h-10 w-10 text-blue-600" />
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Tasks</p>
                  <p className="text-3xl font-bold text-gray-900">{summary.total_tasks}</p>
                </div>
                <DocumentTextIcon className="h-10 w-10 text-indigo-600" />
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Merged</p>
                  <p className="text-3xl font-bold text-gray-900">{summary.total_merged}</p>
                  <p className="text-sm text-gray-500">
                    {summary.total_tasks > 0 ? ((summary.total_merged / summary.total_tasks) * 100).toFixed(1) : 0}%
                  </p>
                </div>
                <CheckCircleIcon className="h-10 w-10 text-green-600" />
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Rework</p>
                  <p className="text-3xl font-bold text-gray-900">{summary.total_rework || 0}</p>
                </div>
                <ExclamationTriangleIcon className="h-10 w-10 text-orange-600" />
              </div>
            </div>
          </div>

          {/* Complexity Breakdown Tables - Per Interface */}
          <div className="grid grid-cols-1 gap-6">
            {/* Merged Complexity - Per Interface */}
            <div className="card">
              <h3 className="text-lg font-semibold mb-4">Complexity Breakdown (Merged Only)</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="text-left text-xs font-medium text-gray-500 border-b-2">
                      <th className="pb-3 px-4">Interface</th>
                      <th className="pb-3 px-4 text-center" colSpan="2">Count</th>
                      <th className="pb-3 px-4 text-center bg-red-50" colSpan="2">Expert</th>
                      <th className="pb-3 px-4 text-center bg-orange-50" colSpan="2">Hard</th>
                      <th className="pb-3 px-4 text-center bg-yellow-50" colSpan="2">Medium</th>
                      <th className="pb-3 px-4 text-center" colSpan="2">Total</th>
                    </tr>
                    <tr className="text-xs font-medium text-gray-500 border-b">
                      <th className="pb-2"></th>
                      <th className="pb-2 text-center">Count</th>
                      <th className="pb-2 text-center">Percent</th>
                      <th className="pb-2 text-center bg-red-50">Count</th>
                      <th className="pb-2 text-center bg-red-50">Percent</th>
                      <th className="pb-2 text-center bg-orange-50">Count</th>
                      <th className="pb-2 text-center bg-orange-50">Percent</th>
                      <th className="pb-2 text-center bg-yellow-50">Count</th>
                      <th className="pb-2 text-center bg-yellow-50">Percent</th>
                      <th className="pb-2 text-center">Count</th>
                      <th className="pb-2 text-center">Percent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {interfaces.filter(i => i.interface_num >= 1 && i.interface_num <= 5).map((interface_data) => {
                      const merged = interface_data.complexity_breakdown.merged;
                      const total = merged.total;
                      const expertPct = total > 0 ? ((merged.expert / total) * 100).toFixed(2) : '0.00';
                      const hardPct = total > 0 ? ((merged.hard / total) * 100).toFixed(2) : '0.00';
                      const mediumPct = total > 0 ? ((merged.medium / total) * 100).toFixed(2) : '0.00';
                      
                      return (
                        <tr key={interface_data.interface_num} className="border-t hover:bg-gray-50">
                          <td className="py-3 px-4 font-medium">Interface {interface_data.interface_num}</td>
                          <td className="py-3 px-4 text-center">{interface_data.merged}</td>
                          <td className="py-3 px-4 text-center">{interface_data.total_tasks > 0 ? ((interface_data.merged / interface_data.total_tasks) * 100).toFixed(2) : '0.00'}%</td>
                          <td className="py-3 px-4 text-center bg-red-50 font-semibold">{merged.expert}</td>
                          <td className="py-3 px-4 text-center bg-red-50">{expertPct}%</td>
                          <td className="py-3 px-4 text-center bg-orange-50 font-semibold">{merged.hard}</td>
                          <td className="py-3 px-4 text-center bg-orange-50">{hardPct}%</td>
                          <td className="py-3 px-4 text-center bg-yellow-50 font-semibold">{merged.medium}</td>
                          <td className="py-3 px-4 text-center bg-yellow-50">{mediumPct}%</td>
                          <td className="py-3 px-4 text-center font-bold">{total}</td>
                          <td className="py-3 px-4 text-center">100%</td>
                        </tr>
                      );
                    })}
                    <tr className="border-t-2 font-bold bg-gray-50">
                      <td className="py-3 px-4">Total</td>
                      <td className="py-3 px-4 text-center">{summary.total_merged}</td>
                      <td className="py-3 px-4 text-center">{summary.total_tasks > 0 ? ((summary.total_merged / summary.total_tasks) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center bg-red-50">{summary.complexity_breakdown.merged.expert}</td>
                      <td className="py-3 px-4 text-center bg-red-50">{summary.total_merged > 0 ? ((summary.complexity_breakdown.merged.expert / summary.total_merged) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center bg-orange-50">{summary.complexity_breakdown.merged.hard}</td>
                      <td className="py-3 px-4 text-center bg-orange-50">{summary.total_merged > 0 ? ((summary.complexity_breakdown.merged.hard / summary.total_merged) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center bg-yellow-50">{summary.complexity_breakdown.merged.medium}</td>
                      <td className="py-3 px-4 text-center bg-yellow-50">{summary.total_merged > 0 ? ((summary.complexity_breakdown.merged.medium / summary.total_merged) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center">{summary.total_merged}</td>
                      <td className="py-3 px-4 text-center">100%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* All Statuses Complexity - Per Interface */}
            <div className="card">
              <h3 className="text-lg font-semibold mb-4">Complexity Breakdown (All Statuses)</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="text-left text-xs font-medium text-gray-500 border-b-2">
                      <th className="pb-3 px-4">Interface</th>
                      <th className="pb-3 px-4 text-center" colSpan="2">Count</th>
                      <th className="pb-3 px-4 text-center bg-red-50" colSpan="2">Expert</th>
                      <th className="pb-3 px-4 text-center bg-orange-50" colSpan="2">Hard</th>
                      <th className="pb-3 px-4 text-center bg-yellow-50" colSpan="2">Medium</th>
                      <th className="pb-3 px-4 text-center" colSpan="2">Total</th>
                    </tr>
                    <tr className="text-xs font-medium text-gray-500 border-b">
                      <th className="pb-2"></th>
                      <th className="pb-2 text-center">Count</th>
                      <th className="pb-2 text-center">Percent</th>
                      <th className="pb-2 text-center bg-red-50">Count</th>
                      <th className="pb-2 text-center bg-red-50">Percent</th>
                      <th className="pb-2 text-center bg-orange-50">Count</th>
                      <th className="pb-2 text-center bg-orange-50">Percent</th>
                      <th className="pb-2 text-center bg-yellow-50">Count</th>
                      <th className="pb-2 text-center bg-yellow-50">Percent</th>
                      <th className="pb-2 text-center">Count</th>
                      <th className="pb-2 text-center">Percent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {interfaces.filter(i => i.interface_num >= 1 && i.interface_num <= 5).map((interface_data) => {
                      const allStatuses = interface_data.complexity_breakdown.all_statuses;
                      const total = allStatuses.total;
                      const expertPct = total > 0 ? ((allStatuses.expert / total) * 100).toFixed(2) : '0.00';
                      const hardPct = total > 0 ? ((allStatuses.hard / total) * 100).toFixed(2) : '0.00';
                      const mediumPct = total > 0 ? ((allStatuses.medium / total) * 100).toFixed(2) : '0.00';
                      const nonMergedCount = interface_data.total_tasks - interface_data.merged;
                      
                      return (
                        <tr key={interface_data.interface_num} className="border-t hover:bg-gray-50">
                          <td className="py-3 px-4 font-medium">Interface {interface_data.interface_num}</td>
                          <td className="py-3 px-4 text-center">{nonMergedCount}</td>
                          <td className="py-3 px-4 text-center">{((nonMergedCount / interface_data.total_tasks) * 100).toFixed(2)}%</td>
                          <td className="py-3 px-4 text-center bg-red-50 font-semibold">{allStatuses.expert}</td>
                          <td className="py-3 px-4 text-center bg-red-50">{expertPct}%</td>
                          <td className="py-3 px-4 text-center bg-orange-50 font-semibold">{allStatuses.hard}</td>
                          <td className="py-3 px-4 text-center bg-orange-50">{hardPct}%</td>
                          <td className="py-3 px-4 text-center bg-yellow-50 font-semibold">{allStatuses.medium}</td>
                          <td className="py-3 px-4 text-center bg-yellow-50">{mediumPct}%</td>
                          <td className="py-3 px-4 text-center font-bold">{total}</td>
                          <td className="py-3 px-4 text-center">100%</td>
                        </tr>
                      );
                    })}
                    <tr className="border-t-2 font-bold bg-gray-50">
                      <td className="py-3 px-4">Total</td>
                      <td className="py-3 px-4 text-center">{summary.total_tasks}</td>
                      <td className="py-3 px-4 text-center">100%</td>
                      <td className="py-3 px-4 text-center bg-red-50">{summary.complexity_breakdown.all_statuses.expert}</td>
                      <td className="py-3 px-4 text-center bg-red-50">{summary.total_tasks > 0 ? ((summary.complexity_breakdown.all_statuses.expert / summary.total_tasks) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center bg-orange-50">{summary.complexity_breakdown.all_statuses.hard}</td>
                      <td className="py-3 px-4 text-center bg-orange-50">{summary.total_tasks > 0 ? ((summary.complexity_breakdown.all_statuses.hard / summary.total_tasks) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center bg-yellow-50">{summary.complexity_breakdown.all_statuses.medium}</td>
                      <td className="py-3 px-4 text-center bg-yellow-50">{summary.total_tasks > 0 ? ((summary.complexity_breakdown.all_statuses.medium / summary.total_tasks) * 100).toFixed(2) : 0}%</td>
                      <td className="py-3 px-4 text-center">{summary.total_tasks}</td>
                      <td className="py-3 px-4 text-center">100%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Individual Interface Breakdowns */}
          <div className="space-y-6">
            <h3 className="text-lg font-semibold text-gray-900">Interface Breakdown (Interfaces 1-5)</h3>
            
            <div className="grid grid-cols-1 gap-6">
              {interfaces.filter(i => i.interface_num >= 1 && i.interface_num <= 5).map((interface_data) => (
                <div key={interface_data.interface_num} className="card">
                  <div className="flex items-center mb-4">
                    <div className="w-12 h-12 rounded-full bg-blue-500 flex items-center justify-center text-white text-xl font-bold mr-4">
                      {interface_data.interface_num}
                    </div>
                    <div>
                      <h4 className="text-xl font-bold text-gray-900">Interface {interface_data.interface_num}</h4>
                      <p className="text-sm text-gray-600">{interface_data.total_tasks} total tasks</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-gray-50 p-3 rounded">
                      <p className="text-xs text-gray-600 mb-1">Total Tasks</p>
                      <p className="text-2xl font-bold">{interface_data.total_tasks}</p>
                    </div>
                    <div className="bg-green-50 p-3 rounded">
                      <p className="text-xs text-gray-600 mb-1">Merged</p>
                      <p className="text-2xl font-bold text-green-600">{interface_data.merged}</p>
                      <p className="text-xs text-gray-500">
                        {interface_data.total_tasks > 0 ? ((interface_data.merged / interface_data.total_tasks) * 100).toFixed(1) : '0.0'}%
                      </p>
                    </div>
                    <div className="bg-orange-50 p-3 rounded">
                      <p className="text-xs text-gray-600 mb-1">Open</p>
                      <p className="text-2xl font-bold text-orange-600">
                        {interface_data.open}
                      </p>
                    </div>
                    <div className="bg-red-50 p-3 rounded">
                      <p className="text-xs text-gray-600 mb-1">Rework</p>
                      <p className="text-2xl font-bold text-red-600">{interface_data.rework}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Merged Complexity */}
                    <div>
                      <h5 className="text-sm font-semibold text-gray-700 mb-3">Merged Complexity</h5>
                      <div className="space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Expert</span>
                          <div className="flex items-center">
                            <div className="w-32 bg-gray-200 rounded-full h-3 mr-2">
                              <div 
                                className="bg-red-500 h-3 rounded-full" 
                                style={{ width: `${interface_data.complexity_breakdown.merged.percentages?.expert || 0}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold w-20 text-right">
                              {interface_data.complexity_breakdown.merged.expert} ({interface_data.complexity_breakdown.merged.percentages?.expert || 0}%)
                            </span>
                          </div>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Hard</span>
                          <div className="flex items-center">
                            <div className="w-32 bg-gray-200 rounded-full h-3 mr-2">
                              <div 
                                className="bg-orange-500 h-3 rounded-full" 
                                style={{ width: `${interface_data.complexity_breakdown.merged.percentages?.hard || 0}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold w-20 text-right">
                              {interface_data.complexity_breakdown.merged.hard} ({interface_data.complexity_breakdown.merged.percentages?.hard || 0}%)
                            </span>
                          </div>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Medium</span>
                          <div className="flex items-center">
                            <div className="w-32 bg-gray-200 rounded-full h-3 mr-2">
                              <div 
                                className="bg-yellow-500 h-3 rounded-full" 
                                style={{ width: `${interface_data.complexity_breakdown.merged.percentages?.medium || 0}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold w-20 text-right">
                              {interface_data.complexity_breakdown.merged.medium} ({interface_data.complexity_breakdown.merged.percentages?.medium || 0}%)
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* All Statuses Complexity */}
                    <div>
                      <h5 className="text-sm font-semibold text-gray-700 mb-3">All Statuses Complexity</h5>
                      <div className="space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Expert</span>
                          <div className="flex items-center">
                            <div className="w-32 bg-gray-200 rounded-full h-3 mr-2">
                              <div 
                                className="bg-red-500 h-3 rounded-full" 
                                style={{ width: `${interface_data.complexity_breakdown.all_statuses.percentages?.expert || 0}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold w-20 text-right">
                              {interface_data.complexity_breakdown.all_statuses.expert} ({interface_data.complexity_breakdown.all_statuses.percentages?.expert || 0}%)
                            </span>
                          </div>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Hard</span>
                          <div className="flex items-center">
                            <div className="w-32 bg-gray-200 rounded-full h-3 mr-2">
                              <div 
                                className="bg-orange-500 h-3 rounded-full" 
                                style={{ width: `${interface_data.complexity_breakdown.all_statuses.percentages?.hard || 0}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold w-20 text-right">
                              {interface_data.complexity_breakdown.all_statuses.hard} ({interface_data.complexity_breakdown.all_statuses.percentages?.hard || 0}%)
                            </span>
                          </div>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">Medium</span>
                          <div className="flex items-center">
                            <div className="w-32 bg-gray-200 rounded-full h-3 mr-2">
                              <div 
                                className="bg-yellow-500 h-3 rounded-full" 
                                style={{ width: `${interface_data.complexity_breakdown.all_statuses.percentages?.medium || 0}%` }}
                              ></div>
                            </div>
                            <span className="text-sm font-semibold w-20 text-right">
                              {interface_data.complexity_breakdown.all_statuses.medium} ({interface_data.complexity_breakdown.all_statuses.percentages?.medium || 0}%)
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* PR Status Breakdown Table */}
          {statusBreakdown && statusBreakdown.breakdown && statusBreakdown.breakdown.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold mb-4">
                PR Status Breakdown by Complexity
                <span className="text-sm text-gray-500 font-normal ml-2">
                  (Total: {statusBreakdown.total_prs} PRs)
                </span>
              </h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" rowSpan="2">
                        PR Status
                      </th>
                      <th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border-l" colSpan="2">
                        Overall
                      </th>
                      <th className="py-3 px-4 text-center text-xs font-medium text-red-700 uppercase tracking-wider border-l" colSpan="2">
                        Expert
                      </th>
                      <th className="py-3 px-4 text-center text-xs font-medium text-orange-700 uppercase tracking-wider border-l" colSpan="2">
                        Hard
                      </th>
                      <th className="py-3 px-4 text-center text-xs font-medium text-yellow-700 uppercase tracking-wider border-l" colSpan="2">
                        Medium
                      </th>
                    </tr>
                    <tr className="bg-gray-100">
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase border-l">Count</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase">Percent</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase border-l">Count</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase">Percent</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase border-l">Count</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase">Percent</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase border-l">Count</th>
                      <th className="py-2 px-4 text-center text-xs font-medium text-gray-500 uppercase">Percent</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {statusBreakdown.breakdown.map((item) => (
                      <tr key={item.status} className="hover:bg-gray-50">
                        <td className="py-3 px-4 text-sm font-medium text-gray-900">{item.status}</td>
                        <td className="py-3 px-4 text-center text-sm border-l">{item.count}</td>
                        <td className="py-3 px-4 text-center text-sm">{item.percent}%</td>
                        <td className="py-3 px-4 text-center text-sm bg-red-50 border-l">{item.complexity.expert.count}</td>
                        <td className="py-3 px-4 text-center text-sm bg-red-50">{item.complexity.expert.percent}%</td>
                        <td className="py-3 px-4 text-center text-sm bg-orange-50 border-l">{item.complexity.hard.count}</td>
                        <td className="py-3 px-4 text-center text-sm bg-orange-50">{item.complexity.hard.percent}%</td>
                        <td className="py-3 px-4 text-center text-sm bg-yellow-50 border-l">{item.complexity.medium.count}</td>
                        <td className="py-3 px-4 text-center text-sm bg-yellow-50">{item.complexity.medium.percent}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detail View - Interface Table */}
      {view === 'detail' && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Interface
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Total Tasks
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Merged
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Expert
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Hard
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Medium
                  </th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Rework
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {interfaces.filter(i => i.interface_num >= 1 && i.interface_num <= 5).map((interface_data) => {
                  const mergedPercent = interface_data.total_tasks > 0 
                    ? ((interface_data.merged / interface_data.total_tasks) * 100).toFixed(1)
                    : 0;
                  const allStatuses = interface_data.complexity_breakdown.all_statuses;
                  const merged = interface_data.complexity_breakdown.merged;
                  
                  return (
                    <tr key={interface_data.interface_num} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10">
                            <div className="h-10 w-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold">
                              {interface_data.interface_num}
                            </div>
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">
                              Interface {interface_data.interface_num}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className="text-lg font-semibold">{interface_data.total_tasks}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <div>
                          <span className="text-lg font-semibold">{interface_data.merged}</span>
                          <div className="text-xs text-gray-500">{mergedPercent}%</div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <div>
                          <span className="font-semibold">{allStatuses.expert + merged.expert}</span>
                          <div className="text-xs text-gray-500">
                            M: {merged.expert} / A: {allStatuses.expert}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <div>
                          <span className="font-semibold">{allStatuses.hard + merged.hard}</span>
                          <div className="text-xs text-gray-500">
                            M: {merged.hard} / A: {allStatuses.hard}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <div>
                          <span className="font-semibold">{allStatuses.medium + merged.medium}</span>
                          <div className="text-xs text-gray-500">
                            M: {merged.medium} / A: {allStatuses.medium}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          interface_data.rework > 10 ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {interface_data.rework}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default InterfaceView;

