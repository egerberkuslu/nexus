"""
Network Performance Management API - Complete Backend Implementation
Provides comprehensive REST API endpoints for network performance testing and monitoring.
Compatible with Mininet environments and integrates with the NetworkPerformanceManager.
"""

from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time
import threading
from functools import wraps

from utils.logger import setup_logger, log_api_request
from core.performance_manager import (
    NetworkPerformanceManager,
    PerformanceTestPlanner,
    RealTimeMonitor,
    validate_performance_request,
    get_mininet_manager,
    get_available_hosts,
    check_network_prerequisites,
    generate_performance_report,
    analyze_performance_results,
    process_comprehensive_test,
    get_host_pairs,
    process_bandwidth_test,
    process_latency_test,
    process_jitter_test,
    process_packet_loss_test,
    execute_test_plan
)

logger = setup_logger(__name__)
performance_api_bp = Blueprint('performance_api', __name__)

# Global performance manager instance
_performance_managers = {}
_active_monitors = {}

# Constants
SUPPORTED_TEST_TYPES = ['bandwidth', 'latency', 'jitter', 'packet_loss', 'comprehensive', 'stress']
MAX_CONCURRENT_TESTS = 5
DEFAULT_TEST_DURATION = 30
MAX_TEST_DURATION = 3600
MIN_MONITORING_INTERVAL = 10
MAX_MONITORING_INTERVAL = 300

def get_performance_manager():
    """Get or create performance manager instance for current network"""
    mininet_mgr = get_mininet_manager()
    if not mininet_mgr:
        return None
    
    # Use network instance as key
    network_id = id(mininet_mgr.net) if mininet_mgr.net else 'default'
    
    if network_id not in _performance_managers:
        _performance_managers[network_id] = NetworkPerformanceManager(mininet_mgr)
    
    return _performance_managers[network_id]

def validate_network_running():
    """Decorator to validate that network is running before API calls"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            mininet_mgr = get_mininet_manager()
            if not mininet_mgr or not mininet_mgr.net or not mininet_mgr.is_running:
                return jsonify({
                    'success': False,
                    'error': 'Network not running',
                    'message': 'A Mininet network must be running to perform performance tests'
                }), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_test_parameters(required_params=None):
    """Decorator to validate test parameters"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = request.get_json() or {}
                
                # Validate required parameters
                if required_params:
                    missing_params = [p for p in required_params if p not in data]
                    if missing_params:
                        return jsonify({
                            'success': False,
                            'error': 'Missing required parameters',
                            'missing': missing_params
                        }), 400
                
                # Validate test duration
                duration = data.get('duration', DEFAULT_TEST_DURATION)
                if not isinstance(duration, (int, float)) or duration < 1 or duration > MAX_TEST_DURATION:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid duration',
                        'message': f'Duration must be between 1 and {MAX_TEST_DURATION} seconds'
                    }), 400
                
                # Validate test types
                test_types = data.get('test_types')
                if test_types and not isinstance(test_types, list):
                    return jsonify({
                        'success': False,
                        'error': 'Invalid test_types',
                        'message': 'test_types must be a list'
                    }), 400
                
                if test_types:
                    invalid_types = [t for t in test_types if t not in SUPPORTED_TEST_TYPES]
                    if invalid_types:
                        return jsonify({
                            'success': False,
                            'error': 'Invalid test types',
                            'invalid': invalid_types,
                            'supported': SUPPORTED_TEST_TYPES
                        }), 400
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Parameter validation error: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Parameter validation failed: {str(e)}'
                }), 400
        return decorated_function
    return decorator

# ======================= SYSTEM STATUS AND PREREQUISITES =======================

