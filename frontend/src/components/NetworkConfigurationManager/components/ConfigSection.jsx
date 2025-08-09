import React from 'react';
import { ChevronDown } from 'lucide-react';

const ConfigSection = ({ title, icon: Icon, children, expanded, onToggle, actions }) => (
  <div className="bg-white text-black rounded-xl border border-gray-200 mb-4 overflow-hidden">
    <div
      className="flex items-center justify-between p-4 bg-gray-50 cursor-pointer hover:bg-gray-100 transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-100 rounded-lg">
          <Icon className="text-blue-600" size={20} />
        </div>
        <h3 className="text-lg font-semibold text-black">{title}</h3>
      </div>
      <div className="flex items-center gap-2">
        {actions}
        <ChevronDown
          size={20}
          className={`text-black transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
        />
      </div>
    </div>
    {expanded && (
      <div className="p-4 border-t border-gray-100 bg-white">
        {children}
      </div>
    )}
  </div>
);

export default ConfigSection;
