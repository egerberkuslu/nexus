# Mininet Web Framework Troubleshooting Guide

## Quick Diagnostic Commands

Before diving into specific issues, run these commands to get an overview of your system:

```bash
# System health check script
#!/bin/bash
echo "=== Mininet Web Framework Health Check ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Not running as root (required for Mininet)"
else
    echo "✅ Running as root"
fi

# Check service status
echo -e "\n--- Service Status ---"
curl -s http://localhost:5000/api/status | jq . 2>/dev/null || echo "❌ Backend not responding"
curl -s http://localhost:3000 >/dev/null 2>&1 && echo "✅ Frontend accessible" || echo "❌ Frontend not accessible"
curl -s http://localhost:3001/health >/dev/null 2>&1 && echo "✅ MCP Server accessible" || echo "❌ MCP Server not accessible"

# Check ports
echo -e "\n--- Port Status ---"
netstat -tulpn | grep -E ':(3000|5000|3001|6633)' | while read line; do
    echo "✅ $line"
done

# Check processes
echo -e "\n--- Process Status ---"
ps aux | grep -E '(python.*app.py|npm start|node.*mcp)' | grep -v grep

# Check Mininet
echo -e "\n--- Mininet Status ---"
sudo mn --test pingall 2>/dev/null >/dev/null && echo "✅ Mininet working" || echo "❌ Mininet not working"

# Check OVS
echo -e "\n--- Open vSwitch Status ---"
sudo ovs-vsctl show 2>/dev/null >/dev/null && echo "✅ OVS available" || echo "❌ OVS not available"

echo -e "\n=== Health Check Complete ==="
```

## Common Issues and Solutions

### 1. Installation Issues

#### Problem: Permission Denied Errors
```
Error: EACCES: permission denied, access '/usr/local/lib/node_modules'
```

**Solution:**
```bash
# Fix npm permissions
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.profile
source ~/.profile

# Or install with proper permissions
sudo npm install -g --unsafe-perm
```

#### Problem: Python Package Installation Fails
```
Error: Microsoft Visual C++ 14.0 is required
```

**Solution:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install build-essential python3-dev

# CentOS/RHEL
sudo dnf groupinstall "Development Tools"
sudo dnf install python3-devel

# Retry installation
pip install -r requirements.txt
```

#### Problem: Mininet Installation Fails
```
Error: Unable to find Mininet installation
```

**Solution:**
```bash
# Ubuntu/Debian - Install from package manager
sudo apt update
sudo apt install mininet

# Or install from source
git clone https://github.com/mininet/mininet
cd mininet
git checkout -b mininet-2.3.1 2.3.1
./util/install.sh -nfv

# Verify installation
sudo mn --version
sudo mn --test pingall
```

### 2. Service Startup Issues

#### Problem: Backend Won't Start
```
Error: Address already in use: 5000
```

**Solution:**
```bash
# Find process using port 5000
sudo netstat -tulpn | grep :5000
sudo lsof -i :5000

# Kill the process
sudo fuser -k 5000/tcp

# Or change port in backend configuration
export FLASK_PORT=5001
python backend/app.py
```

#### Problem: Frontend Build Fails
```
Error: Node Sass version 8.0.0 is incompatible with ^4.0.0
```

**Solution:**
```bash
# Clear node modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

# Or rebuild node-sass
npm rebuild node-sass

# Update if necessary
npm update
```

#### Problem: Root Permission Issues
```
Error: Mininet must run as root
```

**Solution:**
```bash
# Run backend as root
sudo python backend/app.py

# Or configure sudo for specific operations
echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/mn, /usr/bin/ovs-vsctl" | sudo tee /etc/sudoers.d/mininet

# Add user to mininet group
sudo groupadd mininet
sudo usermod -a -G mininet $USER
```

### 3. Network Creation Issues

#### Problem: Network Creation Fails
```
Error: Cannot create network: topology validation failed
```

**Diagnosis:**
```bash
# Check topology configuration
curl -X POST http://localhost:5000/api/topology/validate \
  -H "Content-Type: application/json" \
  -d @your-topology.json

