# Enhanced Mininet Web Framework

A modular, feature-rich web framework for managing Mininet networks with full Ryu controller integration and real-time monitoring capabilities.

## 🏗️ Project Structure

```
mininet-web-framework/
├── backend/
│   ├── app.py                    # Main Flask application
│   ├── start.py                  # Enhanced startup script (RECOMMENDED)
│   ├── start_simple.py           # Simple startup script (WORKING)
│   ├── run.sh                    # Shell startup script
│   ├── diagnose.py               # Import diagnostic tool
│   ├── fix_imports.py            # Import path fixer
│   ├── requirements.txt          # Python dependencies
│   ├── README.md                 # This file
│   ├── api/                      # API route blueprints
│   │   ├── __init__.py
│   │   ├── network_routes.py     # Network management endpoints
│   │   ├── controller_routes.py  # Controller management endpoints
│   │   ├── topology_routes.py    # Topology & visualization endpoints
│   │   └── stats_routes.py       # Statistics & metrics endpoints
│   ├── core/                     # Core functionality modules
│   │   ├── __init__.py
│   │   ├── mininet_manager.py    # Main network management class
│   │   ├── ryu_controller.py     # Enhanced Ryu controller manager
│   │   ├── stats_collector.py    # Real-time statistics collection
│   │   └── router.py             # Custom router implementation
│   └── utils/                    # Utility modules
│       ├── __init__.py
│       └── logger.py             # Logging utilities
└── frontend/                     # React frontend (separate)
    └── src/
        └── MininetVisualizer.jsx # Enhanced frontend component
```

## ✨ Key Features

### 🎯 **Enhanced Controller Management**
- **Full Web API Control**: Start, stop, restart Ryu controller via REST API
- **Controller Visibility**: Controllers now included in topology API responses
- **Real-time Logs**: Access controller logs through `/api/controller/logs`
- **Multiple App Support**: Switch between different Ryu applications dynamically
- **Status Monitoring**: Comprehensive controller status and statistics
- **Application Discovery**: Automatic detection of available Ryu applications

### 🗂️ **Modular Architecture**
- **Separation of Concerns**: Clean separation between API routes, core logic, and utilities
- **Blueprint-based APIs**: Organized API endpoints using Flask blueprints
- **Reusable Components**: Modular design for easy maintenance and extension
- **Import Management**: Robust import handling with diagnostic tools

### 📊 **Advanced Statistics & Monitoring**
- **Real-time Metrics**: Live network statistics collection from actual interfaces
- **Historical Data**: Time-series data with configurable retention (50 data points)
- **Interface Statistics**: Per-node interface monitoring with error tracking
- **Flow Statistics**: OpenFlow table analysis and flow entry monitoring
- **Export Capabilities**: JSON, CSV, YAML export formats
- **Performance Trends**: Bandwidth and latency trend analysis

### 🔧 **Enhanced Router Support**
- **Proper Type Detection**: Fixed router classification in topology responses
- **Interface Management**: Advanced router interface configuration
- **Routing Table Access**: View and manage routing tables via API
- **Multi-subnet Support**: Enhanced routing between network segments

### 🌐 **Comprehensive API Coverage**
- **Network Management**: Complete lifecycle management
- **Controller Operations**: Full controller control and monitoring
- **Topology Services**: Enhanced topology with controller integration
- **Statistics Services**: Real-time and historical data analysis

## 🚀 **Quick Start**

### Prerequisites
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install mininet openvswitch-switch

# Optional: Create conda environment (recommended)
conda create -n sdn-mininet python=3.9
conda activate sdn-mininet
```

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd mininet-web-framework/backend

# Install Python dependencies
pip install -r requirements.txt

# Install Ryu controller
pip install ryu

# Make scripts executable
chmod +x run.sh
chmod +x start.py start_simple.py
```

### Running the Application

#### **Option 1: Simple Startup (Recommended for testing)**
```bash
# Start with the simple Python script (most reliable)
sudo python start_simple.py
```

#### **Option 2: Enhanced Startup**
```bash
# Start with the full-featured startup script
sudo python start.py
```

#### **Option 3: Shell Script**
```bash
# Start with the shell script
sudo ./run.sh
```

#### **Option 4: Direct Flask App**
```bash
# Start the main Flask application directly
sudo python app.py
```

### **Troubleshooting Startup Issues**

If you encounter import errors:
```bash
# Run the diagnostic tool
python diagnose.py

# Fix import paths if needed
python fix_imports.py

# Then try starting again
sudo python start_simple.py
```

## 🔧 **API Documentation**

The framework provides a comprehensive REST API with the following endpoints:

### **Global Status**
- `GET /api/status` - Get overall system status
- `GET /api/test` - Test API connectivity

