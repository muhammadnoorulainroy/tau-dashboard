import React, { useState, useEffect } from 'react';
import { 
  getDashboardOverview, 
  getTimelineStats,
  getPRStateDistribution 
} from '../services/api';
import StatCard from './StatCard';
import ChartCard from './ChartCard';
import ActivityFeed from './ActivityFeed';
import { 
  UserGroupIcon, 
  DocumentTextIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#2ecc71', '#f39c12', '#e74c3c', '#f1c40f', '#3498db', '#9b59b6'];

const Dashboard = ({ lastUpdate }) => {
  const [overview, setOverview] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [stateDistribution, setStateDistribution] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [lastUpdate]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [overviewRes, timelineRes, stateRes] = await Promise.all([
        getDashboardOverview(),
        getTimelineStats(30),
        getPRStateDistribution()
      ]);

      setOverview(overviewRes.data);
      
      // Process timeline data for charts
      const timeline = timelineRes.data;
      const chartData = timeline.dates.map(date => ({
        date: date.substring(5), // Show only MM-DD
        created: timeline.data[date]?.created || 0,
        merged: timeline.data[date]?.merged || 0,
        rework: timeline.data[date]?.rework || 0
      }));
      setTimelineData(chartData);

      // Process state distribution for pie chart
      const distribution = stateRes.data.distribution;
      const pieData = Object.entries(distribution)
        .filter(([_, value]) => value > 0)
        .map(([key, value]) => ({
          name: key.replace(/_/g, ' ').toUpperCase(),
          value
        }));
      setStateDistribution(pieData);

    } catch (error) {
      // Error fetching dashboard data
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
            Live
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total PRs"
          value={overview?.total_prs || 0}
          icon={DocumentTextIcon}
          trend="+12%"
          trendUp={true}
          color="primary"
        />
        <StatCard
          title="Open PRs"
          value={overview?.open_prs || 0}
          icon={ClockIcon}
          trend={`${Math.round((overview?.open_prs / overview?.total_prs) * 100)}%`}
          color="warning"
        />
        <StatCard
          title="Merged PRs"
          value={overview?.merged_prs || 0}
          icon={CheckCircleIcon}
          trend={`${Math.round((overview?.merged_prs / overview?.total_prs) * 100)}%`}
          trendUp={true}
          color="success"
        />
        <StatCard
          title="Avg. Rework"
          value={overview?.average_rework?.toFixed(2) || '0'}
          icon={ArrowPathIcon}
          trend="-5%"
          trendUp={false}
          color="danger"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Developers"
          value={overview?.total_developers || 0}
          icon={UserGroupIcon}
          color="primary"
          small
        />
        <StatCard
          title="Reviewers"
          value={overview?.total_reviewers || 0}
          icon={UserGroupIcon}
          color="success"
          small
        />
        <StatCard
          title="Domains"
          value={overview?.total_domains || 0}
          icon={DocumentTextIcon}
          color="warning"
          small
        />
        <StatCard
          title="Active Tasks"
          value={overview?.open_prs || 0}
          icon={ExclamationTriangleIcon}
          color="danger"
          small
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ChartCard title="PR Activity Timeline">
            {timelineData && (
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
                    stroke="#f39c12" 
                    strokeWidth={2}
                    dot={{ fill: '#f39c12', r: 3 }}
                    activeDot={{ r: 5 }}
                    name="Created"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="merged" 
                    stroke="#2ecc71" 
                    strokeWidth={2}
                    dot={{ fill: '#2ecc71', r: 3 }}
                    activeDot={{ r: 5 }}
                    name="Merged"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="rework" 
                    stroke="#e74c3c" 
                    strokeWidth={2}
                    dot={{ fill: '#e74c3c', r: 3 }}
                    activeDot={{ r: 5 }}
                    name="Rework"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>

        <div>
          <ChartCard title="PR State Distribution">
            {stateDistribution && (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart margin={{ top: 5, right: 25, bottom: 5, left: 25 }}>
                  <Pie
                    data={stateDistribution}
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
                    {stateDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend 
                    verticalAlign="bottom" 
                    height={25}
                    iconSize={10}
                    wrapperStyle={{ fontSize: '12px', paddingTop: '5px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>
      </div>

      {/* Rework by Day Chart */}
      <ChartCard title="Daily PR Statistics">
        {timelineData && (
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
              <Bar dataKey="created" fill="#f39c12" name="Created" />
              <Bar dataKey="merged" fill="#2ecc71" name="Merged" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-3">
          <ActivityFeed activities={overview?.recent_activity || []} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;


