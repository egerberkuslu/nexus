#!/bin/bash
# Update LocalAI Worker P2P Token
# Usage: ./update-worker-token.sh "YOUR_TOKEN_HERE"

if [ -z "$1" ]; then
    echo "❌ Error: TOKEN value required"
    echo ""
    echo "Usage: $0 \"YOUR_P2P_TOKEN\""
    echo ""
    echo "Example:"
    echo "  $0 \"YWRkcmVzc2VzOgogIC0gL2lwNC8xNzIuMTcuMC4yL3RjcC85MDAxL3AycC8xMkQzS29vV1lvdXJQZWVySUQKcmVuZGV6dm91czogcDJwCg==\""
    exit 1
fi

NEW_TOKEN="$1"
TOPOLOGY_ID="e70d74bf-c12b-44cc-9e91-9f8818437004"

echo "🔧 Updating P2P TOKEN for workers..."
echo "Token: $NEW_TOKEN"
echo ""

docker exec d55cb2264375 psql -U caduceus -d caduceus_flux -c "
UPDATE nodes
SET properties = jsonb_set(
  properties::jsonb,
  '{docker_environment,TOKEN}',
  '\"$NEW_TOKEN\"'::jsonb
)
WHERE name IN ('host-7', 'host-8')
  AND topology_id = '$TOPOLOGY_ID';

SELECT name,
       properties->'docker_environment'->>'TOKEN' as token,
       properties->'docker_environment'->>'WORKER_ID' as worker_id
FROM nodes
WHERE name IN ('host-7', 'host-8');
"

echo ""
echo "✅ TOKEN updated! Now restart the emulation to apply changes."