### **Network Management (`/api/network/`)**
- `POST /create` - Create network topology
- `POST /start` - Start the network
- `POST /stop` - Stop the network
- `POST /restart` - Restart the network
- `POST /reset` - Reset network and clear data
- `POST /ping` - Run connectivity tests (all hosts)
- `POST /ping/<source>/<target>` - Specific host ping test
- `GET /status` - Get detailed network status
- `POST /hosts/<host_id>/cmd` - Execute commands on specific hosts
- `GET /flows` - Get OpenFlow statistics from switches

### **Controller Management (`/api/controller/`)**
- `GET /status` - Get comprehensive controller status
- `POST /start` - Start Ryu controller with specified app
- `POST /stop` - Stop Ryu controller
- `POST /restart` - Restart controller
- `GET /logs?lines=<number>` - Get controller logs
- `POST /logs/clear` - Clear controller logs
- `GET /apps` - List available Ryu applications
- `POST /switch/<switch_id>` - Switch controller application
- `GET|POST /config` - Get/update controller configuration
- `GET /stats` - Get detailed controller statistics

### **Topology Management (`/api/topology/`)**
- `GET /full` - **Complete topology including controllers**
- `GET /nodes?type=<node_type>` - Get network nodes (optionally filtered)
- `GET /links` - Get all network links with statistics
- `GET /controllers` - **Get detailed controller information**
- `GET /stats` - Get topology statistics summary
- `GET /node/<node_id>` - Get detailed node information
- `GET /visualize` - Get visualization-ready topology data
- `GET /export?format=<json|yaml|dot>` - Export topology
- `POST /import` - Import topology configuration

### **Statistics & Monitoring (`/api/stats/`)**
- `GET /metrics` - Real-time network metrics
- `GET /detailed` - Comprehensive network statistics
- `GET /historical?minutes=<time_range>` - Historical data
- `GET /interface/<node_id>` - Per-node interface statistics
- `GET /flows/<switch_id>` - Switch-specific flow statistics
- `GET /bandwidth` - Bandwidth utilization statistics
- `GET /latency` - Latency statistics and trends
- `GET /errors` - Error and dropped packet statistics
- `POST /reset` - Reset all statistics
- `GET /export?format=<json|csv>&minutes=<range>` - Export statistics

## 📋 **Configuration**

### **Environment Detection**
The framework automatically detects and configures:
- Python environment (conda or system Python)
- Ryu installation path and availability
- Available controller applications
- Network interface capabilities

### **Controller Configuration**
```python
# Default controller settings (can be modified via API)
CONTROLLER_PORT = 6633
CONTROLLER_TYPE = 'simple_switch_13'
PYTHON_EXECUTABLE = auto-detected
```

### **Statistics Collection**
```python
# Statistics settings
METRICS_HISTORY_SIZE = 50      # Number of historical data points
STATS_COLLECTION_INTERVAL = 3s # Default collection interval
LOG_RETENTION_SIZE = 1000      # Number of log entries to retain
```

## 🎯 **Usage Examples**

### **Basic Network Operations**
```bash
# Create and start a network
curl -X POST http://localhost:5000/api/network/create
curl -X POST http://localhost:5000/api/network/start

# Start Ryu controller
curl -X POST http://localhost:5000/api/controller/start \
  -H "Content-Type: application/json" \
  -d '{"type": "simple_switch_13"}'

# Run connectivity test
curl -X POST http://localhost:5000/api/network/ping
```

### **Get Complete Topology (Including Controllers)**
```bash
# Get full topology with controllers
curl http://localhost:5000/api/topology/full

# Get only controllers
curl http://localhost:5000/api/topology/controllers

# Get topology statistics
curl http://localhost:5000/api/topology/stats
```

### **Monitor Real-time Statistics**
```bash
# Get current network metrics
curl http://localhost:5000/api/stats/metrics

# Get historical data (last 30 minutes)
curl http://localhost:5000/api/stats/historical?minutes=30

# Get bandwidth statistics with trends
curl http://localhost:5000/api/stats/bandwidth
```

### **Controller Management**
```bash
# Get controller status
curl http://localhost:5000/api/controller/status

# Get controller logs (last 100 lines)
curl http://localhost:5000/api/controller/logs?lines=100

# Switch to different controller app
curl -X POST http://localhost:5000/api/controller/switch/s1 \
  -H "Content-Type: application/json" \
  -d '{"app": "hub"}'

# Restart controller
curl -X POST http://localhost:5000/api/controller/restart
```

### **Host Command Execution**
```bash
# Execute command on specific host
curl -X POST http://localhost:5000/api/network/hosts/h1/cmd \
  -H "Content-Type: application/json" \
  -d '{"command": "ifconfig"}'

# Run ping between specific hosts
curl -X POST http://localhost:5000/api/network/ping/h1/h2 \
  -H "Content-Type: application/json" \
  -d '{"count": 4}'
```

### **Data Export**
```bash
# Export topology as JSON
curl http://localhost:5000/api/topology/export?format=json > topology.json

# Export topology as DOT format for Graphviz
curl http://localhost:5000/api/topology/export?format=dot > topology.dot

# Export statistics as CSV
curl http://localhost:5000/api/stats/export?format=csv&minutes=60 > stats.csv
```

