import React, { useState, useEffect } from 'react';
import { 
  getDashboardOverview, 
  getTimelineStats,
  getStatusBreakdown 
} from '../services/api';
import StatCard from './StatCard';
import ChartCard from './ChartCard';
import { 
  UserGroupIcon, 
  DocumentTextIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  FolderIcon,
  ArchiveBoxIcon
} from '@heroicons/react/24/outline';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

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

const Dashboard = ({ lastUpdate }) => {
  const [overview, setOverview] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [statusBreakdown, setStatusBreakdown] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [lastUpdate]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [overviewRes, timelineRes, statusRes] = await Promise.all([
        getDashboardOverview(),
        getTimelineStats(30),
        getStatusBreakdown()
      ]);

      setOverview(overviewRes.data);
      
      // Process timeline data for charts
      const timeline = timelineRes.data;
      const chartData = timeline.map(item => ({
        date: item.date.substring(5), // Show only MM-DD
        created: item.created || 0,
        approved: item.approved || 0,
        rework: item.rework || 0
      }));
      setTimelineData(chartData);

      // Process status breakdown for pie chart
      if (statusRes.data && statusRes.data[0]) {
        const breakdown = statusRes.data[0].breakdown;
        const pieData = Object.entries(breakdown)
          .filter(([_, value]) => value > 0)
          .map(([key, value]) => ({
            name: STATUS_LABELS[key] || key.replace(/_/g, ' ').toUpperCase(),
            value,
            color: STATUS_COLORS[key] || '#6b7280'
          }));
        setStatusBreakdown(pieData);
      }

    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="card h-32 skeleton"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold text-gray-900">Dashboard Overview</h2>
        <div className="flex items-center space-x-2">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-success-100 text-success-800">
            <span className="w-2 h-2 mr-1.5 bg-success-400 rounded-full animate-pulse"></span>
            Task Agent API
          </span>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Tasks"
          value={overview?.total_tasks || 0}
          icon={DocumentTextIcon}
          color="primary"
        />
        <StatCard
          title="In Review"
          value={overview?.in_review_count || 0}
          icon={ClockIcon}
          trend={overview?.total_tasks > 0 ? `${Math.round((overview?.in_review_count / overview?.total_tasks) * 100)}%` : '0%'}
          color="warning"
        />
        <StatCard
          title="Approved"
          value={overview?.approved_count || 0}
          icon={CheckCircleIcon}
          trend={overview?.total_tasks > 0 ? `${Math.round((overview?.approved_count / overview?.total_tasks) * 100)}%` : '0%'}
          trendUp={true}
          color="success"
        />
        <StatCard
          title="Rework"
          value={overview?.rework_count || 0}
          icon={ArrowPathIcon}
          trend={overview?.total_tasks > 0 ? `${Math.round((overview?.rework_count / overview?.total_tasks) * 100)}%` : '0%'}
          color="danger"
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Trainers"
          value={overview?.total_trainers || 0}
          icon={UserGroupIcon}
          color="primary"
          small
        />
        <StatCard
          title="Domains"
          value={overview?.total_domains || 0}
          icon={FolderIcon}
          color="success"
          small
        />
        <StatCard
          title="Batches"
          value={overview?.total_batches || 0}
          icon={ArchiveBoxIcon}
          color="warning"
          small
        />
        <StatCard
          title="Approval Rate"
          value={`${((overview?.approval_rate || 0) * 100).toFixed(1)}%`}
          icon={CheckCircleIcon}
          color="success"
          small
        />
      </div>

      {/* Status Breakdown Cards */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Status Breakdown</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
          <div className="text-center p-3 rounded-lg bg-gray-50">
            <p className="text-2xl font-bold text-gray-500">{overview?.draft_count || 0}</p>
            <p className="text-xs text-gray-600">Draft</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-amber-50">
            <p className="text-2xl font-bold text-amber-600">{overview?.pending_review_count || 0}</p>
            <p className="text-xs text-gray-600">Pending Review</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-orange-50">
            <p className="text-2xl font-bold text-orange-600">{overview?.in_expert_review_count || 0}</p>
            <p className="text-xs text-gray-600">Expert Review</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-violet-50">
            <p className="text-2xl font-bold text-violet-600">{overview?.pending_calibrator_review_count || 0}</p>
            <p className="text-xs text-gray-600">Pending Calibrator</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-indigo-50">
            <p className="text-2xl font-bold text-indigo-600">{overview?.in_calibrator_review_count || 0}</p>
            <p className="text-xs text-gray-600">Calibrator Review</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-blue-50">
            <p className="text-2xl font-bold text-blue-600">{overview?.in_pod_lead_review_count || 0}</p>
            <p className="text-xs text-gray-600">Pod Lead Review</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-red-50">
            <p className="text-2xl font-bold text-red-600">{overview?.rework_count || 0}</p>
            <p className="text-xs text-gray-600">Rework</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-green-50">
            <p className="text-2xl font-bold text-green-600">{overview?.approved_count || 0}</p>
            <p className="text-xs text-gray-600">Approved</p>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChartCard title="Task Activity Timeline">
            {timelineData && timelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={timelineData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                  <YAxis stroke="#6b7280" fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb' }}
                    labelStyle={{ color: '#111827', fontWeight: 600 }}
                  />
                  <Legend />
                  <Line 
                    type="monotone" 
                    dataKey="created" 
                    stroke="#f59e0b" 
                    strokeWidth={2}
                    dot={{ fill: '#f59e0b', r: 3 }}
                    activeDot={{ r: 5 }}
                    name="Created"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="approved" 
                    stroke="#22c55e" 
                    strokeWidth={2}
                    dot={{ fill: '#22c55e', r: 3 }}
                    activeDot={{ r: 5 }}
                    name="Approved"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="rework" 
                    stroke="#ef4444" 
                    strokeWidth={2}
                    dot={{ fill: '#ef4444', r: 3 }}
                    activeDot={{ r: 5 }}
                    name="Rework"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-gray-500">
                No timeline data available
              </div>
            )}
          </ChartCard>
        </div>

        <div>
          <ChartCard title="Task Status Distribution">
            {statusBreakdown && statusBreakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart margin={{ top: 5, right: 25, bottom: 5, left: 25 }}>
                  <Pie
                    data={statusBreakdown}
                    cx="50%"
                    cy="42%"
                    labelLine={{
                      stroke: '#9ca3af',
                      strokeWidth: 1
                    }}
                    label={({ name, value, cx, cy, midAngle, innerRadius, outerRadius }) => {
                      const RADIAN = Math.PI / 180;
                      const radius = outerRadius + 25;
                      const x = cx + radius * Math.cos(-midAngle * RADIAN);
                      const y = cy + radius * Math.sin(-midAngle * RADIAN);
                      
                      return (
                        <text 
                          x={x} 
                          y={y} 
                          fill="#374151" 
                          textAnchor={x > cx ? 'start' : 'end'} 
                          dominantBaseline="central"
                          fontSize={12}
                          fontWeight={600}
                        >
                          {value}
                        </text>
                      );
                    }}
                    outerRadius={70}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {statusBreakdown.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend 
                    verticalAlign="bottom" 
                    height={25}
                    iconSize={10}
                    wrapperStyle={{ fontSize: '11px', paddingTop: '5px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-gray-500">
                No status data available
              </div>
            )}
          </ChartCard>
        </div>
      </div>

      {/* Daily Task Statistics */}
      <ChartCard title="Daily Task Statistics">
        {timelineData && timelineData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
              <YAxis stroke="#6b7280" fontSize={12} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb' }}
                labelStyle={{ color: '#111827', fontWeight: 600 }}
              />
              <Legend />
              <Bar dataKey="created" fill="#f59e0b" name="Created" />
              <Bar dataKey="approved" fill="#22c55e" name="Approved" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[250px] flex items-center justify-center text-gray-500">
            No timeline data available
          </div>
        )}
      </ChartCard>

      {/* Sync Info */}
      {overview?.last_sync_time && (
        <div className="text-center text-sm text-gray-500">
          Last synced: {new Date(overview.last_sync_time).toLocaleString()}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
