import React from 'react';
import { RefreshCw } from 'lucide-react';

const ActionButton = ({
  onClick,
  disabled,
  icon,
  label,
  color,
  size = 'md',
  variant = 'solid',
  loading = false
}) => {
  const colorClasses = {
    indigo: 'bg-indigo-500 hover:bg-indigo-600 text-white border-indigo-500',
    green: 'bg-emerald-500 hover:bg-emerald-600 text-white border-emerald-500',
    red: 'bg-red-500 hover:bg-red-600 text-white border-red-500',
    purple: 'bg-purple-500 hover:bg-purple-600 text-white border-purple-500',
    blue: 'bg-blue-500 hover:bg-blue-600 text-white border-blue-500',
    success: 'bg-emerald-500 hover:bg-emerald-600 text-white border-emerald-500',
    danger: 'bg-red-500 hover:bg-red-600 text-white border-red-500',
    pastelIndigo: 'bg-indigo-100 hover:bg-indigo-200 text-indigo-700 border-indigo-200',
  };

  const outlineClasses = {
    indigo: 'border-indigo-500 text-indigo-600 hover:bg-indigo-50',
    green: 'border-emerald-500 text-emerald-600 hover:bg-emerald-50',
    red: 'border-red-500 text-red-600 hover:bg-red-50',
    purple: 'border-purple-500 text-purple-600 hover:bg-purple-50',
    blue: 'border-blue-500 text-blue-600 hover:bg-blue-50',
  };

  const sizeClasses = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-6 py-3 text-sm',
    lg: 'px-8 py-4 text-base'
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center border font-semibold rounded-xl shadow focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white transition-all duration-200 hover:shadow-md hover:scale-105 ${variant === 'outline' ? outlineClasses[color] : colorClasses[color]
        } ${sizeClasses[size]} ${disabled || loading ? 'opacity-50 cursor-not-allowed hover:scale-100' : ''}`}
    >
      {(loading && !disabled) ? (
        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
      ) : (
        icon && <span className="mr-2">{icon}</span>
      )}
      {label}
    </button>
  );
};

export default ActionButton;