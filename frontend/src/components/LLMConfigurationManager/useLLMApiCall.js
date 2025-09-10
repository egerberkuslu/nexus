import { useState, useCallback } from 'react';

const API_BASE = `${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api`;

export const useLLMApiCall = () => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [logs, setLogs] = useState([]);

  const addLog = useCallback((logEntry) => {
    setLogs(prev => {
      const newLogs = [...prev, logEntry];
      return newLogs.slice(-50); // Keep last 50 logs
    });
  }, []);

  // Custom API call wrapper specifically for LLM Configuration Manager
  const llmApiCall = useCallback(async (endpoint, method = 'GET', body = null) => {
    try {
      setConnectionStatus('connecting');
      
      // Prepare fetch options
      const fetchOptions = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
        },
      };
      
      // Add body for POST/PUT requests
      if (body && (method === 'POST' || method === 'PUT')) {
        fetchOptions.body = JSON.stringify(body);
      }
      
      console.log(`🚀 LLM API Call: ${method} ${API_BASE}${endpoint}`);
      if (body) {
        console.log('📤 Request body:', body);
      }
      
      const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);
      
      console.log(`📊 Response status: ${response.status} ${response.statusText}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      setConnectionStatus('connected');
      const data = await response.json();
      
      console.log('📥 Response data:', data);
      
      return { success: true, data };
    } catch (error) {
      setConnectionStatus('error');
      console.error('❌ LLM API Error:', error);
      
      const logEntry = {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString(),
        message: `LLM API Error (${endpoint}): ${error.message}`,
        type: 'error',
        category: 'llm-api',
        timestamp: Date.now()
      };

      setLogs(prev => {
        const newLogs = [...prev, logEntry];
        return newLogs.slice(-50);
      });
      
      return { success: false, error: error.message };
    }
  }, []);

  return { 
    llmApiCall, 
    addLog, 
    connectionStatus, 
    logs 
  };
};
