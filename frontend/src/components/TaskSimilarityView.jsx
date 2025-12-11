import React, { useState, useEffect } from 'react';
import { getEnvironments, getTasks, getTaskSimilarity, getActionSimilarity, searchSimilarTasks } from '../services/api';
import {
  SparklesIcon,
  FunnelIcon,
  ArrowsPointingOutIcon,
  ChevronUpDownIcon,
  QuestionMarkCircleIcon,
  MagnifyingGlassIcon,
  DocumentTextIcon
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

const STATUS_COLORS = {
  'draft': 'bg-gray-100 text-gray-800',
  'pending_review': 'bg-amber-100 text-amber-800',
  'in_expert_review': 'bg-orange-100 text-orange-800',
  'pending_calibrator_review': 'bg-violet-100 text-violet-800',
  'in_calibrator_review': 'bg-indigo-100 text-indigo-800',
  'in_pod_lead_review': 'bg-blue-100 text-blue-800',
  'rework': 'bg-red-100 text-red-800',
  'approved': 'bg-green-100 text-green-800'
};

const DIFFICULTY_COLORS = {
  'expert': 'bg-purple-100 text-purple-800',
  'hard': 'bg-orange-100 text-orange-800',
  'medium': 'bg-blue-100 text-blue-800'
};

const TaskSimilarityView = ({ lastUpdate }) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedTask, setExpandedTask] = useState(null);
  const [similarTasks, setSimilarTasks] = useState({});
  const [loadingSimilarity, setLoadingSimilarity] = useState({});
  
  // Tab state
  const [activeTab, setActiveTab] = useState('task'); // 'task', 'action', or 'custom'
  
  // Available filter options
  const [environments, setEnvironments] = useState([]);
  const [difficulties] = useState(['medium', 'hard', 'expert']);
  
  // Active filters
  const [selectedDomain, setSelectedDomain] = useState('');
  const [selectedDifficulty, setSelectedDifficulty] = useState('');

  // Sorting
  const [sortBy, setSortBy] = useState('similarity');
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
    setCurrentPage(1);
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 ml-1 text-gray-300">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 15L12 18.75 15.75 15m-7.5-6L12 5.25 15.75 9" />
      </svg>
    );
    return sortOrder === 'desc' ? (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 ml-1">
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
      </svg>
    ) : (
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4 ml-1">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
      </svg>
    );
  };

  const sortTasks = (data) => {
    return [...data].sort((a, b) => {
      let aVal, bVal;
      
      if (sortBy === 'similarity') {
        const aTop = similarTasks[a.id]?.[0];
        const bTop = similarTasks[b.id]?.[0];
        aVal = aTop?.similarity_score ?? -1;
        bVal = bTop?.similarity_score ?? -1;
      } else {
        aVal = a[sortBy];
        bVal = b[sortBy];
      }
      
      // Handle nulls
      if (aVal == null) aVal = sortOrder === 'desc' ? -Infinity : Infinity;
      if (bVal == null) bVal = sortOrder === 'desc' ? -Infinity : Infinity;
      
      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
      }
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
    });
  };
  
  // Custom search state
  const [customSearchText, setCustomSearchText] = useState('');
  const [customSearchType, setCustomSearchType] = useState('instruction'); // 'instruction' or 'action'
  const [customSearchDomain, setCustomSearchDomain] = useState('');
  const [customSearchResults, setCustomSearchResults] = useState([]);
  const [customSearchLoading, setCustomSearchLoading] = useState(false);
  const [minSimilarity, setMinSimilarity] = useState(0.3);

  useEffect(() => {
    fetchEnvironments();
  }, []);
  
  useEffect(() => {
    if (selectedDomain) {
      fetchTasks();
      setCurrentPage(1);
    }
  }, [selectedDomain, selectedDifficulty, lastUpdate]);
  
  // Fetch similarity for current page when page changes
  useEffect(() => {
    if (tasks.length > 0 && activeTab !== 'custom') {
      const startIdx = (currentPage - 1) * itemsPerPage;
      const pageTasks = tasks.slice(startIdx, startIdx + itemsPerPage);
      fetchSimilarityForPage(pageTasks);
    }
  }, [currentPage, itemsPerPage, activeTab]);

  const fetchEnvironments = async () => {
    try {
      const response = await getEnvironments();
      const envs = response.data || [];
      setEnvironments(envs);
      
      // Set default domain to first environment with approved tasks
      const defaultEnv = envs.find(e => e.approved_count > 0) || envs[0];
      if (defaultEnv) {
        setSelectedDomain(defaultEnv.name);
      }
    } catch (error) {
      console.error('Error fetching environments:', error);
    }
  };

  const fetchTasks = async () => {
    if (!selectedDomain) return;
    
    setLoading(true);
    setSimilarTasks({}); // Reset similarity data when filters change
    try {
      // Fetch approved tasks for similarity comparison
      const params = {
        domain: selectedDomain,
        status: 'approved',
        per_page: 100
      };
      if (selectedDifficulty) {
        params.difficulty = selectedDifficulty;
      }
      
      const response = await getTasks(params);
      const fetchedTasks = response.data.data || [];
      setTasks(fetchedTasks);
      
      // Pre-fetch similarity for first page of tasks
      fetchSimilarityForPage(fetchedTasks.slice(0, itemsPerPage));
    } catch (error) {
      console.error('Error fetching tasks:', error);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  };
  
  const fetchSimilarityForPage = async (pageTasks) => {
    const endpoint = activeTab === 'action' ? getActionSimilarity : getTaskSimilarity;
    
    for (const task of pageTasks) {
      if (!similarTasks[task.id]) {
        try {
          const response = await endpoint(task.id, 1); // Just get top 1
          setSimilarTasks(prev => ({
            ...prev,
            [task.id]: response.data.similar_tasks || []
          }));
        } catch (error) {
          // Silently fail for individual tasks
        }
      }
    }
  };

  const fetchSimilarityForTask = async (taskId) => {
    if (similarTasks[taskId]) return; // Already loaded
    
    setLoadingSimilarity(prev => ({ ...prev, [taskId]: true }));
    
    try {
      const endpoint = activeTab === 'action' ? getActionSimilarity : getTaskSimilarity;
      const response = await endpoint(taskId, 5);
      
      setSimilarTasks(prev => ({
        ...prev,
        [taskId]: response.data.similar_tasks || []
      }));
    } catch (error) {
      console.error('Error fetching similarity:', error);
      setSimilarTasks(prev => ({
        ...prev,
        [taskId]: []
      }));
    } finally {
      setLoadingSimilarity(prev => ({ ...prev, [taskId]: false }));
    }
  };

  const handleExpand = async (taskId) => {
    if (expandedTask === taskId) {
      setExpandedTask(null);
    } else {
      setExpandedTask(taskId);
      await fetchSimilarityForTask(taskId);
    }
  };

  const handleCustomSearch = async () => {
    if (!customSearchText.trim()) return;
    
    setCustomSearchLoading(true);
    try {
      const response = await searchSimilarTasks(customSearchText, {
        domain: customSearchDomain || null,
        searchType: customSearchType,
        limit: 20,
        minSimilarity: minSimilarity
      });
      setCustomSearchResults(response.data.results || []);
    } catch (error) {
      console.error('Error searching similar tasks:', error);
      setCustomSearchResults([]);
    } finally {
      setCustomSearchLoading(false);
    }
  };

  const getSimilarityColor = (similarity) => {
    if (similarity === null || similarity === undefined) return 'text-gray-400';
    if (similarity >= 0.9) return 'text-red-600 font-bold';
    if (similarity >= 0.8) return 'text-orange-600 font-bold';
    if (similarity >= 0.7) return 'text-yellow-600 font-semibold';
    if (similarity >= 0.5) return 'text-blue-600 font-semibold';
    return 'text-green-600 font-semibold';
  };

  // Sorting and Pagination
  const sortedTasks = sortTasks(tasks);
  const totalPages = Math.ceil(sortedTasks.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const currentTasks = sortedTasks.slice(startIndex, startIndex + itemsPerPage);

  if (loading && tasks.length === 0) {
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
        <div className="flex items-center">
          <SparklesIcon className="h-8 w-8 text-purple-600 mr-3" />
          <h2 className="text-3xl font-bold text-gray-900">Task Similarity</h2>
        </div>
        <span className="text-sm text-gray-500">
          {tasks.length} approved tasks
        </span>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => { setActiveTab('task'); setSimilarTasks({}); setExpandedTask(null); }}
            className={`${
              activeTab === 'task'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-all flex items-center`}
          >
            <DocumentTextIcon className="h-4 w-4 mr-2" />
            Instruction Similarity
          </button>
          <button
            onClick={() => { setActiveTab('action'); setSimilarTasks({}); setExpandedTask(null); }}
            className={`${
              activeTab === 'action'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-all flex items-center`}
          >
            <ArrowsPointingOutIcon className="h-4 w-4 mr-2" />
            Action Similarity
          </button>
          <button
            onClick={() => { setActiveTab('custom'); }}
            className={`${
              activeTab === 'custom'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-all flex items-center`}
          >
            <MagnifyingGlassIcon className="h-4 w-4 mr-2" />
            Custom Search
          </button>
        </nav>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <QuestionMarkCircleIcon className="h-5 w-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
          <div className="text-sm text-blue-900">
            <p className="font-semibold mb-1">
              {activeTab === 'task' ? 'How Instruction Similarity Works' : 
               activeTab === 'action' ? 'How Action Similarity Works' : 
               'How Custom Search Works'}
            </p>
            <p className="mb-2">
              {activeTab === 'task' 
                ? 'We analyze semantic similarity between task instructions using AI embeddings. Each task is converted into a numerical vector and compared using cosine similarity (0-1 scale).'
                : activeTab === 'action'
                ? 'Action similarity compares the sequence of tool calls (actions) taken to complete tasks. We analyze which tools were used and in what order to identify tasks with similar execution patterns.'
                : 'Paste any text (instruction or action sequence) and find similar tasks in the database. This is useful for checking if a new task idea already exists or finding related tasks for reference.'
              }
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div>
                <span className="font-semibold">Similarity Scores:</span>
                <ul className="mt-1 space-y-0.5 ml-2">
                  <li>• <span className="text-red-600 font-bold">0.9-1.0:</span> Near duplicates</li>
                  <li>• <span className="text-orange-600 font-bold">0.8-0.9:</span> Very similar</li>
                  <li>• <span className="text-yellow-600">0.7-0.8:</span> Related tasks</li>
                  <li>• <span className="text-blue-600">0.5-0.7:</span> Somewhat similar</li>
                  <li>• <span className="text-green-600">&lt;0.5:</span> Different tasks</li>
                </ul>
              </div>
              <div>
                <span className="font-semibold">Useful For:</span>
                <ul className="mt-1 space-y-0.5 ml-2">
                  <li>• Finding duplicate tasks</li>
                  <li>• Checking if a task idea exists</li>
                  <li>• Finding reference tasks</li>
                  <li>• Quality control</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Custom Search Tab Content */}
      {activeTab === 'custom' && (
        <div className="space-y-6">
          {/* Custom Search Input */}
          <div className="card">
            <div className="flex items-center mb-4">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-500 mr-2" />
              <h3 className="text-lg font-semibold text-gray-900">Search for Similar Tasks</h3>
            </div>
            
            <div className="space-y-4">
              {/* Search Type and Domain Row */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Search Type</label>
                  <select
                    value={customSearchType}
                    onChange={(e) => setCustomSearchType(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="instruction">Instruction Similarity</option>
                    <option value="action">Action Sequence Similarity</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Environment (optional)</label>
                  <select
                    value={customSearchDomain}
                    onChange={(e) => setCustomSearchDomain(e.target.value)}
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
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Min Similarity</label>
                  <select
                    value={minSimilarity}
                    onChange={(e) => setMinSimilarity(parseFloat(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="0.1">10%</option>
                    <option value="0.2">20%</option>
                    <option value="0.3">30%</option>
                    <option value="0.4">40%</option>
                    <option value="0.5">50%</option>
                    <option value="0.6">60%</option>
                    <option value="0.7">70%</option>
                  </select>
                </div>
              </div>
              
              {/* Text Area */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Paste your {customSearchType === 'instruction' ? 'task instruction' : 'action sequence'} here:
                </label>
                <textarea
                  value={customSearchText}
                  onChange={(e) => setCustomSearchText(e.target.value)}
                  placeholder={customSearchType === 'instruction' 
                    ? "Enter the task instruction text you want to find similar tasks for..."
                    : "Enter tool names or action sequence (e.g., 'click_element, type_text, submit_form')..."
                  }
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 resize-y"
                />
              </div>
              
              {/* Search Button */}
              <div className="flex justify-end">
                <button
                  onClick={handleCustomSearch}
                  disabled={!customSearchText.trim() || customSearchLoading}
                  className={`px-6 py-2 rounded-md font-medium flex items-center ${
                    !customSearchText.trim() || customSearchLoading
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : 'bg-purple-600 text-white hover:bg-purple-700'
                  }`}
                >
                  {customSearchLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Searching...
                    </>
                  ) : (
                    <>
                      <MagnifyingGlassIcon className="h-4 w-4 mr-2" />
                      Find Similar Tasks
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
          
          {/* Custom Search Results */}
          {customSearchResults.length > 0 && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <SparklesIcon className="h-5 w-5 text-purple-500" />
                  Found {customSearchResults.length} Similar Tasks
                </h3>
                <span className="text-sm text-gray-500">
                  {customSearchType === 'instruction' ? 'By instruction text' : 'By action sequence'}
                </span>
              </div>
              <div className="space-y-4">
                {customSearchResults.map((result, idx) => (
                  <div key={idx} className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-gray-50 to-white border-b">
                      <div className="flex items-center gap-3">
                        <div className={`text-2xl font-bold ${getSimilarityColor(result.similarity_score)}`}>
                          {(result.similarity_score * 100).toFixed(0)}%
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_COLORS[result.status] || 'bg-gray-100 text-gray-800'}`}>
                            {result.status?.replace(/_/g, ' ')}
                          </span>
                          {result.difficulty && (
                            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${DIFFICULTY_COLORS[result.difficulty] || 'bg-gray-100 text-gray-800'}`}>
                              {result.difficulty}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-gray-700">
                          {result.domain?.replace(/_/g, ' ')}
                        </div>
                        {result.trainer_name && (
                          <div className="text-xs text-gray-400">
                            by {result.trainer_name}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {/* Content */}
                    <div className="p-4">
                      {result.description && (
                        <div className="text-sm font-medium text-gray-800 mb-2">
                          {result.description}
                        </div>
                      )}
                      
                      {customSearchType === 'instruction' ? (
                        /* Show instruction text */
                        <div className="text-sm text-gray-600 leading-relaxed bg-gray-50 p-3 rounded-lg">
                          {result.instruction_text || 'No instruction available'}
                        </div>
                      ) : (
                        /* Show action sequence */
                        <div className="space-y-2">
                          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Action Sequence
                          </div>
                          {result.action_sequence ? (
                            <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg font-mono">
                              {result.action_sequence}
                            </div>
                          ) : (
                            <div className="text-sm text-gray-400 italic">
                              No action sequence data available
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* No Results Message */}
          {customSearchResults.length === 0 && customSearchText && !customSearchLoading && (
            <div className="card text-center py-8 text-gray-500">
              <p>No similar tasks found. Try:</p>
              <ul className="text-sm mt-2 space-y-1">
                <li>• Lowering the minimum similarity threshold</li>
                <li>• Using different keywords</li>
                <li>• Searching in all environments</li>
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Task/Action Similarity Tab Content */}
      {activeTab !== 'custom' && (
        <>
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
                  Environment <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedDomain}
                  onChange={(e) => setSelectedDomain(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">Select environment...</option>
                  {environments.map((env) => (
                    <option key={env.id} value={env.name}>
                      {env.name.replace(/_/g, ' ')} ({env.approved_count} approved)
                    </option>
                  ))}
                </select>
              </div>

              {/* Difficulty Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Difficulty
                </label>
                <select
                  value={selectedDifficulty}
                  onChange={(e) => setSelectedDifficulty(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">All Difficulties</option>
                  {difficulties.map((diff) => (
                    <option key={diff} value={diff}>
                      {diff.charAt(0).toUpperCase() + diff.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Approved Tasks</p>
          <p className="text-3xl font-bold text-gray-900">{tasks.length}</p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Environment</p>
          <p className="text-xl font-bold text-purple-600">
            {selectedDomain?.replace(/_/g, ' ') || 'None selected'}
          </p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-gray-600">Similarity Type</p>
          <p className="text-xl font-bold text-blue-600">
            {activeTab === 'task' ? 'Instruction' : 'Action Sequence'}
          </p>
        </div>
      </div>

      {/* Tasks Table */}
      <div className="card">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p>No approved tasks found for the selected filters.</p>
            <p className="text-sm mt-2">Try selecting a different environment.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Task
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <div className="flex items-center gap-1">
                      {activeTab === 'task' ? 'Instruction' : 'Actions'}
                      <Tooltip text={activeTab === 'task' 
                        ? "The task instruction text used for similarity comparison" 
                        : "The action sequence (tools used) for similarity comparison"}>
                        <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                      </Tooltip>
                    </div>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button 
                      onClick={() => handleSort('similarity')}
                      className="flex items-center gap-1 hover:text-gray-700"
                    >
                      Most Similar
                      <SortIcon field="similarity" />
                      <Tooltip text="The most similar task found - score and task ID. Click to sort.">
                        <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
                      </Tooltip>
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button 
                      onClick={() => handleSort('difficulty')}
                      className="flex items-center hover:text-gray-700"
                    >
                      Difficulty
                      <SortIcon field="difficulty" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <button 
                      onClick={() => handleSort('trainer_name')}
                      className="flex items-center hover:text-gray-700"
                    >
                      Trainer
                      <SortIcon field="trainer_name" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {currentTasks.map((task) => {
                  const topSimilar = similarTasks[task.id]?.[0];
                  
                  return (
                  <React.Fragment key={task.id}>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium text-gray-900">
                          {task.description || 'No description'}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm text-gray-700 max-w-sm">
                          {activeTab === 'task' ? (
                            <span className="line-clamp-2">
                              {task.instruction_text?.substring(0, 120) || 'N/A'}
                              {task.instruction_text?.length > 120 && '...'}
                            </span>
                          ) : (
                            <div className="flex flex-wrap gap-1">
                              {(() => {
                                const actionNodes = task.tool_sequence?.nodes?.filter(n => n.label || n.tool_name || n.name) || [];
                                if (actionNodes.length === 0) return <span className="text-gray-400">N/A</span>;
                                return (
                                  <>
                                    {actionNodes.slice(0, 4).map((node, i) => (
                                      <span key={i} className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 text-xs rounded">
                                        {node.label || node.tool_name || node.name}
                                      </span>
                                    ))}
                                    {actionNodes.length > 4 && (
                                      <span className="text-xs text-gray-400">+{actionNodes.length - 4}</span>
                                    )}
                                  </>
                                );
                              })()}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {loadingSimilarity[task.id] ? (
                          <div className="flex items-center text-gray-400 text-sm">
                            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-purple-500 mr-2"></div>
                            Loading...
                          </div>
                        ) : topSimilar ? (
                          <div className="space-y-1">
                            <div className={`text-lg font-bold ${getSimilarityColor(topSimilar.similarity_score)}`}>
                              {(topSimilar.similarity_score * 100).toFixed(0)}%
                            </div>
                            <div className="text-xs text-gray-500 font-mono">
                              {topSimilar.task_agent_id}
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">No data</span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${DIFFICULTY_COLORS[task.difficulty] || 'bg-gray-100 text-gray-800'}`}>
                          {task.difficulty || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {task.trainer_name || 'Unknown'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <button
                          onClick={() => handleExpand(task.id)}
                          className="text-purple-600 hover:text-purple-800 flex items-center text-xs font-medium"
                        >
                          <ArrowsPointingOutIcon className="h-4 w-4 mr-1" />
                          {expandedTask === task.id ? 'Collapse' : 'View All'}
                        </button>
                      </td>
                    </tr>
                    
{/* Expanded Row - Similar Tasks */}
                                    {expandedTask === task.id && (
                                      <tr>
                                        <td colSpan="6" className="px-6 py-4 bg-gradient-to-b from-purple-50 to-white">
                                          <div className="space-y-5">
                                            {/* Full Instruction or Action Sequence */}
                                            <div className="bg-white rounded-lg border border-purple-200 p-4">
                                              <h4 className="font-semibold text-purple-900 mb-2 flex items-center gap-2">
                                                {activeTab === 'task' ? (
                                                  <>
                                                    <DocumentTextIcon className="h-5 w-5" />
                                                    Task Instruction
                                                  </>
                                                ) : (
                                                  <>
                                                    <ArrowsPointingOutIcon className="h-5 w-5" />
                                                    Action Sequence ({task.tool_sequence?.nodes?.filter(n => n.label || n.tool_name || n.name).length || 0} steps)
                                                  </>
                                                )}
                                              </h4>
                                              {activeTab === 'task' ? (
                                                <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                                                  {task.instruction_text || 'No instruction available'}
                                                </p>
                                              ) : (
                                                <div className="flex flex-wrap gap-2">
                                                  {task.tool_sequence?.nodes?.filter(n => n.label || n.tool_name || n.name).length > 0 ? (
                                                    task.tool_sequence.nodes
                                                      .filter(n => n.label || n.tool_name || n.name)
                                                      .map((node, i) => (
                                                        <span key={i} className="px-3 py-1.5 bg-purple-100 text-purple-800 text-sm rounded-lg font-medium">
                                                          {i + 1}. {node.label || node.tool_name || node.name}
                                                        </span>
                                                      ))
                                                  ) : (
                                                    <span className="text-gray-400 italic">No action sequence data</span>
                                                  )}
                                                </div>
                                              )}
                                            </div>
                                            
                                            {/* Similar Tasks */}
                                            <div>
                                              <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                                <SparklesIcon className="h-5 w-5 text-purple-500" />
                                                Top Similar Tasks
                                                <span className="text-sm font-normal text-gray-500">
                                                  ({activeTab === 'task' ? 'by instruction text' : 'by action sequence'})
                                                </span>
                                              </h4>
                              
                              {loadingSimilarity[task.id] ? (
                                <div className="flex items-center text-gray-500">
                                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-600 mr-2"></div>
                                  Loading similar tasks...
                                </div>
                              ) : similarTasks[task.id]?.length > 0 ? (
                                <div className="space-y-2">
                                  {similarTasks[task.id].map((similar, idx) => (
                                    <div key={idx} className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                                      {/* Header with score */}
                                      <div className="flex items-center justify-between px-4 py-2 bg-gradient-to-r from-gray-50 to-white border-b">
                                        <div className="flex items-center gap-3">
                                          <div className={`text-xl font-bold ${getSimilarityColor(similar.similarity_score)}`}>
                                            {(similar.similarity_score * 100).toFixed(0)}%
                                          </div>
                                          <div className="text-sm text-gray-500">match</div>
                                          {similar.difficulty && (
                                            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${DIFFICULTY_COLORS[similar.difficulty] || 'bg-gray-100 text-gray-600'}`}>
                                              {similar.difficulty}
                                            </span>
                                          )}
                                        </div>
                                        <div className="text-xs text-gray-400">
                                          {similar.domain?.replace(/_/g, ' ')}
                                        </div>
                                      </div>
                                      
                                      {/* Content - different based on tab */}
                                      <div className="p-4">
                                        {activeTab === 'task' ? (
                                          /* Instruction Similarity - Show instruction text */
                                          <div className="text-sm text-gray-700 leading-relaxed">
                                            {similar.instruction_text || similar.description || 'No instruction available'}
                                          </div>
                                        ) : (
                                          /* Action Similarity - Show tool sequence */
                                          <div className="space-y-2">
                                            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                                              Action Sequence
                                            </div>
                                            <div className="flex flex-wrap gap-1.5">
                                              {(() => {
                                                const actionNodes = similar.tool_sequence?.nodes?.filter(n => n.label || n.tool_name || n.name) || [];
                                                if (actionNodes.length === 0) return <span className="text-gray-400 text-sm italic">No action sequence data</span>;
                                                return (
                                                  <>
                                                    {actionNodes.slice(0, 12).map((node, i) => (
                                                      <span key={i} className="px-2 py-1 bg-indigo-50 text-indigo-700 text-xs rounded-md font-medium">
                                                        {node.label || node.tool_name || node.name}
                                                      </span>
                                                    ))}
                                                    {actionNodes.length > 12 && (
                                                      <span className="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded-md">
                                                        +{actionNodes.length - 12} more
                                                      </span>
                                                    )}
                                                  </>
                                                );
                                              })()}
                                            </div>
                                          </div>
                                        )}
                                        
                                        {/* Footer with trainer */}
                                        {similar.trainer_name && (
                                          <div className="mt-3 pt-2 border-t border-gray-100 text-xs text-gray-400">
                                            by {similar.trainer_name}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <p className="text-sm text-gray-500">
                                  No similar tasks found. Similarity data may not be computed yet.
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {tasks.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between">
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
              <div className="text-sm text-gray-700">
                Showing <span className="font-medium">{startIndex + 1}</span> to{' '}
                <span className="font-medium">{Math.min(startIndex + itemsPerPage, sortedTasks.length)}</span> of{' '}
                <span className="font-medium">{sortedTasks.length}</span> tasks
              </div>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center space-x-2">
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
        </>
      )}
    </div>
  );
};

export default TaskSimilarityView;
