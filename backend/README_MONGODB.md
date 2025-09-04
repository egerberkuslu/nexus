# MongoDB Integration for Mininet Web Framework

This document explains the MongoDB integration that allows you to save and load network topologies and device configurations.

## Features Added

### 🗄️ **Storage Capabilities**
- **Save Topologies**: Store complete network topologies with all nodes, links, and controllers
- **Save Configurations**: Store device-specific configurations (host, switch, router, controller)
- **Load Topologies**: Restore saved topologies and create them in Mininet
- **Load Configurations**: Apply saved configurations to devices
- **Export/Import**: Download saved data as JSON/YAML files

### 🔧 **Database Structure**
- **Topologies Collection**: Stores complete topology data with metadata
- **Configurations Collection**: Stores device configurations organized by type
- **Automatic Indexing**: Optimized queries with proper database indexes
- **Data Validation**: Ensures data integrity before storage

### 🌐 **API Endpoints**
```
Storage Management:
- POST /api/storage/topologies              # Save current topology
- GET  /api/storage/topologies              # List all saved topologies
- GET  /api/storage/topologies/{id}         # Get specific topology
- POST /api/storage/topologies/{id}/load    # Load topology into Mininet
- PUT  /api/storage/topologies/{id}         # Update topology
- DELETE /api/storage/topologies/{id}       # Delete topology

- POST /api/storage/configurations          # Save configuration
- GET  /api/storage/configurations          # List configurations (filter by device_type)
- GET  /api/storage/configurations/{id}     # Get specific configuration
- PUT  /api/storage/configurations/{id}     # Update configuration
- DELETE /api/storage/configurations/{id}   # Delete configuration

Export/Import:
- GET  /api/storage/export/topology/{id}    # Export topology as JSON/YAML
- GET  /api/storage/export/configuration/{id} # Export configuration as JSON/YAML
- GET  /api/storage/stats                   # Get storage statistics
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Install MongoDB
sudo apt update
sudo apt install mongodb

# Or using Docker
docker run -d --name mongodb -p 27017:27017 mongo:latest

# Install Python dependencies
cd backend
pip install -r requirements.txt
```

### 2. Start MongoDB

```bash
# Using system service
sudo systemctl start mongodb
sudo systemctl enable mongodb

# Or using Docker
docker start mongodb
```

### 3. Initialize Database

```bash
# Run the setup script
cd backend
python setup_mongodb.py
```

This script will:
- ✅ Test MongoDB connection
- ✅ Create database indexes
- ✅ Optionally create sample data

### 4. Environment Configuration (Optional)

Create a `.env` file in the backend directory:

```env
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=mininet_web_framework

# Optional: MongoDB Authentication
# MONGODB_USERNAME=your_username
# MONGODB_PASSWORD=your_password

# Application Settings
AUTO_SAVE_TOPOLOGIES=false
AUTO_SAVE_CONFIGURATIONS=false
```

## Usage Guide

### 💾 **Saving Topologies**

1. **From the Web Interface:**
   - Create a network topology
   - Click the "Storage" button in the header or control panel
   - Click "Save Current" in the topologies tab
   - Enter name and description
   - Click "Save"

2. **From API:**
   ```bash
   curl -X POST http://localhost:5000/api/storage/topologies \
     -H "Content-Type: application/json" \
     -d '{
       "name": "my_topology",
       "description": "My custom network topology",
       "topology_type": "custom"
     }'
   ```

### 📂 **Loading Topologies**

1. **From the Web Interface:**
   - Open Storage Manager
   - Browse saved topologies
   - Click "Load" on desired topology
   - Topology will be created in Mininet

2. **From API:**
   ```bash
   curl -X POST http://localhost:5000/api/storage/topologies/{id}/load
   ```

### ⚙️ **Managing Configurations**

1. **Save Device Configuration:**
   ```bash
   curl -X POST http://localhost:5000/api/storage/configurations \
     -H "Content-Type: application/json" \
     -d '{
       "name": "web_server_host",
       "description": "Host configured as web server",
       "device_type": "host",
       "configuration_data": {
         "ip": "192.168.1.100",
         "services": ["apache2", "ssh"],
         "firewall_rules": ["allow 80", "allow 22"]
       }
     }'
   ```

