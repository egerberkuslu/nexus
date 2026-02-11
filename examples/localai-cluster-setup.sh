#!/bin/bash
# LocalAI P2P Cluster Setup Script for Mininet Topology
# This script helps set up LocalAI host and workers in your Mininet topology

set -e

echo "🚀 LocalAI P2P Cluster Setup for Mininet"
echo "=========================================="
echo ""

# Configuration
HOST_CONTAINER="mn.host-7a5e"
WORKER_CONTAINERS=("mn.host-1" "mn.host-8")

# Function to start LocalAI on host
start_host() {
    echo "🎯 Starting LocalAI on host node..."
    docker exec -d $HOST_CONTAINER bash -c "PROFILE=cpu /aio/entrypoint.sh > /var/log/localai.log 2>&1"
    echo "⏳ Waiting for host to generate P2P token (30 seconds)..."
    sleep 30
}

# Function to extract token from host logs
extract_token() {
    echo "🔑 Extracting P2P token from host..."

    # Try to get token from logs
    TOKEN=$(docker exec $HOST_CONTAINER grep -A 20 "Generated Token" /var/log/localai.log 2>/dev/null | \
            grep -v "Generated Token" | \
            grep -v "To use the token" | \
            head -1 | \
            tr -d ' \n\r')

    if [ -z "$TOKEN" ]; then
        echo "⚠️  Token not found yet, waiting another 30 seconds..."
        sleep 30
        TOKEN=$(docker exec $HOST_CONTAINER grep -A 20 "Generated Token" /var/log/localai.log 2>/dev/null | \
                grep -v "Generated Token" | \
                grep -v "To use the token" | \
                head -1 | \
                tr -d ' \n\r')
    fi

    if [ -z "$TOKEN" ]; then
        echo "❌ Could not extract P2P token automatically."
        echo "📋 Please get it manually with:"
        echo "   docker exec $HOST_CONTAINER grep -A 5 'Generated Token' /var/log/localai.log"
        echo ""
        read -p "Enter the token manually: " TOKEN
    fi

    echo "✅ P2P Token obtained: ${TOKEN:0:50}..."
}

# Function to start workers
start_workers() {
    echo "👥 Starting worker nodes..."

    local worker_id=1
    for worker in "${WORKER_CONTAINERS[@]}"; do
        echo "   Starting worker $worker_id on $worker..."
        docker exec -d $worker bash -c "export TOKEN='$TOKEN' && export WORKER_ID='worker-$worker_id' && PROFILE=cpu /aio/entrypoint.sh > /var/log/localai.log 2>&1"
        ((worker_id++))
    done
}

# Function to check status
check_status() {
    echo ""
    echo "📊 Checking cluster status..."
    sleep 10

    # Get host IP from container
    HOST_IP=$(docker exec $HOST_CONTAINER hostname -I | awk '{print $1}')
    HOST_PORT=8080

    echo ""
    echo "✅ Cluster Setup Complete!"
    echo "=========================="
    echo ""
    echo "🌐 Web Interface:"
    echo "   http://$HOST_IP:$HOST_PORT"
    echo "   http://localhost:32778 (if using Mininet port mapping)"
    echo ""
    echo "🔍 Check cluster status:"
    echo "   curl http://localhost:32778/api/p2p/stats"
    echo "   curl http://localhost:32778/api/p2p/workers"
    echo ""
    echo "📋 View logs:"
    echo "   docker exec $HOST_CONTAINER tail -f /var/log/localai.log"
    for worker in "${WORKER_CONTAINERS[@]}"; do
        echo "   docker exec $worker tail -f /var/log/localai.log"
    done
    echo ""
    echo "💡 Tip: Access the web UI to see distributed inference in action!"
}

# Main execution
main() {
    start_host
    extract_token
    start_workers
    check_status
}

# Run
main
