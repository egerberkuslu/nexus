import React from 'react';
import { X, CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';

export const MessageDisplay = ({ message, onClose }) => {
  if (!message) return null;

  const styles = {
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-800',
      icon: <CheckCircle className="w-5 h-5 text-green-600" />
    },
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      icon: <XCircle className="w-5 h-5 text-red-600" />
    },
    warning: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-800',
      icon: <AlertCircle className="w-5 h-5 text-yellow-600" />
    },
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      icon: <Info className="w-5 h-5 text-blue-600" />
    }
  };

  const style = styles[message.type] || styles.info;

  return (
    <div className={`mb-4 p-3 rounded-lg border ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {style.icon}
          <span className={`text-sm font-medium ${style.text}`}>{message.text}</span>
        </div>
        <button 
          onClick={onClose} 
          className={`${style.text} hover:opacity-70 transition-opacity`}
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};