# Mininet Web Framework Setup Guide

## System Requirements

### Operating System
- **Ubuntu/Debian 20.04+** (Recommended)
- **CentOS/RHEL 8+**
- **Arch Linux** (with custom configurations)
- **macOS** (limited support - VM recommended)

### Hardware Requirements
- **CPU**: 4+ cores (8+ recommended for complex topologies)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: 20GB free space minimum
- **Network**: Internet connection for package installation

### Software Prerequisites
- **Python**: 3.8+ (Python 3.10+ recommended)
- **Node.js**: 16.0+ (for frontend)
- **Git**: Latest version
- **Docker**: 20.10+ (optional, for containerized controllers)
- **Java**: OpenJDK 11+ (for OpenDaylight controller)

## Installation Methods

### Method 1: Quick Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/mininet-web-framework.git
cd mininet-web-framework

# Run the automated setup script
chmod +x setup.sh
sudo ./setup.sh --full

# Start all services
./start-all.sh
```

### Method 2: Manual Installation

#### Step 1: System Dependencies

**Ubuntu/Debian:**
```bash
# Update package manager
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3 python3-pip python3-venv \
    nodejs npm \
    git curl wget \
    build-essential \
    openvswitch-switch \
    net-tools iputils-ping traceroute \
    iperf3 tcpdump wireshark-common

# Install Mininet
sudo apt install -y mininet

# Verify Mininet installation
sudo mn --test pingall
```

**CentOS/RHEL:**
```bash
# Enable EPEL repository
sudo dnf install -y epel-release

# Install system dependencies
sudo dnf install -y \
    python3 python3-pip \
    nodejs npm \
    git curl wget \
    gcc gcc-c++ make \
    openvswitch \
    net-tools iputils traceroute \
    iperf3 tcpdump wireshark-common

# Install Mininet from source
git clone https://github.com/mininet/mininet
cd mininet
git checkout -b mininet-2.3.1 2.3.1
./util/install.sh -nfv
cd ..
```

#### Step 2: Python Environment Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# Install MCP server dependencies
cd mcp_server
pip install -r requirements_mcp.txt
cd ..
```

#### Step 3: Frontend Setup

```bash
cd frontend

# Install Node.js dependencies
npm install

# Build production version (optional)
npm run build

cd ..
```

#### Step 4: Database Setup (Optional)

**MongoDB (for persistence features):**
```bash
# Ubuntu/Debian
sudo apt install -y mongodb
sudo systemctl start mongodb
sudo systemctl enable mongodb

# CentOS/RHEL
sudo dnf install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod

# Test connection
mongo --eval "db.version()"
```

#### Step 5: SDN Controller Setup (Optional)

**Ryu Controller:**
```bash
# Install Ryu
pip install ryu

# Test installation
ryu-manager --version
```

**POX Controller:**
```bash
# Clone POX
git clone https://github.com/noxrepo/pox
cd pox
git checkout dart
cd ..
```

**OpenDaylight Controller (Docker):**
```bash
# Pull OpenDaylight image
docker pull opendaylight/odl:latest

# Create Docker network
docker network create odl-network

# Run OpenDaylight
docker run -d --name odl \
  --network odl-network \
  -p 8181:8181 -p 6633:6633 -p 8080:8080 \
  opendaylight/odl:latest
```

### Method 3: Docker Setup

#### Using Docker Compose
```bash
# Clone repository
git clone https://github.com/your-org/mininet-web-framework.git
cd mininet-web-framework

# Copy environment file
cp env.example .env

# Edit environment variables
nano .env

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

#### Docker Environment Variables (.env)
```bash
# Flask Backend Configuration
FLASK_ENV=production
FLASK_DEBUG=false
FLASK_PORT=5000

# Frontend Configuration
REACT_APP_API_URL=http://localhost:5000
REACT_APP_MCP_URL=http://localhost:3001

# Database Configuration
MONGODB_URI=mongodb://localhost:27017/mininet_db
MONGODB_DATABASE=mininet_web

# MCP Server Configuration
MCP_SERVER_PORT=3001
MCP_FLASK_URL=http://backend:5000

# Controller Configuration
RYU_APP=simple_switch_13
CONTROLLER_HOST=0.0.0.0
CONTROLLER_PORT=6633

# LLM Configuration (Optional)
OPENAI_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
OLLAMA_URL=http://localhost:11434
```

## Configuration

### Backend Configuration

#### Flask Application (backend/config.py)
```python
import os

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # Database settings
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017'
    MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE') or 'mininet_web'
    
    # Mininet settings
    MININET_AUTO_CLEANUP = True
    MININET_LOG_LEVEL = 'info'
    
    # Controller settings
    DEFAULT_CONTROLLER = 'ryu'
    CONTROLLER_TIMEOUT = 30
    
    # Performance settings
    STATS_COLLECTION_INTERVAL = 3
    METRICS_HISTORY_LIMIT = 100
