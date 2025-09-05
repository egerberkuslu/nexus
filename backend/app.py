#!/usr/bin/env python3
"""
Mininet Web Framework - Main Flask Application
Enhanced modular architecture with separate components
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
    from api.switch_routes import switch_bp
    from core.mininet_manager import MininetManager
    from utils.logger import setup_logger
    from api.diagnostic_routes import diagnostic_bp
    from api.device_management import device_mgmt_bp
    from api.protocol_management import protocol_mgmt_bp
    from api.host_management import host_mgmt_bp
    from api.performance_management import performance_api_bp
    from api.llm_routes import llm_bp
    from api.llm_config_routes import llm_config_bp
    from database.connection import init_database

except ImportError as e:
    print(f"Import error: {e}")
    print("Please run 'python fix_imports.py' to diagnose import issues")
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

# Register blueprints
app.register_blueprint(network_bp, url_prefix='/api/network')
app.register_blueprint(controller_bp, url_prefix='/api/controller')
app.register_blueprint(topology_bp, url_prefix='/api/topology')
app.register_blueprint(stats_bp, url_prefix='/api/stats')
app.register_blueprint(storage_bp, url_prefix='/api/storage')
app.register_blueprint(snapshot_bp, url_prefix='/api/snapshots')
app.register_blueprint(switch_bp, url_prefix='/api/switch')
app.register_blueprint(diagnostic_bp, url_prefix='/api/diagnostic')
app.register_blueprint(device_mgmt_bp, url_prefix='/api/device-management')
app.register_blueprint(protocol_mgmt_bp, url_prefix='/api/protocol-management')
app.register_blueprint(host_mgmt_bp, url_prefix='/api/host-management')
app.register_blueprint(performance_api_bp, url_prefix='/api/performance-management')
app.register_blueprint(llm_bp, url_prefix='/api/llm')
app.register_blueprint(llm_config_bp, url_prefix='/api/llm-config')


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

def check_environment():
    """Check if environment is properly set up"""
    # Check if running as root
    if os.geteuid() != 0:
        logger.error("Mininet must run as root")
        print("*** ERROR: Mininet must run as root ***")
        print("Please run this script with sudo:")
        print("  sudo python app.py")
        exit(1)
    
    # Check Python environment and Ryu availability
    python_info = subprocess.run(['which', 'python3'], capture_output=True, text=True)
    logger.info(f"Using Python: {python_info.stdout.strip() if python_info.returncode == 0 else 'python3'}")
    
    # Test Ryu availability
    ryu_test = subprocess.run([
        sys.executable, '-c', 
        'import ryu.cmd.manager; print("✓ Ryu available")'
    ], capture_output=True, text=True)
    
    if ryu_test.returncode != 0:
        logger.warning("Ryu not available in current Python environment")
        print("*** WARNING: Ryu not available in current Python environment ***")
        
        # Check conda environment
        conda_python = '/home/ege/anaconda3/envs/sdn-mininet/bin/python'
        if os.path.exists(conda_python):
            conda_ryu_test = subprocess.run([
                conda_python, '-c', 
                'import ryu.cmd.manager; print("✓ Ryu found in conda env")'
            ], capture_output=True, text=True)
            
            if conda_ryu_test.returncode == 0:
                logger.info(f"Found Ryu in conda environment: {conda_python}")
                print(f"✓ Found Ryu in conda environment: {conda_python}")
            else:
                logger.error("Ryu not found in conda environment")
                print("*** ERROR: Ryu not found anywhere ***")
                exit(1)
        else:
            logger.error("Conda environment not found")
            print("*** ERROR: Please install Ryu ***")
            exit(1)
    else:
        logger.info("Ryu available in current environment")
        print("✓ Ryu available in current environment")

if __name__ == '__main__':
    # Register cleanup function
    atexit.register(cleanup)
    
    # Check environment
    check_environment()
    
    print("\nStarting Enhanced Mininet Web Framework...")
    print("✓ Modular architecture with separate files")
    print("✓ Controller included in topology API") 
    print("✓ Full controller management via web API")
    print("✓ Real network statistics collection")
    print("✓ Running with root privileges")
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