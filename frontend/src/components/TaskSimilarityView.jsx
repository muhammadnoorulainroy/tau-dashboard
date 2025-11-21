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
  
  // Tab state
  const [activeTab, setActiveTab] = useState('browse'); // 'browse' or 'search'
  
  // Custom instruction search state
  const [customInstruction, setCustomInstruction] = useState('');
  const [searchDomain, setSearchDomain] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchLimit, setSearchLimit] = useState(20);
  const [searchMessage, setSearchMessage] = useState(null); // Success/error message
  
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
  const [sortBy, setSortBy] = useState('most_similar');
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
      let aVal, bVal;
      
      // Special handling for most_similar sorting (by similarity score)
      if (field === 'most_similar') {
        aVal = a.most_similar?.similarity ?? -1;
        bVal = b.most_similar?.similarity ?? -1;
      } else {
        aVal = a[field];
        bVal = b[field];
        
        // Handle null values
        if (aVal === null) aVal = -1;
        if (bVal === null) bVal = -1;
      }
      
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

  const searchSimilarTasks = async () => {
    if (!customInstruction.trim()) {
      setSearchMessage({ type: 'error', text: 'Please enter an instruction to search' });
      return;
    }
    
    if (!searchDomain) {
      setSearchMessage({ type: 'error', text: 'Please select a domain' });
      return;
    }
    
    setSearching(true);
    setSearchResults([]);
    setSearchMessage(null);
    
    try {
      const response = await api.post('/task-similarity/search', {
        instruction: customInstruction.trim(),
        domain: searchDomain,
        limit: searchLimit
      });
      
      const results = response.data.results || [];
      setSearchResults(results);
      
      // Show success message with details
      const totalCompared = response.data.total_compared || results.length;
      const topScore = results.length > 0 ? (results[0].similarity * 100).toFixed(1) : 0;
      
      setSearchMessage({ 
        type: 'success', 
        text: `✓ Similarity calculated! Found ${results.length} results out of ${totalCompared} tasks compared. Top match: ${topScore}% similar.`
      });
      
      // Auto-hide success message after 5 seconds
      setTimeout(() => {
        setSearchMessage(null);
      }, 5000);
      
    } catch (error) {
      console.error('Error searching similar tasks:', error);
      setSearchMessage({ 
        type: 'error', 
        text: 'Failed to search similar tasks. Please try again.'
      });
    } finally {
      setSearching(false);
    }
  };

  const exportToCSV = () => {
    // Helper function to escape CSV values (handle commas, quotes, newlines)
    const escapeCSV = (value) => {
      if (value === null || value === undefined) return 'N/A';
      const str = String(value);
      // If contains comma, quote, or newline, wrap in quotes and escape existing quotes
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const headers = [
      'PR Number',
      'Task Title',
      'Task Folder Path',
      'Trainer',
      'Week',
      'Interface',
      'Difficulty',
      'Pass Count',
      'Total Trials',
      'Pass Rate %',
      'Instruction (Full)',
      'Most Similar PR',
      'Most Similar Title',
      'Most Similar Folder',
      'Most Similar Trainer',
      'Most Similar Score',
      'Most Similar Instruction (Full)',
      'Least Similar PR',
      'Least Similar Score'
    ];
    
    const rows = tasks.map(task => {
      const passRate = task.total_trials > 0 
        ? ((task.pass_count / task.total_trials) * 100).toFixed(1) 
        : 'N/A';
      
      return [
        task.pr_number || 'N/A',
        escapeCSV(task.pr_title || 'N/A'),
        escapeCSV(task.task_folder_path || 'N/A'),
        escapeCSV(task.trainer_name || 'N/A'),
        task.week_num || 'N/A',
        task.interface_num || 'N/A',
        task.difficulty || 'N/A',
        task.pass_count || 'N/A',
        task.total_trials || 'N/A',
        passRate,
        escapeCSV(task.instruction || 'N/A'),
        task.most_similar?.pr_number || 'N/A',
        escapeCSV(task.most_similar?.pr_title || 'N/A'),
        escapeCSV(task.most_similar?.task_folder_path || 'N/A'),
        escapeCSV(task.most_similar?.trainer_name || 'N/A'),
        task.most_similar?.similarity ? task.most_similar.similarity.toFixed(3) : 'N/A',
        escapeCSV(task.most_similar?.instruction || 'N/A'),
        task.least_similar?.pr_number || 'N/A',
        task.least_similar?.similarity ? task.least_similar.similarity.toFixed(3) : 'N/A'
      ];
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
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

  // Color scheme for Most Similar column (text only, more emphasis than avg)
  const getMostSimilarColor = (similarity) => {
    if (similarity === null || similarity === undefined) return 'text-gray-400';
    if (similarity >= 0.9) return 'text-red-600 font-bold text-base';  // Near duplicates - red & bold
    if (similarity >= 0.8) return 'text-orange-600 font-bold';  // Very similar - orange & bold
    if (similarity >= 0.7) return 'text-yellow-600 font-semibold';  // Related - yellow
    if (similarity >= 0.5) return 'text-blue-600 font-semibold';  // Somewhat similar - blue
    return 'text-green-600 font-semibold';  // Different - green
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
        {activeTab === 'browse' && (
          <button
            onClick={exportToCSV}
            disabled={tasks.length === 0}
            className="btn btn-secondary flex items-center"
          >
            <ArrowDownTrayIcon className="h-5 w-5 mr-2" />
            Export CSV
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('browse')}
            className={`${
              activeTab === 'browse'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Browse Similarities
          </button>
          <button
            onClick={() => setActiveTab('search')}
            className={`${
              activeTab === 'search'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Search Custom Instruction
          </button>
        </nav>
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

      {/* Browse Tab Content */}
      {activeTab === 'browse' && (
        <>
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Total Tasks</p>
          <p className="text-3xl font-bold text-gray-900">{tasks.length}</p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-gray-600">With Similarity Data</p>
          <p className="text-3xl font-bold text-purple-600">
            {tasks.filter(t => t.most_similar !== null).length}
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
                    <button onClick={() => handleSort('most_similar')} className="flex items-center hover:text-gray-700">
                      Most Similar <ChevronUpDownIcon className="h-4 w-4 ml-1" />
                    </button>
                    <Tooltip text="The task with the highest similarity score to this one. Scores are color-coded: red (0.9+) for near duplicates, orange (0.8+) for very similar tasks, yellow (0.7+) for related tasks, blue (0.5+) for somewhat similar, green (<0.5) for different tasks.">
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
                  <td colSpan="7" className="px-6 py-12 text-center text-gray-500">
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
                            <span className="text-gray-500 ml-1">(</span>
                            <span className={getMostSimilarColor(task.most_similar.similarity)}>
                              {task.most_similar.similarity.toFixed(3)}
                            </span>
                            <span className="text-gray-500">)</span>
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
                        <td colSpan="7" className="px-6 py-4 bg-gray-50">
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
        </>
      )}

      {/* Search Tab Content */}
      {activeTab === 'search' && (
        <div className="space-y-6">
          {/* Instructions */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start">
              <QuestionMarkCircleIcon className="h-5 w-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
              <div className="text-sm text-blue-900">
                <p className="font-semibold mb-1">How Custom Instruction Search Works</p>
                <p>
                  Paste any task instruction below, select a domain, and we'll find the most similar tasks from that domain. 
                  This uses the same AI-powered semantic similarity technology to compare your instruction against all merged tasks.
                </p>
              </div>
            </div>
          </div>

          {/* Search Form */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Search for Similar Tasks</h3>
            
            <div className="space-y-4">
              {/* Domain Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Domain *
                </label>
                <select
                  value={searchDomain}
                  onChange={(e) => setSearchDomain(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">Select a domain...</option>
                  {domains.map(domain => (
                    <option key={domain.id} value={domain.name}>{domain.name}</option>
                  ))}
                </select>
              </div>

              {/* Instruction Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Task Instruction *
                </label>
                <textarea
                  value={customInstruction}
                  onChange={(e) => setCustomInstruction(e.target.value)}
                  placeholder="Paste your task instruction here... (e.g., 'You are an AI assistant helping with incident management. Handle the following request...')"
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
                />
                <p className="mt-1 text-xs text-gray-500">
                  {customInstruction.length} characters
                </p>
              </div>

              {/* Results Limit */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Number of Results
                </label>
                <select
                  value={searchLimit}
                  onChange={(e) => setSearchLimit(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value={10}>10 results</option>
                  <option value={20}>20 results</option>
                  <option value={50}>50 results</option>
                  <option value={100}>100 results</option>
                </select>
              </div>

              {/* Search Button */}
              <button
                onClick={searchSimilarTasks}
                disabled={searching || !customInstruction.trim() || !searchDomain}
                className="btn btn-primary w-full flex items-center justify-center"
              >
                {searching ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Searching...
                  </>
                ) : (
                  <>
                    <SparklesIcon className="h-5 w-5 mr-2" />
                    Find Similar Tasks
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Progress Indicator */}
          {searching && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center">
                <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <div className="text-sm text-blue-900">
                  <p className="font-semibold">Calculating similarity...</p>
                  <p className="text-xs mt-1">Comparing your instruction against all tasks in <span className="font-medium">{searchDomain}</span></p>
                </div>
              </div>
            </div>
          )}

          {/* Success/Error Message */}
          {searchMessage && !searching && (
            <div className={`rounded-lg p-4 ${
              searchMessage.type === 'success' 
                ? 'bg-green-50 border border-green-200' 
                : 'bg-red-50 border border-red-200'
            }`}>
              <div className="flex items-start">
                {searchMessage.type === 'success' ? (
                  <svg className="h-5 w-5 text-green-600 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <svg className="h-5 w-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
                  </svg>
                )}
                <div className={`text-sm ${
                  searchMessage.type === 'success' ? 'text-green-900' : 'text-red-900'
                }`}>
                  {searchMessage.text}
                </div>
              </div>
            </div>
          )}

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Search Results ({searchResults.length} most similar tasks)
              </h3>
              
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Similarity
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        PR
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Task
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Trainer
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Week
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Interface
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Difficulty
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Pass Rate
                      </th>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Instruction Preview
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {searchResults.map((result) => (
                      <tr key={result.pr_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            result.similarity >= 0.9 ? 'bg-red-100 text-red-800' :
                            result.similarity >= 0.8 ? 'bg-orange-100 text-orange-800' :
                            result.similarity >= 0.7 ? 'bg-yellow-100 text-yellow-800' :
                            result.similarity >= 0.6 ? 'bg-blue-100 text-blue-800' :
                            'bg-green-100 text-green-800'
                          }`}>
                            {(result.similarity * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <a 
                            href={`${githubUrlBase}/pull/${result.pr_number}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            #{result.pr_number}
                          </a>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          <div className="max-w-xs truncate" title={result.pr_title}>
                            {result.pr_title}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {result.trainer_name || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {result.week_num || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {result.interface_num || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                            result.difficulty === 'medium' ? 'bg-green-100 text-green-800' :
                            result.difficulty === 'hard' ? 'bg-yellow-100 text-yellow-800' :
                            result.difficulty === 'expert' ? 'bg-red-100 text-red-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {result.difficulty || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {result.pass_rate !== null ? `${result.pass_rate.toFixed(0)}%` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500">
                          <div className="max-w-md truncate" title={result.instruction}>
                            {result.instruction_preview || 'N/A'}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* No results message */}
          {!searching && searchResults.length === 0 && customInstruction.trim() && searchDomain && (
            <div className="card text-center py-12">
              <p className="text-gray-500">Enter an instruction and click "Find Similar Tasks" to see results.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TaskSimilarityView;

