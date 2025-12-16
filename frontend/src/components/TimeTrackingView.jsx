import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';
import { 
  ClockIcon, 
  DocumentPlusIcon, 
  ArrowPathIcon, 
  CheckCircleIcon,
  UserGroupIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline';

const PER_PAGE_OPTIONS = [10, 25, 50, 100];

export default function TimeTrackingView() {
  const [weekOffset, setWeekOffset] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [perPage, setPerPage] = useState(25);
  
  // Cache for prefetched weeks: { "offset_page_perPage_search": data }
  const cacheRef = useRef({});

  // Generate cache key
  const getCacheKey = (offset, page, per, search) => 
    `${offset}_${page}_${per}_${search || ''}`;

  const fetchData = useCallback(async () => {
    const cacheKey = getCacheKey(weekOffset, currentPage, perPage, searchTerm);
    
    // Check cache first
    if (cacheRef.current[cacheKey]) {
      setData(cacheRef.current[cacheKey]);
      setLoading(false);
      setError(null);
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const params = {
        week_offset: weekOffset,
        page: currentPage,
        per_page: perPage,
      };
      if (searchTerm) {
        params.trainer_email = searchTerm;
      }
      const response = await api.get('/v2/time-tracking/weekly', { params });
      setData(response.data);
      
      // Store in cache
      cacheRef.current[cacheKey] = response.data;
      
      // Prefetch adjacent weeks (don't block UI)
      prefetchAdjacentWeeks(weekOffset, currentPage, perPage, searchTerm);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [weekOffset, searchTerm, currentPage, perPage]);

  // Prefetch previous and next weeks in background
  const prefetchAdjacentWeeks = async (offset, page, per, search) => {
    const adjacentOffsets = [offset - 1]; // Only prefetch previous week (can't go to future)
    if (offset < 0) adjacentOffsets.push(offset + 1); // Also prefetch next if not current
    
    for (const adjOffset of adjacentOffsets) {
      const adjKey = getCacheKey(adjOffset, page, per, search);
      if (!cacheRef.current[adjKey]) {
        try {
          const params = { week_offset: adjOffset, page, per_page: per };
          if (search) params.trainer_email = search;
          const response = await api.get('/v2/time-tracking/weekly', { params });
          cacheRef.current[adjKey] = response.data;
        } catch {
          // Silently fail prefetch
        }
      }
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Clear cache when search term changes (invalidate all cached data)
  useEffect(() => {
    cacheRef.current = {};
    setCurrentPage(1);
  }, [searchTerm]);

  // Reset page on week change (but keep cache)
  useEffect(() => {
    setCurrentPage(1);
  }, [weekOffset]);

  const formatHours = (hours, short = false) => {
    if (!hours || hours === 0) return '-';
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    if (short) {
      // Short format for table cells: "8h" or "8h 30m"
      if (m === 0) return `${h}h`;
      return `${h}h ${m}m`;
    }
    // Full format
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
  };

  const getHoursColor = (hours) => {
    if (!hours || hours === 0) return 'text-gray-400';
    if (hours >= 8) return 'text-green-600';
    if (hours >= 6) return 'text-yellow-600';
    if (hours >= 4) return 'text-orange-500';
    return 'text-red-500';
  };

  const getDates = () => {
    if (!data) return [];
    const dates = [];
    const start = new Date(data.start_date);
    for (let i = 0; i < 7; i++) {
      const date = new Date(start);
      date.setDate(start.getDate() + i);
      dates.push({
        key: date.toISOString().split('T')[0],
        label: date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
        dayName: date.toLocaleDateString('en-US', { weekday: 'short' }),
      });
    }
    return dates;
  };

  const formatWeekRange = () => {
    if (!data?.start_date || !data?.end_date) return '';
    const start = new Date(data.start_date);
    const end = new Date(data.end_date);
    const formatDate = (d) => `${d.getMonth() + 1}/${d.getDate()}/${d.getFullYear()}`;
    return `${formatDate(start)} - ${formatDate(end)}`;
  };

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-12 w-48"></div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card h-24 skeleton"></div>
          ))}
        </div>
        <div className="card">
          <div className="skeleton h-[400px]"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h2 className="text-3xl font-bold text-gray-900">Time Tracking</h2>
        <div className="card border-red-200 bg-red-50">
          <div className="p-4 text-red-700">
            <h3 className="font-semibold mb-2">Error Loading Data</h3>
            <p>{error}</p>
            <button
              onClick={fetchData}
              className="mt-3 px-4 py-2 bg-red-600 hover:bg-red-700 rounded text-white text-sm"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const dates = getDates();
  const totalPages = data?.total_pages || 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Time Tracking</h2>
          <p className="text-gray-500 text-sm mt-1">
            Jibble hours & task metrics for {formatWeekRange()}
          </p>
        </div>
      </div>

      {/* Summary Stats */}
      {data?.summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <ClockIcon className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <div className="text-sm text-gray-500">Total Hours</div>
                <div className="text-2xl font-bold text-gray-900">{formatHours(data.summary.total_hours)}</div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <DocumentPlusIcon className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <div className="text-sm text-gray-500">Tasks Created</div>
                <div className="text-2xl font-bold text-gray-900">{data.summary.total_tasks_created}</div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <ArrowPathIcon className="h-6 w-6 text-orange-600" />
              </div>
              <div>
                <div className="text-sm text-gray-500">Rework Completed</div>
                <div className="text-2xl font-bold text-gray-900">{data.summary.total_rework_completed}</div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <CheckCircleIcon className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <div className="text-sm text-gray-500">Tasks Reviewed</div>
                <div className="text-2xl font-bold text-gray-900">{data.summary.total_tasks_reviewed}</div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <CheckCircleIcon className="h-6 w-6 text-emerald-600" />
              </div>
              <div>
                <div className="text-sm text-gray-500">Tasks Approved</div>
                <div className="text-2xl font-bold text-gray-900">{data.summary.total_tasks_approved || 0}</div>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-cyan-100 rounded-lg">
                <UserGroupIcon className="h-6 w-6 text-cyan-600" />
              </div>
              <div>
                <div className="text-sm text-gray-500">Active Trainers</div>
                <div className="text-2xl font-bold text-gray-900">{data.summary.active_trainers}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="card">
        <div className="flex items-center gap-6 text-sm">
          <span className="text-gray-500 font-medium">Legend:</span>
          <span className="flex items-center gap-1">
            <ClockIcon className="h-4 w-4 text-blue-500" />
            <span className="text-gray-600">Hours</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-5 h-5 flex items-center justify-center bg-green-100 text-green-700 rounded text-xs font-bold">C</span>
            <span className="text-gray-600">Created</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-5 h-5 flex items-center justify-center bg-orange-100 text-orange-700 rounded text-xs font-bold">R</span>
            <span className="text-gray-600">Rework</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-5 h-5 flex items-center justify-center bg-purple-100 text-purple-700 rounded text-xs font-bold">V</span>
            <span className="text-gray-600">Reviewed</span>
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-4">
          {/* Week Navigation */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setWeekOffset(prev => prev - 1)}
              className="btn btn-secondary flex items-center gap-1"
            >
              <ChevronLeftIcon className="h-4 w-4" />
              Prev
            </button>
            <span className="px-4 py-2 bg-gray-100 rounded-lg text-gray-900 font-medium text-center whitespace-nowrap">
              {formatWeekRange()}
            </span>
            <button
              onClick={() => setWeekOffset(prev => Math.min(0, prev + 1))}
              disabled={weekOffset >= 0}
              className="btn btn-secondary flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRightIcon className="h-4 w-4" />
            </button>
            {weekOffset < 0 && (
              <button
                onClick={() => setWeekOffset(0)}
                className="btn btn-primary flex items-center gap-1"
              >
                Current Week
              </button>
            )}
          </div>

          {/* Search */}
          <div className="flex-1 max-w-md">
            <div className="relative">
              <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search by name, Turing email, or Jibble email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input pl-10 w-full"
              />
            </div>
          </div>

          {/* Per Page */}
          <div className="flex items-center gap-2">
            <span className="text-gray-500 text-sm">Show:</span>
            <select
              value={perPage}
              onChange={(e) => {
                setPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="input"
            >
              {PER_PAGE_OPTIONS.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>

          {loading && (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-600"></div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">
                  Name / Email
                </th>
                <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total
                </th>
                {dates.map(date => (
                  <th key={date.key} className="text-center px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[160px]">
                    <div>{date.label}</div>
                    <div className="flex justify-center items-center gap-2 mt-1 text-[10px] font-normal normal-case">
                      <ClockIcon className="h-3 w-3 text-blue-500" />
                      <span className="text-green-600">C</span>
                      <span className="text-orange-500">R</span>
                      <span className="text-purple-600">V</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data?.trainers?.map((trainer, idx) => (
                <tr key={trainer.turing_email || idx} className="hover:bg-gray-50">
                  <td className="px-4 py-3 sticky left-0 bg-white z-10">
                    <div className="font-medium text-gray-900">{trainer.person_name || 'Unknown'}</div>
                    <div className="text-gray-500 text-xs">{trainer.turing_email}</div>
                    <div className="flex gap-2 mt-1 text-xs">
                      {trainer.total_tasks_created > 0 && (
                        <span className="text-green-600">+{trainer.total_tasks_created} created</span>
                      )}
                      {trainer.total_rework_completed > 0 && (
                        <span className="text-orange-500">{trainer.total_rework_completed} rework</span>
                      )}
                      {trainer.total_tasks_reviewed > 0 && (
                        <span className="text-purple-600">{trainer.total_tasks_reviewed} reviewed</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center whitespace-nowrap">
                    <span className={`font-semibold text-sm ${getHoursColor(trainer.total_hours)}`}>
                      {formatHours(trainer.total_hours)}
                    </span>
                  </td>
                  {dates.map(date => {
                    const hours = trainer.daily_hours?.[date.key] || 0;
                    const created = trainer.daily_tasks_created?.[date.key] || 0;
                    const rework = trainer.daily_rework_completed?.[date.key] || 0;
                    const reviewed = trainer.daily_tasks_reviewed?.[date.key] || 0;
                    
                    return (
                      <td key={date.key} className="px-2 py-3 text-center">
                        <div className="flex justify-center items-center gap-2 text-xs">
                          <span className={`font-medium ${getHoursColor(hours)}`}>{formatHours(hours)}</span>
                          <span className={`w-5 text-center ${created > 0 ? 'text-green-600 font-medium' : 'text-gray-300'}`}>
                            {created || '-'}
                          </span>
                          <span className={`w-5 text-center ${rework > 0 ? 'text-orange-500 font-medium' : 'text-gray-300'}`}>
                            {rework || '-'}
                          </span>
                          <span className={`w-5 text-center ${reviewed > 0 ? 'text-purple-600 font-medium' : 'text-gray-300'}`}>
                            {reviewed || '-'}
                          </span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
              {(!data?.trainers || data.trainers.length === 0) && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                    No time tracking data found for this week.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="card">
          <div className="flex items-center justify-between">
            <div className="text-gray-500 text-sm">
              Showing {((currentPage - 1) * perPage) + 1} - {Math.min(currentPage * perPage, data.total)} of {data.total} trainers
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
                className="btn btn-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                First
              </button>
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="btn btn-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <span className="px-3 py-1 text-gray-700">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="btn btn-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRightIcon className="h-4 w-4" />
              </button>
              <button
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage === totalPages}
                className="btn btn-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Last
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