@performance_api_bp.route('/performance/status', methods=['GET'])
@log_api_request
@validate_network_running()
def get_performance_status():
    """Get comprehensive performance testing system status"""
    try:
        mininet_mgr = get_mininet_manager()
        perf_mgr = get_performance_manager()
        
        # Check network prerequisites
        prerequisites = check_network_prerequisites(mininet_mgr)
        
        # Get available hosts
        hosts = get_available_hosts(mininet_mgr)
        host_info = []
        for host in hosts:
            host_data = {
                'name': host.name,
                'ip': host.IP() if hasattr(host, 'IP') else 'unknown',
                'iperf3_available': False,
                'ping_available': False
            }
            
            # Check tool availability
            try:
                iperf_result = host.cmd('which iperf3 2>/dev/null')
                host_data['iperf3_available'] = bool(iperf_result.strip())
                
                ping_result = host.cmd('which ping 2>/dev/null')
                host_data['ping_available'] = bool(ping_result.strip())
            except:
                pass
            
            host_info.append(host_data)
        
        # Get monitoring status
        monitoring_active = perf_mgr.real_time_monitor.monitoring_active if perf_mgr else False
        
        # Get test history summary
        test_history_count = len(perf_mgr.test_history) if perf_mgr else 0
        
        # Build the status data - THIS IS THE FIX
        status_data = {
            'system_ready': prerequisites.get('network_running', False) and len(hosts) >= 2,
            'network_running': prerequisites.get('network_running', False),
            'total_hosts': len(hosts),
            'available_host_pairs': len(hosts) * (len(hosts) - 1) // 2,
            'hosts': host_info,
            'prerequisites': prerequisites,
            'monitoring': {
                'active': monitoring_active,
                'interval': perf_mgr.real_time_monitor.monitor_interval if perf_mgr else None
            },
            'test_history': {
                'total_sessions': test_history_count,
                'last_test': perf_mgr.test_history[-1]['metadata']['test_session_id'] if perf_mgr and perf_mgr.test_history else None
            },
            'capabilities': {
                'supported_test_types': SUPPORTED_TEST_TYPES,
                'max_test_duration': MAX_TEST_DURATION,
                'max_concurrent_tests': MAX_CONCURRENT_TESTS
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Log for debugging
        logger.info(f"Performance status response: system_ready={status_data['system_ready']}, total_hosts={status_data['total_hosts']}")
        
        # Return single-level structure - no double nesting
        return jsonify({
            'success': True,
            'data': status_data
        })
        
    except Exception as e:
        logger.error(f"Error getting performance status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/prerequisites', methods=['GET'])
@log_api_request
def check_performance_prerequisites():
    """Check and report on performance testing prerequisites"""
    try:
        mininet_mgr = get_mininet_manager()
        if not mininet_mgr:
            return jsonify({
                'success': False,
                'error': 'Mininet manager not available',
                'prerequisites': {
                    'network_running': False,
                    'issues': ['Mininet manager not initialized'],
                    'recommendations': ['Initialize Mininet manager']
                }
            }), 400
        
        prerequisites = check_network_prerequisites(mininet_mgr)
        
        # Add additional system checks
        system_checks = {
            'python_version': True,  # Already running if we get here
            'required_modules': True,  # numpy, psutil already imported
            'disk_space': True  # Assume sufficient for now
        }
        
        prerequisites['system_checks'] = system_checks
        prerequisites['ready_for_testing'] = (
            prerequisites.get('network_running', False) and
            prerequisites.get('hosts_available', 0) >= 2 and
            prerequisites.get('iperf3_available', 0) > 0
        )
        
        return jsonify({
            'success': True,
            'data': prerequisites,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error checking prerequisites: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================= HOST AND NETWORK DISCOVERY =======================

@performance_api_bp.route('/performance/hosts', methods=['GET'])
@log_api_request
@validate_network_running()
def get_performance_hosts():
    """Get available hosts for performance testing"""
    try:
        mininet_mgr = get_mininet_manager()
        hosts = get_available_hosts(mininet_mgr)
        
        detailed_hosts = []
        for host in hosts:
            host_info = {
                'name': host.name,
                'ip': host.IP() if hasattr(host, 'IP') else 'unknown',
                'interfaces': [],
                'capabilities': {
                    'iperf3': False,
                    'ping': False,
                    'netstat': False
                },
                'system_info': {}
            }
            
            # Get interface information
            try:
                for intf in host.intfList():
                    if intf.name != 'lo':
                        intf_info = {
                            'name': intf.name,
                            'ip': getattr(intf, 'ip', 'unknown'),
                            'mac': getattr(intf, 'mac', 'unknown'),
                            'status': 'up' if intf.isUp() else 'down'
                        }
                        host_info['interfaces'].append(intf_info)
            except Exception as e:
                logger.warning(f"Error getting interfaces for {host.name}: {e}")
            
            # Check tool capabilities
            try:
                tools = ['iperf3', 'ping', 'netstat']
                for tool in tools:
                    result = host.cmd(f'which {tool} 2>/dev/null')
                    host_info['capabilities'][tool] = bool(result.strip())
            except Exception as e:
                logger.warning(f"Error checking tools for {host.name}: {e}")
            
            # Get basic system info
            try:
                host_info['system_info'] = {
                    'kernel': host.cmd('uname -r 2>/dev/null').strip(),
                    'arch': host.cmd('uname -m 2>/dev/null').strip(),
                    'uptime': host.cmd('uptime 2>/dev/null').strip()
                }
            except:
                pass
            
            detailed_hosts.append(host_info)
        
        # Generate possible test pairs
        test_pairs = []
        for i, src in enumerate(detailed_hosts):
            for dst in detailed_hosts[i+1:]:
                test_pairs.append({
                    'src_host': src['name'],
                    'dst_host': dst['name'],
                    'src_ip': src['ip'],
                    'dst_ip': dst['ip'],
                    'can_test_bandwidth': src['capabilities']['iperf3'] and dst['capabilities']['iperf3'],
                    'can_test_latency': src['capabilities']['ping'] and dst['capabilities']['ping']
                })
        
        response_data = {
            'hosts': detailed_hosts,
            'total_hosts': len(detailed_hosts),
            'possible_test_pairs': test_pairs,
            'total_pairs': len(test_pairs)
        }
        
        return jsonify({
            'success': True,
            'data': response_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting performance hosts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================= PERFORMANCE TESTING ENDPOINTS =======================

@performance_api_bp.route('/performance/test/comprehensive', methods=['POST'])
@log_api_request
@validate_network_running()
@validate_test_parameters()
def run_comprehensive_test():
    """Run comprehensive performance test suite"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        src_host = data.get('src_host')
        dst_host = data.get('dst_host')
        duration = data.get('duration', DEFAULT_TEST_DURATION)
        test_types = data.get('test_types', ['bandwidth', 'latency', 'jitter', 'packet_loss'])
        parallel_streams = data.get('parallel_streams', 1)
        validate_only = data.get('validate_only', False)
        
        # Validate host parameters
        if src_host == dst_host:
            return jsonify({
                'success': False,
                'error': 'Source and destination hosts cannot be the same'
            }), 400
        
        # Get performance manager
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # If validation only, return test plan
        if validate_only:
            mininet_mgr = get_mininet_manager()
            hosts = get_available_hosts(mininet_mgr)
            
            planner = PerformanceTestPlanner()
            
            if src_host and dst_host:
                src = next((h for h in hosts if h.name == src_host), None)
                dst = next((h for h in hosts if h.name == dst_host), None)
                if not src or not dst:
                    return jsonify({
                        'success': False,
                        'error': 'Specified hosts not found'
                    }), 400
                
                process_comprehensive_test(planner, src, dst, test_types, duration)
            else:
                # Test all pairs
                host_pairs = get_host_pairs(hosts)
                for src, dst in host_pairs:
                    process_comprehensive_test(planner, src, dst, test_types, duration)
            
            return jsonify({
                'success': True,
                'validation': True,
                'data': {
                    'total_tests': len(planner.get_plan()),
                    'estimated_duration': duration * len(planner.get_plan()),
                    'test_details': planner.get_plan()
                }
            })
        
        # Run actual test
        logger.info(f"Starting comprehensive test: {src_host} -> {dst_host}, duration: {duration}s")
        
        result = perf_mgr.run_comprehensive_test(
            src_host=src_host,
            dst_host=dst_host,
            duration=duration,
            test_types=test_types
        )
        
        if result.get('success'):
            logger.info(f"Comprehensive test completed successfully")
            return jsonify({
                'success': True,
                'data': result,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.warning(f"Comprehensive test failed: {result.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Test execution failed'),
                'details': result
            }), 400
        
    except Exception as e:
        logger.error(f"Error in comprehensive test endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/test/stress', methods=['POST'])
@log_api_request
@validate_network_running()
@validate_test_parameters()
def run_stress_test():
    """Run network stress test with multiple concurrent flows"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        duration = data.get('duration', 300)  # 5 minutes default for stress test
        concurrent_flows = data.get('concurrent_flows', 10)
        flow_size = data.get('flow_size', '100M')
        validate_only = data.get('validate_only', False)
        
        # Validate parameters
        if concurrent_flows < 1 or concurrent_flows > 50:
            return jsonify({
                'success': False,
                'error': 'Invalid concurrent_flows',
                'message': 'concurrent_flows must be between 1 and 50'
            }), 400
        
        if duration > 3600:  # Max 1 hour for stress test
            return jsonify({
                'success': False,
                'error': 'Invalid duration',
                'message': 'Stress test duration cannot exceed 3600 seconds (1 hour)'
            }), 400
        
        # Get performance manager
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # If validation only, return test plan
        if validate_only:
            mininet_mgr = get_mininet_manager()
            hosts = get_available_hosts(mininet_mgr)
            
            if len(hosts) < 2:
                return jsonify({
                    'success': False,
                    'error': 'Need at least 2 hosts for stress testing'
                }), 400
            
            estimated_data_per_flow = flow_size.replace('M', 'MB').replace('G', 'GB')
            
            return jsonify({
                'success': True,
                'validation': True,
                'data': {
                    'concurrent_flows': concurrent_flows,
                    'duration': duration,
                    'flow_size': flow_size,
                    'participating_hosts': len(hosts),
                    'estimated_total_data': f"{concurrent_flows} x {estimated_data_per_flow}",
                    'estimated_network_load': 'High - this test will saturate network links'
                }
            })
        
        # Run actual stress test
        logger.info(f"Starting stress test: {concurrent_flows} flows, duration: {duration}s")
        
        result = perf_mgr.run_stress_test(
            duration=duration,
            concurrent_flows=concurrent_flows,
            flow_size=flow_size
        )
        
        if result.get('success'):
            logger.info(f"Stress test completed successfully")
            return jsonify({
                'success': True,
                'data': result,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.warning(f"Stress test failed: {result.get('error', 'Unknown error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Stress test execution failed'),
                'details': result
            }), 400
        
    except Exception as e:
        logger.error(f"Error in stress test endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/test/custom', methods=['POST'])
@log_api_request
@validate_network_running()
@validate_test_parameters(['test_type', 'src_host', 'dst_host'])
def run_custom_test():
    """Run a single custom performance test"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        test_type = data.get('test_type').lower()
        src_host = data.get('src_host')
        dst_host = data.get('dst_host')
        duration = data.get('duration', DEFAULT_TEST_DURATION)
        
        # Test-specific parameters
        test_params = data.get('parameters', {})
        
        if test_type not in ['bandwidth', 'latency', 'jitter', 'packet_loss']:
            return jsonify({
                'success': False,
                'error': 'Invalid test type',
                'supported': ['bandwidth', 'latency', 'jitter', 'packet_loss']
            }), 400
        
        # Get network objects
        mininet_mgr = get_mininet_manager()
        hosts = get_available_hosts(mininet_mgr)
        
        src = next((h for h in hosts if h.name == src_host), None)
        dst = next((h for h in hosts if h.name == dst_host), None)
        
        if not src or not dst:
            return jsonify({
                'success': False,
                'error': 'Specified hosts not found'
            }), 404
        
        # Create test planner and execute single test
        planner = PerformanceTestPlanner()
        
        # Add appropriate test to plan
        if test_type == 'bandwidth':
            parallel_streams = test_params.get('parallel_streams', 1)
            process_bandwidth_test(planner, src, dst, duration, parallel_streams)
        elif test_type == 'latency':
            count = test_params.get('packet_count', min(1000, duration * 10))
            interval = test_params.get('interval', 0.1)
            process_latency_test(planner, src, dst, count, interval)
        elif test_type == 'jitter':
            bandwidth = test_params.get('bandwidth', '10M')
            process_jitter_test(planner, src, dst, duration, bandwidth)
        elif test_type == 'packet_loss':
            patterns = test_params.get('patterns', ['normal', 'burst', 'random'])
            process_packet_loss_test(planner, src, dst, patterns)
        
        # Execute the test
        execute_test_plan(planner, mininet_mgr)
        
        results = planner.get_results()
        if results:
            result = results[0]  # Single test result
            return jsonify({
                'success': True,
                'data': {
                    'test_type': test_type,
                    'src_host': src_host,
                    'dst_host': dst_host,
                    'result': result,
                    'execution_time': (planner.end_time - planner.start_time).total_seconds() if planner.start_time and planner.end_time else 0
                },
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No test results generated'
            }), 500
        
    except Exception as e:
        logger.error(f"Error in custom test endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================= REAL-TIME MONITORING ENDPOINTS =======================

@performance_api_bp.route('/performance/monitoring/start', methods=['POST'])
@log_api_request
@validate_network_running()
def start_monitoring():
    """Start real-time performance monitoring"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        interval = data.get('interval', 30)
        hosts = data.get('hosts')  # Optional: specific hosts to monitor
        
        # Validate interval
        if interval < MIN_MONITORING_INTERVAL or interval > MAX_MONITORING_INTERVAL:
            return jsonify({
                'success': False,
                'error': 'Invalid monitoring interval',
                'message': f'Interval must be between {MIN_MONITORING_INTERVAL} and {MAX_MONITORING_INTERVAL} seconds'
            }), 400
        
        # Get performance manager
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Check if monitoring is already active
        if perf_mgr.real_time_monitor.monitoring_active:
            return jsonify({
                'success': False,
                'error': 'Monitoring already active',
                'current_interval': perf_mgr.real_time_monitor.monitor_interval
            }), 400
        
        # Validate hosts if specified
        if hosts:
            mininet_mgr = get_mininet_manager()
            available_hosts = [h.name for h in get_available_hosts(mininet_mgr)]
            invalid_hosts = [h for h in hosts if h not in available_hosts]
            if invalid_hosts:
                return jsonify({
                    'success': False,
                    'error': 'Invalid hosts specified',
                    'invalid_hosts': invalid_hosts,
                    'available_hosts': available_hosts
                }), 400
        
        # Start monitoring
        success = perf_mgr.start_real_time_monitoring(interval, hosts)
        
        if success:
            logger.info(f"Started real-time monitoring with {interval}s interval")
            return jsonify({
                'success': True,
                'data': {
                    'monitoring_active': True,
                    'interval': interval,
                    'monitored_hosts': hosts or 'all',
                    'started_at': datetime.now().isoformat()
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start monitoring'
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/monitoring/stop', methods=['POST'])
@log_api_request
def stop_monitoring():
    """Stop real-time performance monitoring"""
    try:
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        if not perf_mgr.real_time_monitor.monitoring_active:
            return jsonify({
                'success': True,
                'message': 'Monitoring was not active'
            })
        
        perf_mgr.stop_real_time_monitoring()
        
        logger.info("Stopped real-time monitoring")
        return jsonify({
            'success': True,
            'data': {
                'monitoring_active': False,
                'stopped_at': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/monitoring/status', methods=['GET'])
@log_api_request
def get_monitoring_status():
    """Get current real-time monitoring status and metrics"""
    try:
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Get current metrics
        metrics = perf_mgr.get_real_time_metrics()
        
        return jsonify({
            'success': True,
            'data': metrics,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/monitoring/history', methods=['GET'])
@log_api_request
def get_monitoring_history():
    """Get historical monitoring data"""
    try:
        # Extract query parameters
        pair_key = request.args.get('pair_key')
        limit = request.args.get('limit', type=int)
        
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Get history
        history = perf_mgr.real_time_monitor.get_history(pair_key, limit)
        
        return jsonify({
            'success': True,
            'data': {
                'history': history,
                'pair_key': pair_key,
                'limit': limit
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting monitoring history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================= RESULTS AND REPORTING ENDPOINTS =======================

@performance_api_bp.route('/performance/results/history', methods=['GET'])
@log_api_request
def get_test_history():
    """Get test execution history"""
    try:
        # Extract query parameters
        limit = request.args.get('limit', type=int)
        test_type = request.args.get('test_type')
        
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Get history
        history = perf_mgr.get_test_history(limit)
        
        # Filter by test type if specified
        if test_type:
            filtered_history = []
            for session in history:
                metadata = session.get('metadata', {})
                if metadata.get('test_type') == test_type or test_type in metadata.get('test_types', []):
                    filtered_history.append(session)
            history = filtered_history
        
        return jsonify({
            'success': True,
            'data': {
                'history': history,
                'total_sessions': len(history),
                'filtered_by': test_type if test_type else None
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting test history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/results/session/<session_id>', methods=['GET'])
@log_api_request
def get_session_results(session_id):
    """Get detailed results for a specific test session"""
    try:
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Find session in history
        session = None
        for s in perf_mgr.test_history:
            if s.get('metadata', {}).get('test_session_id') == session_id:
                session = s
                break
        
        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'session_id': session_id
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'session_id': session_id,
                'session': session
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting session results: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/reports/generate', methods=['POST'])
@log_api_request
def generate_performance_report():
    """Generate comprehensive performance report"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        session_id = data.get('session_id')
        format_type = data.get('format', 'json')
        include_analysis = data.get('include_analysis', True)
        include_charts = data.get('include_charts', False)
        
        if format_type not in ['json', 'html', 'pdf']:
            return jsonify({
                'success': False,
                'error': 'Invalid format',
                'supported_formats': ['json', 'html', 'pdf']
            }), 400
        
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Generate report
        report = perf_mgr.generate_report(
            session_id=session_id,
            format=format_type,
            include_analysis=include_analysis
        )
        
        if 'error' in report:
            return jsonify({
                'success': False,
                'error': report['error']
            }), 400
        
        # Add metadata
        report['report_metadata'] = {
            'generated_at': datetime.now().isoformat(),
            'format': format_type,
            'session_id': session_id,
            'include_analysis': include_analysis,
            'include_charts': include_charts
        }
        
        return jsonify({
            'success': True,
            'data': report,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/reports/analyze', methods=['POST'])
@log_api_request
def analyze_performance_data():
    """Analyze performance data and provide insights"""
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        session_id = data.get('session_id')
        analysis_type = data.get('analysis_type', 'comprehensive')
        comparison_baseline = data.get('comparison_baseline')
        
        perf_mgr = get_performance_manager()
        if not perf_mgr:
            return jsonify({
                'success': False,
                'error': 'Performance manager not available'
            }), 500
        
        # Get test results
        if session_id:
            session = next((s for s in perf_mgr.test_history if s['metadata'].get('test_session_id') == session_id), None)
            if not session:
                return jsonify({
                    'success': False,
                    'error': f'Session {session_id} not found'
                }), 404
            test_results = session['results']
        else:
            # Use latest session
            if not perf_mgr.test_history:
                return jsonify({
                    'success': False,
                    'error': 'No test history available'
                }), 400
            test_results = perf_mgr.test_history[-1]['results']
        
        # Perform analysis
        analysis = analyze_performance_results(test_results)
        
        # Add trend analysis if baseline provided
        if comparison_baseline:
            baseline_session = next((s for s in perf_mgr.test_history if s['metadata'].get('test_session_id') == comparison_baseline), None)
            if baseline_session:
                # Simple trend comparison
                baseline_results = baseline_session['results']
                trend_analysis = compare_performance_results(baseline_results, test_results)
                analysis['trend_comparison'] = trend_analysis
        
        return jsonify({
            'success': True,
            'data': {
                'analysis': analysis,
                'session_id': session_id,
                'analysis_type': analysis_type,
                'baseline_comparison': comparison_baseline
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error analyzing performance data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================= UTILITY AND MANAGEMENT ENDPOINTS =======================

@performance_api_bp.route('/performance/cleanup', methods=['POST'])
@log_api_request
def cleanup_performance_resources():
    """Cleanup performance testing resources"""
    try:
        data = request.get_json() or {}
        cleanup_type = data.get('cleanup_type', 'all')
        
        perf_mgr = get_performance_manager()
        if perf_mgr:
            # Stop monitoring if active
            if perf_mgr.real_time_monitor.monitoring_active:
                perf_mgr.stop_real_time_monitoring()
            
            # Cleanup based on type
            if cleanup_type in ['all', 'history']:
                # Clear test history but keep recent sessions
                keep_recent = data.get('keep_recent_sessions', 5)
                if len(perf_mgr.test_history) > keep_recent:
                    perf_mgr.test_history = perf_mgr.test_history[-keep_recent:]
            
            if cleanup_type in ['all', 'monitoring']:
                # Clear monitoring history
                perf_mgr.real_time_monitor.performance_history.clear()
            
            # General cleanup
            perf_mgr.cleanup()
        
        # Kill any remaining iperf3 processes in the network
        try:
            mininet_mgr = get_mininet_manager()
            if mininet_mgr and mininet_mgr.net:
                hosts = get_available_hosts(mininet_mgr)
                for host in hosts:
                    host.cmd('pkill -f iperf3 2>/dev/null || true')
        except Exception as e:
            logger.warning(f"Error cleaning up iperf3 processes: {e}")
        
        logger.info(f"Performance resources cleaned up: {cleanup_type}")
        return jsonify({
            'success': True,
            'data': {
                'cleanup_type': cleanup_type,
                'cleaned_at': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up performance resources: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@performance_api_bp.route('/performance/tools/install', methods=['POST'])
@log_api_request
@validate_network_running()
def install_performance_tools():
    """Install performance testing tools on network hosts"""
    try:
        data = request.get_json() or {}
        tools = data.get('tools', ['iperf3'])
        hosts = data.get('hosts')  # Optional: specific hosts
        
        supported_tools = ['iperf3', 'netperf', 'nuttcp']
        invalid_tools = [t for t in tools if t not in supported_tools]
        if invalid_tools:
            return jsonify({
                'success': False,
                'error': 'Invalid tools specified',
                'invalid_tools': invalid_tools,
                'supported_tools': supported_tools
            }), 400
        
        mininet_mgr = get_mininet_manager()
        target_hosts = get_available_hosts(mininet_mgr)
        
        # Filter hosts if specified
        if hosts:
            target_hosts = [h for h in target_hosts if h.name in hosts]
        
        installation_results = {}
        
        for host in target_hosts:
            host_results = {}
            
            for tool in tools:
                try:
                    # Check if already installed
                    check_result = host.cmd(f'which {tool} 2>/dev/null')
                    if check_result.strip():
                        host_results[tool] = {
                            'status': 'already_installed',
                            'path': check_result.strip()
                        }
                        continue
                    
                    # Try to install
                    if tool == 'iperf3':
                        install_cmd = 'apt-get update && apt-get install -y iperf3'
                    elif tool == 'netperf':
                        install_cmd = 'apt-get update && apt-get install -y netperf'
                    elif tool == 'nuttcp':
                        install_cmd = 'apt-get update && apt-get install -y nuttcp'
                    
                    # Note: This may not work in Mininet without proper setup
                    install_result = host.cmd(install_cmd)
                    
                    # Verify installation
                    verify_result = host.cmd(f'which {tool} 2>/dev/null')
                    if verify_result.strip():
                        host_results[tool] = {
                            'status': 'installed',
                            'path': verify_result.strip()
                        }
                    else:
                        host_results[tool] = {
                            'status': 'failed',
                            'error': 'Installation completed but tool not found'
                        }
                    
                except Exception as e:
                    host_results[tool] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            installation_results[host.name] = host_results
        
        return jsonify({
            'success': True,
            'data': {
                'installation_results': installation_results,
                'tools_requested': tools,
                'hosts_processed': [h.name for h in target_hosts]
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error installing performance tools: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================= HELPER FUNCTIONS =======================

def compare_performance_results(baseline_results, current_results):
    """Compare two sets of performance results for trend analysis"""
    comparison = {
        'bandwidth_trend': 'stable',
        'latency_trend': 'stable',
        'improvements': [],
        'degradations': []
    }
    
    try:
        # Compare bandwidth results
        baseline_bw = [r.get('bandwidth_mbps', 0) for r in baseline_results if r.get('test_type') == 'bandwidth' and r.get('success')]
        current_bw = [r.get('bandwidth_mbps', 0) for r in current_results if r.get('test_type') == 'bandwidth' and r.get('success')]
        
        if baseline_bw and current_bw:
            baseline_avg = sum(baseline_bw) / len(baseline_bw)
            current_avg = sum(current_bw) / len(current_bw)
            change_percent = ((current_avg - baseline_avg) / baseline_avg) * 100
            
            if change_percent > 10:
                comparison['bandwidth_trend'] = 'improved'
                comparison['improvements'].append(f'Bandwidth improved by {change_percent:.1f}%')
            elif change_percent < -10:
                comparison['bandwidth_trend'] = 'degraded'
                comparison['degradations'].append(f'Bandwidth decreased by {abs(change_percent):.1f}%')
        
        # Compare latency results
        baseline_lat = [r.get('mean_ms', 0) for r in baseline_results if r.get('test_type') == 'latency' and r.get('success')]
        current_lat = [r.get('mean_ms', 0) for r in current_results if r.get('test_type') == 'latency' and r.get('success')]
        
        if baseline_lat and current_lat:
            baseline_avg = sum(baseline_lat) / len(baseline_lat)
            current_avg = sum(current_lat) / len(current_lat)
            change_percent = ((current_avg - baseline_avg) / baseline_avg) * 100
            
            if change_percent > 20:
                comparison['latency_trend'] = 'degraded'
                comparison['degradations'].append(f'Latency increased by {change_percent:.1f}%')
            elif change_percent < -20:
                comparison['latency_trend'] = 'improved'
                comparison['improvements'].append(f'Latency improved by {abs(change_percent):.1f}%')
    
    except Exception as e:
        logger.warning(f"Error in trend comparison: {e}")
        comparison['comparison_error'] = str(e)
    
    return comparison

# Error handlers
@performance_api_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'message': 'The requested performance API endpoint does not exist'
    }), 404

@performance_api_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Method not allowed',
        'message': 'The HTTP method is not allowed for this endpoint'
    }), 405

@performance_api_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error in performance API: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred in the performance testing system'
    }), 500


# Cleanup function for application shutdown
def cleanup_all_performance_managers():
    """Cleanup all performance managers on application shutdown"""
    for manager in _performance_managers.values():
        try:
            manager.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up performance manager: {e}")
    
    _performance_managers.clear()
    _active_monitors.clear()
    logger.info("All performance managers cleaned up")