import React from 'react';
import { TrendingUp } from 'lucide-react';

const MetricCard = ({ icon, label, value, trend, color = 'blue', subtitle }) => (
  <div className={`bg-white border border-gray-200 rounded-2xl p-6 shadow hover:shadow-lg transition-all duration-300 hover:scale-105`}>
    <div className="flex items-start justify-between">
      <div className="flex-1">
        <div className="flex items-center gap-3 mb-2">
          <div className={`p-2 bg-${color}-100 rounded-xl border border-${color}-200`}>
            {icon}
          </div>
          <div>
            <p className={`text-${color}-600 text-sm font-medium`}>{label}</p>
            {subtitle && <p className="text-gray-500 text-xs">{subtitle}</p>}
          </div>
        </div>
        <p className={`text-3xl font-bold text-gray-800 mb-1`}>{value}</p>
        {trend && (
          <div className={`flex items-center gap-1 text-xs ${trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-500'
            }`}>
            <TrendingUp className="w-3 h-3" />
            <span>{trend > 0 ? '+' : ''}{trend.toFixed(1)}%</span>
          </div>
        )}
      </div>
    </div>
  </div>
);

export default MetricCard;