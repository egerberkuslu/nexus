#!/bin/bash
# Single command to enable CRIU - Copy/paste this entire block

echo "Enabling CRIU support..."

# Enable Docker experimental (requires sudo)
echo '{"experimental": true}' | sudo tee /etc/docker/daemon.json > /dev/null
sudo systemctl restart docker
sleep 5

# Verify Docker experimental
if docker version --format '{{.Server.Experimental}}' | grep -q "true"; then
    echo "✅ Docker experimental: ENABLED"
else
    echo "❌ Docker experimental: FAILED"
    exit 1
fi

# Restart snapshot service
docker-compose restart snapshot-service
sleep 8

# Check API
echo ""
echo "Checking API status..."
curl -s http://localhost:8006/api/snapshots/types | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Docker Experimental:', data.get('docker_experimental'))
print('CRIU Available:', data.get('criu_available'))
print('')
if data.get('criu_available'):
    print('✅ SUCCESS! CRIU is enabled in frontend!')
    print('')
    print('Go to: http://localhost:3000')
    print('Create Snapshot → CRIU types should be available')
else:
    print('⚠️  CRIU will become available after starting an emulation')
"
