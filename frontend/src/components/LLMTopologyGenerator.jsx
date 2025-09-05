import React, { useState, useCallback } from 'react';
import { 
  Brain, 
  Send, 
  Loader2, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Copy,
  Download,
  RefreshCw,
  Sparkles,
  Network,
  Settings,
  Eye,
  EyeOff,
  RotateCcw,
  Monitor,
  Link as LinkIcon
} from 'lucide-react';

const LLMTopologyGenerator = ({ 
  isOpen, 
  onClose, 
  onGenerateTopology,
  onLoadGeneratedTopology 
}) => {
  const [description, setDescription] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedTopology, setGeneratedTopology] = useState(null);
  const [error, setError] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [generationHistory, setGenerationHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Example prompts for quick start
  const examplePrompts = [
    {
      title: "Ryu Controller Network",
      description: "Create a star topology with Ryu controller managing switches.",
      prompt: "Create a star topology with a central switch connected to 4 hosts. Use Ryu controller to manage the switch. Each host should have a unique IP address in the 10.0.0.x range."
    },
    {
      title: "POX Controller Network",
      description: "Build a linear network with POX controller.",
      prompt: "Build a linear network with 3 switches connected in a line and 2 hosts at each end. Use POX controller to manage the switches. Hosts should have IPs 10.0.1.10 and 10.0.2.10."
    },
    {
      title: "OpenDaylight Network",
      description: "Create a mesh network with OpenDaylight controller.",
      prompt: "Create a fully connected mesh of 4 switches with hosts attached to each switch. Use OpenDaylight controller to manage all switches. Use realistic IP addresses."
    },
    {
      title: "OsKen Controller Network",
      description: "Design a router network with OsKen controller.",
      prompt: "Design a network with a router connecting two subnets. Each subnet has a switch with 2 hosts. Use OsKen controller. Router IP is 10.0.0.1, subnet 1 hosts are 10.0.1.x, subnet 2 hosts are 10.0.2.x."
    }
  ];

  const generateTopology = useCallback(async () => {
    if (!description.trim()) {
      setError('Please enter a network description');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setGeneratedTopology(null);

    try {
      console.log('Sending LLM request:', { description: description.trim() });
      
      const response = await fetch('http://localhost:5000/api/llm/generate-topology', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          description: description.trim(),
          parameters: {}
        }),
      });

      console.log('LLM API response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('LLM API error response:', errorText);
        setError(`Server error (${response.status}): ${errorText}`);
        return;
      }

      const result = await response.json();
      console.log('LLM API result:', result);

      if (result.success) {
        setGeneratedTopology(result);
        
        // Add to history
        const historyItem = {
          id: Date.now(),
          description: description.trim(),
          timestamp: new Date().toISOString(),
          success: true,
          topology: result.topology_config
        };
        setGenerationHistory(prev => [historyItem, ...prev.slice(0, 9)]); // Keep last 10
        
        // Auto-show preview
        setShowPreview(true);
      } else {
        console.error('LLM generation failed:', result);
        setError(result.error || 'Failed to generate topology');
      }
    } catch (err) {
      console.error('LLM request error:', err);
      setError(`Network error: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  }, [description]);

  const loadGeneratedTopology = useCallback(() => {
    if (generatedTopology && generatedTopology.topology_config) {
      onLoadGeneratedTopology(generatedTopology.topology_config);
      onClose();
    }
  }, [generatedTopology, onLoadGeneratedTopology, onClose]);

  const handleExamplePrompt = useCallback((prompt) => {
    setDescription(prompt);
    setError(null);
  }, []);

  const copyToClipboard = useCallback((text) => {
    navigator.clipboard.writeText(text);
  }, []);

  const exportTopology = useCallback(() => {
    if (generatedTopology && generatedTopology.topology_config) {
      const blob = new Blob([JSON.stringify(generatedTopology.topology_config, null, 2)], { 
        type: 'application/json' 
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `llm-generated-topology-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [generatedTopology]);

  const clearGeneration = useCallback(() => {
    setDescription('');
    setGeneratedTopology(null);
    setError(null);
    setShowPreview(false);
  }, []);

  const loadFromHistory = useCallback((historyItem) => {
    setDescription(historyItem.description);
    setGeneratedTopology({
      success: true,
      topology_config: historyItem.topology
    });
    setError(null);
    setShowPreview(true);
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
              <Brain className="w-7 h-7 text-purple-500" />
              AI Topology Generator
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
                title="Generation History"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
                title="Toggle Preview"
              >
                {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 transition-colors"
          >
            <XCircle className="w-6 h-6" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Left Panel - Input */}
          <div className="w-2/3 border-r border-gray-200 p-6 flex flex-col">
            <div className="mb-6 flex-1 flex flex-col">
              <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-500" />
                Describe Your Network
              </h3>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the network topology you want to create. Be specific about nodes, connections, IP addresses, and any special requirements..."
                className="w-full flex-1 min-h-48 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
              />
              <div className="flex justify-between items-center mt-2">
                <span className="text-sm text-gray-500">
                  {description.length} characters
                </span>
                <button
                  onClick={() => copyToClipboard(description)}
                  className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                >
                  <Copy className="w-3 h-3" />
                  Copy
                </button>
              </div>
            </div>

            {/* Example Prompts - Smaller Section */}
            <div className="mb-4">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Quick Examples</h4>
              <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto">
                {examplePrompts.map((example, index) => (
                  <div
                    key={index}
                    className="p-2 bg-gray-50 rounded-lg border border-gray-200 hover:border-purple-300 transition-colors cursor-pointer"
                    onClick={() => handleExamplePrompt(example.prompt)}
                  >
                    <div className="font-medium text-xs text-gray-800 mb-1">
                      {example.title}
                    </div>
                    <div className="text-xs text-gray-600 line-clamp-2">
                      {example.description}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Generation History */}
            {showHistory && generationHistory.length > 0 && (
              <div className="mb-6">
                <h4 className="text-md font-medium text-gray-700 mb-3">Recent Generations</h4>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {generationHistory.map((item) => (
                    <div
                      key={item.id}
                      className="p-2 bg-gray-50 rounded border border-gray-200 hover:border-purple-300 transition-colors cursor-pointer"
                      onClick={() => loadFromHistory(item)}
                    >
                      <div className="text-xs text-gray-600 mb-1">
                        {new Date(item.timestamp).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-800 truncate">
                        {item.description}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Generate Button */}
            <div className="mt-auto space-y-2">
              <button
                onClick={generateTopology}
                disabled={!description.trim() || isGenerating}
                className="w-full bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    Generate Topology
                  </>
                )}
              </button>
              
              {/* Test API Button */}
              <button
                onClick={async () => {
                  try {
                    const response = await fetch('http://localhost:5000/api/llm/status');
                    const result = await response.json();
                    console.log('LLM API Status:', result);
                    alert(`LLM API Status: ${response.ok ? 'OK' : 'Error'}\nResponse: ${JSON.stringify(result, null, 2)}`);
                  } catch (err) {
                    console.error('LLM API test failed:', err);
                    alert(`LLM API Test Failed: ${err.message}`);
                  }
                }}
                className="w-full bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600 transition-colors text-sm"
              >
                Test API Connection
              </button>
            </div>
          </div>

          {/* Right Panel - Results */}
          <div className="w-1/3 p-4 flex flex-col bg-gradient-to-br from-slate-50 to-blue-50">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                <div className="p-1.5 bg-blue-100 rounded-lg">
                  <Network className="w-5 h-5 text-blue-600" />
                </div>
                Generated Topology
              </h3>
              {generatedTopology && generatedTopology.success && (
                <div className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                  <CheckCircle className="w-3 h-3" />
                  Success
                </div>
              )}
            </div>

            {error && (
              <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-400 rounded-r-xl shadow-sm animate-pulse">
                <div className="flex items-start gap-3">
                  <XCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-semibold text-red-800 mb-1">Generation Failed</div>
                    <p className="text-sm text-red-700 leading-relaxed">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {generatedTopology && generatedTopology.success ? (
              <div className="flex-1 flex flex-col space-y-6">
                {/* Success Stats */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-white rounded-lg p-3 shadow-sm border border-gray-100">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-blue-100 rounded">
                        <Monitor className="w-4 h-4 text-blue-600" />
                      </div>
                      <div>
                        <div className="text-lg font-bold text-gray-800">
                          {generatedTopology.topology_config?.topology?.nodes?.length || 0}
                        </div>
                        <div className="text-xs text-gray-600">Nodes</div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-white rounded-lg p-3 shadow-sm border border-gray-100">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-green-100 rounded">
                        <LinkIcon className="w-4 h-4 text-green-600" />
                      </div>
                      <div>
                        <div className="text-lg font-bold text-gray-800">
                          {generatedTopology.topology_config?.topology?.links?.length || 0}
                        </div>
                        <div className="text-xs text-gray-600">Links</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Preview Toggle */}
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-gray-800">Preview</h4>
                  <button
                    onClick={() => setShowPreview(!showPreview)}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-white border border-gray-200 rounded hover:bg-gray-50 transition-colors"
                  >
                    {showPreview ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showPreview ? 'Hide' : 'Show'}
                  </button>
                </div>

                {/* Preview Content */}
                {showPreview && generatedTopology.topology_config && (
                  <div className="flex-1 bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <div className="h-full overflow-auto p-3">
                      <div className="space-y-3">
                        {/* Nodes Section */}
                        <div>
                          <div className="flex items-center gap-1 mb-2">
                            <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                            <h5 className="text-xs font-semibold text-gray-800">Nodes</h5>
                          </div>
                          <div className="space-y-1">
                            {generatedTopology.topology_config.topology?.nodes?.map((node, index) => (
                              <div key={index} className="p-2 bg-gray-50 rounded border border-gray-100">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${
                                      node.type === 'host' ? 'bg-indigo-500' :
                                      node.type === 'switch' ? 'bg-blue-500' :
                                      node.type === 'router' ? 'bg-emerald-500' :
                                      'bg-red-500'
                                    }`}></div>
                                    <div>
                                      <div className="font-mono text-xs font-semibold text-gray-800">{node.id}</div>
                                      <div className="text-xs text-gray-600 capitalize">{node.type}</div>
                                    </div>
                                  </div>
                                  {node.ip && (
                                    <div className="text-xs font-mono text-gray-500 bg-white px-1 py-0.5 rounded text-xs">
                                      {node.ip}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Links Section */}
                        <div>
                          <div className="flex items-center gap-1 mb-2">
                            <div className="w-1.5 h-1.5 bg-green-500 rounded-full"></div>
                            <h5 className="text-xs font-semibold text-gray-800">Links</h5>
                          </div>
                          <div className="space-y-1">
                            {generatedTopology.topology_config.topology?.links?.map((link, index) => (
                              <div key={index} className="p-2 bg-gray-50 rounded border border-gray-100">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1">
                                    <span className="font-mono text-xs font-medium text-gray-800">{link.source}</span>
                                    <div className="w-3 h-0.5 bg-gray-300"></div>
                                    <span className="font-mono text-xs font-medium text-gray-800">{link.target}</span>
                                  </div>
                                  <div className="flex items-center gap-1">
                                    <span className="text-xs px-1 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">
                                      {link.bandwidth}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={loadGeneratedTopology}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-2 rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all duration-200 flex items-center justify-center gap-1 text-sm shadow-md hover:shadow-lg"
                  >
                    <Network className="w-4 h-4" />
                    Load
                  </button>
                  <button
                    onClick={exportTopology}
                    className="px-4 py-2 border border-gray-200 text-gray-700 rounded-lg hover:border-gray-300 hover:bg-gray-50 transition-all duration-200 flex items-center gap-1 text-sm"
                  >
                    <Download className="w-4 h-4" />
                    Export
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <div className="relative mb-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-purple-100 to-blue-100 rounded-full mx-auto flex items-center justify-center">
                      <Brain className="w-8 h-8 text-purple-500" />
                    </div>
                    <div className="absolute -top-1 -right-1 w-4 h-4 bg-yellow-400 rounded-full flex items-center justify-center">
                      <Sparkles className="w-3 h-3 text-yellow-600" />
                    </div>
                  </div>
                  <h3 className="text-lg font-bold text-gray-800 mb-2">Ready to Generate</h3>
                  <p className="text-sm text-gray-600">
                    Describe your network topology and let AI create it for you.
                  </p>
                </div>
              </div>
            )}

            {/* Clear Button */}
            {(description || generatedTopology) && (
              <div className="mt-4 pt-3 border-t border-gray-200">
                <button
                  onClick={clearGeneration}
                  className="w-full px-3 py-2 text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-all duration-200 flex items-center justify-center gap-1 text-sm"
                >
                  <RotateCcw className="w-3 h-3" />
                  Clear All
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LLMTopologyGenerator;
