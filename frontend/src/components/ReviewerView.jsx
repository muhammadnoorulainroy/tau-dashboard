import React, { useState, useEffect } from 'react';
import { getReviewerMetrics } from '../services/api';
import { 
  ClipboardDocumentCheckIcon,
  CheckIcon,
  XMarkIcon,
  ChevronUpIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';

const ReviewerView = ({ lastUpdate }) => {
  const [reviewers, setReviewers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('total_reviews');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    fetchReviewers();
  }, [lastUpdate, sortBy]);

  const fetchReviewers = async () => {
    setLoading(true);
    try {
      const response = await getReviewerMetrics({ sort_by: sortBy });
      setReviewers(response.data.data);  // Updated: response.data.data
      setTotal(response.data.total);     // New: get total count
    } catch (error) {
      console.error('Error fetching reviewers:', error);
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
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Reviewers</h2>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            Total: {total} reviewers
          </span>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reviewer
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('total_reviews')}
                >
                  <div className="flex items-center justify-center">
                    Total Reviews
                    {sortBy === 'total_reviews' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('approved_reviews')}
                >
                  <div className="flex items-center justify-center">
                    Approved
                    {sortBy === 'approved_reviews' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('changes_requested')}
                >
                  <div className="flex items-center justify-center">
                    Changes Requested
                    {sortBy === 'changes_requested' && (
                      sortOrder === 'desc' ? <ChevronDownIcon className="h-4 w-4 ml-1" /> : <ChevronUpIcon className="h-4 w-4 ml-1" />
                    )}
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Approval Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Domains
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Recent Activity
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {reviewers.map((reviewer) => {
                const approvalRate = reviewer.total_reviews > 0 
                  ? ((reviewer.approved_reviews / reviewer.total_reviews) * 100).toFixed(1) 
                  : 0;
                
                return (
                  <tr key={reviewer.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-success-400 to-success-600 flex items-center justify-center text-white">
                            <ClipboardDocumentCheckIcon className="h-6 w-6" />
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">
                            {reviewer.username}
                          </div>
                          <div className="text-sm text-gray-500">
                            Reviewer
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="text-lg font-semibold text-gray-900">{reviewer.total_reviews}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-100 text-success-800">
                        <CheckIcon className="h-3 w-3 mr-1" />
                        {reviewer.approved_reviews}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
                        <XMarkIcon className="h-3 w-3 mr-1" />
                        {reviewer.changes_requested}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-[100px]">
                          <div 
                            className={`h-2 rounded-full ${
                              approvalRate > 70 ? 'bg-success-500' : 
                              approvalRate > 40 ? 'bg-warning-500' : 'bg-danger-500'
                            }`}
                            style={{ width: `${approvalRate}%` }}
                          ></div>
                        </div>
                        <span className="text-xs font-medium text-gray-700 ml-2">{approvalRate}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {reviewer.metrics?.domains && Object.keys(reviewer.metrics.domains).slice(0, 3).map(domain => (
                          <span key={domain} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                            {domain} ({reviewer.metrics.domains[domain]})
                          </span>
                        ))}
                        {reviewer.metrics?.domains && Object.keys(reviewer.metrics.domains).length > 3 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
                            +{Object.keys(reviewer.metrics.domains).length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {reviewer.metrics?.recent_reviews && reviewer.metrics.recent_reviews.length > 0 ? (
                        <div className="text-xs">
                          <div className="text-gray-900 truncate max-w-xs">
                            {reviewer.metrics.recent_reviews[0].pr_title}
                          </div>
                          <div className={`mt-1 ${
                            reviewer.metrics.recent_reviews[0].state === 'APPROVED' ? 'text-success-600' : 'text-warning-600'
                          }`}>
                            {reviewer.metrics.recent_reviews[0].state}
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-500">No recent activity</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ReviewerView;