# Check available resources
free -h
df -h /tmp
```

**Solution:**
```bash
# Fix common topology issues:

# 1. Invalid IP addresses
# Ensure all IPs are in valid format and ranges
{
  "hosts": [
    {"name": "h1", "ip": "10.0.1.1/24"},  # ✅ Correct format
    {"name": "h2", "ip": "10.0.1.2"}      # ❌ Missing subnet mask
  ]
}

# 2. Duplicate device names
# Ensure all device names are unique
{
  "hosts": [
    {"name": "h1", "ip": "10.0.1.1/24"},
    {"name": "h1", "ip": "10.0.1.2/24"}   # ❌ Duplicate name
  ]
}

# 3. Invalid links
# Ensure links reference existing devices
{
  "links": [
    {"source": "h1", "target": "s1"},     # ✅ Both exist
    {"source": "h1", "target": "s999"}    # ❌ s999 doesn't exist
  ]
}
```

#### Problem: Controller Connection Fails
```
Error: Controller not reachable at 127.0.0.1:6633
```

**Diagnosis:**
```bash
# Check if controller is running
sudo netstat -tulpn | grep :6633
ps aux | grep ryu

# Test controller connectivity
telnet 127.0.0.1 6633

# Check controller logs
tail -f /var/log/ryu/ryu.log
```

**Solution:**
```bash
# Start Ryu controller manually
ryu-manager ryu.app.simple_switch_13 &

# Or use different controller
curl -X POST http://localhost:5000/api/controller/start \
  -H "Content-Type: application/json" \
  -d '{
    "controller_type": "pox",
    "port": 6633
  }'

# Check firewall settings
sudo ufw status
sudo iptables -L | grep 6633
```

#### Problem: Switches Don't Connect to Controller
```
Warning: Switch s1 not connected to controller
```

**Diagnosis:**
```bash
# Check switch status
sudo ovs-vsctl show
sudo ovs-vsctl get-controller s1

# Check OpenFlow version compatibility
sudo ovs-vsctl get bridge s1 protocols
```

**Solution:**
```bash
# Manually set controller
sudo ovs-vsctl set-controller s1 tcp:127.0.0.1:6633

# Set OpenFlow version
sudo ovs-vsctl set bridge s1 protocols=OpenFlow13

# Restart switches
sudo ovs-vsctl del-br s1
# Recreate network through API
```

### 4. Performance Issues

#### Problem: High Latency Between Hosts
```
Latency > 100ms between h1 and h2 (expected < 10ms)
```

**Diagnosis:**
```bash
# Trace network path
curl -X POST http://localhost:5000/api/diagnostic/traceroute \
  -H "Content-Type: application/json" \
  -d '{"src": "h1", "dst": "h2"}'

# Check system resources
top
iotop
free -h
```

**Solution:**
```bash
# 1. Reduce system load
# Kill unnecessary processes
sudo killall chrome firefox

# 2. Optimize network settings
# Increase buffer sizes
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
sudo sysctl -p

# 3. Check for software switches overwhelming CPU
# Monitor CPU usage of switch processes
pidstat -u 1 | grep ovs

# 4. Use hardware timestamping if available
sudo ovs-vsctl set Interface veth1 other_config:enable-hardware-timestamp=true
```

#### Problem: Low Bandwidth Performance
```
Bandwidth: 100 Mbps (expected > 900 Mbps)
```

**Diagnosis:**
```bash
# Check link configuration
curl -X GET http://localhost:5000/api/topology/links

# Check interface statistics
sudo ovs-ofctl dump-ports s1

# Monitor system performance
sar -n DEV 1 10
```

**Solution:**
```bash
# 1. Check link bandwidth limits
curl -X POST http://localhost:5000/api/network/links/modify \
  -H "Content-Type: application/json" \
  -d '{
    "src": "s1",
    "dst": "s2", 
    "bandwidth": "1Gbps"
  }'

