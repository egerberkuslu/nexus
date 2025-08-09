import React from 'react';
import { Download, Upload, RefreshCw } from 'lucide-react';

export const StatusBar = ({ networkStatus, controllerStatus, onExport, onImport, onRefresh }) => {
  return (
    <div className="flex items-center gap-3">
      {/* Status Indicators */}
      <div className="flex items-center gap-4 px-3 py-1.5 bg-gray-100 rounded-lg">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            networkStatus.running ? 'bg-green-500' : 'bg-gray-400'
          }`} />
          <span className="text-xs font-medium text-gray-600">Network</span>
        </div>
        <div className="w-px h-4 bg-gray-300" />
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            controllerStatus.running ? 'bg-blue-500' : 'bg-gray-400'
          }`} />
          <span className="text-xs font-medium text-gray-600">Controller</span>
        </div>
      </div>
      
      {/* Action Buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={onRefresh}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw size={16} />
        </button>
        <button
          onClick={onExport}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          title="Export Configuration"
        >
          <Download size={16} />
        </button>
        <label className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer" 
               title="Import Configuration">
          <Upload size={16} />
          <input 
            type="file" 
            accept=".json" 
            onChange={onImport} 
            className="hidden" 
          />
        </label>
      </div>
    </div>
  );
};