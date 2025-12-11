import React, { useState, useEffect } from 'react';
import {
  getPodLeadAggregation,
  getCalibratorAggregation,
  getExpertReviewerAggregation,
  getEnvironments
} from '../services/api';
import {
  ChartBarIcon,
  FunnelIcon,
  UserGroupIcon,
  CheckBadgeIcon,
  ClipboardDocumentCheckIcon,
  MagnifyingGlassIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';

const AggregationView = ({ lastUpdate }) => {
  const [activeTab, setActiveTab] = useState('pod-leads');
  const [loading, setLoading] = useState(true);
  const [podLeads, setPodLeads] = useState([]);
  const [calibrators, setCalibrators] = useState([]);
  const [expertReviewers, setExpertReviewers] = useState([]);
  const [environments, setEnvironments] = useState([]);
  const [selectedDomain, setSelectedDomain] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Sorting
  const [sortBy, setSortBy] = useState('total_tasks');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const perPageOptions = [10, 25, 50, 100];
  
  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <ChevronUpDownIcon className="h-4 w-4 ml-1 text-gray-300" />;
    return sortOrder === 'desc' ? 
      <ChevronDownIcon className="h-4 w-4 ml-1" /> : 
      <ChevronUpIcon className="h-4 w-4 ml-1" />;
  };

  const ChevronUpDownIcon = ({ className }) => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 15L12 18.75 15.75 15m-7.5-6L12 5.25 15.75 9" />
    </svg>
  );

  const sortData = (data) => {
    return [...data].sort((a, b) => {
      let aVal = a[sortBy];
      let bVal = b[sortBy];
      
      // Handle computed fields
      if (sortBy === 'reviewed_count') {
        aVal = (a.approved_count || 0) + (a.rework_count || 0);
        bVal = (b.approved_count || 0) + (b.rework_count || 0);
      }
      
      // Null handling
      if (aVal == null) aVal = 0;
      if (bVal == null) bVal = 0;
      
      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
      }
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
    });
  };

  useEffect(() => {
    fetchEnvironments();
  }, []);

  useEffect(() => {
    fetchData();
    setCurrentPage(1); // Reset to page 1 when tab or domain changes
  }, [activeTab, selectedDomain, lastUpdate]);

  const fetchEnvironments = async () => {
    try {
      const response = await getEnvironments();
      setEnvironments(response.data || []);
    } catch (error) {
      console.error('Error fetching environments:', error);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const domain = selectedDomain || null;
      
      if (activeTab === 'pod-leads') {
        const response = await getPodLeadAggregation(domain);
        setPodLeads(response.data || []);
      } else if (activeTab === 'calibrators') {
        const response = await getCalibratorAggregation(domain);
        setCalibrators(response.data || []);
      } else if (activeTab === 'expert-reviewers') {
        const response = await getExpertReviewerAggregation(domain);
        setExpertReviewers(response.data || []);
      }
    } catch (error) {
      console.error('Error fetching aggregation data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatRate = (rate) => `${(rate * 100).toFixed(1)}%`;

  const filterBySearch = (items, nameKey, emailKey) => {
    if (!searchQuery.trim()) return items;
    const query = searchQuery.toLowerCase();
    return items.filter(item => 
      (item[nameKey]?.toLowerCase().includes(query)) ||
      (item[emailKey]?.toLowerCase().includes(query))
    );
  };

  const renderPersonRow = (person, nameKey, emailKey) => {
    const name = person[nameKey] || 'Unknown';
    const email = person[emailKey];
    const uniqueKey = email || name;
    
    return (
      <tr key={uniqueKey} className="hover:bg-gray-50">
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center">
            <div className="h-9 w-9 rounded-full bg-purple-100 flex items-center justify-center">
              <span className="text-purple-600 font-medium text-sm">
                {name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
              </span>
            </div>
            <div className="ml-3">
              <div className="text-sm font-medium text-gray-900">{name}</div>
              {email && <div className="text-xs text-gray-500">{email}</div>}
              {!email && <div className="text-xs text-gray-400 italic">No email</div>}
            </div>
          </div>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="font-bold text-lg text-gray-900">{person.total_tasks}</span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-800">
            {person.reviewed_count || (person.approved_count + person.rework_count)}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
            {person.approved_count}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">
            {person.rework_count}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
            {person.in_review_count}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">
            {person.draft_count}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className={`font-semibold ${person.approval_rate >= 0.7 ? 'text-green-600' : person.approval_rate >= 0.4 ? 'text-yellow-600' : 'text-red-600'}`}>
            {formatRate(person.approval_rate)}
          </span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className={`font-semibold ${person.rework_rate <= 0.2 ? 'text-green-600' : person.rework_rate <= 0.4 ? 'text-yellow-600' : 'text-red-600'}`}>
            {formatRate(person.rework_rate)}
          </span>
        </td>
        <td className="px-4 py-3 text-center text-sm text-gray-600">
          {person.trainer_count}
        </td>
        <td className="px-4 py-3 text-center text-sm text-gray-600">
          {person.domain_count}
        </td>
      </tr>
    );
  };

  const renderTable = (data, nameKey, emailKey, roleLabel) => {
    const filteredData = filterBySearch(data, nameKey, emailKey);
    
    // Apply sorting
    const sortedData = sortData(filteredData);
    
    // Pagination
    const totalPages = Math.ceil(sortedData.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedData = sortedData.slice(startIndex, startIndex + itemsPerPage);
    
    if (loading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
        </div>
      );
    }

    if (filteredData.length === 0) {
      return (
        <div className="text-center py-12 text-gray-500">
          <UserGroupIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p>No {roleLabel.toLowerCase()} found</p>
          {searchQuery && <p className="text-sm mt-1">Try adjusting your search</p>}
        </div>
      );
    }

    return (
      <>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {roleLabel}
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('total_tasks')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Total
                    <SortIcon field="total_tasks" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('reviewed_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Reviewed
                    <SortIcon field="reviewed_count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('approved_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Approved
                    <SortIcon field="approved_count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('rework_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Rework
                    <SortIcon field="rework_count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('in_review_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    In Review
                    <SortIcon field="in_review_count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('draft_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Draft
                    <SortIcon field="draft_count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('approval_rate')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Approval Rate
                    <SortIcon field="approval_rate" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('rework_rate')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Rework Rate
                    <SortIcon field="rework_rate" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('trainer_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Trainers
                    <SortIcon field="trainer_count" />
                  </button>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button 
                    onClick={() => handleSort('domain_count')}
                    className="flex items-center justify-center mx-auto hover:text-gray-700"
                  >
                    Domains
                    <SortIcon field="domain_count" />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {paginatedData.map(person => renderPersonRow(person, nameKey, emailKey))}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Show</span>
              <select
                value={itemsPerPage}
                onChange={(e) => { setItemsPerPage(Number(e.target.value)); setCurrentPage(1); }}
                className="px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {perPageOptions.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
              <span className="text-sm text-gray-500">per page</span>
            </div>
            <div className="text-sm text-gray-500">
              Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, sortedData.length)} of {sortedData.length}
            </div>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <span className="text-sm text-gray-700">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRightIcon className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </>
    );
  };

  const renderSummaryCards = (data) => {
    const totals = data.reduce((acc, item) => ({
      total: acc.total + item.total_tasks,
      approved: acc.approved + item.approved_count,
      rework: acc.rework + item.rework_count,
      in_review: acc.in_review + item.in_review_count
    }), { total: 0, approved: 0, rework: 0, in_review: 0 });

    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="card text-center">
          <div className="text-3xl font-bold text-gray-900">{data.length}</div>
          <div className="text-sm text-gray-500">
            {activeTab === 'pod-leads' ? 'POD Leads' : 
             activeTab === 'calibrators' ? 'Calibrators' : 'Expert Reviewers'}
          </div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-purple-600">{totals.total}</div>
          <div className="text-sm text-gray-500">Total Tasks</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-green-600">{totals.approved}</div>
          <div className="text-sm text-gray-500">Approved</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-red-600">{totals.rework}</div>
          <div className="text-sm text-gray-500">Rework</div>
        </div>
      </div>
    );
  };

  const currentData = activeTab === 'pod-leads' ? podLeads : 
                      activeTab === 'calibrators' ? calibrators : expertReviewers;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center">
          <ChartBarIcon className="h-8 w-8 text-purple-600 mr-3" />
          <h2 className="text-3xl font-bold text-gray-900">Reviewers</h2>
        </div>
      </div>

      {/* Info - NOW AT THE TOP */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <InformationCircleIcon className="h-5 w-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
          <div className="text-sm text-blue-900">
            <p className="font-semibold mb-1">About Reviewers</p>
            <ul className="space-y-1 text-xs">
              <li>• <strong>POD Leads:</strong> Team leads responsible for final task approval</li>
              <li>• <strong>Calibrators:</strong> Reviewers who calibrate task quality and provide feedback</li>
              <li>• <strong>Expert Reviewers:</strong> Subject matter experts who review task accuracy</li>
              <li>• <strong>Reviewed:</strong> Total tasks reviewed (Approved + Rework) - tasks where a review decision was made</li>
              <li>• <strong>Approval Rate:</strong> Percentage of reviewed tasks that were approved (Approved / Reviewed)</li>
              <li>• <strong>Rework Rate:</strong> Percentage of reviewed tasks that needed revisions (Rework / Reviewed)</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => { setActiveTab('pod-leads'); setCurrentPage(1); }}
            className={`${
              activeTab === 'pod-leads'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-all`}
          >
            <UserGroupIcon className="h-5 w-5 mr-2" />
            POD Leads
          </button>
          <button
            onClick={() => { setActiveTab('calibrators'); setCurrentPage(1); }}
            className={`${
              activeTab === 'calibrators'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-all`}
          >
            <ClipboardDocumentCheckIcon className="h-5 w-5 mr-2" />
            Calibrators
          </button>
          <button
            onClick={() => { setActiveTab('expert-reviewers'); setCurrentPage(1); }}
            className={`${
              activeTab === 'expert-reviewers'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center transition-all`}
          >
            <CheckBadgeIcon className="h-5 w-5 mr-2" />
            Expert Reviewers
          </button>
        </nav>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center mb-4">
          <FunnelIcon className="h-5 w-5 text-gray-500 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Domain Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Environment
            </label>
            <select
              value={selectedDomain}
              onChange={(e) => { setSelectedDomain(e.target.value); setCurrentPage(1); }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">All Environments</option>
              {environments.map((env) => (
                <option key={env.id} value={env.name}>
                  {env.name.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <div className="relative">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                placeholder="Search by name or email..."
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      {renderSummaryCards(currentData)}

      {/* Table */}
      <div className="card">
        {activeTab === 'pod-leads' && 
          renderTable(podLeads, 'pod_lead_name', 'pod_lead_email', 'POD Lead')}
        {activeTab === 'calibrators' && 
          renderTable(calibrators, 'calibrator_name', 'calibrator_email', 'Calibrator')}
        {activeTab === 'expert-reviewers' && 
          renderTable(expertReviewers, 'expert_reviewer_name', 'expert_reviewer_email', 'Expert Reviewer')}
      </div>
    </div>
  );
};

export default AggregationView;
