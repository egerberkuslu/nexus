import React from 'react';

export const TabNavigation = ({ currentTab, onTabChange, tabs }) => {
  return (
    <div className="bg-white border-b border-gray-200">
      <div className="px-6">
        <nav className="flex space-x-6">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`
                  flex items-center gap-2 px-1 py-3 border-b-2 font-medium text-sm transition-colors
                  ${isActive
                    ? 'border-blue-500 text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <Icon size={16} className={isActive ? 'text-gray-900' : 'text-gray-400'} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className={`
                    ml-2 px-2 py-0.5 text-xs rounded-full
                    ${isActive 
                      ? 'bg-blue-100 text-blue-600' 
                      : 'bg-gray-100 text-gray-600'
                    }
                  `}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
};