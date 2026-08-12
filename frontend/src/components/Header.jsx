import React from 'react';
import { Wifi, Maximize2, Minimize2 } from 'lucide-react';
import StatusBadge from './StatusBadgeLegacy';

const Header = ({
  networkStatus,
  controllerStatus,
  refreshRate,
  setRefreshRate,
  isFullscreen,
  setIsFullscreen,
  extraActions
}) => {
  return (
    <header className="bg-gradient-to-r from-gray-50 to-gray-100 shadow-lg border-b border-gray-200 backdrop-blur-xl">
      <div className="max-w-[95%] mx-auto px-6 py-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <img
              src="../rsz_logo2.png"
              alt="Nexus Logo"
              className="w-24 object-contain"
              style={{
                mixBlendMode: 'multiply',
                aspectRatio: '4 / 3'
              }}
            />
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-800 to-gray-900 bg-clip-text text-transparent">
                Nexus
              </h1>
              <p className="text-gray-600 text-sm">
                Software-Defined Network Management & Real-time Monitoring
              </p>
            </div>
          </div>


          <div className="flex items-center gap-4">
            <StatusBadge
              status={networkStatus.running}
              text={networkStatus.running ? 'Network Online' : 'Network Offline'}
              icon="🌐"
              pulse={networkStatus.running}
            />
            <StatusBadge
              status={controllerStatus.running}
              text={controllerStatus.running ? 'Controller Active' : 'Controller Inactive'}
              icon="🤖"
              pulse={controllerStatus.running}
            />

            {/* Settings menu */}
            <div className="flex items-center gap-2">
              <select
                value={refreshRate}
                onChange={(e) => setRefreshRate(Number(e.target.value))}
                className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 text-sm focus:ring-2 focus:ring-indigo-500"
              >
                <option value={1000}>1s refresh</option>
                <option value={3000}>3s refresh</option>
                <option value={5000}>5s refresh</option>
                <option value={10000}>10s refresh</option>
              </select>

              <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
              >
                {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
              </button>
            </div>

            {/* Extra Actions */}
            {extraActions && (
              <div className="ml-4">
                {extraActions}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;