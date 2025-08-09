import React from 'react';
import { ChevronDown, Plus, Trash2, AlertCircle } from 'lucide-react';

// Input Field Component
export const InputField = ({ 
  label, 
  value, 
  onChange, 
  placeholder, 
  type = 'text', 
  error, 
  helper, 
  icon: Icon,
  disabled = false 
}) => (
  <div className="space-y-1.5 text-black">
    {label && (
      <label className="block text-sm font-medium text-black">{label}</label>
    )}
    <div className="relative">
      {Icon && (
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon className="h-4 w-4 text-black" />
        </div>
      )}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={`
          w-full px-3 py-2 text-sm text-black placeholder-black
          border rounded-lg transition-colors bg-white
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          disabled:bg-gray-50 disabled:text-black disabled:cursor-not-allowed
          ${Icon ? 'pl-10' : ''}
          ${error ? 'border-red-300' : 'border-gray-300 hover:border-gray-400'}
        `}
      />
    </div>
    {helper && !error && (
      <p className="text-xs text-black">{helper}</p>
    )}
    {error && (
      <p className="text-xs text-red-600 flex items-center gap-1">
        <AlertCircle className="w-3 h-3" />
        {error}
      </p>
    )}
  </div>
);

// Select Field Component
export const SelectField = ({ 
  label, 
  value, 
  onChange, 
  options, 
  error, 
  helper, 
  icon: Icon,
  disabled = false 
}) => (
  <div className="space-y-1.5 text-black">
    {label && (
      <label className="block text-sm font-medium text-black">{label}</label>
    )}
    <div className="relative">
      {Icon && (
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon className="h-4 w-4 text-black" />
        </div>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`
          w-full px-3 py-2 text-sm text-black
          border rounded-lg transition-colors bg-white
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          disabled:bg-gray-50 disabled:text-black disabled:cursor-not-allowed
          appearance-none
          ${Icon ? 'pl-10' : ''}
          ${error ? 'border-red-300' : 'border-gray-300 hover:border-gray-400'}
        `}
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-black pointer-events-none" />
    </div>
    {helper && !error && (
      <p className="text-xs text-black">{helper}</p>
    )}
    {error && (
      <p className="text-xs text-red-600 flex items-center gap-1">
        <AlertCircle className="w-3 h-3" />
        {error}
      </p>
    )}
  </div>
);

// Checkbox Field Component
export const CheckboxField = ({ label, checked, onChange, helper, disabled = false }) => (
  <div className="space-y-1 text-black">
    <label className="flex items-center gap-3 cursor-pointer group">
      <div className="relative">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
          className="sr-only"
        />
        <div className={`
          w-4 h-4 rounded border-2 transition-colors flex items-center justify-center
          ${checked 
            ? 'bg-blue-500 border-blue-500' 
            : 'bg-white border-gray-300 group-hover:border-gray-400'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}>
          {checked && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      </div>
      <span className={`text-sm ${disabled ? 'text-black opacity-50' : 'text-black'}`}>{label}</span>
    </label>
    {helper && (
      <p className="text-xs text-black ml-7">{helper}</p>
    )}
  </div>
);

// Config Section Component
export const ConfigSection = ({ 
  title, 
  icon: Icon, 
  children, 
  expanded = true, 
  onToggle, 
  actions,
  className = '' 
}) => {
  return (
    <div className={`bg-white rounded-lg text-black border border-gray-200 ${className}`}>
      {onToggle ? (
        <button
          onClick={onToggle}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors text-black"
        >
          <div className="flex items-center gap-3">
            {Icon && (
              <div className="p-2 bg-gray-100 rounded-lg">
                <Icon size={16} className="text-black" />
              </div>
            )}
            <h3 className="text-sm font-semibold text-black">{title}</h3>
          </div>
          <div className="flex items-center gap-3">
            {actions}
            <ChevronDown className={`w-4 h-4 text-black transition-transform ${
              expanded ? 'rotate-180' : ''
            }`} />
          </div>
        </button>
      ) : (
        <div className="px-4 py-3 flex items-center justify-between text-black">
          <div className="flex items-center gap-3">
            {Icon && (
              <div className="p-2 bg-gray-100 rounded-lg">
                <Icon size={16} className="text-black" />
              </div>
            )}
            <h3 className="text-sm font-semibold text-black">{title}</h3>
          </div>
          {actions}
        </div>
      )}
      {expanded && (
        <div className="px-4 py-3 border-t border-gray-100 text-black">
          {children}
        </div>
      )}
    </div>
  );
};

// Empty State Component
export const EmptyState = ({ icon, title, description, action }) => (
  <div className="flex flex-col text-black items-center justify-center py-12 px-4">
    <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
      {icon}
    </div>
    <h3 className="text-base font-semibold text-black mb-1">{title}</h3>
    <p className="text-sm text-black text-center max-w-sm">{description}</p>
    {action && <div className="mt-4">{action}</div>}
  </div>
);

// Dynamic List Component
export const DynamicList = ({ items, onChange, placeholder, addLabel, itemComponent }) => {
  const handleAdd = () => onChange([...items, '']);
  const handleRemove = (index) => onChange(items.filter((_, i) => i !== index));
  const handleUpdate = (index, value) => {
    const newItems = [...items];
    newItems[index] = value;
    onChange(newItems);
  };

  return (
    <div className="space-y-2 text-black">
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-2 group">
          {itemComponent ? (
            itemComponent(item, index, handleUpdate)
          ) : (
            <input
              type="text"
              value={item}
              onChange={(e) => handleUpdate(index, e.target.value)}
              placeholder={placeholder}
              className="flex-1 px-3 py-2 text-sm text-black placeholder-black border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          )}
          <button
            onClick={() => handleRemove(index)}
            className="p-2 text-black hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
      <button
        onClick={handleAdd}
        className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-dashed border-gray-300 rounded-lg text-black hover:border-gray-400 hover:text-black hover:bg-gray-50 transition-colors text-sm"
      >
        <Plus size={16} />
        {addLabel}
      </button>
    </div>
  );
};

// Action Button Component
export const ActionButton = ({ 
  onClick, 
  loading, 
  icon, 
  label, 
  variant = 'primary', 
  size = 'md', 
  disabled = false,
  className = ''
}) => {
  const variants = {
    primary: 'bg-gray-900 hover:bg-gray-800 text-white',
    secondary: 'bg-white hover:bg-gray-50 text-black border border-gray-300',
    success: 'bg-green-600 hover:bg-green-700 text-white',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
    warning: 'bg-yellow-500 hover:bg-yellow-600 text-white'
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base'
  };

  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`
        inline-flex items-center gap-2 rounded-lg font-medium transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variants[variant]} ${sizes[size]} ${className}
      `}
    >
      {loading ? (
        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : icon}
      <span className="text-white">{label}</span>
    </button>
  );
};

// Status Badge Component
export const StatusBadge = ({ status, label }) => {
  const styles = {
    healthy: 'bg-green-100 text-black border-green-200',
    warning: 'bg-yellow-100 text-black border-yellow-200',
    error: 'bg-red-100 text-black border-red-200',
    info: 'bg-blue-100 text-black border-blue-200',
    neutral: 'bg-gray-100 text-black border-gray-200'
  };

  return (
    <span className={`
      inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border
      ${styles[status] || styles.neutral}
    `}>
      {label}
    </span>
  );
};
