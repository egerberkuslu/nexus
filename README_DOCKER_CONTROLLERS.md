# Docker SDN Controllers Setup

This guide explains how to run the Mininet Web Framework with all SDN controllers (Ryu, POX, os-ken, OpenDaylight) in Docker containers.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 4GB RAM available
- Ports 3000, 5000, 6633, 8181 available

### 1. Quick Test
First, verify that all controllers can be installed:

```bash
./quick-test.sh
```

### 2. Full Setup
Build and start all services with controllers:

```bash
./build-and-test.sh
```

### 3. Access the Application
- **Web Interface**: http://localhost:3000
- **API Endpoint**: http://localhost:5000
- **OpenDaylight GUI**: http://localhost:8181 (admin/admin)

## 📋 Available Controllers

| Controller | Status | Port | Description |
|------------|--------|------|-------------|
| **Ryu** | ✅ | 6633 | Python-based OpenFlow controller |
| **os-ken** | ✅ | 6633 | Official Ryu replacement |
| **POX** | ✅ | 6633 | Educational OpenFlow controller |
| **OpenDaylight** | ✅ | 8181 | Enterprise SDN platform |

## 🐳 Docker Services

### Main Services
```yaml
services:
  backend:     # Main application with all controllers
  frontend:    # React web interface  
  mongodb:     # Database
```

### Ports Exposed
- `3000`: Frontend web interface
- `5000`: Backend REST API
- `6633`: OpenFlow protocol (controllers)
- `8181`: OpenDaylight REST API
- `27017`: MongoDB

## 🔧 Manual Commands

### Build Services
```bash
# Build with all controllers
docker-compose -f docker-compose.controllers.yml build

# Build specific service
docker-compose -f docker-compose.controllers.yml build backend
```

### Start/Stop Services
```bash
# Start all services
docker-compose -f docker-compose.controllers.yml up -d

# Stop all services
docker-compose -f docker-compose.controllers.yml down

# View logs
docker-compose -f docker-compose.controllers.yml logs -f backend
```

### Test Controllers
```bash
# Test controllers inside container
docker-compose -f docker-compose.controllers.yml exec backend python3 docker_controller_test.py

# Verify controller installations
docker-compose -f docker-compose.controllers.yml exec backend /verify_controllers.sh
```

## 🎯 Controller Usage

### Switching Controllers
Use the web interface or API to switch between controllers:

```python
# API example
import requests

# Start Ryu controller
response = requests.post('http://localhost:5000/api/controller/start', 
                        json={'type': 'ryu', 'app': 'simple_switch_13'})

# Switch to POX
response = requests.post('http://localhost:5000/api/controller/start', 
                        json={'type': 'pox', 'app': 'l2_learning'})

# Switch to OpenDaylight
response = requests.post('http://localhost:5000/api/controller/start', 
                        json={'type': 'opendaylight', 'app': 'l2switch'})
```

### Creating Topologies
```python
# Create topology with specific controller
topology = {
    'nodes': [
        {'id': 'h1', 'type': 'host'},
        {'id': 's1', 'type': 'switch'},
        {'id': 'c0', 'type': 'controller'}
    ],
    'links': [
        {'source': 'h1', 'target': 's1'}
    ]
}

response = requests.post('http://localhost:5000/api/topology/create', 
                        json={
                            'topology': topology,
                            'controller_type': 'ryu',
                            'controller_app': 'simple_switch_13'
                        })
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Controllers Not Starting
```bash
# Check controller status
docker-compose -f docker-compose.controllers.yml exec backend python3 -c "
from core.mininet_manager import MininetManager
manager = MininetManager()
print(manager.get_all_controller_info())
"
```

#### 2. Port Conflicts
```bash
# Check what's using ports
netstat -tulpn | grep -E ':(3000|5000|6633|8181|27017)'

# Use different ports in docker-compose.controllers.yml
```

#### 3. Memory Issues
```bash
# Check container memory usage
docker stats

# Increase Docker memory limit in Docker Desktop
```

#### 4. Java Issues (OpenDaylight)
```bash
# Verify Java in container
docker-compose -f docker-compose.controllers.yml exec backend java -version

# Check OpenDaylight logs
docker-compose -f docker-compose.controllers.yml exec backend tail -f /opt/opendaylight/data/log/karaf.log
```

### Debug Commands
```bash
# Enter container shell
docker-compose -f docker-compose.controllers.yml exec backend bash

# Check controller binaries
ls -la /opt/pox/pox.py
ls -la /opt/opendaylight/bin/karaf

# Test Python imports
python3 -c "import ryu; print('Ryu OK')"
python3 -c "from core.mininet_manager import MininetManager; print('Framework OK')"
```

### Logs
```bash
# View all logs
docker-compose -f docker-compose.controllers.yml logs

# Follow backend logs
docker-compose -f docker-compose.controllers.yml logs -f backend

# View specific service logs
docker-compose -f docker-compose.controllers.yml logs mongodb
docker-compose -f docker-compose.controllers.yml logs frontend
```

## 📊 Performance Tips

### Resource Allocation
- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores
- **For OpenDaylight**: Additional 2GB RAM

### Docker Settings
```bash
# Increase Docker memory (Docker Desktop)
# Settings → Resources → Memory → 6GB+

# For Linux, no memory limit by default
```

### Controller-Specific Tips

#### Ryu/os-ken
- Lightweight, starts quickly
- Good for development and testing
- Supports many OpenFlow versions

#### POX
- Python-based, easy to modify
- Great for learning and prototyping
- Slower than Ryu but more educational

#### OpenDaylight
- Enterprise-grade, feature-rich
- Requires more memory (2GB+)
- Takes longer to start (60-120 seconds)
- Provides web GUI and extensive APIs

## 🔐 Security Notes

### Default Credentials
- **OpenDaylight**: admin/admin
- **MongoDB**: No authentication (development only)

### Production Deployment
For production, update:
1. Change default passwords
2. Enable MongoDB authentication
3. Use HTTPS/TLS
4. Restrict network access
5. Update container images regularly

## 📚 Additional Resources

### Documentation
- [Ryu Documentation](https://ryu.readthedocs.io/)
- [POX Documentation](https://noxrepo.github.io/pox-doc/)
- [OpenDaylight Documentation](https://docs.opendaylight.org/)
- [Mininet Documentation](http://mininet.org/walkthrough/)

### API Reference
- Backend API: http://localhost:5000/api/docs (when running)
- OpenDaylight API: http://localhost:8181/apidoc/explorer/index.html

### Examples
See the `test_*.py` files for usage examples:
- `test_multi_controller.py`: Multi-controller testing
- `test_opendaylight.py`: OpenDaylight-specific testing
- `docker_controller_test.py`: Docker environment testing
