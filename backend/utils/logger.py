"""
Logging utility for the Mininet Web Framework
"""

import logging
import sys
from datetime import datetime
from functools import wraps

def setup_logger(name, level=logging.INFO):
    """Set up a logger with consistent formatting"""
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding multiple handlers
    if logger.handlers:
        return logger
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def log_api_request(func):
    """Decorator to log API requests - FIXED to preserve function names"""
    @wraps(func)  # This preserves the original function name and metadata
    def wrapper(*args, **kwargs):
        from flask import request
        logger = logging.getLogger('api')
        
        # Log request
        logger.info(f"{request.method} {request.path} - {request.remote_addr}")
        
        try:
            result = func(*args, **kwargs)
            logger.info(f"Request completed successfully")
            return result
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    return wrapper