## 🔍 **Monitoring & Debugging**

### **Log Categories**
The framework uses structured logging with categories:
- **`network`**: Network operations (create, start, stop, ping)
- **`controller`**: Controller operations (start, stop, app switching)
- **`terminal`**: Host command execution
- **`test`**: Network testing operations
- **`api`**: API request/response logging
- **`system`**: General system events

### **Real-time Monitoring**
```bash
# Monitor controller logs in real-time
watch -n 2 'curl -s http://localhost:5000/api/controller/logs?lines=10'

# Monitor network metrics
watch -n 1 'curl -s http://localhost:5000/api/stats/metrics | jq'

# Monitor network status
watch -n 3 'curl -s http://localhost:5000/api/status | jq'
```

### **Diagnostic Tools**
```bash
# Check import paths and dependencies
python diagnose.py

# Fix import issues
python fix_imports.py

# Test API connectivity
curl http://localhost:5000/api/test
```

## 🎨 **Frontend Integration**

The backend is designed to work with the enhanced React frontend that provides:

- **Interactive Topology Visualization**: Drag-and-drop network topology with controllers
- **Real-time Dashboards**: Live metrics and performance monitoring
- **Controller Management UI**: Web-based controller operations
- **Terminal Interface**: Host command execution through web UI
- **Flow Table Viewer**: OpenFlow statistics visualization
- **Log Monitoring**: Real-time log streaming with filtering

## 🔧 **Development**

### **Adding New API Endpoints**
1. Choose the appropriate blueprint in `api/`
2. Add your route function with proper error handling
3. Update the API documentation
4. Test with curl or the frontend

### **Extending Statistics Collection**
1. Modify `core/stats_collector.py`
2. Add new metrics to the collection methods
3. Update the API responses in `api/stats_routes.py`

### **Adding New Controller Apps**
1. Install the Ryu application
2. Add it to the available apps list in `api/controller_routes.py`
3. Test controller switching functionality

## 📊 **Performance Considerations**

- **Statistics Collection**: Configurable intervals to balance real-time data with performance
- **Memory Management**: Limited history retention to prevent memory issues
- **API Response Times**: Optimized for sub-second response times
- **Concurrent Operations**: Thread-safe operations for simultaneous API calls

## 🔒 **Security Notes**

- **Root Privileges**: Required for Mininet operations
- **Local Development**: Designed for local development and testing
- **API Security**: No authentication implemented (add as needed for production)
- **Command Execution**: Host commands executed with network namespace restrictions

## 🛠️ **Troubleshooting**

### **Common Issues**

1. **"Must run as root" error**:
   ```bash
   sudo python start_simple.py
   ```

2. **Import errors**:
   ```bash
   python diagnose.py
   python fix_imports.py
   ```

3. **Ryu not found**:
   ```bash
   pip install ryu
   # or in conda environment:
   conda activate sdn-mininet
   pip install ryu
   ```

4. **Controller won't start**:
   - Check if port 6633 is available
   - Verify Ryu installation with `python diagnose.py`
   - Check controller logs via API

5. **Network creation fails**:
   - Ensure Mininet is installed: `sudo apt-get install mininet`
   - Clean existing instances: `sudo mn -c`

### **Environment Issues**

- **Python Path**: The framework auto-detects conda environments
- **Permissions**: Ensure proper sudo access for Mininet operations
- **Dependencies**: Use `pip install -r requirements.txt` to install all dependencies

## 📝 **Logging**

Comprehensive logging with different levels:
- **API requests**: All API calls with timing information
- **Network events**: Topology changes and network operations
- **Controller events**: Ryu controller lifecycle and errors
- **Statistics**: Data collection and processing events
- **System events**: Application startup, shutdown, and errors

## 🚦 **Status**

- ✅ **Modular Architecture**: Complete separation of concerns
- ✅ **Controller in Topology**: Controllers visible in topology API responses
- ✅ **Full Controller Control**: Web API for all controller operations
- ✅ **Enhanced Statistics**: Real-time and historical metrics with export
- ✅ **Router Support**: Proper router type detection and management
- ✅ **Export/Import**: Topology and statistics data exchange
- ✅ **Error Handling**: Comprehensive error handling and logging
- ✅ **Documentation**: Complete API documentation with examples

---

**🌐 Server**: Runs on `http://localhost:5000`  
**⚡ Requirements**: Root privileges for Mininet operations  
**🔧 Compatible**: Ubuntu 18.04+, Python 3.7+, Mininet 2.3+, Ryu 4.30+

## 📞 **Support**

For issues and questions:
1. Check the troubleshooting section above
2. Run diagnostic tools (`diagnose.py`, `fix_imports.py`)
3. Check application logs and API responses
4. Verify environment setup and dependencies

**Happy SDN Development! 🚀**