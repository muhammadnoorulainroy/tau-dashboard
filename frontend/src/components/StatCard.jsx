import React from 'react';
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/outline';

const StatCard = ({ title, value, icon: Icon, trend, trendUp, color = 'primary', small = false }) => {
  const colorClasses = {
    primary: {
      bg: 'bg-blue-100',
      icon: 'text-blue-600'
    },
    success: {
      bg: 'bg-green-100',
      icon: 'text-green-600'
    },
    warning: {
      bg: 'bg-amber-100',
      icon: 'text-amber-600'
    },
    danger: {
      bg: 'bg-red-100',
      icon: 'text-red-600'
    },
  };

  return (
    <div className={`stat-card ${small ? 'p-4' : ''}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className={`${small ? 'text-2xl' : 'text-3xl'} font-bold text-gray-900 mt-1`}>
            {value}
          </p>
          {trend && (
            <div className="flex items-center mt-2">
              {trendUp ? (
                <ArrowUpIcon className="h-4 w-4 text-green-600 mr-1" />
              ) : (
                <ArrowDownIcon className="h-4 w-4 text-red-600 mr-1" />
              )}
              <span className={`text-sm font-medium ${trendUp ? 'text-green-600' : 'text-red-600'}`}>
                {trend}
              </span>
            </div>
          )}
        </div>
        {Icon && (
          <div className={`p-3 rounded-xl ${colorClasses[color].bg} shadow-sm`}>
            <Icon className={`h-7 w-7 ${colorClasses[color].icon}`} />
          </div>
        )}
      </div>
    </div>
  );
};

export default StatCard;