```

#### Logging Configuration (backend/logging.yaml)
```yaml
version: 1
formatters:
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    datefmt: '%Y-%m-%d %H:%M:%S'

handlers:
  console:
    class: logging.StreamHandler
    formatter: detailed
    level: INFO
  
  file:
    class: logging.FileHandler
    filename: '/var/log/mininet-web/app.log'
    formatter: detailed
    level: DEBUG

loggers:
  mininet_web:
    handlers: [console, file]
    level: DEBUG
    propagate: false

root:
  level: INFO
  handlers: [console]
```

### Frontend Configuration

#### Environment Configuration (.env.local)
```bash
# API Configuration
REACT_APP_API_URL=http://localhost:5000
REACT_APP_WS_URL=ws://localhost:5000

# Feature Flags
REACT_APP_ENABLE_DIAGNOSTICS=true
REACT_APP_ENABLE_PERFORMANCE=true
REACT_APP_ENABLE_LLM=true

# Polling Intervals (milliseconds)
REACT_APP_STATUS_INTERVAL=3000
REACT_APP_METRICS_INTERVAL=3000
REACT_APP_LOGS_INTERVAL=9000

# UI Configuration
REACT_APP_DEFAULT_THEME=dark
REACT_APP_ENABLE_ANIMATIONS=true
```

### MCP Server Configuration

#### FastMCP Configuration (mcp_server/config.yaml)
```yaml
# Server Configuration
server:
  host: "0.0.0.0"
  port: 3001
  debug: true
  log_level: "INFO"

# Flask Backend
flask:
  url: "http://localhost:5000"
  timeout: 30
  retry_attempts: 3

# MCP Servers
mcp_servers:
  mininet-controller:
    name: "Mininet Network Controller"
    description: "MCP server for Mininet network simulation control"
    command: ["python3", "fastmcp_server.py"]
    env:
      FLASK_URL: "http://localhost:5000"
    timeout: 30
    retry_attempts: 3

# LLM Integration
llm_services:
  default_service: "ollama"
  services:
    ollama:
      url: "http://localhost:11434"
      model: "llama3.1:8b"
    openai:
      model: "gpt-4"
      api_key_env: "OPENAI_API_KEY"
    gemini:
      model: "gemini-1.5-flash"
      api_key_env: "GEMINI_API_KEY"
```

#### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "mininet-web": {
      "command": "python3",
      "args": ["/path/to/mininet-web-framework/mcp_server/fastmcp_server.py"],
      "env": {
        "FLASK_URL": "http://localhost:5000"
      },
      "cwd": "/path/to/mininet-web-framework/mcp_server"
    }
  }
}
```

## Service Configuration

### Systemd Services

#### Backend Service (mininet-web-backend.service)
```ini
[Unit]
Description=Mininet Web Framework Backend
After=network.target mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/mininet-web-framework/backend
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Frontend Service (mininet-web-frontend.service)
```ini
[Unit]
Description=Mininet Web Framework Frontend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/mininet-web-framework/frontend
ExecStart=/usr/bin/npm start
Environment=NODE_ENV=production
Environment=PORT=3000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### MCP Server Service (mininet-mcp-server.service)
```ini
[Unit]
Description=Mininet MCP Server
After=network.target mininet-web-backend.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/mininet-web-framework/mcp_server
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python fastmcp_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Install and Enable Services
```bash
# Copy service files
sudo cp *.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable mininet-web-backend
sudo systemctl enable mininet-web-frontend
sudo systemctl enable mininet-mcp-server

# Start services
sudo systemctl start mininet-web-backend
sudo systemctl start mininet-web-frontend
sudo systemctl start mininet-mcp-server

# Check status
sudo systemctl status mininet-web-*
```

## Network Configuration

### Open vSwitch Setup
```bash
# Install OVS
sudo apt install -y openvswitch-switch

# Configure OVS
sudo ovs-vsctl set-manager ptcp:6640
sudo ovs-vsctl set bridge br0 protocols=OpenFlow13

# Start OVS services
sudo systemctl enable openvswitch-switch
sudo systemctl start openvswitch-switch
```

### Firewall Configuration
```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 3000/tcp  # Frontend
sudo ufw allow 5000/tcp  # Backend API
sudo ufw allow 3001/tcp  # MCP Server
sudo ufw allow 6633/tcp  # OpenFlow
sudo ufw allow 8181/tcp  # ODL REST API
sudo ufw reload

