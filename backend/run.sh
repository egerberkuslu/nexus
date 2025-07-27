#!/bin/bash

# Enhanced Mininet Web Framework Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root (use sudo)"
    echo "Usage: sudo ./run.sh"
    exit 1
fi

print_status "Starting Enhanced Mininet Web Framework..."

# Check if we're in the correct directory
if [ ! -f "app.py" ]; then
    print_error "app.py not found. Please run this script from the backend directory."
    exit 1
fi

# Clean up any existing Mininet processes
print_status "Cleaning up existing Mininet processes..."
mn -c > /dev/null 2>&1 || true

# Check Python environment
print_status "Checking Python environment..."

# Try to find conda environment
CONDA_PYTHON="/home/ege/anaconda3/envs/sdn-mininet/bin/python"
if [ -f "$CONDA_PYTHON" ]; then
    PYTHON_CMD="$CONDA_PYTHON"
    print_success "Found conda environment: $CONDA_PYTHON"
else
    PYTHON_CMD="python3"
    print_warning "Using system Python: $PYTHON_CMD"
fi

# Check if required packages are installed
print_status "Checking dependencies..."

# Check Flask
if ! $PYTHON_CMD -c "import flask" 2>/dev/null; then
    print_error "Flask not found. Installing dependencies..."
    $PYTHON_CMD -m pip install -r requirements.txt
fi

# Check Ryu
if ! $PYTHON_CMD -c "import ryu" 2>/dev/null; then
    print_error "Ryu not found. Installing Ryu..."
    $PYTHON_CMD -m pip install ryu
fi

# Check Mininet
if ! which mn > /dev/null; then
    print_error "Mininet not found. Please install Mininet:"
    echo "  sudo apt-get install mininet"
    exit 1
fi

# Check Open vSwitch
if ! which ovs-vsctl > /dev/null; then
    print_error "Open vSwitch not found. Please install OVS:"
    echo "  sudo apt-get install openvswitch-switch"
    exit 1
fi

print_success "All dependencies verified"

# Set up environment variables and change to correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

print_status "Working directory: $SCRIPT_DIR"
print_status "PYTHONPATH: $PYTHONPATH"

# Test imports before starting
print_status "Testing Python imports..."
if ! $PYTHON_CMD -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from utils.logger import setup_logger
from core.mininet_manager import MininetManager
print('All imports successful')
" 2>/dev/null; then
    print_error "Import test failed. Running import fixer..."
    $PYTHON_CMD fix_imports.py
    
    # Test again
    if ! $PYTHON_CMD -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from utils.logger import setup_logger
from core.mininet_manager import MininetManager
print('Imports fixed successfully')
" 2>/dev/null; then
        print_error "Could not fix imports. Please check the file structure."
        exit 1
    fi
fi

print_success "Import test passed"

# Create logs directory if it doesn't exist
mkdir -p logs

print_status "Starting the server..."
print_status "Server will be available at: http://localhost:5000"
print_status "Press Ctrl+C to stop the server"
echo ""
print_status "=== Enhanced Features ==="
print_status "✓ Modular architecture with separate components"
print_status "✓ Controller included in topology API"
print_status "✓ Full Ryu controller management via web API"
print_status "✓ Real-time network statistics collection"
print_status "✓ Fixed router type detection and classification"
print_status "✓ Comprehensive API endpoints for all operations"
echo ""

# Function to handle cleanup on exit
cleanup() {
    print_status "Shutting down..."
    print_status "Cleaning up Mininet processes..."
    mn -c > /dev/null 2>&1 || true
    print_success "Cleanup complete"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start the application
$PYTHON_CMD app.py

# If we get here, the application exited
cleanup