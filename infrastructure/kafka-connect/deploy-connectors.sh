#!/bin/bash
# Deploy Kafka Connect connectors

KAFKA_CONNECT_URL="${KAFKA_CONNECT_URL:-http://localhost:8083}"
CONNECTORS_DIR="$(dirname "$0")/connectors"
CONNECTOR_ALLOWLIST="${KAFKA_CONNECT_CONNECTORS:-}"

echo "🔌 Deploying Kafka Connect connectors..."
echo "Kafka Connect URL: $KAFKA_CONNECT_URL"
echo ""

# Wait for Kafka Connect to be ready
echo "⏳ Waiting for Kafka Connect to be ready..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if curl -s -o /dev/null -w "%{http_code}" "$KAFKA_CONNECT_URL" | grep -q "200\|404"; then
        echo "✅ Kafka Connect is ready"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "Waiting... ($retry_count/$max_retries)"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ Kafka Connect is not ready after $max_retries attempts"
    exit 1
fi

# Function to deploy a connector
deploy_connector() {
    local connector_file=$1
    local connector_name=$(basename "$connector_file" .json)

    echo ""
    echo "📦 Deploying connector: $connector_name"

    local rendered_file
    rendered_file="$(mktemp)"
    if command -v envsubst >/dev/null 2>&1; then
        # Restrict substitution to known vars so we don't corrupt SMT types like `ExtractField$Value`.
        envsubst '$POSTGRES_HOST $POSTGRES_PORT $POSTGRES_DB $POSTGRES_USER $POSTGRES_PASSWORD $INFLUXDB_URL $INFLUXDB_TOKEN $INFLUXDB_ORG $INFLUXDB_BUCKET' < "$connector_file" > "$rendered_file"
    else
        cp "$connector_file" "$rendered_file"
    fi

    # Check if connector already exists
    if curl -s "$KAFKA_CONNECT_URL/connectors/$connector_name" | grep -q "error_code"; then
        echo "  Creating new connector..."
        response=$(curl -s -X POST \
            -H "Content-Type: application/json" \
            --data @"$rendered_file" \
            "$KAFKA_CONNECT_URL/connectors")
    else
        echo "  Connector exists, updating..."
        # Extract config from JSON
        config=$(cat "$rendered_file" | jq '.config')
        response=$(curl -s -X PUT \
            -H "Content-Type: application/json" \
            --data "$config" \
            "$KAFKA_CONNECT_URL/connectors/$connector_name/config")
    fi

    rm -f "$rendered_file" || true

    # Check response
    if echo "$response" | grep -q "error_code"; then
        echo "  ❌ Failed to deploy connector:"
        echo "$response" | jq '.'
        return 1
    else
        echo "  ✅ Connector deployed successfully"
        return 0
    fi
}

# Deploy all connectors
success_count=0
fail_count=0

for connector_file in "$CONNECTORS_DIR"/*.json; do
    if [ -f "$connector_file" ]; then
        connector_name=$(basename "$connector_file" .json)
        if [ -n "$CONNECTOR_ALLOWLIST" ]; then
            if ! echo ",$CONNECTOR_ALLOWLIST," | grep -q ",$connector_name,"; then
                echo ""
                echo "Skipping connector (not in allowlist): $connector_name"
                continue
            fi
        fi
        if deploy_connector "$connector_file"; then
            success_count=$((success_count + 1))
        else
            fail_count=$((fail_count + 1))
        fi
    fi
done

# Summary
echo ""
echo "============================================"
echo "📊 Deployment Summary:"
echo "  ✅ Successful: $success_count"
echo "  ❌ Failed: $fail_count"
echo "============================================"

# List all connectors
echo ""
echo "📋 Active connectors:"
curl -s "$KAFKA_CONNECT_URL/connectors" | jq '.'

# Check connector status
echo ""
echo "🔍 Connector status:"
for connector in $(curl -s "$KAFKA_CONNECT_URL/connectors" | jq -r '.[]'); do
    echo ""
    echo "  Connector: $connector"
    curl -s "$KAFKA_CONNECT_URL/connectors/$connector/status" | jq '.connector.state, .tasks[].state'
done

echo ""
echo "✨ Done!"
