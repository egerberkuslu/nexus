#!/bin/bash
# Caduceus-Flux Kafka Pipeline Setup Script
# Initializes the complete Kafka-based metrics streaming pipeline

set -e

echo "🚀 Caduceus-Flux Kafka Pipeline Setup"
echo "======================================"
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Step 1: Check if .env exists
echo "📋 Step 1: Checking environment configuration..."
if [ ! -f .env ]; then
    print_warning ".env file not found, copying from .env.example"
    cp .env.example .env
    print_success ".env file created"
else
    print_success ".env file exists"
fi

# Ensure Kafka is enabled
if grep -q "^KAFKA_ENABLED=false" .env; then
    print_warning "Kafka is disabled in .env, enabling..."
    sed -i 's/^KAFKA_ENABLED=false/KAFKA_ENABLED=true/' .env
    print_success "Kafka enabled in .env"
elif grep -q "^KAFKA_ENABLED=true" .env; then
    print_success "Kafka is already enabled"
else
    print_warning "KAFKA_ENABLED not set, adding to .env"
    echo "KAFKA_ENABLED=true" >> .env
    print_success "Kafka enabled in .env"
fi

echo ""

# Step 2: Start Docker services
echo "🐳 Step 2: Starting Docker services..."
print_info "This may take a few minutes on first run..."

docker compose up -d

echo ""
print_info "Waiting for services to be healthy..."
sleep 20

# Check critical services
CRITICAL_SERVICES=("zookeeper" "kafka" "postgres" "influxdb")
ALL_HEALTHY=true

for service in "${CRITICAL_SERVICES[@]}"; do
    if docker ps --filter "name=caduceus-$service" --filter "status=running" | grep -q "caduceus-$service"; then
        print_success "$service is running"
    else
        print_error "$service is not running"
        ALL_HEALTHY=false
    fi
done

if [ "$ALL_HEALTHY" = false ]; then
    print_error "Some services failed to start. Check logs with: docker compose logs"
    exit 1
fi

echo ""

# Step 3: Wait for Kafka to be ready
echo "⏳ Step 3: Waiting for Kafka broker to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec caduceus-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
        print_success "Kafka broker is ready"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Kafka broker failed to start after $MAX_RETRIES attempts"
    print_info "Check logs with: docker logs caduceus-kafka"
    exit 1
fi

echo ""

# Step 4: Create Kafka topics
echo "📝 Step 4: Creating Kafka topics..."

TOPICS=("metrics.raw" "metrics.processed" "alerts.anomaly" "alerts.security" "actions.routing" "actions.mano" "events" "metrics.dlq")

for topic in "${TOPICS[@]}"; do
    if docker exec caduceus-kafka kafka-topics --bootstrap-server localhost:9092 --list | grep -q "^${topic}$"; then
        print_info "Topic '${topic}' already exists"
    else
        docker exec caduceus-kafka kafka-topics \
            --create \
            --bootstrap-server localhost:9092 \
            --topic "${topic}" \
            --partitions 3 \
            --replication-factor 1 \
            --config retention.ms=604800000 \
            > /dev/null 2>&1
        print_success "Created topic '${topic}'"
    fi
done

echo ""

# Step 5: Initialize PostgreSQL schema
echo "🗄️  Step 5: Initializing PostgreSQL metrics schema..."

if docker exec caduceus-postgres psql -U caduceus -d caduceus_flux -c "\dt network_metrics" 2>/dev/null | grep -q "network_metrics"; then
    print_info "PostgreSQL schema already initialized"
else
    print_info "Running database migrations..."
    docker exec -i caduceus-postgres psql -U caduceus -d caduceus_flux < backend/database/migrations/001_create_metrics_tables.sql > /dev/null 2>&1
    print_success "PostgreSQL schema initialized"
fi

echo ""

# Step 6: Wait for Kafka Connect to be ready
echo "🔌 Step 6: Waiting for Kafka Connect to be ready..."
MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8083 | grep -q "200\|404"; then
        print_success "Kafka Connect is ready"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_warning "Kafka Connect may not be fully ready, continuing anyway..."
fi

echo ""

# Step 7: Deploy Kafka Connect connectors
echo "🔗 Step 7: Deploying Kafka Connect connectors..."

if [ -f infrastructure/kafka-connect/deploy-connectors.sh ]; then
    chmod +x infrastructure/kafka-connect/deploy-connectors.sh
    ./infrastructure/kafka-connect/deploy-connectors.sh
else
    print_warning "Connector deployment script not found, skipping..."
fi

echo ""

# Step 8: Verify services
echo "🔍 Step 8: Verifying service endpoints..."

ENDPOINTS=(
    "http://localhost:8013/health|Metrics Collector"
    "http://localhost:8011/health|Monitoring Service"
    "http://localhost:8083|Kafka Connect"
    "http://localhost:3001|Grafana"
    "http://localhost:9090|Prometheus"
)

for endpoint in "${ENDPOINTS[@]}"; do
    URL="${endpoint%%|*}"
    NAME="${endpoint##*|}"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
        print_success "$NAME is accessible at $URL"
    else
        print_warning "$NAME may not be ready yet at $URL (HTTP $HTTP_CODE)"
    fi
done

echo ""

# Final summary
echo "============================================"
echo "✨ Kafka Pipeline Setup Complete!"
echo "============================================"
echo ""
echo "📊 Access Points:"
echo "  - Frontend:            http://localhost:3000"
echo "  - API Gateway:         http://localhost:80"
echo "  - Metrics Collector:   http://localhost:8013"
echo "  - Monitoring Service:  http://localhost:8011"
echo "  - Grafana:             http://localhost:3001 (admin/changeme_grafana_password)"
echo "  - Prometheus:          http://localhost:9090"
echo "  - Kafka Connect:       http://localhost:8083"
echo ""
echo "🔧 Next Steps:"
echo ""
echo "1. Start an emulation:"
echo "   curl -X POST http://localhost:8012/api/emulation/start \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"topology_id\": \"your-topology-id\"}'"
echo ""
echo "2. Start metrics collection:"
echo "   curl -X POST http://localhost:8013/api/start-collection \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"devices\": [\"h1\", \"h2\", \"s1\"]}'"
echo ""
echo "3. View metrics in Grafana:"
echo "   - Open http://localhost:3001"
echo "   - Navigate to Dashboards → Network Metrics - Real-time"
echo ""
echo "4. Check Kafka topics:"
echo "   docker exec caduceus-kafka kafka-topics --bootstrap-server localhost:9092 --list"
echo ""
echo "5. Monitor Kafka messages:"
echo "   docker exec caduceus-kafka kafka-console-consumer \\"
echo "     --bootstrap-server localhost:9092 \\"
echo "     --topic metrics.raw \\"
echo "     --from-beginning \\"
echo "     --max-messages 10"
echo ""
echo "📚 Documentation:"
echo "  - KAFKA_SETUP.md         - Kafka setup and operations"
echo "  - METRICS_PIPELINE.md    - Data pipeline architecture"
echo "  - KAFKA_INTEGRATION_SUMMARY.md - Implementation details"
echo ""
echo "💡 Troubleshooting:"
echo "  - Check logs:    docker compose logs -f [service-name]"
echo "  - Restart:       docker compose restart [service-name]"
echo "  - Full restart:  docker compose down && docker compose up -d"
echo ""
print_success "Setup complete! Happy streaming! 🎉"
