import React, { useState, useEffect } from 'react';
import { getTasks, getEnvironments } from '../services/api';
import { 
  DocumentTextIcon, 
  ChevronUpIcon,
  ChevronDownIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  EyeIcon
} from '@heroicons/react/24/outline';

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

const DIFFICULTY_COLORS = {
  'expert': 'bg-purple-100 text-purple-800',
  'hard': 'bg-orange-100 text-orange-800',
  'medium': 'bg-blue-100 text-blue-800'
};

const TasksView = ({ lastUpdate }) => {
  const [tasks, setTasks] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedDifficulty, setSelectedDifficulty] = useState('');
  const [domains, setDomains] = useState([]);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const perPageOptions = [10, 25, 50, 100];
  
  // Task detail modal
  const [selectedTask, setSelectedTask] = useState(null);

  useEffect(() => {
    fetchDomains();
  }, []);

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    fetchTasks();
  }, [lastUpdate, sortBy, sortOrder, debouncedSearchTerm, selectedDomain, selectedStatus, selectedDifficulty, page, perPage]);
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [sortBy, sortOrder, debouncedSearchTerm, selectedDomain, selectedStatus, selectedDifficulty]);

  const fetchDomains = async () => {
    try {
      const response = await getEnvironments();
      setDomains((response.data || []).map(e => e.name));
    } catch (error) {
      console.error('Error fetching domains:', error);
    }
  };

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const params = { 
        sort_by: sortBy,
        sort_order: sortOrder,
        page: page,
        per_page: perPage
      };
      if (debouncedSearchTerm) params.search = debouncedSearchTerm;
      if (selectedDomain) params.domain = selectedDomain;
      if (selectedStatus) params.status = selectedStatus;
      if (selectedDifficulty) params.difficulty = selectedDifficulty;
      
      const response = await getTasks(params);
      setTasks(response.data.data || []);
      setTotal(response.data.total || 0);
      setTotalPages(response.data.total_pages || 0);
    } catch (error) {
      setTasks([]);
      setTotal(0);
      console.error('Error fetching tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return null;
    return sortOrder === 'desc' ? 
      <ChevronDownIcon className="h-4 w-4 ml-1" /> : 
      <ChevronUpIcon className="h-4 w-4 ml-1" />;
  };

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Tasks</h2>
        <span className="text-sm text-gray-500">
          Total: {total} tasks
        </span>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search tasks..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input pl-10 w-full"
              />
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <FunnelIcon className="h-5 w-5 text-gray-400" />
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="input"
            >
              <option value="">All Domains</option>
              {domains.map(domain => (
                <option key={domain} value={domain}>{domain.replace(/_/g, ' ')}</option>
              ))}
            </select>
            
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="input"
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="pending_review">Pending Review</option>
              <option value="in_expert_review">Expert Review</option>
              <option value="in_review">All In Review</option>
              <option value="rework">Rework</option>
              <option value="approved">Approved</option>
            </select>
            
            <select
              value={selectedDifficulty}
              onChange={(e) => setSelectedDifficulty(e.target.value)}
              className="input"
            >
              <option value="">All Difficulties</option>
              <option value="expert">Expert</option>
              <option value="hard">Hard</option>
              <option value="medium">Medium</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden flex-1 flex flex-col">
        <div className="overflow-x-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Task
                    </span>
                  </th>
                  <th className="px-4 py-3 text-left">
                    <button 
                      onClick={() => handleSort('status')}
                      className="flex items-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700"
                    >
                      Status
                      <SortIcon field="status" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left">
                    <button 
                      onClick={() => handleSort('difficulty')}
                      className="flex items-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700"
                    >
                      Difficulty
                      <SortIcon field="difficulty" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Domain
                    </span>
                  </th>
                  <th className="px-4 py-3 text-left">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Trainer
                    </span>
                  </th>
                  <th className="px-4 py-3 text-center">
                    <button 
                      onClick={() => handleSort('rework_count')}
                      className="flex items-center justify-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700 mx-auto"
                    >
                      Rework
                      <SortIcon field="rework_count" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left">
                    <button 
                      onClick={() => handleSort('created_at')}
                      className="flex items-center text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-700"
                    >
                      Created
                      <SortIcon field="created_at" />
                    </button>
                  </th>
                  <th className="px-4 py-3 text-center">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="max-w-xs">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {task.description || 'No description'}
                        </div>
                        <div className="text-xs text-gray-500 truncate">
                          {task.task_agent_id}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[task.status] || 'bg-gray-100 text-gray-800'}`}>
                        {STATUS_LABELS[task.status] || task.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${DIFFICULTY_COLORS[task.difficulty] || 'bg-gray-100 text-gray-800'}`}>
                        {task.difficulty || 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-600">
                        {task.domain?.replace(/_/g, ' ') || 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900">{task.trainer_name || 'Unknown'}</div>
                      <div className="text-xs text-gray-500">{task.trainer_email}</div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-sm font-medium ${task.rework_count > 0 ? 'text-red-600' : 'text-gray-500'}`}>
                        {task.rework_count}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-500">
                        {task.created_at ? new Date(task.created_at).toLocaleDateString() : 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => setSelectedTask(task)}
                        className="text-primary-600 hover:text-primary-800"
                      >
                        <EyeIcon className="h-5 w-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Show</span>
              <select
                value={perPage}
                onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}
                className="input text-sm py-1 px-2"
              >
                {perPageOptions.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
              <span className="text-sm text-gray-500">per page</span>
            </div>
            <div className="text-sm text-gray-500">
              Showing {((page - 1) * perPage) + 1} to {Math.min(page * perPage, total)} of {total} tasks
            </div>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn btn-secondary btn-sm"
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <span className="text-sm text-gray-700">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn btn-secondary btn-sm"
              >
                <ChevronRightIcon className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Task Detail Modal */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Task Details</h3>
                <button
                  onClick={() => setSelectedTask(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">Task ID</label>
                  <p className="text-sm text-gray-900 font-mono">{selectedTask.task_agent_id}</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-gray-500">Description</label>
                  <p className="text-sm text-gray-900">{selectedTask.description || 'No description'}</p>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-500">Status</label>
                    <p><span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[selectedTask.status]}`}>
                      {STATUS_LABELS[selectedTask.status] || selectedTask.status}
                    </span></p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Difficulty</label>
                    <p><span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${DIFFICULTY_COLORS[selectedTask.difficulty]}`}>
                      {selectedTask.difficulty || 'N/A'}
                    </span></p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-500">Domain</label>
                    <p className="text-sm text-gray-900">{selectedTask.domain?.replace(/_/g, ' ') || 'N/A'}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Interface</label>
                    <p className="text-sm text-gray-900">{selectedTask.interface_num || 'N/A'}</p>
                  </div>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-gray-500">Trainer</label>
                  <p className="text-sm text-gray-900">{selectedTask.trainer_name || 'Unknown'}</p>
                  <p className="text-xs text-gray-500">{selectedTask.trainer_email}</p>
                </div>
                
                <div>
                  <label className="text-sm font-medium text-gray-500">Batch</label>
                  <p className="text-sm text-gray-900">{selectedTask.batch_name || 'N/A'}</p>
                </div>
                
                {selectedTask.instruction_text && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Instruction</label>
                    <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded">{selectedTask.instruction_text}</p>
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-500">Created</label>
                    <p className="text-sm text-gray-900">
                      {selectedTask.created_at ? new Date(selectedTask.created_at).toLocaleString() : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Updated</label>
                    <p className="text-sm text-gray-900">
                      {selectedTask.updated_at ? new Date(selectedTask.updated_at).toLocaleString() : 'N/A'}
                    </p>
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

export default TasksView;

