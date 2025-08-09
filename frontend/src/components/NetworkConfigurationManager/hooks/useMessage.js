// hooks/useMessage.js
import { useState } from 'react';

/**
 * Custom hook for managing toast messages and notifications
 * Provides functionality to show, clear, and auto-dismiss messages
 */
export const useMessage = () => {
  const [message, setMessage] = useState('');

  /**
   * Show a message with specified type and text
   * @param {string} text - The message text to display
   * @param {string} type - Message type: 'success', 'error', 'info', 'warning'
   */
  const showMessage = (text, type = 'info') => {
    setMessage({ text, type });
    
    // Auto-dismiss message after 5 seconds
    setTimeout(() => setMessage(''), 5000);
  };

  /**
   * Manually clear the current message
   */
  const clearMessage = () => setMessage('');

  /**
   * Show a success message
   * @param {string} text - Success message text
   */
  const showSuccess = (text) => showMessage(text, 'success');

  /**
   * Show an error message
   * @param {string} text - Error message text
   */
  const showError = (text) => showMessage(text, 'error');

  /**
   * Show an info message
   * @param {string} text - Info message text
   */
  const showInfo = (text) => showMessage(text, 'info');

  /**
   * Show a warning message
   * @param {string} text - Warning message text
   */
  const showWarning = (text) => showMessage(text, 'warning');

  return { 
    message, 
    showMessage, 
    clearMessage,
    showSuccess,
    showError,
    showInfo,
    showWarning
  };
};