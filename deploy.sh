#!/bin/bash

###############################################################################
# Caduceus-Flux Deployment Script
# Deploys the complete network emulation platform
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Configuration
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}║              🎮 Caduceus-Flux Deployment 🎮               ║${NC}"
    echo -e "${BLUE}║         Network Emulation Platform v1.0.0                  ║${NC}"
    echo -e "${BLUE}║                                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

###############################################################################
# Pre-flight Checks
###############################################################################

check_requirements() {
    print_step "Checking system requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker is installed ($(docker --version))"
    
    # Check Docker Compose - support both v1 and v2
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
        print_success "Docker Compose V1 is installed"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
        print_success "Docker Compose V2 is installed"
    else
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
    print_success "Docker daemon is running"
    
    # Check disk space (need at least 10GB)
    available_space=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$available_space" -lt 10 ]; then
        print_warning "Low disk space: ${available_space}GB available (10GB+ recommended)"
    else
        print_success "Sufficient disk space: ${available_space}GB available"
    fi
    
    echo ""
}

###############################################################################
# Environment Configuration
###############################################################################

setup_environment() {
    print_step "Setting up environment configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE" ]; then
            print_step "Creating .env file from .env.example..."
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            print_success "Created .env file"
        else
            print_step "Creating default .env file..."
            cat > "$ENV_FILE" << 'EOF'
# Caduceus-Flux Environment Configuration

# PostgreSQL
POSTGRES_USER=caduceus
POSTGRES_PASSWORD=caduceus_secure_password_change_me
POSTGRES_DB=caduceus_flux

# MongoDB
MONGO_INITDB_ROOT_USERNAME=caduceus
MONGO_INITDB_ROOT_PASSWORD=caduceus_mongo_password_change_me
MONGO_DATABASE=caduceus_snapshots

# Redis
REDIS_PASSWORD=caduceus_redis_password_change_me

# RabbitMQ
RABBITMQ_DEFAULT_USER=caduceus
RABBITMQ_DEFAULT_PASS=caduceus_rabbitmq_password_change_me

# Grafana
GRAFANA_ADMIN_PASSWORD=admin_change_me

# Application
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Network
NETWORK_SUBNET=172.20.0.0/16
EOF
            print_success "Created default .env file"
        fi
        
        print_warning "Please review and update passwords in .env file before production deployment!"
    else
        print_success ".env file already exists"
    fi
    
    echo ""
}

###############################################################################
# Network Setup
###############################################################################

setup_network() {
    print_step "Setting up Docker networks..."
    
    if ! docker network ls | grep -q "caduceus-flux-network"; then
        docker network create caduceus-flux-network --subnet=172.20.0.0/16 || true
        print_success "Created Docker network"
    else
        print_success "Docker network already exists"
    fi
    
    echo ""
}

###############################################################################
# Build Images
###############################################################################

build_images() {
    print_step "Building Docker images..."
    echo ""
    
    # Build all images
    $DOCKER_COMPOSE build --parallel
    
    print_success "All images built successfully"
    echo ""
}

###############################################################################
# Database Initialization
###############################################################################

init_databases() {
    print_step "Initializing databases..."
    
    # Start only database services
    $DOCKER_COMPOSE up -d postgres mongodb redis influxdb
    
    print_step "Waiting for databases to be ready..."
    sleep 10
    
    # Check PostgreSQL
    for i in {1..30}; do
        if $DOCKER_COMPOSE exec -T postgres pg_isready -U caduceus &> /dev/null; then
            print_success "PostgreSQL is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Check MongoDB
    for i in {1..30}; do
        if $DOCKER_COMPOSE exec -T mongodb mongosh --eval "db.adminCommand('ping')" &> /dev/null; then
            print_success "MongoDB is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    print_success "Databases initialized"
    echo ""
}

###############################################################################
# Start Services
###############################################################################

start_services() {
    print_step "Starting all services..."
    echo ""
    
    # Start infrastructure services first
    print_step "Starting infrastructure services..."
    $DOCKER_COMPOSE up -d consul rabbitmq
    sleep 5
    
    # Start backend services
    print_step "Starting backend microservices..."
    $DOCKER_COMPOSE up -d \
        topology-service \
        orchestrator \
        protocol-manager \
        device-manager \
        controller-manager \
        snapshot \
        webshell \
        export-import \
        topology-generator \
        p4-manager \
        monitoring
    sleep 5
    
    # Start emulation container
    print_step "Starting emulation container..."
    $DOCKER_COMPOSE up -d emulation-container
    sleep 3
    
    # Start SDN controllers
    print_step "Starting SDN controllers..."
    $DOCKER_COMPOSE up -d osken ryu
    sleep 3
    
    # Start monitoring stack
    print_step "Starting monitoring stack..."
    $DOCKER_COMPOSE up -d prometheus grafana
    sleep 3
    
    # Start API gateway
    print_step "Starting API gateway..."
    $DOCKER_COMPOSE up -d nginx
    sleep 2
    
    # Start frontend
    print_step "Starting frontend..."
    $DOCKER_COMPOSE up -d frontend
    sleep 2
    
    print_success "All services started"
    echo ""
}

###############################################################################
# Health Checks
###############################################################################

