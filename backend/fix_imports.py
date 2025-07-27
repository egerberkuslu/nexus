#!/usr/bin/env python3
"""
Import path fixer for the Mininet Web Framework
Run this if you encounter import issues
"""

import os
import sys

def fix_imports():
    """Fix Python import paths"""
    # Get the directory where this script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add current directory to Python path
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Set PYTHONPATH environment variable
    pythonpath = os.environ.get('PYTHONPATH', '')
    if current_dir not in pythonpath:
        os.environ['PYTHONPATH'] = f"{current_dir}:{pythonpath}" if pythonpath else current_dir
    
    print(f"Added {current_dir} to Python path")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")

if __name__ == "__main__":
    fix_imports()
    
    # Test imports
    print("Testing imports...")
    try:
        from utils.logger import setup_logger
        print("✓ utils.logger imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import utils.logger: {e}")
    
    try:
        from core.router import Router
        print("✓ core.router imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import core.router: {e}")
    
    try:
        from core.stats_collector import NetworkStatsCollector
        print("✓ core.stats_collector imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import core.stats_collector: {e}")
    
    try:
        from core.ryu_controller import RyuControllerManager
        print("✓ core.ryu_controller imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import core.ryu_controller: {e}")
    
    try:
        from core.mininet_manager import MininetManager
        print("✓ core.mininet_manager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import core.mininet_manager: {e}")
    
    try:
        from api.network_routes import network_bp
        print("✓ api.network_routes imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import api.network_routes: {e}")
    
    print("Import test completed!")