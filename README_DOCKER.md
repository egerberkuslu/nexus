# Mininet Web Framework - Docker Deployment Guide

This guide provides comprehensive instructions for deploying the Mininet Web Framework using Docker with full SDN controller support.

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 4GB RAM available for containers
- Linux host (required for Mininet networking)

### Start All Services (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd mininet-web-framework

# Start all services with SDN controllers
./docker-manage.sh start
```

This will start:
- **MongoDB** (port 27017)
- **Backend API** (port 5000) with all SDN controllers
- **Frontend** (port 3000)
- **OpenDaylight** (ports 8181, 8101, 6633)

### Access the Application

- **Web Interface**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **OpenDaylight REST API**: http://localhost:8181
- **OpenDaylight SSH**: localhost:8101 (karaf/karaf)

## 🎛️ Management Commands

The `docker-manage.sh` script provides easy management:

```bash
# Start all services with controllers
./docker-manage.sh start

# Start basic services only (no controllers)
./docker-manage.sh start-basic

# Check service status
./docker-manage.sh status

# View logs
./docker-manage.sh logs
./docker-manage.sh logs backend

# Test OpenDaylight installation
./docker-manage.sh test-odl

# Stop all services
./docker-manage.sh stop

# Restart all services
./docker-manage.sh restart

# Clean up everything
./docker-manage.sh clean
```

## 🏗️ Architecture

### Services Overview

| Service | Port | Description |
|---------|------|-------------|
| MongoDB | 27017 | Database for storing network configurations |
| Backend | 5000 | Flask API with Mininet and SDN controllers |
| Frontend | 3000 | React web interface |
| OpenDaylight | 8181 | REST API for network management |
| OpenDaylight | 8101 | SSH/Karaf console |
| OpenFlow | 6633 | OpenFlow protocol for switches |

### SDN Controllers Included

1. **OpenDaylight** (Primary)
   - Full REST API support
   - OpenFlow 1.3 support
   - L2 switching capabilities
   - Karaf-based modular architecture

2. **Ryu** (Python-based)
   - Lightweight and fast
   - OpenFlow 1.3 support
   - Easy to extend with custom applications

3. **POX** (Python-based)
   - Educational and research focused
   - Simple controller framework
   - Good for learning SDN concepts

4. **os-ken** (Ryu replacement)
   - Official OpenStack controller
   - Production-ready
   - High performance

## 🔧 Configuration

### Environment Variables

The following environment variables can be customized:

```bash
# Database
MONGODB_URI=mongodb://mongodb:27017/
DATABASE_NAME=mininet_web_framework

# Application
FLASK_ENV=production
PYTHONPATH=/app

# Controllers
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
POX_HOME=/opt/pox
ODL_HOME=/opt/opendaylight
```

### OpenDaylight Configuration

OpenDaylight is pre-configured with the following features:
- `odl-restconf-all` - REST API
- `odl-openflowjava-protocol` - OpenFlow support
- `odl-openflowplugin-app-table-miss-enforcer` - Flow management
- `odl-openflowplugin-flow-services` - Flow services

### Memory Settings

OpenDaylight is configured with:
- Initial memory: 512MB
- Maximum memory: 2048MB

## 🐛 Troubleshooting

### Common Issues

#### 1. OpenDaylight Not Starting

```bash
# Check OpenDaylight logs
./docker-manage.sh logs backend

# Test OpenDaylight installation
./docker-manage.sh test-odl

# Check Java installation
docker-compose exec backend java -version
```

#### 2. Port Conflicts

If you have port conflicts, modify the ports in `docker-compose.yml`:

```yaml
ports:
  - "5001:5000"  # Change backend port
  - "3001:80"    # Change frontend port
  - "8182:8181"  # Change OpenDaylight REST port
```

#### 3. Permission Issues

The containers run with elevated privileges for networking:

```bash
# Check if containers have proper permissions
docker-compose exec backend whoami
docker-compose exec backend ls -la /dev/net/tun
```

#### 4. Memory Issues

If OpenDaylight fails to start due to memory:

```bash
# Check available memory
docker stats

