import { useCallback } from 'react';

const API_BASE = `${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api`;

export const useApiCall = (setConnectionStatus, setLogs) => {
  // Enhanced logging with categorization
  const addLog = useCallback((message, type = 'info', category = 'system') => {
    const logEntry = {
      id: Date.now() + Math.random(),
      time: new Date().toLocaleTimeString(),
      message,
      type,
      category,
      timestamp: Date.now()
    };

    setLogs(prev => {
      const newLogs = [...prev, logEntry];
      return newLogs.slice(-50); // Keep last 50 logs
    });
  }, [setLogs]);

  // Enhanced API call wrapper with error handling
  const apiCall = useCallback(async (endpoint, options = {}) => {
    try {
      setConnectionStatus('connecting');
      const response = await fetch(`${API_BASE}${endpoint}`, {
        timeout: 10000,
        ...options
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      setConnectionStatus('connected');
      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      setConnectionStatus('error');
      // Use addLog directly without including it in dependencies to avoid circular dependency
      const logEntry = {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString(),
        message: `API Error (${endpoint}): ${error.message}`,
        type: 'error',
        category: 'api',
        timestamp: Date.now()
      };

      setLogs(prev => {
        const newLogs = [...prev, logEntry];
        return newLogs.slice(-50);
      });
      return { success: false, error: error.message };
    }
  }, [setConnectionStatus, setLogs]);

  return { apiCall, addLog };
};