# 2. Optimize TCP settings
echo 'net.ipv4.tcp_congestion_control = bbr' >> /etc/sysctl.conf
echo 'net.core.default_qdisc = fq' >> /etc/sysctl.conf
sudo sysctl -p

# 3. Use multiple flows for testing
curl -X POST http://localhost:5000/api/performance/test/stress \
  -H "Content-Type: application/json" \
  -d '{
    "duration": 30,
    "concurrent_flows": 4
  }'
```

### 5. API Connection Issues

#### Problem: API Returns 500 Internal Server Error
```
Error: Internal server error when calling /api/network/status
```

**Diagnosis:**
```bash
# Check backend logs
tail -f backend/logs/app.log
journalctl -u mininet-web-backend -f

# Check Python environment
python3 -c "import flask, mininet; print('OK')"

# Test API manually
curl -v http://localhost:5000/api/test
```

**Solution:**
```bash
# 1. Restart backend service
sudo systemctl restart mininet-web-backend

# Or manually
sudo pkill -f "python.*app.py"
cd backend && sudo python app.py

# 2. Check dependencies
pip install -r requirements.txt --force-reinstall

# 3. Clear Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# 4. Check database connection
mongo --eval "db.version()" # If using MongoDB
```

#### Problem: CORS Errors in Browser
```
Error: Access-Control-Allow-Origin header is missing
```

**Solution:**
```python
# Check backend CORS configuration
from flask_cors import CORS
app = Flask(__name__)
CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])
```

```bash
# Or start backend with CORS enabled
FLASK_CORS_ORIGINS="http://localhost:3000" python backend/app.py
```

### 6. MCP Server Issues

#### Problem: MCP Server Not Responding
```
Error: MCP server connection timeout
```

**Diagnosis:**
```bash
# Check MCP server process
ps aux | grep mcp_server
ps aux | grep fastmcp

# Check port availability
netstat -tulpn | grep :3001

# Test MCP server directly
curl http://localhost:3001/health
```

**Solution:**
```bash
# 1. Restart MCP server
cd mcp_server
python3 fastmcp_server.py &

# 2. Check configuration
cat config.yaml
export FLASK_URL="http://localhost:5000"

# 3. Install dependencies
pip install -r requirements_mcp.txt

# 4. Check backend connectivity from MCP server
curl http://localhost:5000/api/status
```

#### Problem: AI Assistant Can't Connect to MCP
```
Error: Failed to connect to MCP server
```

**Solution:**
```json
// Check Claude Desktop configuration
{
  "mcpServers": {
    "mininet-web": {
      "command": "python3",
      "args": ["/full/path/to/fastmcp_server.py"],
      "env": {
        "FLASK_URL": "http://localhost:5000"
      },
      "cwd": "/full/path/to/mcp_server"
    }
  }
}
```

```bash
# Test MCP server with inspector
npx @modelcontextprotocol/inspector python3 fastmcp_server.py

# Check MCP protocol compliance
node test_mcp_protocol.js
```

### 7. Frontend Issues

#### Problem: Frontend Won't Load
```
Error: This site can't be reached
```

**Diagnosis:**
```bash
# Check if React dev server is running
ps aux | grep "npm start"
netstat -tulpn | grep :3000

# Check for build errors
cd frontend
npm run build
```

**Solution:**
```bash
# 1. Restart frontend
cd frontend
npm start

# 2. Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

# 3. Check for port conflicts
sudo fuser -k 3000/tcp
PORT=3001 npm start

# 4. Build and serve static files
npm run build
sudo python3 -m http.server 3000 -d build
```

#### Problem: API Calls Fail from Frontend
```
Error: Network Error when calling backend API
```

**Solution:**
```javascript
// Check API URL configuration
// In .env.local
REACT_APP_API_URL=http://localhost:5000

// In your code
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';
```

```bash
# Test API from frontend host
curl -X GET http://localhost:5000/api/status
```

### 8. Database and Storage Issues

#### Problem: MongoDB Connection Failed
```
Error: Could not connect to MongoDB
```

**Solution:**
```bash
# 1. Start MongoDB service
sudo systemctl start mongod
sudo systemctl enable mongod

