#!/bin/bash
# Caduceus-Flux Quick Start Script
# This script helps you get started with Caduceus-Flux quickly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_header() {
    echo ""
    print_message "$BLUE" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_message "$BLUE" "  $1"
    print_message "$BLUE" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

print_success() {
    print_message "$GREEN" "✓ $1"
}

print_error() {
    print_message "$RED" "✗ $1"
}

print_warning() {
    print_message "$YELLOW" "⚠ $1"
}

print_info() {
    print_message "$BLUE" "ℹ $1"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        print_success "Docker found: v$DOCKER_VERSION"
    else
        print_error "Docker not found. Please install Docker 24.0+"
        exit 1
    fi

    # Check Docker Compose
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f4 | cut -d',' -f1)
        print_success "Docker Compose found: v$COMPOSE_VERSION"
    else
        print_error "Docker Compose not found. Please install Docker Compose 2.20+"
        exit 1
    fi

    # Check if Docker daemon is running
    if docker ps &> /dev/null; then
        print_success "Docker daemon is running"
    else
        print_error "Docker daemon is not running. Please start Docker"
        exit 1
    fi

    # Check available memory
    TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_MEM" -lt 8 ]; then
        print_warning "System has ${TOTAL_MEM}GB RAM. Recommended: 16GB+"
    else
        print_success "System memory: ${TOTAL_MEM}GB RAM"
    fi

    # Check available disk space
    DISK_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$DISK_SPACE" -lt 30 ]; then
        print_warning "Available disk space: ${DISK_SPACE}GB. Recommended: 50GB+"
    else
        print_success "Available disk space: ${DISK_SPACE}GB"
    fi
}

# Setup environment
setup_environment() {
    print_header "Setting Up Environment"

    if [ ! -f .env ]; then
        print_info "Creating .env file from template..."
        cp .env.example .env
        print_success ".env file created"
        print_warning "Please review and update .env file with your settings"
    else
        print_success ".env file already exists"
    fi
}

# Build services
build_services() {
    print_header "Building Services"

    print_info "This may take 10-20 minutes on first run..."

    if docker-compose build; then
        print_success "All services built successfully"
    else
        print_error "Failed to build services"
        exit 1
    fi
}

# Start infrastructure
start_infrastructure() {
    print_header "Starting Infrastructure Services"

    print_info "Starting PostgreSQL, MongoDB, Redis, RabbitMQ, Consul..."

    docker-compose up -d postgres mongodb redis rabbitmq consul influxdb

    print_info "Waiting for services to be healthy (30s)..."
    sleep 30

    # Check health
    if docker-compose ps | grep -q "unhealthy"; then
        print_warning "Some services are unhealthy. Checking logs..."
        docker-compose ps
    else
        print_success "Infrastructure services are running"
    fi
}

# Start all services
start_all_services() {
    print_header "Starting All Services"

    print_info "Starting microservices and emulation container..."

    if docker-compose up -d; then
        print_success "All services started"
    else
        print_error "Failed to start services"
        exit 1
    fi

    print_info "Waiting for services to initialize (20s)..."
    sleep 20
}

# Show service status
show_status() {
    print_header "Service Status"

    docker-compose ps

    echo ""
    print_header "Access Points"

    print_success "Topology Service API: http://localhost:8001/docs"
    print_success "MCP Server API: http://localhost:8012/docs"
    print_success "Grafana: http://localhost:3001 (admin/admin)"
    print_success "Prometheus: http://localhost:9090"
    print_success "RabbitMQ Management: http://localhost:15672 (caduceus/changeme)"
    print_success "Consul UI: http://localhost:8500"

    echo ""
}

# Create test project
create_test_project() {
    print_header "Creating Test Project"

    print_info "Waiting for Topology Service to be ready..."

    # Wait for topology service
    for i in {1..30}; do
        if curl -s http://localhost:8001/health &> /dev/null; then
            print_success "Topology Service is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Topology Service did not start in time"
            return 1
        fi
        sleep 2
    done

    print_info "Creating test project..."

    PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8001/api/projects \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Quick Start Project",
            "description": "Created by quick-start script"
        }')

    PROJECT_ID=$(echo $PROJECT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

    if [ -z "$PROJECT_ID" ]; then
        print_warning "Could not create test project automatically"
        print_info "You can create it manually via the API"
        return 1
    fi

    print_success "Project created with ID: $PROJECT_ID"

    # Save project ID for later use
    echo "$PROJECT_ID" > .last_project_id

    print_info "Importing simple topology example..."

    # Import topology
    curl -s -X POST "http://localhost:8001/api/topologies/import?project_id=$PROJECT_ID" \
        -H "Content-Type: application/json" \
        -d @examples/simple-topology.json > /dev/null

    if [ $? -eq 0 ]; then
        print_success "Simple topology imported successfully"
        print_info "You can view it at: http://localhost:8001/api/topologies"
    else
        print_warning "Could not import topology automatically"
    fi
}