# CentOS/RHEL (FirewallD)
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --permanent --add-port=3001/tcp
sudo firewall-cmd --permanent --add-port=6633/tcp
sudo firewall-cmd --permanent --add-port=8181/tcp
sudo firewall-cmd --reload
```

## Verification and Testing

### System Health Check
```bash
#!/bin/bash
# health-check.sh

echo "=== System Health Check ==="

# Check Python version
echo "Python version:"
python3 --version

# Check Node.js version
echo "Node.js version:"
node --version

# Check Mininet
echo "Testing Mininet:"
sudo mn --test pingall

# Check OVS
echo "Open vSwitch status:"
sudo ovs-vsctl show

# Check services
echo "Service status:"
sudo systemctl status mininet-web-backend --no-pager -l
sudo systemctl status mininet-web-frontend --no-pager -l
sudo systemctl status mininet-mcp-server --no-pager -l

# Check ports
echo "Port availability:"
netstat -tulpn | grep -E ':(3000|5000|3001|6633)'

# Test API endpoints
echo "API endpoint test:"
curl -s http://localhost:5000/api/test | jq .
curl -s http://localhost:5000/api/status | jq .

echo "=== Health Check Complete ==="
```

### Performance Verification
```bash
# Test network creation performance
time curl -X POST http://localhost:5000/api/network/create \
  -H "Content-Type: application/json" \
  -d '{"type": "linear", "hosts": 4}'

# Test frontend loading
curl -s -o /dev/null -w "%{time_total}" http://localhost:3000

# Test MCP server
curl -s http://localhost:3001/health
```

### Integration Tests
```bash
cd tests/

# Run backend tests
python -m pytest backend_tests.py -v

# Run frontend tests
npm test -- --watchAll=false

# Run MCP server tests
python test_mcp_server.py

# Run end-to-end tests
python e2e_tests.py
```

## Security Configuration

### SSL/TLS Setup (Production)

#### Generate Certificates
```bash
# Create SSL directory
sudo mkdir -p /etc/mininet-web/ssl

# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/mininet-web/ssl/private.key \
  -out /etc/mininet-web/ssl/certificate.crt

# Set permissions
sudo chmod 600 /etc/mininet-web/ssl/private.key
sudo chmod 644 /etc/mininet-web/ssl/certificate.crt
```

#### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /etc/mininet-web/ssl/certificate.crt;
    ssl_certificate_key /etc/mininet-web/ssl/private.key;
    
    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # MCP Server
    location /mcp/ {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting Common Issues

### Permission Issues
```bash
# Fix Mininet permissions
sudo usermod -a -G mininet $USER
newgrp mininet

# Fix file permissions
sudo chown -R $USER:$USER /path/to/mininet-web-framework
chmod +x backend/app.py
chmod +x mcp_server/*.py
```

### Port Conflicts
```bash
# Check port usage
sudo netstat -tulpn | grep -E ':(3000|5000|3001)'

# Kill processes using ports
sudo fuser -k 3000/tcp
sudo fuser -k 5000/tcp
sudo fuser -k 3001/tcp
```

### Service Dependencies
```bash
# Check service logs
journalctl -u mininet-web-backend -f
journalctl -u mininet-web-frontend -f
journalctl -u mininet-mcp-server -f

# Restart services in order
sudo systemctl restart mininet-web-backend
sleep 5
sudo systemctl restart mininet-mcp-server
sleep 5
sudo systemctl restart mininet-web-frontend
```

## Quick Start Commands

```bash
# Development mode
cd mininet-web-framework

# Terminal 1: Backend
cd backend && sudo python app.py

# Terminal 2: Frontend
cd frontend && npm start

# Terminal 3: MCP Server
cd mcp_server && python fastmcp_server.py

# Terminal 4: Test the setup
curl http://localhost:5000/api/status
open http://localhost:3000
```

## Next Steps

After successful installation:

1. **Read the Usage Guide**: Check `docs/USAGE.md` for examples
2. **Explore the API**: Review `docs/API.md` for endpoint details
3. **Review Architecture**: Study `docs/ARCHITECTURE.md` for system design
4. **Check Troubleshooting**: See `docs/TROUBLESHOOTING.md` for common issues
5. **Set up AI Integration**: Configure Claude or other AI assistants with MCP

## Support

- **Documentation**: Full documentation in the `docs/` directory
- **Examples**: Sample configurations in the `examples/` directory
- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: GitHub Discussions for questions and community support