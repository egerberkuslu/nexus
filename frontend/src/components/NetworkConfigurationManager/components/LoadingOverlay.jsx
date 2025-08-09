// components/LoadingOverlay.jsx
import React from 'react';

const LoadingOverlay = ({ loading }) => {
  if (!loading) return null;

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-8 flex items-center gap-4 shadow-2xl border border-white/50">
        <div className="relative">
          <div className="w-8 h-8 border-4 border-blue-200 rounded-full animate-spin"></div>
          <div className="absolute inset-0 w-8 h-8 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
        </div>
        <span className="text-slate-700 font-semibold text-lg">Processing Configuration...</span>
      </div>
    </div>
  );
};

export default LoadingOverlay;