2. **List Configurations by Type:**
   ```bash
   # Get all host configurations
   curl http://localhost:5000/api/storage/configurations?device_type=host
   
   # Get all configurations
   curl http://localhost:5000/api/storage/configurations
   ```

### 📊 **Storage Statistics**

```bash
curl http://localhost:5000/api/storage/stats
```

Returns:
```json
{
  "success": true,
  "stats": {
    "topologies": {
      "total": 5,
      "by_type": {
        "custom": 3,
        "predefined": 2
      }
    },
    "configurations": {
      "total": 12,
      "by_device_type": {
        "host": 4,
        "switch": 3,
        "router": 3,
        "controller": 2
      }
    }
  }
}
```

## Data Models

### Topology Model
```python
{
  "_id": ObjectId,
  "name": str,                    # Unique name
  "description": str,             # Description
  "topology_data": {              # Complete topology data
    "nodes": [...],               # Network nodes
    "links": [...],               # Network links
    "controllers": [...],         # Controllers
    "stats": {...}                # Statistics
  },
  "topology_type": str,           # 'custom', 'predefined', 'simple'
  "metadata": {...},              # Additional metadata
  "created_at": datetime,
  "updated_at": datetime
}
```

### Configuration Model
```python
{
  "_id": ObjectId,
  "name": str,                    # Unique name
  "description": str,             # Description
  "device_type": str,             # 'host', 'switch', 'router', 'controller'
  "configuration_data": {...},    # Device-specific configuration
  "metadata": {...},              # Additional metadata
  "created_at": datetime,
  "updated_at": datetime
}
```

## Auto-Save Feature

Enable automatic saving of topologies by setting environment variable:

```bash
export AUTO_SAVE_TOPOLOGIES=true
```

When enabled, topologies are automatically saved when:
- Getting full topology data via API
- Significant topology changes occur

Auto-saved topologies have names like: `auto_save_20231201_143022`

## Web Interface Features

### Storage Manager UI
- **📋 Browse saved items** with search and filtering
- **💾 Save current topology** with name and description
- **📂 Load topologies** directly into Mininet
- **📤 Export/Import** as JSON or YAML files
- **🗑️ Delete unwanted** topologies and configurations
- **📊 View statistics** and metadata

### Access Points
- **Header Button**: "Storage" button in the main header
- **Control Panel**: "Storage" button in the network control panel
- **Quick Actions**: Save/Load buttons in various components

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   ```bash
   # Check if MongoDB is running
   sudo systemctl status mongodb
   
   # Check MongoDB logs
   sudo journalctl -u mongodb
   
   # Test connection manually
   mongo --eval "db.adminCommand('ping')"
   ```

2. **Permission Errors**
   ```bash
   # Fix MongoDB permissions
   sudo chown -R mongodb:mongodb /var/lib/mongodb
   sudo chown mongodb:mongodb /tmp/mongodb-27017.sock
   ```

3. **Import Errors**
   ```bash
   # Ensure all dependencies are installed
   pip install -r requirements.txt
   
   # Check Python path
   export PYTHONPATH=/path/to/backend:$PYTHONPATH
   ```

### Database Maintenance

```bash
# View database collections
mongo mininet_web_framework --eval "show collections"

# Count documents
mongo mininet_web_framework --eval "db.topologies.count()"
mongo mininet_web_framework --eval "db.configurations.count()"

# Clear all data (be careful!)
mongo mininet_web_framework --eval "db.dropDatabase()"
```

## Architecture Overview

```
Frontend (React)
    ↓
StorageManager Component
    ↓
Storage API Routes (/api/storage/*)
    ↓
Database Services Layer
    ↓
MongoDB Models & Validation
    ↓
MongoDB Database
```

The integration follows a clean architecture with:
- **Separation of concerns** between API, services, and database layers
- **Data validation** at multiple levels
- **Error handling** with proper logging
- **Extensible design** for future enhancements

## Future Enhancements

- **🔐 User Authentication**: Multi-user support with personal storage
- **🏷️ Tagging System**: Organize topologies and configurations with tags
- **📋 Templates**: Pre-built topology templates for common scenarios
- **🔄 Version Control**: Track changes and maintain version history
- **🌐 Sharing**: Share topologies and configurations between users
- **📈 Analytics**: Usage statistics and performance metrics

---

For more information, see the main project README or contact the development team.
