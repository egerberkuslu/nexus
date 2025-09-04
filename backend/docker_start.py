#!/usr/bin/env python3
"""
Docker-specific startup script for Mininet Web Framework
Bypasses some of the environment checks that are problematic in containers
"""

import os
import sys
import subprocess
import atexit

# Fix import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Set PYTHONPATH for subprocesses
pythonpath = os.environ.get('PYTHONPATH', '')
if current_dir not in pythonpath:
    os.environ['PYTHONPATH'] = f"{current_dir}:{pythonpath}" if pythonpath else current_dir

from flask import Flask
from flask_cors import CORS

# Import blueprints and core components
try:
    from api.network_routes import network_bp
    from api.controller_routes import controller_bp
    from api.topology_routes import topology_bp
    from api.stats_routes import stats_bp
    from api.storage_routes import storage_bp
    from api.snapshot_routes import snapshot_bp
    from core.mininet_manager import MininetManager
    from utils.logger import setup_logger
    from api.diagnostic_routes import diagnostic_bp
    from api.device_management import device_mgmt_bp
    from api.protocol_management import protocol_mgmt_bp
    from api.host_management import host_mgmt_bp
    from api.performance_management import performance_api_bp
    from database.connection import init_database


except ImportError as e:
    print(f"Import error: {e}")
    print("Please check the file structure and ensure all files are present")
    sys.exit(1)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Setup logging
logger = setup_logger(__name__)

# Initialize database
logger.info("Initializing MongoDB connection...")
if init_database():
    logger.info("✓ MongoDB connected successfully")
else:
    logger.warning("⚠ MongoDB connection failed - storage features will be disabled")

# Initialize Mininet manager (singleton)
mininet_mgr = MininetManager()

# Initialize Mininet manager with default controller setup
logger.info("✓ Mininet manager initialized with available controllers")

# Register blueprints
app.register_blueprint(network_bp, url_prefix='/api/network')
app.register_blueprint(controller_bp, url_prefix='/api/controller')
app.register_blueprint(topology_bp, url_prefix='/api/topology')
app.register_blueprint(stats_bp, url_prefix='/api/stats')
app.register_blueprint(storage_bp, url_prefix='/api/storage')
app.register_blueprint(snapshot_bp, url_prefix='/api/snapshots')
app.register_blueprint(diagnostic_bp, url_prefix='/api/diagnostic')
app.register_blueprint(device_mgmt_bp, url_prefix='/api/device-management')
app.register_blueprint(protocol_mgmt_bp, url_prefix='/api/protocol-management')
app.register_blueprint(host_mgmt_bp, url_prefix='/api/host-management')
app.register_blueprint(performance_api_bp, url_prefix='/api/performance-management')

# Make mininet_mgr available to blueprints
app.config['MININET_MANAGER'] = mininet_mgr

@app.route('/api/test', methods=['GET', 'POST'])
def test_endpoint():
    """Test endpoint to verify API is working"""
    from flask import jsonify, request
    return jsonify({'message': 'API is working', 'method': request.method})

@app.route('/api/status', methods=['GET'])
def get_global_status():
    """Get overall system status"""
    from flask import jsonify
    return jsonify({
        'running': mininet_mgr.is_running,
        'network_exists': mininet_mgr.net is not None,
        'controller': mininet_mgr.get_controller_status(),
        'system': 'ready'
    })

def cleanup():
    """Clean up Mininet resources"""
    logger.info("Cleaning up resources...")
    mininet_mgr.stop_network()
    os.system('mn -c > /dev/null 2>&1')

if __name__ == '__main__':
    # Register cleanup function
    atexit.register(cleanup)
    
    print("\nStarting Enhanced Mininet Web Framework (Docker)...")
    print("✓ Modular architecture with separate files")
    print("✓ Controller included in topology API") 
    print("✓ Full controller management via web API")
    print("✓ Real network statistics collection")
    print("✓ Running in Docker container")
    print("API available at http://localhost:5000")
    print("\nAPI Endpoints:")
    print("  Network Management:")
    print("    - POST /api/network/create")
    print("    - POST /api/network/start")
    print("    - POST /api/network/stop")
    print("    - POST /api/network/ping")
    print("  Controller Management:")
    print("    - GET /api/controller/status")
    print("    - POST /api/controller/start")
    print("    - POST /api/controller/stop")
    print("    - POST /api/controller/restart")
    print("    - GET /api/controller/logs")
    print("  Topology & Stats:")
    print("    - GET /api/topology/full")
    print("    - GET /api/topology/nodes")
    print("    - GET /api/topology/links") 
    print("    - GET /api/stats/metrics")
    print("    - GET /api/stats/detailed")
    print("Press Ctrl+C to stop the server")
    print("-" * 60)
    
    try:
        from mininet.log import setLogLevel
        setLogLevel('info')
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        cleanup()
        print("Cleanup complete. Goodbye!")