# 2. Check MongoDB status
sudo systemctl status mongod
mongo --eval "db.version()"

# 3. Check configuration
cat /etc/mongod.conf
sudo tail -f /var/log/mongodb/mongod.log

# 4. Create database and collections
mongo
use mininet_web
db.createCollection("topologies")
db.createCollection("snapshots")
```

#### Problem: Snapshot Creation Fails
```
Error: Failed to create network snapshot
```

**Solution:**
```bash
# Check available disk space
df -h /tmp
df -h /var/lib/mongodb

# Check permissions
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chmod 755 /var/lib/mongodb

# Clear old snapshots
curl -X GET http://localhost:5000/api/snapshots/list
# Delete old snapshots via API
```

### 9. Performance and Monitoring Issues

#### Problem: High CPU Usage
```
CPU usage consistently > 90%
```

**Diagnosis:**
```bash
# Identify CPU-intensive processes
top -c
htop
pidstat -u 2 5

# Check system load
uptime
sar -u 1 10
```

**Solution:**
```bash
# 1. Optimize network size
# Reduce number of hosts/switches in topology

# 2. Tune polling intervals
# In frontend .env
REACT_APP_STATUS_INTERVAL=10000  # Increase from 3000ms
REACT_APP_METRICS_INTERVAL=10000

# 3. Limit monitoring scope
curl -X POST http://localhost:5000/api/stats/monitoring/start \
  -H "Content-Type: application/json" \
  -d '{
    "interval": 10,
    "devices": ["s1", "s2"]
  }'

# 4. Use performance mode
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

#### Problem: Memory Leaks
```
Memory usage continuously increasing
```

**Solution:**
```bash
# Monitor memory usage
watch -n 1 'free -h'
pmap -x <pid>

# Clear Python caches
python3 -c "
import gc
gc.collect()
"

# Restart services periodically
# Add to crontab
0 */6 * * * systemctl restart mininet-web-backend
```

### 10. Security Issues

#### Problem: Firewall Blocking Connections
```
Error: Connection refused
```

**Solution:**
```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 3000/tcp comment "Frontend"
sudo ufw allow 5000/tcp comment "Backend API"
sudo ufw allow 3001/tcp comment "MCP Server"
sudo ufw allow 6633/tcp comment "OpenFlow"
sudo ufw reload

# CentOS/RHEL (FirewallD)
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --permanent --add-port=3001/tcp
sudo firewall-cmd --permanent --add-port=6633/tcp
sudo firewall-cmd --reload

# Check rules
sudo ufw status verbose
sudo firewall-cmd --list-all
```

#### Problem: SSL/TLS Certificate Issues
```
Error: certificate verify failed
```

**Solution:**
```bash
# Generate self-signed certificate
sudo mkdir -p /etc/ssl/mininet-web
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/mininet-web/private.key \
  -out /etc/ssl/mininet-web/certificate.crt

# Configure Flask for SSL
export FLASK_SSL_CERT="/etc/ssl/mininet-web/certificate.crt"
export FLASK_SSL_KEY="/etc/ssl/mininet-web/private.key"

# Or disable SSL verification for development
export PYTHONHTTPSVERIFY=0
```

## Logging and Debugging

### Enable Debug Logging

```bash
# Backend debug logging
export FLASK_ENV=development
export FLASK_DEBUG=1
python backend/app.py

# Frontend debug mode
REACT_APP_DEBUG=1 npm start

# MCP Server debug logging
DEBUG=1 python mcp_server/fastmcp_server.py
```

### Log File Locations

```bash
# Application logs
tail -f backend/logs/app.log
tail -f frontend/logs/npm-debug.log
tail -f mcp_server/logs/mcp.log

# System logs
sudo journalctl -u mininet-web-backend -f
sudo journalctl -u mininet-web-frontend -f
sudo tail -f /var/log/openvswitch/ovs-vswitchd.log
sudo tail -f /var/log/ryu/ryu.log
```

