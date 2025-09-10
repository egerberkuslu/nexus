#!/usr/bin/env python3
"""
Simple startup script for Mininet Web Framework
This handles all the import path issues automatically
"""

import os
import sys
import subprocess

def main():
    # Check if running as root
    if os.geteuid() != 0:
        print("ERROR: Must run as root")
        print("Usage: sudo python start.py")
        sys.exit(1)
    
    # Get script directory and set up paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Add to Python path
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    # Set environment variable for subprocesses
    os.environ['PYTHONPATH'] = f"{script_dir}:{os.environ.get('PYTHONPATH', '')}"
    
    print("Starting Enhanced Mininet Web Framework...")
    print(f"Working directory: {script_dir}")
    print(f"Python path: {sys.path[0]}")
    
    # Clean up existing Mininet processes
    print("Cleaning up existing processes...")
    try:
        subprocess.run(['mn', '-c'], capture_output=True)
    except:
        pass
    
    # Test imports
    print("Testing imports...")
    try:
        from utils.logger import setup_logger
        from core.mininet_manager import MininetManager
        print("✓ All imports successful")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        print("Please check the file structure and ensure all files are present")
        sys.exit(1)
    
    # Import and run Flask app
    try:
        # Import app components
        from flask import Flask
        from flask_cors import CORS
        from api.network_routes import network_bp
        from api.controller_routes import controller_bp
        from api.topology_routes import topology_bp
        from api.stats_routes import stats_bp
        
        # Create Flask app
        app = Flask(__name__)
        CORS(app)
        
        # Setup logger
        logger = setup_logger(__name__)
        
        # Initialize Mininet manager
        mininet_mgr = MininetManager()
        app.config['MININET_MANAGER'] = mininet_mgr
        
        # Register blueprints
        app.register_blueprint(network_bp, url_prefix='/api/network')
        app.register_blueprint(controller_bp, url_prefix='/api/controller')
        app.register_blueprint(topology_bp, url_prefix='/api/topology')
        app.register_blueprint(stats_bp, url_prefix='/api/stats')
        
        # Add test endpoint
        @app.route('/api/test', methods=['GET', 'POST'])
        def test_endpoint():
            from flask import jsonify, request
            return jsonify({'message': 'API is working', 'method': request.method})
        
        @app.route('/api/status', methods=['GET'])
        def get_global_status():
            from flask import jsonify
            return jsonify({
                'running': mininet_mgr.is_running,
                'network_exists': mininet_mgr.net is not None,
                'controller': mininet_mgr.get_controller_status(),
                'system': 'ready'
            })
        
        # Cleanup function
        def cleanup():
            logger.info("Cleaning up resources...")
            try:
                # Stop network if running
                if mininet_mgr.is_running:
                    logger.info("Stopping Mininet network...")
                    mininet_mgr.stop_network()
                
                # Stop all controllers
                logger.info("Stopping all controllers...")
                mininet_mgr.controller_factory.stop_all_controllers()
                
                # Force reset controller states
                logger.info("Resetting controller states...")
                mininet_mgr.controller_factory.reset_controller_states()
                
                # Force cleanup of any remaining Mininet processes
                logger.info("Cleaning up Mininet processes...")
                subprocess.run(['mn', '-c'], capture_output=True)
                
                # Force cleanup of any remaining controller processes
                logger.info("Cleaning up controller processes...")
                controller_processes = ['ryu-manager', 'pox.py', 'osken', 'karaf']
                for process_name in controller_processes:
                    try:
                        subprocess.run(['pkill', '-f', process_name], 
                                      capture_output=True, text=True)
                    except Exception:
                        pass
                
                logger.info("Cleanup completed successfully - exiting program")
                
                # Force exit the program
                import sys
                sys.exit(0)
                
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                # Still exit even if cleanup failed
                import sys
                sys.exit(1)
        
        # Register cleanup
        import atexit
        atexit.register(cleanup)
        
        # Start server
        print("\n" + "="*60)
        print("Enhanced Mininet Web Framework")
        print("="*60)
        print("✓ Modular architecture with separate files")
        print("✓ Controller included in topology API")
        print("✓ Full controller management via web API")
        print("✓ Real-time network statistics")
        print("✓ Fixed router type detection")
        print("✓ Running with root privileges")
        print("\nAPI available at: http://localhost:5000")
        print("Press Ctrl+C to stop")
        print("="*60)
        
        from mininet.log import setLogLevel
        setLogLevel('info')
        
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        cleanup()
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()