// hooks/useNetworkApi.js
import { useState, useCallback } from 'react';

/**
 * Custom hook for network API communication
 * Provides a centralized API client with error handling and loading states
 */
export const useNetworkApi = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Make an API call to the network management backend
   * @param {string} endpoint - API endpoint (e.g., '/network/start')
   * @param {object} options - Fetch options (method, body, headers, etc.)
   * @returns {Promise} API response data
   */
  const apiCall = useCallback(async (endpoint, options = {}) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...options.headers
        },
        ...options
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage;
        
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.error || errorJson.message || `HTTP ${response.status}: ${response.statusText}`;
        } catch {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        }
        
        throw new Error(errorMessage);
      }
      
      const data = await response.json();
      return data;
    } catch (error) {
      console.error(`API call failed for ${endpoint}:`, error);
      setError(error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * GET request helper
   * @param {string} endpoint - API endpoint
   * @param {object} options - Additional fetch options
   */
  const get = useCallback((endpoint, options = {}) => {
    return apiCall(endpoint, { method: 'GET', ...options });
  }, [apiCall]);

  /**
   * POST request helper
   * @param {string} endpoint - API endpoint
   * @param {object} data - Request body data
   * @param {object} options - Additional fetch options
   */
  const post = useCallback((endpoint, data = {}, options = {}) => {
    return apiCall(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      ...options
    });
  }, [apiCall]);

  /**
   * PUT request helper
   * @param {string} endpoint - API endpoint
   * @param {object} data - Request body data
   * @param {object} options - Additional fetch options
   */
  const put = useCallback((endpoint, data = {}, options = {}) => {
    return apiCall(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options
    });
  }, [apiCall]);

  /**
   * DELETE request helper
   * @param {string} endpoint - API endpoint
   * @param {object} options - Additional fetch options
   */
  const del = useCallback((endpoint, options = {}) => {
    return apiCall(endpoint, { method: 'DELETE', ...options });
  }, [apiCall]);

  /**
   * Upload file helper
   * @param {string} endpoint - API endpoint
   * @param {FormData} formData - Form data with file
   * @param {object} options - Additional fetch options
   */
  const upload = useCallback((endpoint, formData, options = {}) => {
    return apiCall(endpoint, {
      method: 'POST',
      body: formData,
      headers: {
        // Don't set Content-Type for FormData, let browser set it
        ...options.headers
      },
      ...options
    });
  }, [apiCall]);

  /**
   * Clear any existing error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return { 
    apiCall,
    get,
    post,
    put,
    delete: del,
    upload,
    loading,
    error,
    clearError
  };
};