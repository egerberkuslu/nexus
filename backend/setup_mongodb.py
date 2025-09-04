#!/usr/bin/env python3
"""
MongoDB Setup Script for Mininet Web Framework
Helps set up MongoDB connection and create initial data
"""

import os
import sys
from database.connection import init_database, get_database
from database.services import get_topology_service, get_configuration_service
from utils.logger import setup_logger

logger = setup_logger(__name__)

def check_mongodb_connection():
    """Check if MongoDB is accessible"""
    try:
        db_manager = get_database()
        if db_manager.connect():
            logger.info("✓ MongoDB connection successful")
            return True
        else:
            logger.error("✗ MongoDB connection failed")
            return False
    except Exception as e:
        logger.error(f"✗ MongoDB connection error: {e}")
        return False

def create_sample_data():
    """Create sample topology and configuration data"""
    try:
        topology_service = get_topology_service()
        config_service = get_configuration_service()
        
        # Sample topology
        sample_topology = {
            "nodes": [
                {"id": "h1", "type": "host", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01"},
                {"id": "h2", "type": "host", "ip": "10.0.0.2", "mac": "00:00:00:00:00:02"},
                {"id": "s1", "type": "switch", "dpid": "0000000000000001"}
            ],
            "links": [
                {"source": "h1", "target": "s1", "bandwidth": "10Mbps"},
                {"source": "h2", "target": "s1", "bandwidth": "10Mbps"}
            ],
            "controllers": [
                {"id": "c0", "type": "controller", "ip": "127.0.0.1", "port": 6633}
            ],
            "stats": {"node_count": 3, "link_count": 2}
        }
        
        topology_id = topology_service.save_topology(
            name="sample_simple_topology",
            description="A simple topology with 2 hosts connected to 1 switch",
            topology_data=sample_topology,
            topology_type="sample",
            metadata={"created_by": "setup_script", "sample": True}
        )
        
        if topology_id:
            logger.info(f"✓ Sample topology created with ID: {topology_id}")
        
        # Sample host configuration
        host_config = {
            "ip": "10.0.0.1",
            "netmask": "255.255.255.0",
            "gateway": "10.0.0.254",
            "dns": ["8.8.8.8", "8.8.4.4"],
            "hostname": "sample-host",
            "services": ["ssh"],
            "routes": [],
            "interfaces": []
        }
        
        config_id = config_service.save_configuration(
            name="sample_host_config",
            description="Sample host configuration with basic network settings",
            device_type="host",
            configuration_data=host_config,
            metadata={"created_by": "setup_script", "sample": True}
        )
        
        if config_id:
            logger.info(f"✓ Sample host configuration created with ID: {config_id}")
        
        # Sample switch configuration
        switch_config = {
            "openflow_version": "1.3",
            "controller_ip": "127.0.0.1",
            "controller_port": 6633,
            "dpid": "0000000000000001",
            "fail_mode": "secure",
            "protocols": ["OpenFlow13"],
            "flow_tables": [],
            "ports": []
        }
        
        switch_config_id = config_service.save_configuration(
            name="sample_switch_config",
            description="Sample switch configuration with OpenFlow 1.3",
            device_type="switch",
            configuration_data=switch_config,
            metadata={"created_by": "setup_script", "sample": True}
        )
        
        if switch_config_id:
            logger.info(f"✓ Sample switch configuration created with ID: {switch_config_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error creating sample data: {e}")
        return False

def main():
    """Main setup function"""
    print("=" * 60)
    print("MongoDB Setup for Mininet Web Framework")
    print("=" * 60)
    
    # Check if MongoDB is running
    print("\n1. Checking MongoDB connection...")
    if not check_mongodb_connection():
        print("\n❌ Setup failed: Cannot connect to MongoDB")
        print("\nPlease ensure MongoDB is running:")
        print("  - Install MongoDB: sudo apt install mongodb")
        print("  - Start MongoDB: sudo systemctl start mongodb")
        print("  - Or use Docker: docker run -d -p 27017:27017 mongo")
        return False
    
    # Initialize database (create indexes)
    print("\n2. Initializing database...")
    if init_database():
        print("✓ Database initialized successfully")
    else:
        print("⚠ Database initialization had some issues")
    
    # Create sample data
    print("\n3. Creating sample data...")
    create_sample = input("Create sample topologies and configurations? (y/n): ").lower().strip()
    
    if create_sample == 'y':
        if create_sample_data():
            print("✓ Sample data created successfully")
        else:
            print("⚠ Sample data creation had some issues")
    
    print("\n" + "=" * 60)
    print("Setup completed!")
    print("=" * 60)
    print("\nYou can now:")
    print("1. Start the backend server: python app.py")
    print("2. Access the Storage Manager in the web interface")
    print("3. Save and load topologies and configurations")
    print("\nEnvironment variables (optional):")
    print("  MONGODB_URI=mongodb://localhost:27017/")
    print("  DATABASE_NAME=mininet_web_framework")
    print("  AUTO_SAVE_TOPOLOGIES=false")
    print("  AUTO_SAVE_CONFIGURATIONS=false")
    
    return True

if __name__ == "__main__":
    # Add current directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
    except Exception as e:
        print(f"\n\nSetup failed with error: {e}")
        sys.exit(1)