check_services() {
    print_step "Checking service health..."
    echo ""
    
    local all_healthy=true
    
    # Check each critical service
    services=(
        "postgres:5432"
        "mongodb:27017"
        "redis:6379"
        "rabbitmq:5672"
        "consul:8500"
        "topology-service:8001"
        "orchestrator:8002"
        "nginx:80"
        "frontend:80"
    )
    
    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        if $DOCKER_COMPOSE ps | grep -q "$name.*Up"; then
            print_success "$name is running"
        else
            print_error "$name is NOT running"
            all_healthy=false
        fi
    done
    
    echo ""
    
    if [ "$all_healthy" = true ]; then
        print_success "All critical services are healthy"
    else
        print_warning "Some services are not running. Check logs with: docker-compose logs [service-name]"
    fi
    
    echo ""
}

###############################################################################
# Display Access Information
###############################################################################

show_access_info() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    Access Information                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Web Interfaces:${NC}"
    echo -e "  Frontend:         ${YELLOW}http://localhost:3000${NC}"
    echo -e "  Grafana:          ${YELLOW}http://localhost:3001${NC} (admin/admin)"
    echo -e "  Prometheus:       ${YELLOW}http://localhost:9090${NC}"
    echo -e "  RabbitMQ:         ${YELLOW}http://localhost:15672${NC} (caduceus/caduceus_rabbitmq_password_change_me)"
    echo -e "  Consul:           ${YELLOW}http://localhost:8500${NC}"
    echo ""
    echo -e "${GREEN}API Endpoints:${NC}"
    echo -e "  API Gateway:      ${YELLOW}http://localhost/api${NC}"
    echo -e "  Topology:         ${YELLOW}http://localhost/api/topologies${NC}"
    echo -e "  Emulation:        ${YELLOW}http://localhost/api/emulation${NC}"
    echo -e "  Protocols:        ${YELLOW}http://localhost/api/protocols${NC}"
    echo -e "  Devices:          ${YELLOW}http://localhost/api/devices${NC}"
    echo ""
    echo -e "${GREEN}SDN Controllers:${NC}"
    echo -e "  OS-Ken:           ${YELLOW}http://localhost:6653${NC} (OpenFlow)"
    echo -e "  OS-Ken API:       ${YELLOW}http://localhost:8080${NC} (REST)"
    echo -e "  Ryu:              ${YELLOW}http://localhost:6633${NC} (OpenFlow)"
    echo ""
    echo -e "${GREEN}Databases:${NC}"
    echo -e "  PostgreSQL:       ${YELLOW}localhost:5432${NC}"
    echo -e "  MongoDB:          ${YELLOW}localhost:27017${NC}"
    echo -e "  Redis:            ${YELLOW}localhost:6379${NC}"
    echo -e "  InfluxDB:         ${YELLOW}localhost:8086${NC}"
    echo ""
    echo -e "${GREEN}Useful Commands:${NC}"
    echo -e "  View logs:        ${YELLOW}$DOCKER_COMPOSE logs -f [service]${NC}"
    echo -e "  Stop all:         ${YELLOW}$DOCKER_COMPOSE down${NC}"
    echo -e "  Restart service:  ${YELLOW}$DOCKER_COMPOSE restart [service]${NC}"
    echo -e "  Check status:     ${YELLOW}$DOCKER_COMPOSE ps${NC}"
    echo ""
}

###############################################################################
# Main Deployment Flow
###############################################################################

main() {
    print_header
    
    # Parse arguments
    case "${1:-deploy}" in
        deploy)
            check_requirements
            setup_environment
            setup_network
            build_images
            init_databases
            start_services
            sleep 5
            check_services
            show_access_info
            
            print_success "Deployment complete! 🎉"
            echo ""
            print_step "The platform is now running. Access the frontend at: http://localhost:3000"
            ;;
            
        start)
            check_requirements
            print_step "Starting services..."
            $DOCKER_COMPOSE up -d
            sleep 10
            check_services
            show_access_info
            ;;
            
        stop)
            print_step "Stopping services..."
            $DOCKER_COMPOSE down
            print_success "All services stopped"
            ;;
            
        restart)
            check_requirements
            print_step "Restarting services..."
            $DOCKER_COMPOSE restart
            sleep 10
            check_services
            ;;
            
        rebuild)
            check_requirements
            print_step "Rebuilding and restarting..."
            $DOCKER_COMPOSE down
            build_images
            $DOCKER_COMPOSE up -d
            sleep 10
            check_services
            show_access_info
            ;;
            
        clean)
            print_warning "This will remove all containers, volumes, and networks!"
            read -p "Are you sure? (yes/no): " confirm
            if [ "$confirm" = "yes" ]; then
                $DOCKER_COMPOSE down -v --remove-orphans
                docker network rm caduceus-flux-network || true
                print_success "Cleanup complete"
            else
                print_step "Cleanup cancelled"
            fi
            ;;
            
        logs)
            if [ -n "$2" ]; then
                $DOCKER_COMPOSE logs -f "$2"
            else
                $DOCKER_COMPOSE logs -f
            fi
            ;;
            
        status)
            check_requirements
            check_services
            show_access_info
            ;;
            
        *)
            echo "Usage: $0 {deploy|start|stop|restart|rebuild|clean|logs|status}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Full deployment (default)"
            echo "  start    - Start all services"
            echo "  stop     - Stop all services"
            echo "  restart  - Restart all services"
            echo "  rebuild  - Rebuild images and restart"
            echo "  clean    - Remove all containers and volumes"
            echo "  logs     - View logs (optionally specify service)"
            echo "  status   - Check service status"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"

