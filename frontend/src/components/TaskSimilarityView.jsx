import React, { useState, useEffect } from 'react';
import api from '../services/api';
import {
  SparklesIcon,
  FunnelIcon,
  ArrowsPointingOutIcon,
  ArrowDownTrayIcon,
  ChevronUpDownIcon,
  QuestionMarkCircleIcon
} from '@heroicons/react/24/outline';

// Tooltip component for inline help
const Tooltip = ({ text, children }) => {
  return (
    <div className="relative inline-flex items-center group">
      {children}
      <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 hidden group-hover:block z-[9999] pointer-events-none">
        <div className="bg-gray-900 text-white text-sm rounded py-3 px-4 w-80 whitespace-normal shadow-xl border border-gray-700 normal-case">
          {text}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-[-1px]">
            <div className="border-4 border-transparent border-b-gray-900"></div>
          </div>
        </div>
      </div>
    </div>
  );
};

const TaskSimilarityView = ({ lastUpdate }) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState(null);
  const [githubUrlBase, setGithubUrlBase] = useState('https://github.com');
  
  // Available filter options
  const [weeks, setWeeks] = useState([]);
  const [domains, setDomains] = useState([]);
  const [interfaces, setInterfaces] = useState([1, 2, 3, 4, 5]);
  const [complexities, setComplexities] = useState(['medium', 'hard', 'expert', 'unclassified', 'not_enough_trials']);
  
  // Active filters
  const [activeFilters, setActiveFilters] = useState({
    domain: null,
    week: null,
    interface: null,
    complexity: null
  });

  // Sorting
  const [sortBy, setSortBy] = useState('avg_similarity');
  const [sortOrder, setSortOrder] = useState('desc');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 50;

  useEffect(() => {
    initializeFilters();
  }, []);
  
  useEffect(() => {
    if (activeFilters.domain) {
      fetchTaskSimilarity();
      setCurrentPage(1); // Reset to first page when filters change
    }
  }, [activeFilters, lastUpdate]);

  const initializeFilters = async () => {
    try {
      // Fetch weeks and domains
      const [weeksRes, domainsRes] = await Promise.all([
        api.get('/weeks'),
        api.get('/domains/list')
      ]);
      
      const weeksList = weeksRes.data.weeks || [];
      const domainsList = domainsRes.data.domains || [];
      
      setWeeks(weeksList);
      setDomains(domainsList);
      
      // Set default filters
      if (weeksList.length > 0 && domainsList.length > 0) {
        const defaultWeekNum = weeksList.length > 1 ? weeksList[1].week_num : weeksList[0].week_num;
        
        // Default to hr_experts or first domain
        const defaultDomain = domainsList.find(d => d.name === 'hr_experts') || domainsList[0];
        
        setActiveFilters({
          domain: defaultDomain.name,
          week: defaultWeekNum,
          interface: null,
          complexity: null
        });
      }
    } catch (error) {
      console.error('Error initializing filters:', error);
    }
  };

  const fetchTaskSimilarity = async () => {
    if (!activeFilters.domain) return;
    
    setLoading(true);
    try {
      const params = {};
      if (activeFilters.week) params.week = activeFilters.week;
      if (activeFilters.interface) params.interface = activeFilters.interface;
      if (activeFilters.complexity) params.complexity = activeFilters.complexity;
      
      const response = await api.get(`/task-similarity/${activeFilters.domain}`, { params });
      let tasksData = response.data.tasks || [];
      
      // Store GitHub URL base from response
      if (response.data.github_url_base) {
        setGithubUrlBase(response.data.github_url_base);
      }
      
      // Apply sorting
      tasksData = sortTasks(tasksData, sortBy, sortOrder);
      
      setTasks(tasksData);
    } catch (error) {
      console.error('Error fetching task similarity:', error);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  };

  const sortTasks = (tasksData, field, order) => {
    return [...tasksData].sort((a, b) => {
      let aVal = a[field];
      let bVal = b[field];
      
      // Handle null values
      if (aVal === null) aVal = -1;
      if (bVal === null) bVal = -1;
      
      if (order === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      // Toggle sort order
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    
    // Re-sort tasks
    setTasks(sortTasks(tasks, field, sortOrder === 'asc' ? 'desc' : 'asc'));
  };

  const exportToCSV = () => {
    const headers = ['PR Number', 'Difficulty', 'Pass Count', 'Total Trials', 'Avg Similarity', 'Most Similar PR', 'Least Similar PR'];
    const rows = tasks.map(task => [
      task.pr_number,
      task.difficulty || 'N/A',
      task.pass_count || 'N/A',
      task.total_trials || 'N/A',
      task.avg_similarity ? task.avg_similarity.toFixed(3) : 'N/A',
      task.most_similar?.pr_number || 'N/A',
      task.least_similar?.pr_number || 'N/A'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `task-similarity-${activeFilters.domain}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const getDifficultyColor = (difficulty) => {
    switch (difficulty) {
      case 'medium':
        return 'bg-green-100 text-green-800';
      case 'hard':
        return 'bg-yellow-100 text-yellow-800';
      case 'expert':
        return 'bg-red-100 text-red-800';
      case 'not_enough_trials':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDifficulty = (difficulty) => {
    if (!difficulty) return 'N/A';
    // Replace underscores with spaces and capitalize each word
    return difficulty
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getSimilarityColor = (similarity) => {
    if (similarity === null) return 'text-gray-400';
    if (similarity >= 0.8) return 'text-green-600 font-semibold';
    if (similarity >= 0.6) return 'text-blue-600 font-semibold';
    if (similarity >= 0.4) return 'text-yellow-600 font-semibold';
    return 'text-red-600 font-semibold';
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

  // Pagination calculations
  const totalPages = Math.ceil(tasks.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentTasks = tasks.slice(startIndex, endIndex);

  const goToPage = (page) => {
    setCurrentPage(Math.max(1, Math.min(page, totalPages)));
    setExpandedRow(null); // Collapse any expanded rows when changing pages
    window.scrollTo({ top: 0, behavior: 'smooth' }); // Scroll to top
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center">
          <SparklesIcon className="h-8 w-8 text-purple-600 mr-3" />
          <h2 className="text-3xl font-bold text-gray-900">Task Similarity</h2>
        </div>
        <button
          onClick={exportToCSV}
          disabled={tasks.length === 0}
          className="btn btn-secondary flex items-center"
        >
          <ArrowDownTrayIcon className="h-5 w-5 mr-2" />
          Export CSV
        </button>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <QuestionMarkCircleIcon className="h-5 w-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
          <div className="text-sm text-blue-900">
            <p className="font-semibold mb-1">How Task Similarity Works</p>
            <p className="mb-2">
              We analyze semantic similarity between task instructions. Each task is converted into a numerical vector (embedding), 
              and we calculate how similar tasks are to each other using cosine similarity (0-1 scale).
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div>
                <span className="font-semibold">Similarity Scores:</span>
                <ul className="mt-1 space-y-0.5 ml-2">
                  <li className="flex items-center">• <span className="inline-block w-14 ml-1">0.9-1.0:</span> Near duplicates</li>
                  <li className="flex items-center">• <span className="inline-block w-14 ml-1">0.7-0.8:</span> Related tasks</li>
                  <li className="flex items-center">• <span className="inline-block w-14 ml-1">&lt;0.5:</span> Different tasks</li>
                </ul>
              </div>
              <div>
                <span className="font-semibold">Difficulty Levels:</span>
                <ul className="mt-1 space-y-1 ml-2">
                  <li className="flex items-center">• <span className="px-1.5 py-0.5 bg-green-100 text-green-800 rounded text-xs font-medium ml-1 mr-2 inline-block w-16 text-center">Medium</span> 62.5-75% pass rate</li>
                  <li className="flex items-center">• <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-800 rounded text-xs font-medium ml-1 mr-2 inline-block w-16 text-center">Hard</span> 37.5-56% pass rate</li>
                  <li className="flex items-center">• <span className="px-1.5 py-0.5 bg-red-100 text-red-800 rounded text-xs font-medium ml-1 mr-2 inline-block w-16 text-center">Expert</span> 18.75-31% pass rate</li>
                </ul>
              </div>
              <div>
                <span className="font-semibold">Useful For:</span>
                <ul className="mt-1 space-y-0.5 ml-2">
                  <li>• Finding duplicate tasks</li>
                  <li>• Grouping related tasks</li>
                  <li>• Analyzing task difficulty</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center mb-4">
          <FunnelIcon className="h-5 w-5 text-gray-500 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Domain Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Domain <span className="text-red-500">*</span>
            </label>
            <select
              value={activeFilters.domain || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, domain: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {domains.map((domain) => (
                <option key={domain.id} value={domain.name}>
                  {domain.name}
                </option>
              ))}
            </select>
          </div>

          {/* Week Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Week
            </label>
            <select
              value={activeFilters.week || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, week: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">All Weeks</option>
              {weeks.map((week) => (
                <option key={week.id} value={week.week_num}>
                  {week.week_name}
                </option>
              ))}
            </select>
          </div>

          {/* Interface Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Interface
            </label>
            <select
              value={activeFilters.interface || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, interface: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">All Interfaces</option>
              {interfaces.map((num) => (
                <option key={num} value={num}>
                  Interface {num}
                </option>
              ))}
            </select>
          </div>

          {/* Complexity Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Difficulty
            </label>
            <select
              value={activeFilters.complexity || ''}
              onChange={(e) => setActiveFilters({ ...activeFilters, complexity: e.target.value || null })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">All Difficulties</option>
              {complexities.map((comp) => (
                <option key={comp} value={comp}>
                  {formatDifficulty(comp)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Total Tasks</p>
          <p className="text-3xl font-bold text-gray-900">{tasks.length}</p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Avg Similarity</p>
          <p className="text-3xl font-bold text-purple-600">
            {tasks.length > 0 
              ? (tasks.reduce((sum, t) => sum + (t.avg_similarity || 0), 0) / tasks.length).toFixed(3)
              : 'N/A'}
          </p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-gray-600">With Data</p>
          <p className="text-3xl font-bold text-green-600">
            {tasks.filter(t => t.avg_similarity !== null).length}
          </p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Avg Pass Rate</p>
          <p className="text-3xl font-bold text-blue-600">
            {tasks.length > 0 && tasks.some(t => t.total_trials)
              ? ((tasks.reduce((sum, t) => sum + (t.pass_count || 0), 0) / 
                  tasks.reduce((sum, t) => sum + (t.total_trials || 0), 0)) * 100).toFixed(1) + '%'
              : 'N/A'}
          </p>
        </div>
      </div>

      {/* Tasks Table */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 relative">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <button onClick={() => handleSort('pr_number')} className="flex items-center hover:text-gray-700">
                    PR # <ChevronUpDownIcon className="h-4 w-4 ml-1" />
                  </button>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <div className="flex items-center gap-1">
                    Instruction
                    <Tooltip text="The task instruction text from task.json. Click 'Show Full' to expand.">
                      <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                    </Tooltip>
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleSort('difficulty')} className="flex items-center hover:text-gray-700">
                      Difficulty <ChevronUpDownIcon className="h-4 w-4 ml-1" />
                    </button>
                    <Tooltip text="Calculated from pass rates: Medium (62.5-75%), Hard (37.5-56%), Expert (18.75-31%). Blue badge means insufficient trials (<3).">
                      <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                    </Tooltip>
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleSort('pass_count')} className="flex items-center hover:text-gray-700">
                      Pass/Total <ChevronUpDownIcon className="h-4 w-4 ml-1" />
                    </button>
                    <Tooltip text="Number of successful trials out of total trials from result.json (e.g., 7/16 = 7 passes out of 16 trials).">
                      <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                    </Tooltip>
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleSort('avg_similarity')} className="flex items-center hover:text-gray-700">
                      Avg Similarity <ChevronUpDownIcon className="h-4 w-4 ml-1" />
                    </button>
                    <Tooltip text="Average cosine similarity (0-1) with all other tasks in this domain. Higher = more similar to other tasks. 0.7+ means highly related tasks.">
                      <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                    </Tooltip>
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <div className="flex items-center gap-1">
                    Most Similar
                    <Tooltip text="The task with the highest similarity score to this one. Useful for finding duplicate or near-duplicate tasks.">
                      <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                    </Tooltip>
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider overflow-visible">
                  <div className="flex items-center gap-1">
                    Least Similar
                    <Tooltip text="The task with the lowest similarity score to this one. Shows the most different task in the domain.">
                      <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                    </Tooltip>
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tasks.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-6 py-12 text-center text-gray-500">
                    No tasks found matching the selected filters.
                  </td>
                </tr>
              ) : (
                currentTasks.map((task) => (
                  <React.Fragment key={task.pr_number}>
                    <tr className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <a 
                          href={`${githubUrlBase}/pull/${task.pr_number}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline font-medium"
                        >
                          #{task.pr_number}
                        </a>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900 max-w-md truncate">
                          {task.instruction_preview || 'N/A'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getDifficultyColor(task.difficulty)}`}>
                          {formatDifficulty(task.difficulty)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {task.pass_count !== null ? (
                          <span>
                            {task.pass_count}/{task.total_trials}
                            <span className="text-xs text-gray-500 ml-1">
                              ({((task.pass_count / task.total_trials) * 100).toFixed(0)}%)
                            </span>
                          </span>
                        ) : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`text-sm ${getSimilarityColor(task.avg_similarity)}`}>
                          {task.avg_similarity !== null ? task.avg_similarity.toFixed(3) : 'N/A'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {task.most_similar ? (
                          <div>
                            <a 
                              href={`${githubUrlBase}/pull/${task.most_similar.pr_number}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              #{task.most_similar.pr_number}
                            </a>
                            <span className="text-xs text-gray-500 ml-1">
                              ({task.most_similar.similarity.toFixed(3)})
                            </span>
                          </div>
                        ) : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {task.least_similar ? (
                          <div>
                            <a 
                              href={`${githubUrlBase}/pull/${task.least_similar.pr_number}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              #{task.least_similar.pr_number}
                            </a>
                            <span className="text-xs text-gray-500 ml-1">
                              ({task.least_similar.similarity.toFixed(3)})
                            </span>
                          </div>
                        ) : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <button
                          onClick={() => setExpandedRow(expandedRow === task.pr_number ? null : task.pr_number)}
                          className="text-purple-600 hover:text-purple-800 flex items-center"
                        >
                          <ArrowsPointingOutIcon className="h-4 w-4 mr-1" />
                          {expandedRow === task.pr_number ? 'Collapse' : 'Expand'}
                        </button>
                      </td>
                    </tr>
                    {expandedRow === task.pr_number && (
                      <tr>
                        <td colSpan="8" className="px-6 py-4 bg-gray-50">
                          <div className="space-y-3">
                            <div>
                              <h4 className="font-semibold text-gray-900 mb-2">Full Instruction:</h4>
                              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                                {task.instruction || 'No instruction available'}
                              </p>
                            </div>
                            <div className="grid grid-cols-3 gap-4 text-sm">
                              <div>
                                <span className="font-medium text-gray-600">Week:</span> {task.week_num || 'N/A'}
                              </div>
                              <div>
                                <span className="font-medium text-gray-600">Interface:</span> {task.interface_num || 'N/A'}
                              </div>
                              <div>
                                <span className="font-medium text-gray-600">Pod:</span> {task.pod_name || 'N/A'}
                              </div>
                              <div>
                                <span className="font-medium text-gray-600">Trainer:</span> {task.trainer_name || 'N/A'}
                              </div>
                              <div>
                                <span className="font-medium text-gray-600">Merged:</span> {task.merged_at ? new Date(task.merged_at).toLocaleDateString() : 'N/A'}
                              </div>
                              <div>
                                <span className="font-medium text-gray-600">Similarities:</span> {task.similarity_count || 0}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {tasks.length > 0 && totalPages > 1 && (
        <div className="card">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Showing <span className="font-medium">{startIndex + 1}</span> to{' '}
              <span className="font-medium">{Math.min(endIndex, tasks.length)}</span> of{' '}
              <span className="font-medium">{tasks.length}</span> tasks
            </div>
            <div className="flex items-center space-x-2">
              {/* Previous Button */}
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className={`px-3 py-2 text-sm font-medium rounded-md ${
                  currentPage === 1
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                }`}
              >
                Previous
              </button>

              {/* Page Numbers */}
              <div className="flex space-x-1">
                {/* First Page */}
                {currentPage > 3 && (
                  <>
                    <button
                      onClick={() => goToPage(1)}
                      className="px-3 py-2 text-sm font-medium rounded-md bg-white text-gray-700 hover:bg-gray-50 border border-gray-300"
                    >
                      1
                    </button>
                    {currentPage > 4 && (
                      <span className="px-2 py-2 text-gray-500">...</span>
                    )}
                  </>
                )}

                {/* Pages around current */}
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(page => 
                    page === currentPage ||
                    page === currentPage - 1 ||
                    page === currentPage + 1 ||
                    page === currentPage - 2 ||
                    page === currentPage + 2
                  )
                  .filter(page => page > 0 && page <= totalPages)
                  .map(page => (
                    <button
                      key={page}
                      onClick={() => goToPage(page)}
                      className={`px-3 py-2 text-sm font-medium rounded-md ${
                        page === currentPage
                          ? 'bg-purple-600 text-white'
                          : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                      }`}
                    >
                      {page}
                    </button>
                  ))}

                {/* Last Page */}
                {currentPage < totalPages - 2 && (
                  <>
                    {currentPage < totalPages - 3 && (
                      <span className="px-2 py-2 text-gray-500">...</span>
                    )}
                    <button
                      onClick={() => goToPage(totalPages)}
                      className="px-3 py-2 text-sm font-medium rounded-md bg-white text-gray-700 hover:bg-gray-50 border border-gray-300"
                    >
                      {totalPages}
                    </button>
                  </>
                )}
              </div>

              {/* Next Button */}
              <button
                onClick={() => goToPage(currentPage + 1)}
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
          </div>
        </div>
      )}
    </div>
  );
};

export default TaskSimilarityView;

