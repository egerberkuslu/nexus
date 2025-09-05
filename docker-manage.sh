#!/bin/bash

# Mininet Web Framework Docker Management Script
# This script provides easy management of the Docker environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_status "Docker is running"
}

# Function to check if docker-compose is available
check_docker_compose() {
    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "docker-compose is not installed. Please install docker-compose and try again."
        exit 1
    fi
    print_status "docker-compose is available"
}

# Function to build and start all services
start_all() {
    print_header "Starting Mininet Web Framework with All SDN Controllers"
    
    check_docker
    check_docker_compose
    
    print_status "Building and starting all services..."
    docker-compose up --build -d
    
    print_status "Waiting for services to be ready..."
    sleep 30
    
    print_status "Checking service health..."
    docker-compose ps
    
    print_status "Services started successfully!"
    print_status "Frontend: http://localhost:3000"
    print_status "Backend API: http://localhost:5000"
    print_status "OpenDaylight REST API: http://localhost:8181"
    print_status "OpenDaylight SSH: localhost:8101 (karaf/karaf)"
    print_status "OpenFlow: localhost:6633"
}

# Function to start only basic services (without controllers)
start_basic() {
    print_header "Starting Mininet Web Framework (Basic Mode)"
    
    check_docker
    check_docker_compose
    
    print_status "Building and starting basic services..."
    docker-compose -f docker-compose.yml up --build -d mongodb frontend
    
    # Use basic backend without controllers
    docker-compose -f docker-compose.yml run --rm -d \
        --name mininet-backend-basic \
        -p 5000:5000 \
        -e MONGODB_URI=mongodb://mongodb:27017/ \
        -e DATABASE_NAME=mininet_web_framework \
        -e FLASK_ENV=production \
        -e PYTHONPATH=/app \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
        -v /lib/modules:/lib/modules:ro \
        --privileged \
        --cap-add NET_ADMIN \
        --cap-add SYS_ADMIN \
        --cap-add SYS_NICE \
        --cap-add SYS_MODULE \
        --device /dev/net/tun \
        --sysctl net.ipv4.ip_forward=1 \
        --network mininet-web-framework_mininet-network \
        backend
    
    print_status "Basic services started successfully!"
    print_status "Frontend: http://localhost:3000"
    print_status "Backend API: http://localhost:5000"
}

# Function to stop all services
stop_all() {
    print_header "Stopping All Services"
    
    print_status "Stopping all containers..."
    docker-compose down
    
    print_status "All services stopped"
}

# Function to restart all services
restart_all() {
    print_header "Restarting All Services"
    
    stop_all
    sleep 5
    start_all
}

# Function to show logs
show_logs() {
    local service=${1:-""}
    
    if [ -n "$service" ]; then
        print_header "Showing logs for $service"
        docker-compose logs -f "$service"
    else
        print_header "Showing logs for all services"
        docker-compose logs -f
    fi
}

# Function to show service status
show_status() {
    print_header "Service Status"
    
    print_status "Docker containers:"
    docker-compose ps
    
    echo ""
    print_status "Service health checks:"
    
    # Check MongoDB
    if curl -s http://localhost:27017 >/dev/null 2>&1; then
        print_status "✓ MongoDB: Running"
    else
        print_warning "✗ MongoDB: Not accessible"
    fi
    
    # Check Backend
    if curl -s http://localhost:5000/api/status >/dev/null 2>&1; then
        print_status "✓ Backend API: Running"
    else
        print_warning "✗ Backend API: Not accessible"
    fi
    
    # Check Frontend
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        print_status "✓ Frontend: Running"
    else
        print_warning "✗ Frontend: Not accessible"
    fi
    
    # Check OpenDaylight
    if curl -s http://localhost:8181/restconf/operational/system >/dev/null 2>&1; then
        print_status "✓ OpenDaylight REST API: Running"
    else
        print_warning "✗ OpenDaylight REST API: Not accessible"
    fi
    
    # Check OpenDaylight SSH
    if nc -z localhost 8101 2>/dev/null; then
        print_status "✓ OpenDaylight SSH: Running"
    else
        print_warning "✗ OpenDaylight SSH: Not accessible"
    fi
}

# Function to clean up everything
clean_all() {
    print_header "Cleaning Up All Resources"
    
    print_warning "This will remove all containers, volumes, and images. Are you sure? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Stopping and removing containers..."
        docker-compose down -v --remove-orphans
        
        print_status "Removing images..."
        docker-compose down --rmi all
        
        print_status "Cleaning up unused resources..."
        docker system prune -f
        
        print_status "Cleanup completed"
    else
        print_status "Cleanup cancelled"
    fi
}

# Function to test OpenDaylight
test_opendaylight() {
    print_header "Testing OpenDaylight Installation"
    
    print_status "Running OpenDaylight standalone test..."
    docker-compose exec backend python3 test_opendaylight_standalone.py
}

# Function to show help
show_help() {
    echo "Mininet Web Framework Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Start all services with SDN controllers"
    echo "  start-basic Start basic services without controllers"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show service status and health"
    echo "  logs [service] Show logs (optionally for specific service)"
    echo "  test-odl    Test OpenDaylight installation"
    echo "  clean       Clean up all resources (containers, volumes, images)"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start all services"
    echo "  $0 logs backend       # Show backend logs"
    echo "  $0 status             # Check service status"
    echo "  $0 test-odl           # Test OpenDaylight"
}

# Main script logic
case "${1:-help}" in
    start)
        start_all
        ;;
    start-basic)
        start_basic
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    test-odl)
        test_opendaylight
        ;;
    clean)
        clean_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
