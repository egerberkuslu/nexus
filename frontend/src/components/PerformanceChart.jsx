import React from 'react';
import { TrendingUp } from 'lucide-react';

const PerformanceChart = ({ metricsHistory }) => {
  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-3">
          <TrendingUp className="w-5 h-5 text-indigo-500" />
          Performance Trends
        </h2>
      </div>
      <div className="p-6">
        <div className="h-32 flex items-end gap-1 justify-between">
          {metricsHistory.slice(-10).map((metric, idx) => {
            const maxBandwidth = Math.max(...metricsHistory.map(m => m.bandwidth));
            const height = maxBandwidth > 0 ? (metric.bandwidth / maxBandwidth) * 100 : 0;

            return (
              <div key={idx} className="flex flex-col items-center gap-1">
                <div
                  className="w-4 bg-gradient-to-t from-indigo-500 to-indigo-300 rounded-t transition-all duration-300"
                  style={{ height: `${Math.max(height, 5)}%` }}
                ></div>
                <div className="text-[8px] text-gray-500 transform rotate-45 origin-bottom-left">
                  {new Date(metric.timestamp).toLocaleTimeString().split(':').slice(1).join(':')}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 text-xs text-gray-500 text-center">
          Bandwidth (Mbps) - Last 10 readings
        </div>
      </div>
    </div>
  );
};

export default PerformanceChart;