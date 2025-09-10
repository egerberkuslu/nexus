import React, { useState, useEffect } from 'react';
import { useLLMApiCall } from './useLLMApiCall';

const LLMConfigurationManager = () => {
  const [configurations, setConfigurations] = useState([]);
  const [activeConfig, setActiveConfig] = useState(null);
  const [serviceTypes, setServiceTypes] = useState({
    ollama: { name: 'Ollama', description: 'Local Ollama models', requires_api_key: false },
    openai: { name: 'OpenAI', description: 'OpenAI API models', requires_api_key: true },
    gemini: { name: 'Google Gemini', description: 'Google Gemini API models', requires_api_key: true },
    claude: { name: 'Anthropic Claude', description: 'Anthropic Claude API models', requires_api_key: true }
  });
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    service_type: 'ollama',
    model_name: '',
    base_url: '',
    api_key: '',
    metadata: {}
  });

  const { llmApiCall: callApi } = useLLMApiCall();

  // Load configurations on component mount
  useEffect(() => {
    const initializeData = async () => {
      try {
        console.log('🚀 Initializing LLM Configuration Manager...');
        console.log('API Base URL:', process.env.REACT_APP_API_URL || 'http://localhost:5000');
        
        // Test API connectivity first
        console.log('🔍 Testing API connectivity...');
        const testResponse = await callApi('/test', 'GET');
        console.log('✅ API test response:', testResponse);
        
        if (!testResponse || !testResponse.success) {
          throw new Error('API test failed');
        }
        
        // Load data
        console.log('📥 Loading configurations...');
        await loadConfigurations();
        
        console.log('📥 Loading service types...');
        await loadServiceTypes();
        
        console.log('📥 Loading active configuration...');
        await loadActiveConfig();
        
        console.log('✅ Initialization complete!');
      } catch (error) {
        console.error('❌ Failed to initialize LLM config data:', error);
        alert(`Failed to connect to API: ${error.message}. Please check if the backend server is running on http://localhost:5000`);
      }
    };
    
    initializeData();
  }, []);

  const loadConfigurations = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('📥 Loading configurations from API...');
      
      const response = await callApi('/llm-config/configurations', 'GET');
      console.log('📊 Configurations API response:', response);
      console.log('📊 Response type:', typeof response);
      console.log('📊 Response keys:', response ? Object.keys(response) : 'response is null/undefined');
      
      if (response && response.success) {
        console.log('✅ API call successful');
        console.log('📊 response.data:', response.data);
        console.log('📊 response.data.configurations:', response.data?.configurations);
        
        // The useLLMApiCall wraps the response in { success: true, data: {...} }
        // So we need to access response.data.configurations
        const configs = response.data?.configurations || [];
        console.log('📊 Final configs array:', configs);
        console.log('📊 Configs is array:', Array.isArray(configs));
        console.log('📊 Configs length:', configs.length);
        
        setConfigurations(Array.isArray(configs) ? configs : []);
        console.log('✅ Set configurations state to:', Array.isArray(configs) ? configs : []);
      } else {
        console.error('❌ API call failed:', response ? response.error : 'No response received');
        setError(response ? response.error || 'Failed to load configurations' : 'No response received');
        setConfigurations([]); // Ensure it's always an array
      }
    } catch (error) {
      console.error('❌ Exception in loadConfigurations:', error);
      setError(error.message || 'Failed to load configurations');
      setConfigurations([]);
    } finally {
      setLoading(false);
    }
  };

  const loadServiceTypes = async () => {
    try {
      console.log('📥 Loading service types...');
      const response = await callApi('/llm-config/service-types', 'GET');
      console.log('📊 Service types response:', response);
      
      if (response.success) {
        setServiceTypes(response.data?.service_types || {});
        console.log('✅ Service types loaded:', response.data?.service_types);
      } else {
        console.error('❌ Failed to load service types:', response.error);
        // Set default service types as fallback
        setServiceTypes({
          ollama: { name: 'Ollama', description: 'Local Ollama models', requires_api_key: false },
          openai: { name: 'OpenAI', description: 'OpenAI API models', requires_api_key: true },
          gemini: { name: 'Google Gemini', description: 'Google Gemini API models', requires_api_key: true },
          claude: { name: 'Anthropic Claude', description: 'Anthropic Claude API models', requires_api_key: true }
        });
      }
    } catch (error) {
      console.error('❌ Failed to load service types:', error);
      // Set default service types as fallback
      setServiceTypes({
        ollama: { name: 'Ollama', description: 'Local Ollama models', requires_api_key: false },
        openai: { name: 'OpenAI', description: 'OpenAI API models', requires_api_key: true },
        gemini: { name: 'Google Gemini', description: 'Google Gemini API models', requires_api_key: true },
        claude: { name: 'Anthropic Claude', description: 'Anthropic Claude API models', requires_api_key: true }
      });
    }
  };

  const loadActiveConfig = async () => {
    try {
      console.log('📥 Loading active configuration...');
      const response = await callApi('/llm-config/active', 'GET');
      console.log('📊 Active config response:', response);
      
      if (response.success) {
        setActiveConfig(response.data?.configuration);
        console.log('✅ Active config loaded:', response.data?.configuration);
      } else {
        console.log('ℹ️ No active configuration found');
        setActiveConfig(null);
      }
    } catch (error) {
      console.error('❌ Failed to load active configuration:', error);
      setActiveConfig(null);
    }
  };

  const handleCreateConfig = async (e) => {
    e.preventDefault();
    
    // Basic validation
    if (!formData.name.trim()) {
      alert('Please enter a configuration name');
      return;
    }
    if (!formData.service_type) {
      alert('Please select a service type');
      return;
    }
    if (!formData.model_name.trim()) {
      alert('Please enter a model name');
      return;
    }
    
    try {
      console.log('Creating configuration with data:', formData);
      
      // Prepare data for API
      const configData = {
        name: formData.name.trim(),
        service_type: formData.service_type,
        model_name: formData.model_name.trim(),
        base_url: formData.base_url.trim() || null,
        metadata: formData.metadata || {}
      };
      
      // Only add api_key if it's not empty
      if (formData.api_key.trim()) {
        configData.api_key = formData.api_key.trim();
      }
      
      console.log('Sending config data:', configData);
      
      const response = await callApi('/llm-config/configurations', 'POST', configData);
      console.log('Create response:', response);
      
      if (response.success) {
        setShowCreateForm(false);
        setFormData({
          name: '',
          service_type: 'ollama',
          model_name: '',
          base_url: '',
          api_key: '',
          metadata: {}
        });
        await loadConfigurations();
        await loadActiveConfig();
        alert('Configuration created successfully!');
      } else {
        alert(`Failed to create configuration: ${response.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to create configuration:', error);
      alert(`Error creating configuration: ${error.message}`);
    }
  };

  const handleUpdateConfig = async (e) => {
    e.preventDefault();
    try {
      const response = await callApi(`/llm-config/configurations/${editingConfig._id}`, 'PUT', formData);
      if (response.success) {
        setEditingConfig(null);
        setFormData({
          name: '',
          service_type: 'ollama',
          model_name: '',
          base_url: '',
          api_key: '',
          metadata: {}
        });
        await loadConfigurations();
        await loadActiveConfig();
        alert('✅ Configuration updated successfully!');
      } else {
        alert(`❌ Failed to update configuration: ${response.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to update configuration:', error);
    }
  };

  const handleDeleteConfig = async (configId) => {
    if (window.confirm('Are you sure you want to delete this configuration?')) {
      try {
        console.log('Deleting configuration:', configId);
        const response = await callApi(`/llm-config/configurations/${configId}`, 'DELETE');
        console.log('Delete response:', response);
        
        if (response.success) {
          await loadConfigurations();
          await loadActiveConfig();
          alert('✅ Configuration deleted successfully!');
        } else {
          alert(`❌ Failed to delete configuration: ${response.error || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to delete configuration:', error);
        alert(`❌ Delete error: ${error.message}`);
      }
    }
  };

  const handleSetActive = async (configId) => {
    try {
      console.log('Setting active configuration:', configId);
      const response = await callApi('/llm-config/active', 'POST', { config_id: configId });
      console.log('Set active response:', response);

      if (response.success) {
        await loadActiveConfig();

        // Reload the LLM service
        console.log('Reloading LLM service...');
        const reloadResponse = await callApi('/llm/reload-config', 'POST');
        console.log('Reload response:', reloadResponse);

        if (reloadResponse.success) {
          console.log('LLM service reloaded successfully');
          alert('Active configuration updated and LLM service reloaded successfully!');
        } else {
          console.error('Failed to reload LLM service:', reloadResponse.error);
          alert(`Configuration updated but LLM service reload failed: ${reloadResponse.error || 'Unknown error'}`);
        }
      } else {
        alert(`Failed to set active configuration: ${response.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to set active configuration:', error);
      alert(`Error setting active configuration: ${error.message}`);
    }
  };

  const handleTestConfig = async (configId) => {
    try {
      console.log('Testing configuration:', configId);
      const response = await callApi(`/llm-config/configurations/${configId}/test`, 'POST');
      console.log('Test response:', response);
      
      if (response.success) {
        if (response.data?.available) {
          alert(`✅ Configuration test passed: ${response.data?.message || 'Service is available'}`);
        } else {
          alert(`❌ Configuration test failed: ${response.data?.message || 'Service is not available'}`);
        }
      } else {
        alert(`❌ Test failed: ${response.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to test configuration:', error);
      alert(`❌ Test error: ${error.message}`);
    }
  };

  const startEdit = (config) => {
    setEditingConfig(config);
    setFormData({
      name: config.name,
      service_type: config.service_type,
      model_name: config.model_name,
      base_url: config.base_url || '',
      api_key: '', // Don't show existing API key for security
      metadata: config.metadata || {}
    });
  };

  const cancelEdit = () => {
    setEditingConfig(null);
    setFormData({
      name: '',
      service_type: 'ollama',
      model_name: '',
      base_url: '',
      api_key: '',
      metadata: {}
    });
  };

  const getServiceTypeInfo = (serviceType) => {
    return (serviceTypes && serviceTypes[serviceType]) || { name: serviceType, description: '', requires_api_key: false };
  };

  // Add error boundary for render errors
  try {
      return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-4">
            <div className="p-3 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl shadow-lg">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <h2 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
                LLM Configuration Manager
              </h2>
              <p className="text-gray-600 text-lg">Intelligently manage AI models for network topology generation</p>
            </div>
          </div>
        </div>

      {/* Active Configuration */}
      {activeConfig && (
        <div className="mb-8 p-6 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-2xl shadow-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-green-500 rounded-xl shadow-md">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <h3 className="text-xl font-bold text-green-800 mb-1">Active Configuration</h3>
                <p className="text-green-700 font-semibold text-lg">{activeConfig.name}</p>
                <p className="text-green-600">
                  {getServiceTypeInfo(activeConfig.service_type).name} • {activeConfig.model_name}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
              <span className="px-4 py-2 bg-green-500 text-white text-sm font-semibold rounded-full shadow-md">
                Active
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Form */}
      {(showCreateForm || editingConfig) && (
        <div className="mb-8 p-8 bg-white border border-gray-200 rounded-2xl shadow-xl">
          <div className="flex items-center space-x-3 mb-6">
            <div className="p-3 bg-blue-500 rounded-xl shadow-md">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-800">
              {editingConfig ? 'Edit Configuration' : 'Create New Configuration'}
            </h3>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            {editingConfig ? 'Update your LLM configuration settings below.' : 'Configure an AI service for generating network topologies. Choose from Ollama (local), OpenAI, or Google Gemini.'}
          </p>
          <form onSubmit={editingConfig ? handleUpdateConfig : handleCreateConfig} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-gray-700">Configuration Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 shadow-sm hover:shadow-md"
                  placeholder="e.g., My Ollama Setup, Production OpenAI, Gemini Pro"
                  required
                />
                <p className="text-xs text-gray-500">
                  Give this configuration a descriptive name to identify it later
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Service Type</label>
                <select
                  value={formData.service_type}
                  onChange={(e) => setFormData({ ...formData, service_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select a service type...</option>
                  <option value="ollama">🦙 Ollama (Local AI - No API key needed)</option>
                  <option value="openai">🤖 OpenAI (GPT models - Requires API key)</option>
                  <option value="gemini">💎 Google Gemini (AI models - Requires API key)</option>
                  <option value="claude">🧠 Anthropic Claude (AI models - Requires API key)</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Choose the AI service you want to use for topology generation
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Model Name</label>
                <input
                  type="text"
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={
                    formData.service_type === 'ollama' ? 'e.g., deepseek-r1:14b, llama3:8b' :
                    formData.service_type === 'openai' ? 'e.g., gpt-3.5-turbo, gpt-4' :
                    formData.service_type === 'gemini' ? 'e.g., gemini-1.5-flash, gemini-1.5-pro' :
                    formData.service_type === 'claude' ? 'e.g., claude-3-sonnet-20240229, claude-3-haiku-20240307' :
                    'Enter model name...'
                  }
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  {formData.service_type === 'ollama' && 'Enter the Ollama model name (run "ollama list" to see available models)'}
                  {formData.service_type === 'openai' && 'Enter the OpenAI model name (gpt-3.5-turbo, gpt-4, etc.)'}
                  {formData.service_type === 'gemini' && 'Enter the Gemini model name (gemini-1.5-flash, gemini-1.5-pro, etc.)'}
                  {formData.service_type === 'claude' && 'Enter the Claude model name (claude-3-sonnet-20240229, claude-3-haiku-20240307, etc.)'}
                  {!formData.service_type && 'Enter the model name for your selected service'}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={
                    formData.service_type === 'ollama' ? 'http://localhost:11434 (default)' :
                    formData.service_type === 'openai' ? 'https://api.openai.com/v1 (default)' :
                    formData.service_type === 'gemini' ? 'https://generativelanguage.googleapis.com/v1beta (default)' :
                    formData.service_type === 'claude' ? 'https://api.anthropic.com (default)' :
                    'Leave empty for default URL'
                  }
                />
                <p className="text-xs text-gray-500 mt-1">
                  {formData.service_type === 'ollama' && 'Ollama runs locally on port 11434 by default'}
                  {formData.service_type === 'openai' && 'OpenAI API endpoint (usually no need to change)'}
                  {formData.service_type === 'gemini' && 'Google Gemini API endpoint (usually no need to change)'}
                  {formData.service_type === 'claude' && 'Anthropic Claude API endpoint (usually no need to change)'}
                  {!formData.service_type && 'API endpoint for your selected service (leave empty for default)'}
                </p>
              </div>
              {getServiceTypeInfo(formData.service_type).requires_api_key && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                  <input
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder={
                      formData.service_type === 'openai' ? 'sk-... (Get from OpenAI dashboard)' :
                      formData.service_type === 'gemini' ? 'AI... (Get from Google AI Studio)' :
                      formData.service_type === 'claude' ? 'sk-ant-... (Get from Anthropic Console)' :
                      'Enter your API key'
                    }
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {formData.service_type === 'openai' && 'Get your API key from https://platform.openai.com/api-keys'}
                    {formData.service_type === 'gemini' && 'Get your API key from https://aistudio.google.com/app/apikey'}
                    {formData.service_type === 'claude' && 'Get your API key from https://console.anthropic.com/'}
                    {formData.service_type !== 'openai' && formData.service_type !== 'gemini' && formData.service_type !== 'claude' && 'Enter the API key for your selected service'}
                  </p>
                </div>
              )}
            </div>
            <div className="flex space-x-2">
              <button
                type="submit"
                className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl hover:from-blue-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
              >
                <div className="flex items-center space-x-2">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="font-semibold">{editingConfig ? 'Update Configuration' : 'Create Configuration'}</span>
                </div>
              </button>
              <button
                type="button"
                onClick={editingConfig ? cancelEdit : () => setShowCreateForm(false)}
                className="px-6 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-all duration-200 shadow-md hover:shadow-lg"
              >
                <div className="flex items-center space-x-2">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  <span className="font-semibold">Cancel</span>
                </div>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Configurations List */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg shadow-md">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-800">Configurations</h3>
          </div>
          <div className="flex gap-3">
            <button
              onClick={async () => {
                try {
                  console.log('Testing API...');
                  const response = await callApi('/test', 'GET');
                  console.log('Test response:', response);
                  alert(`API Test: ${response.message || 'Success'}`);
                } catch (error) {
                  console.error('API test failed:', error);
                  alert(`API Test Failed: ${error.message}`);
                }
              }}
              className="px-4 py-2 bg-gray-500 text-white rounded-xl hover:bg-gray-600 text-sm font-semibold shadow-md hover:shadow-lg transition-all duration-200"
            >
              Test API
            </button>
            <button
              onClick={async () => {
                console.log('Manually refreshing configurations...');
                await loadConfigurations();
              }}
              className="px-4 py-2 bg-green-500 text-white rounded-xl hover:bg-green-600 text-sm font-semibold shadow-md hover:shadow-lg transition-all duration-200"
            >
              Refresh
            </button>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-6 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl hover:from-blue-700 hover:to-purple-700 font-semibold shadow-lg hover:shadow-xl transition-all duration-200 transform hover:-translate-y-0.5"
            >
              Create New
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600">Loading configurations...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading configurations</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error}</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={loadConfigurations}
                  className="bg-red-100 px-3 py-2 rounded-md text-sm font-medium text-red-800 hover:bg-red-200"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Debug Info */}
      {process.env.NODE_ENV === 'development' && (
        <div className="mb-4 p-4 bg-gray-100 rounded-lg text-xs">
          <div className="flex justify-between items-center mb-2">
            <strong className="text-sm font-bold">🔍 Debug Info</strong>
            <button
              onClick={async () => {
                console.log('🧪 Manual API test...');
                try {
                  const response = await callApi('/test', 'GET');
                  console.log('🧪 Manual test response:', response);
                  alert(`API Test: ${response?.message || 'No response'}`);
                } catch (error) {
                  console.error('🧪 Manual test error:', error);
                  alert(`API Test Error: ${error.message}`);
                }
              }}
              className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
            >
              Test API
            </button>
          </div>
          <div className="space-y-1">
            <div><strong>Loading:</strong> {loading.toString()}</div>
            <div><strong>Error:</strong> {error || 'None'}</div>
            <div><strong>Configurations count:</strong> {(configurations || []).length}</div>
            <div><strong>API Base:</strong> {process.env.REACT_APP_API_URL || 'http://localhost:5000'}</div>
            <details className="mt-2">
              <summary className="cursor-pointer font-semibold">Raw Configurations Data</summary>
              <pre className="mt-1 p-2 bg-gray-200 rounded text-xs overflow-auto max-h-32">
                {JSON.stringify(configurations, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}

      {!loading && !error && (configurations || []).length === 0 && (
        <div className="text-center py-8">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No configurations</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by creating a new LLM configuration.</p>
          <div className="mt-6">
            <button
              onClick={() => setShowCreateForm(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
            >
              Create Configuration
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {(configurations || []).map((config) => {
          // Defensive programming - ensure config is valid
          if (!config || typeof config !== 'object') {
            console.warn('Invalid config object:', config);
            return null;
          }
          
          const serviceInfo = getServiceTypeInfo(config.service_type || 'unknown');
          const isActive = activeConfig && activeConfig._id === config._id;
          
          return (
            <div
              key={config._id || `config-${Math.random()}`}
              className={`p-6 border-2 rounded-2xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 ${
                isActive 
                  ? 'border-green-400 bg-gradient-to-br from-green-50 to-emerald-50 shadow-green-200' 
                  : 'border-gray-200 bg-white hover:border-blue-300'
              }`}
            >
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${
                    config.service_type === 'ollama' ? 'bg-blue-100' :
                    config.service_type === 'openai' ? 'bg-green-100' :
                    config.service_type === 'gemini' ? 'bg-purple-100' :
                    config.service_type === 'claude' ? 'bg-orange-100' : 'bg-gray-100'
                  }`}>
                    <span className="text-lg">
                      {config.service_type === 'ollama' ? '🦙' :
                       config.service_type === 'openai' ? '🤖' :
                       config.service_type === 'gemini' ? '💎' :
                       config.service_type === 'claude' ? '🧠' : '⚙️'}
                    </span>
                  </div>
                  <h4 className="font-bold text-gray-800 text-lg">{config.name || 'Unnamed Configuration'}</h4>
                </div>
                {isActive && (
                  <div className="flex items-center space-x-1">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="px-3 py-1 bg-green-500 text-white text-xs font-semibold rounded-full shadow-md">
                      Active
                    </span>
                  </div>
                )}
              </div>
              
              <div className="space-y-1 text-sm text-gray-600 mb-3">
                <p><span className="font-medium">Service:</span> {serviceInfo.name || 'Unknown'}</p>
                <p><span className="font-medium">Model:</span> {config.model_name || 'Not specified'}</p>
                {config.base_url && (
                  <p><span className="font-medium">URL:</span> {config.base_url}</p>
                )}
                <p><span className="font-medium">API Key:</span> {config.has_api_key ? '✓ Set' : '✗ Not set'}</p>
              </div>

              <div className="flex flex-wrap gap-2">
                {!isActive && config._id && (
                  <button
                    onClick={() => {
                      console.log('Setting active config:', config._id);
                      handleSetActive(config._id);
                    }}
                    className="px-3 py-2 bg-green-500 text-white text-xs font-semibold rounded-lg hover:bg-green-600 shadow-md hover:shadow-lg transition-all duration-200 flex items-center space-x-1"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Set Active</span>
                  </button>
                )}
                {isActive && (
                  <div className="px-3 py-2 bg-green-100 text-green-800 text-xs font-semibold rounded-lg flex items-center space-x-1">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Currently Active</span>
                  </div>
                )}
                {config._id && (
                  <button
                    onClick={() => {
                      console.log('Testing config:', config._id);
                      handleTestConfig(config._id);
                    }}
                    className="px-3 py-2 bg-blue-500 text-white text-xs font-semibold rounded-lg hover:bg-blue-600 shadow-md hover:shadow-lg transition-all duration-200 flex items-center space-x-1"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <span>Test</span>
                  </button>
                )}
                <button
                  onClick={() => {
                    console.log('Starting edit for config:', config);
                    startEdit(config);
                  }}
                  className="px-3 py-2 bg-yellow-500 text-white text-xs font-semibold rounded-lg hover:bg-yellow-600 shadow-md hover:shadow-lg transition-all duration-200 flex items-center space-x-1"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  <span>Edit</span>
                </button>
                {config._id && (
                  <button
                    onClick={() => {
                      console.log('Deleting config:', config._id);
                      handleDeleteConfig(config._id);
                    }}
                    className="px-3 py-2 bg-red-500 text-white text-xs font-semibold rounded-lg hover:bg-red-600 shadow-md hover:shadow-lg transition-all duration-200 flex items-center space-x-1"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span>Delete</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {configurations.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <p>No configurations found. Create your first configuration to get started.</p>
        </div>
      )}
      </div>
    </div>
    );
  } catch (error) {
    console.error('Error rendering LLMConfigurationManager:', error);
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Render Error</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>An error occurred while rendering the component: {error.message}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
};

export default LLMConfigurationManager;