### Debug Network Issues

```bash
# Packet capture
sudo tcpdump -i any -w network-debug.pcap
sudo tshark -i any -f "tcp port 6633"

# OpenFlow debugging
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
sudo ovs-ofctl monitor s1 watch:

# Network namespace debugging
sudo ip netns list
sudo ip netns exec h1 ping 10.0.1.2
```

## Performance Optimization

### System Tuning

```bash
# Network performance tuning
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.netdev_max_backlog = 5000' >> /etc/sysctl.conf
sudo sysctl -p

# Disable swap for better performance
sudo swapoff -a

# CPU frequency scaling
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Application Optimization

```python
# Backend optimization
# Use gunicorn for production
pip install gunicorn
gunicorn --workers 4 --bind 0.0.0.0:5000 app:app

# Frontend optimization
# Build for production
npm run build
serve -s build -p 3000
```

## Emergency Procedures

### Complete System Reset

```bash
#!/bin/bash
# emergency_reset.sh

echo "Performing emergency system reset..."

# Stop all services
sudo pkill -f "python.*app.py"
sudo pkill -f "npm start"
sudo pkill -f "node.*mcp"
sudo pkill -f "ryu-manager"

# Clean Mininet
sudo mn -c

# Reset OVS
sudo ovs-vsctl --all destroy
sudo systemctl restart openvswitch-switch

# Clear logs
sudo rm -f /tmp/mn-*
sudo rm -f backend/logs/*.log
sudo rm -f mcp_server/logs/*.log

# Reset database (if needed)
mongo --eval "db.dropDatabase()" mininet_web

echo "System reset complete. Restart services manually."
```

### Data Recovery

```bash
# Recover from snapshots
curl -X GET http://localhost:5000/api/snapshots/list
curl -X POST http://localhost:5000/api/snapshots/restore \
  -H "Content-Type: application/json" \
  -d '{"snapshot_id": "latest_working_snapshot"}'

# Export current configuration before reset
curl -X GET http://localhost:5000/api/topology/export > backup.json
```

## Getting Help

### Collect System Information

```bash
#!/bin/bash
# collect_debug_info.sh

echo "Collecting debug information..."

# System info
uname -a > debug_info.txt
cat /etc/os-release >> debug_info.txt
free -h >> debug_info.txt
df -h >> debug_info.txt

# Service status
systemctl status mininet-web-* >> debug_info.txt
ps aux | grep -E "(python|npm|node)" >> debug_info.txt

# Network info
sudo ovs-vsctl show >> debug_info.txt
netstat -tulpn >> debug_info.txt

# Logs (last 100 lines)
tail -n 100 backend/logs/app.log >> debug_info.txt
tail -n 100 /var/log/syslog | grep mininet >> debug_info.txt

echo "Debug info collected in debug_info.txt"
```

### Contact Support

When reporting issues, please include:

1. **System Information**: OS version, Python version, Node.js version
2. **Error Messages**: Complete error messages and stack traces
3. **Configuration**: Network topology configuration, if relevant
4. **Steps to Reproduce**: Exact steps that led to the issue
5. **Log Files**: Relevant log entries from services
6. **Debug Information**: Output from debug commands above

### Community Resources

- **Documentation**: Check the complete documentation in the `docs/` directory
- **Examples**: Review example configurations in the `examples/` directory
- **GitHub Issues**: Search existing issues or create new ones
- **GitHub Discussions**: Ask questions and share solutions

### Known Issues and Workarounds

#### Issue: High Memory Usage with Large Topologies
**Workaround**: Implement topology pagination and lazy loading

#### Issue: Controller Disconnect After Extended Use
**Workaround**: Implement automatic controller restart mechanism

#### Issue: Frontend Becomes Unresponsive with Many Updates
**Workaround**: Implement update throttling and virtual scrolling

This troubleshooting guide covers the most common issues and their solutions. Keep it bookmarked for quick reference when problems arise.