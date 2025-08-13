import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Settings,
  XCircle,
  RefreshCw,
  Download,
  Upload,
  Activity,
  Monitor,
  Server,
  Router,
  Terminal
} from 'lucide-react';
import { TabNavigation } from './components/TabNavigation';
import { StatusBar } from './components/StatusBar';
import { MessageDisplay } from './components/MessageDisplay';
import { OverviewTab } from './tabs/OverviewTab';
import { HostConfigTab } from './tabs/HostConfigTab';
import { SwitchConfigTab } from './tabs/SwitchConfigTab';
import { RouterConfigTab } from './tabs/Router/RouterConfigTab';
import { ControllerConfigTab } from './tabs/ControllerConfigTab';
import { TerminalTab } from './tabs/TerminalTab';

const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'host', label: 'Host', icon: Monitor },
  { id: 'switch', label: 'Switch', icon: Server },
  { id: 'router', label: 'Router', icon: Router },
  { id: 'controller', label: 'Controller', icon: Settings },
  { id: 'terminal', label: 'Terminal', icon: Terminal }
];

const NetworkConfigurationManager = ({
  networkStatus = {},
  controllerStatus = {},
  topology = {},
  selectedNode: externalSelectedNode = null,
  activeTab: externalActiveTab = 'overview',
  apiCall,
  addLog,
  onNetworkChange,
  onClose,
  onNodeSelect: externalOnNodeSelect,
  onTabChange: externalOnTabChange,
  isModal = false,
  hideHeader = false
}) => {
  const [internalTab, setInternalTab] = useState(externalActiveTab);
  const [internalSelectedNode, setInternalSelectedNode] = useState(externalSelectedNode);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  // Config states
  const [hostConfig, setHostConfig] = useState({});
  const [switchConfig, setSwitchConfig] = useState({});
  const [routerConfig, setRouterConfig] = useState({});
  const [controllerConfig, setControllerConfig] = useState({});

  const showMessage = useCallback((text, type = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  }, []);

  const clearMessage = useCallback(() => setMessage(null), []);

  const handleTabChange = useCallback(tab => {
    setInternalTab(tab);
    externalOnTabChange?.(tab);
  }, [externalOnTabChange]);

  const handleNodeSelect = useCallback(node => {
    setInternalSelectedNode(node);
    externalOnNodeSelect?.(node);
    const map = { host: 'host', switch: 'switch', router: 'router', controller: 'controller' };
    if (map[node.type]) handleTabChange(map[node.type]);
  }, [externalOnNodeSelect, handleTabChange]);

  const handleExport = useCallback(() => {
    const data = JSON.stringify({ hostConfig, switchConfig, routerConfig, controllerConfig, selected: internalSelectedNode?.id }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showMessage('Exported configuration', 'success');
  }, [hostConfig, switchConfig, routerConfig, controllerConfig, internalSelectedNode, showMessage]);

  const handleImport = useCallback(e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = evt => {
      try {
        const cfg = JSON.parse(evt.target.result);
        setHostConfig(cfg.hostConfig || {});
        setSwitchConfig(cfg.switchConfig || {});
        setRouterConfig(cfg.routerConfig || {});
        setControllerConfig(cfg.controllerConfig || {});
        showMessage('Imported configuration', 'success');
      } catch (err) {
        showMessage('Import error: ' + err.message, 'error');
      }
    };
    reader.readAsText(file);
  }, [showMessage]);

  const handleRefresh = useCallback(() => {
    onNetworkChange?.();
    showMessage('Refreshing...', 'info');
  }, [onNetworkChange, showMessage]);

  useEffect(() => { if (externalActiveTab !== internalTab) setInternalTab(externalActiveTab); }, [externalActiveTab]);
  useEffect(() => { if (externalSelectedNode !== internalSelectedNode) setInternalSelectedNode(externalSelectedNode); }, [externalSelectedNode]);

  const renderContent = useMemo(() => {
    const common = { loading, setLoading, showMessage, apiCall, onNetworkChange };
    switch (internalTab) {
      case 'overview': return <OverviewTab topology={topology} selectedNode={internalSelectedNode} onNodeSelect={handleNodeSelect} {...common} />;
      case 'host': return <HostConfigTab selectedNode={internalSelectedNode} config={hostConfig} updateConfig={setHostConfig} {...common} />;
      case 'switch': return <SwitchConfigTab selectedNode={internalSelectedNode} config={switchConfig} updateConfig={setSwitchConfig} {...common} />;
      case 'router': return <RouterConfigTab selectedNode={internalSelectedNode} config={routerConfig} updateConfig={setRouterConfig} {...common} />;
      case 'controller': return <ControllerConfigTab config={controllerConfig} updateConfig={setControllerConfig} {...common} />;
      case 'terminal': return <TerminalTab topology={topology} selectedNode={internalSelectedNode} onNodeSelect={handleNodeSelect} {...common} />;
      default: return null;
    }
  }, [internalTab, topology, internalSelectedNode, hostConfig, switchConfig, routerConfig, controllerConfig, loading, apiCall, onNetworkChange, handleNodeSelect, showMessage]);

  // Modal Layout with proper scrolling
  const modalWrapper = (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col overflow-hidden border border-gray-200">
        {/* Fixed Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 text-gray-600" />
            <div>
              <h2 className="text-xl font-semibold text-gray-800">Network Configuration</h2>
              <p className="text-sm text-gray-500">Manage your SDN components</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <input type="file" id="import-config" accept="application/json" onChange={handleImport} className="hidden" />
            <label htmlFor="import-config" className="p-2 hover:bg-gray-100 rounded cursor-pointer transition-colors">
              <Upload className="w-5 h-5 text-gray-600" />
            </label>
            <button onClick={handleExport} className="p-2 hover:bg-gray-100 rounded transition-colors">
              <Download className="w-5 h-5 text-gray-600" />
            </button>
            <button onClick={handleRefresh} className="p-2 hover:bg-gray-100 rounded transition-colors">
              <RefreshCw className="w-5 h-5 text-gray-600" />
            </button>
            <button onClick={onClose} className="p-2 text-gray-600 hover:text-gray-800 rounded transition-colors">
              <XCircle className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Fixed Tabs */}
        <div className="flex-shrink-0 bg-white border-b border-gray-200">
          <TabNavigation currentTab={internalTab} onTabChange={handleTabChange} tabs={TABS} />
        </div>

        {/* Scrollable Content Area */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full overflow-y-auto bg-gray-50">
            <div className="p-6">
              <MessageDisplay message={message} onClose={clearMessage} />
              <div className="min-h-0">
                {renderContent}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Page Layout with proper scrolling
  const pageWrapper = (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {!hideHeader && (
        <div className="bg-white border-b border-gray-200 flex-shrink-0">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="w-6 h-6 text-gray-600" />
              <div>
                <h2 className="text-xl font-semibold text-gray-800">Network Configuration</h2>
                <p className="text-sm text-gray-500">Manage your SDN components</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <input type="file" id="import-config-page" accept="application/json" onChange={handleImport} className="hidden" />
              <label htmlFor="import-config-page" className="p-2 hover:bg-gray-100 rounded cursor-pointer transition-colors">
                <Upload className="w-5 h-5 text-gray-600" />
              </label>
              <button onClick={handleExport} className="p-2 hover:bg-gray-100 rounded transition-colors">
                <Download className="w-5 h-5 text-gray-600" />
              </button>
              <button onClick={handleRefresh} className="p-2 hover:bg-gray-100 rounded transition-colors">
                <RefreshCw className="w-5 h-5 text-gray-600" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fixed Tabs */}
      <div className="max-w-7xl mx-auto w-full bg-white border-b border-gray-200 flex-shrink-0">
        <TabNavigation currentTab={internalTab} onTabChange={handleTabChange} tabs={TABS} />
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto">
          <div className="max-w-7xl mx-auto p-6">
            <MessageDisplay message={message} onClose={clearMessage} />
            <div className="min-h-0">
              {renderContent}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return isModal ? modalWrapper : pageWrapper;
};

export default NetworkConfigurationManager;