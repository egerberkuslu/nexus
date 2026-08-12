import React from 'react';

const StatusBadge = ({ status, text, icon, pulse = false }) => (
  <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold border transition-all duration-300 ${status
    ? 'bg-emerald-100 text-emerald-700 border-emerald-300 shadow'
    : 'bg-red-100 text-red-700 border-red-300'
    }`}>
    <div className={`w-3 h-3 rounded-full ${status ? 'bg-emerald-500' : 'bg-red-500'} ${pulse ? 'animate-pulse' : ''}`}></div>
    {icon && <span>{icon}</span>}
    <span>{text}</span>
  </span>
);

export default StatusBadge;