# Reduce OpenDaylight memory in Dockerfile.controllers
echo "wrapper.java.maxmemory=1024" >> /opt/opendaylight/etc/custom.properties
```

### Health Checks

All services include health checks:

```bash
# Check service health
./docker-manage.sh status

# Manual health check
curl -f http://localhost:5000/api/status
curl -f http://localhost:8181/restconf/operational/system
```

## 📊 Monitoring

### Service Status

```bash
# Real-time status
./docker-manage.sh status

# Container resource usage
docker stats

# Service logs
./docker-manage.sh logs
```

### OpenDaylight Monitoring

```bash
# Check OpenDaylight features
docker-compose exec backend /opt/opendaylight/bin/client -h 127.0.0.1 -a 8101 -u karaf -p karaf "feature:list -i"

# Check OpenDaylight nodes
curl http://localhost:8181/restconf/operational/opendaylight-inventory:nodes
```

## 🔄 Development

### Building from Source

```bash
# Build with latest changes
docker-compose build --no-cache

# Rebuild specific service
docker-compose build backend
```

### Adding Custom Controllers

1. Add controller installation to `backend/Dockerfile.controllers`
2. Update controller factory in `backend/core/factories/controller_factory.py`
3. Add controller routes in `backend/api/`
4. Rebuild the container

### Debugging

```bash
# Access container shell
docker-compose exec backend bash

# Check OpenDaylight status
docker-compose exec backend /opt/opendaylight/bin/client -h 127.0.0.1 -a 8101 -u karaf -p karaf "feature:list"

# Test Mininet
docker-compose exec backend python3 -c "from mininet.net import Mininet; print('Mininet OK')"
```

## 📝 Logs

### Log Locations

- **Backend**: `docker-compose logs backend`
- **OpenDaylight**: `/opt/opendaylight/data/log/karaf.log`
- **MongoDB**: `docker-compose logs mongodb`
- **Frontend**: `docker-compose logs frontend`

### Log Levels

Configure log levels in the application:
- Backend: Set `FLASK_ENV=development` for debug logs
- OpenDaylight: Modify `log4j2.xml` in `/opt/opendaylight/etc/`

## 🚀 Production Deployment

### Security Considerations

1. **Change default passwords**:
   ```bash
   # Change OpenDaylight SSH password
   docker-compose exec backend /opt/opendaylight/bin/client -h 127.0.0.1 -a 8101 -u karaf -p karaf "jaas:manage --realm karaf --user karaf --password newpassword"
   ```

2. **Use secrets management**:
   ```yaml
   environment:
     - MONGODB_URI=${MONGODB_URI}
     - SECRET_KEY=${SECRET_KEY}
   ```

3. **Network security**:
   - Use reverse proxy (nginx/traefik)
   - Enable HTTPS
   - Restrict port access

### Performance Tuning

1. **Increase OpenDaylight memory**:
   ```bash
   # Edit Dockerfile.controllers
   echo "wrapper.java.maxmemory=4096" >> /opt/opendaylight/etc/custom.properties
   ```

2. **Optimize MongoDB**:
   ```yaml
   environment:
     - MONGO_INITDB_ROOT_USERNAME=admin
     - MONGO_INITDB_ROOT_PASSWORD=password
   ```

3. **Use production images**:
   ```dockerfile
   FROM node:18-alpine  # Smaller frontend image
   FROM python:3.9-slim  # Smaller backend image
   ```

## 📚 Additional Resources

- [OpenDaylight Documentation](https://docs.opendaylight.org/)
- [Mininet Documentation](http://mininet.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [SDN Controller Comparison](https://www.opennetworking.org/sdn-resources/sdn-tools/)

## 🤝 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the logs: `./docker-manage.sh logs`
3. Test individual components: `./docker-manage.sh test-odl`
4. Create an issue with logs and system information