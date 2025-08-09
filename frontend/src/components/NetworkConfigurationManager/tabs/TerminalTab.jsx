// TerminalTab.jsx - Auto-updating with current status
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Terminal, Play, Trash2, Copy, Download, Monitor, RefreshCw } from 'lucide-react';
import { ConfigSection, ActionButton, EmptyState, SelectField } from '../components/FormComponents';

export const TerminalTab = ({
  topology,
  selectedNode,
  onNodeSelect,
  loading,
  setLoading,
  showMessage,
  apiCall
}) => {
  const [command, setCommand] = useState('');
  const [output, setOutput] = useState('');
  const [history, setHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [currentNode, setCurrentNode] = useState('');
  const [nodeStatus, setNodeStatus] = useState({});
  const outputRef = useRef(null);

  // Update current node when selectedNode changes or load from topology
  useEffect(() => {
    if (selectedNode && selectedNode.id !== currentNode) {
      setCurrentNode(selectedNode.id);
      fetchNodeStatus(selectedNode.id);
    } else if (!currentNode && topology?.nodes?.length > 0) {
      // Auto-select first executable node
      const executableNodes = topology.nodes.filter(n => n.type !== 'switch');
      if (executableNodes.length > 0) {
        setCurrentNode(executableNodes[0].id);
        fetchNodeStatus(executableNodes[0].id);
      }
    }
  }, [selectedNode, topology, currentNode]);

  // Auto-scroll to bottom when output changes
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  // Fetch node status when current node changes
  useEffect(() => {
    if (currentNode) {
      fetchNodeStatus(currentNode);
      
      // Auto-refresh node status every 10 seconds
      const interval = setInterval(() => {
        fetchNodeStatus(currentNode);
      }, 10000);
      
      return () => clearInterval(interval);
    }
  }, [currentNode]);

  const fetchNodeStatus = async (nodeId) => {
    if (!nodeId) return;
    
    try {
      // Get basic node info
      const currentNodeData = topology?.nodes?.find(n => n.id === nodeId);
      if (!currentNodeData) return;

      let status = {
        id: nodeId,
        type: currentNodeData.type,
        ip: currentNodeData.ip || 'Unknown',
        status: 'active'
      };

      // Get additional status for different node types
      if (currentNodeData.type === 'host' || currentNodeData.type === 'router') {
        try {
          // Get current IP and basic info
          const whoamiResult = await executeCommand('whoami', false);
          const uptimeResult = await executeCommand('uptime', false);
          const ifconfigResult = await executeCommand('ifconfig | head -10', false);
          
          status = {
            ...status,
            user: whoamiResult.success ? whoamiResult.result.trim() : 'unknown',
            uptime: uptimeResult.success ? uptimeResult.result.trim() : 'unknown',
            interfaces: ifconfigResult.success ? ifconfigResult.result : 'unknown'
          };
        } catch (error) {
          console.warn('Failed to get extended node status:', error);
        }
      }

      setNodeStatus(status);
    } catch (error) {
      console.error('Error fetching node status:', error);
    }
  };

  const executeCommand = useCallback(async (cmd = command, showInOutput = true) => {
    if (!currentNode || !cmd?.trim()) return { success: false, error: 'No command or node' };
    
    if (showInOutput) setLoading(true);
    
    try {
      const response = await apiCall(`/network/hosts/${currentNode}/cmd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd.trim() })
      });

      const timestamp = new Date().toLocaleTimeString();
      let resultText = '';
      let success = false;

      if (response.success && response.data) {
        if (response.data.success) {
          resultText = response.data.result || 'Command executed successfully';
          success = true;
        } else {
          resultText = response.data.error || 'Command failed';
          success = false;
        }
      } else {
        resultText = response.error || 'Failed to execute command';
        success = false;
      }

      if (showInOutput) {
        const entry = `[${timestamp}] ${currentNode}$ ${cmd}\n${resultText}\n\n`;
        setOutput(prev => prev + entry);
        
        // Add to history
        setHistory(prev => [...prev, cmd.trim()]);
        setHistoryIndex(-1);
        setCommand('');

        showMessage('Command executed', success ? 'success' : 'error');
      }

      return { success, result: resultText };
    } catch (err) {
      const timestamp = new Date().toLocaleTimeString();
      const errEntry = `[${timestamp}] ${currentNode}$ ${cmd}\nError: ${err.message}\n\n`;
      
      if (showInOutput) {
        setOutput(prev => prev + errEntry);
        showMessage(`Failed to execute: ${err.message}`, 'error');
      }
      
      return { success: false, error: err.message };
    } finally {
      if (showInOutput) setLoading(false);
    }
  }, [currentNode, command, apiCall, setLoading, showMessage]);

  const onKeyDown = useCallback(e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeCommand();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length && historyIndex < history.length - 1) {
        const idx = historyIndex + 1;
        setHistoryIndex(idx);
        setCommand(history[history.length - 1 - idx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const idx = historyIndex - 1;
        setHistoryIndex(idx);
        setCommand(history[history.length - 1 - idx]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCommand('');
      }
    }
  }, [history, historyIndex, executeCommand]);

  const clear = () => {
    setOutput('');
    showMessage('Terminal cleared', 'info');
  };

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(output);
      showMessage('Copied to clipboard', 'success');
    } catch {
      showMessage('Copy failed', 'error');
    }
  };

  const downloadOutput = () => {
    const blob = new Blob([output], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `terminal-${currentNode}-${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    showMessage('Export successful', 'success');
  };

  const executeQuickCommand = (cmd) => {
    setCommand(cmd);
    // Auto-execute after a short delay to show the command first
    setTimeout(() => {
      if (cmd.trim()) {
        executeCommand(cmd);
      }
    }, 100);
  };

  const handleNodeChange = (nodeId) => {
    setCurrentNode(nodeId);
    const node = topology?.nodes?.find(n => n.id === nodeId);
    if (node && onNodeSelect) {
      onNodeSelect(node);
    }
    fetchNodeStatus(nodeId);
    
    // Add a message about switching nodes
    const timestamp = new Date().toLocaleTimeString();
    setOutput(prev => prev + `[${timestamp}] Switched to node: ${nodeId}\n\n`);
  };

  // Get executable nodes (exclude switches as they have limited shell access)
  const executableNodes = topology?.nodes?.filter(n => n.type !== 'switch') || [];

  // Get welcome message based on current state
  const getWelcomeMessage = () => {
    if (!currentNode) {
      return "Welcome to the Network Terminal!\nSelect a node to start executing commands.";
    }
    
    const nodeInfo = nodeStatus.id ? `Connected to ${nodeStatus.id} (${nodeStatus.type})` : `Connected to ${currentNode}`;
    const statusInfo = nodeStatus.ip ? `IP: ${nodeStatus.ip}` : '';
    const userInfo = nodeStatus.user ? `User: ${nodeStatus.user}` : '';
    
    return `${nodeInfo}\n${statusInfo}\n${userInfo}\n\nType commands below or use the quick command buttons.\nUse ↑/↓ arrows to navigate command history.`;
  };

  if (!executableNodes.length) {
    return (
      <EmptyState
        icon={<Terminal className="w-8 h-8 text-gray-400" />}        
        title="No Executable Nodes"
        description="Add hosts, routers, or controllers to run commands."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Node Selection and Status */}
      <ConfigSection
        title="Node Selection & Status"
        icon={Monitor}
        expanded={true}
        actions={
          <ActionButton 
            onClick={() => fetchNodeStatus(currentNode)} 
            icon={<RefreshCw size={14} />} 
            title="Refresh Status" 
            size="sm"
            variant="secondary"
            loading={loading}
          />
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <SelectField
              label="Select Node"
              value={currentNode}
              onChange={handleNodeChange}
              options={executableNodes.map(node => ({
                value: node.id,
                label: `${node.id} (${node.type}) ${node.ip ? '- ' + node.ip : ''}`
              }))}
              placeholder="Choose a node..."
            />
          </div>
          
          {/* Current Node Status */}
          {nodeStatus.id && (
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-gray-600">Type:</span>
                  <span className="ml-2 font-medium">{nodeStatus.type}</span>
                </div>
                <div>
                  <span className="text-gray-600">IP:</span>
                  <span className="ml-2 font-mono text-sm">{nodeStatus.ip}</span>
                </div>
                {nodeStatus.user && (
                  <div>
                    <span className="text-gray-600">User:</span>
                    <span className="ml-2 font-mono text-sm">{nodeStatus.user}</span>
                  </div>
                )}
                {nodeStatus.uptime && (
                  <div className="col-span-2">
                    <span className="text-gray-600">Uptime:</span>
                    <span className="ml-2 text-xs">{nodeStatus.uptime}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Quick Node Selection Buttons */}
        <div className="flex flex-wrap gap-2 mt-3">
          {executableNodes.slice(0, 6).map(node => (
            <button
              key={node.id}
              onClick={() => handleNodeChange(node.id)}
              className={`px-3 py-1.5 text-xs border rounded-lg transition ${
                currentNode === node.id 
                  ? 'bg-blue-100 border-blue-300 text-blue-700'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              {node.id} ({node.type})
            </button>
          ))}
        </div>
      </ConfigSection>

      {currentNode && (
        <>
          {/* Terminal Input */}
          <ConfigSection
            title={`Terminal - ${currentNode}`}
            icon={Terminal}
            expanded={true}
            actions={
              <div className="flex space-x-2">
                <ActionButton onClick={clear} icon={<Trash2 size={14} />} title="Clear" />
                <ActionButton onClick={copyAll} icon={<Copy size={14} />} title="Copy" />
                <ActionButton onClick={downloadOutput} icon={<Download size={14} />} title="Export" />
              </div>
            }
          >
            <div className="space-y-4">
              <div className="flex space-x-2">
                <div className="flex-1 relative">
                  <span className="absolute left-3 top-2 text-sm text-gray-500 font-mono">
                    {currentNode}$
                  </span>
                  <input
                    type="text"
                    value={command}
                    onChange={e => setCommand(e.target.value)}
                    onKeyDown={onKeyDown}
                    placeholder="Enter command..."
                    disabled={loading}
                    className="w-full pl-20 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 font-mono text-sm"
                  />
                </div>
                <ActionButton
                  onClick={() => executeCommand()}
                  loading={loading}
                  icon={<Play size={16} />}
                  label="Execute"
                  variant="primary"
                  disabled={!command.trim()}
                />
              </div>

              {/* Quick Commands - Context-aware based on node type */}
              <div>
                <p className="text-xs text-gray-500 mb-2">Quick Commands:</p>
                <div className="flex flex-wrap gap-2">
                  {/* Common commands for all nodes */}
                  {[
                    { label: 'ifconfig', cmd: 'ifconfig', desc: 'Network interfaces' },
                    { label: 'ip addr', cmd: 'ip addr show', desc: 'IP addresses' },
                    { label: 'ps', cmd: 'ps aux | head -10', desc: 'Running processes' },
                    { label: 'uptime', cmd: 'uptime', desc: 'System uptime' }
                  ].map(q => (
                    <button
                      key={q.cmd}
                      onClick={() => executeQuickCommand(q.cmd)}
                      className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-100 transition"
                      title={q.desc}
                      disabled={loading}
                    >
                      {q.label}
                    </button>
                  ))}
                  
                  {/* Host/Router specific commands */}
                  {(nodeStatus.type === 'host' || nodeStatus.type === 'router') && [
                    { label: 'route', cmd: 'ip route show', desc: 'Routing table' },
                    { label: 'arp', cmd: 'arp -a', desc: 'ARP table' },
                    { label: 'ping gw', cmd: "ping -c 3 $(ip route | grep default | awk '{print $3}' | head -1)", desc: 'Ping gateway' },
                    { label: 'netstat', cmd: 'netstat -tuln', desc: 'Network connections' }
                  ].map(q => (
                    <button
                      key={q.cmd}
                      onClick={() => executeQuickCommand(q.cmd)}
                      className="px-3 py-1.5 text-xs border border-blue-200 bg-blue-50 rounded-lg hover:bg-blue-100 transition"
                      title={q.desc}
                      disabled={loading}
                    >
                      {q.label}
                    </button>
                  ))}

                  {/* Router specific commands */}
                  {nodeStatus.type === 'router' && [
                    { label: 'iptables', cmd: 'iptables -L -n', desc: 'Firewall rules' },
                    { label: 'ip forward', cmd: 'cat /proc/sys/net/ipv4/ip_forward', desc: 'IP forwarding status' }
                  ].map(q => (
                    <button
                      key={q.cmd}
                      onClick={() => executeQuickCommand(q.cmd)}
                      className="px-3 py-1.5 text-xs border border-green-200 bg-green-50 rounded-lg hover:bg-green-100 transition"
                      title={q.desc}
                      disabled={loading}
                    >
                      {q.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </ConfigSection>

          {/* Output Window */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow">
            <div className="flex justify-between items-center p-4 border-b border-gray-200">
              <div className="flex space-x-2">
                <span className="w-3 h-3 bg-red-400 rounded-full" />
                <span className="w-3 h-3 bg-yellow-400 rounded-full" />
                <span className="w-3 h-3 bg-green-400 rounded-full" />
              </div>
              <span className="text-xs text-gray-500 font-mono">
                {currentNode} Terminal {nodeStatus.ip && `(${nodeStatus.ip})`}
              </span>
            </div>
            <div
              ref={outputRef}
              className="h-80 overflow-y-auto font-mono text-sm text-gray-900 bg-gray-900 text-green-400 p-4"
            >
              {output ? (
                <pre className="whitespace-pre-wrap">{output}</pre>
              ) : (
                <div className="text-gray-500">
                  <pre className="whitespace-pre-wrap">{getWelcomeMessage()}</pre>
                </div>
              )}
            </div>
          </div>

          {/* Command History */}
          {history.length > 0 && (
            <ConfigSection title="Command History" icon={Terminal} expanded={false}>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {history.slice().reverse().map((cmd, i) => (
                  <button
                    key={i}
                    onClick={() => setCommand(cmd)}
                    className="w-full text-left px-3 py-2 text-sm font-mono border-b border-gray-100 hover:bg-gray-50 transition rounded"
                    title="Click to use this command"
                  >
                    <span className="text-gray-500">{currentNode}$</span> {cmd}
                  </button>
                ))}
              </div>
              <div className="mt-3 flex gap-2">
                <ActionButton
                  onClick={() => setHistory([])}
                  icon={<Trash2 size={14} />}
                  label="Clear History"
                  variant="secondary"
                  size="sm"
                />
                <ActionButton
                  onClick={() => {
                    const historyText = history.map(cmd => `${currentNode}$ ${cmd}`).join('\n');
                    navigator.clipboard.writeText(historyText).then(() => {
                      showMessage('History copied to clipboard', 'success');
                    }).catch(() => {
                      showMessage('Failed to copy history', 'error');
                    });
                  }}
                  icon={<Copy size={14} />}
                  label="Copy History"
                  variant="secondary"
                  size="sm"
                />
              </div>
            </ConfigSection>
          )}
        </>
      )}
    </div>
  );
};