# Show next steps
show_next_steps() {
    print_header "Next Steps"

    echo ""
    print_info "1. View your topology:"
    echo "   curl http://localhost:8001/api/topologies | jq"
    echo ""

    print_info "2. Explore the API documentation:"
    echo "   open http://localhost:8001/docs"
    echo ""

    print_info "3. Check service logs:"
    echo "   docker-compose logs -f topology-service"
    echo ""

    print_info "4. Access monitoring:"
    echo "   open http://localhost:3001  # Grafana"
    echo ""

    print_info "5. Import other examples:"
    echo "   curl -X POST http://localhost:8001/api/topologies/import?project_id=<ID> \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d @examples/wireless-mesh.json"
    echo ""

    print_info "6. Stop all services:"
    echo "   docker-compose down"
    echo ""

    print_info "7. Stop and remove volumes:"
    echo "   docker-compose down -v"
    echo ""

    print_header "Documentation"
    echo ""
    print_info "📖 README.md - Project overview"
    print_info "📖 IMPLEMENTATION_GUIDE.md - Complete implementation guide"
    print_info "📖 PROJECT_SUMMARY.md - Current status and next steps"
    echo ""
}

# Main menu
show_menu() {
    print_header "Caduceus-Flux Quick Start"

    echo "Please select an option:"
    echo ""
    echo "1. Full Setup (check, build, start, test)"
    echo "2. Check Prerequisites Only"
    echo "3. Build Services"
    echo "4. Start Services"
    echo "5. Stop Services"
    echo "6. Show Status"
    echo "7. View Logs"
    echo "8. Create Test Project"
    echo "9. Clean Everything (remove volumes)"
    echo "0. Exit"
    echo ""
    read -p "Enter your choice: " choice

    case $choice in
        1)
            check_prerequisites
            setup_environment
            build_services
            start_infrastructure
            start_all_services
            show_status
            create_test_project
            show_next_steps
            ;;
        2)
            check_prerequisites
            ;;
        3)
            build_services
            ;;
        4)
            start_infrastructure
            start_all_services
            show_status
            ;;
        5)
            print_header "Stopping Services"
            docker-compose down
            print_success "All services stopped"
            ;;
        6)
            show_status
            ;;
        7)
            print_header "Service Logs"
            echo "Available services:"
            docker-compose ps --services
            echo ""
            read -p "Enter service name (or 'all'): " service
            if [ "$service" = "all" ]; then
                docker-compose logs -f
            else
                docker-compose logs -f "$service"
            fi
            ;;
        8)
            create_test_project
            ;;
        9)
            print_header "Cleaning Everything"
            print_warning "This will remove all containers, volumes, and data"
            read -p "Are you sure? (yes/no): " confirm
            if [ "$confirm" = "yes" ]; then
                docker-compose down -v
                print_success "Everything cleaned"
            else
                print_info "Operation cancelled"
            fi
            ;;
        0)
            print_info "Goodbye!"
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            ;;
    esac
}

# Main execution
main() {
    clear

    # Check if running with arguments
    if [ $# -eq 0 ]; then
        # Interactive mode
        while true; do
            show_menu
            echo ""
            read -p "Press Enter to continue..."
            clear
        done
    else
        # Command line mode
        case $1 in
            check)
                check_prerequisites
                ;;
            build)
                build_services
                ;;
            start)
                start_infrastructure
                start_all_services
                show_status
                ;;
            stop)
                docker-compose down
                ;;
            status)
                show_status
                ;;
            logs)
                docker-compose logs -f ${2:-}
                ;;
            clean)
                docker-compose down -v
                ;;
            full)
                check_prerequisites
                setup_environment
                build_services
                start_infrastructure
                start_all_services
                show_status
                create_test_project
                show_next_steps
                ;;
            *)
                echo "Usage: $0 [check|build|start|stop|status|logs|clean|full]"
                exit 1
                ;;
        esac
    fi
}

# Run main function
main "$@"
