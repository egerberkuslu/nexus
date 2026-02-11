#!/bin/bash
# Update LocalAI Topology Environment Variables and Entrypoints
# Based on topology: e70d74bf-c12b-44cc-9e91-9f8818437004

TOPOLOGY_ID="e70d74bf-c12b-44cc-9e91-9f8818437004"
POSTGRES_CONTAINER="caduceus-postgres"

echo "🔧 Updating LocalAI Topology Configuration..."
echo "Topology ID: $TOPOLOGY_ID"
echo ""

# Get the P2P token from the host (if it exists)
echo "📋 Current configuration:"
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
SELECT name,
       device_type,
       properties->>'docker_image' as image,
       properties->>'docker_command' as entrypoint,
       properties->'docker_environment'->>'LOCALAI_P2P_TOKEN' as p2p_token
FROM nodes
WHERE topology_id = '$TOPOLOGY_ID'
  AND device_type = 'host'
ORDER BY name;
" -P pager=off

echo ""
echo "🔄 Updating LocalAI Host Node (localai-host)..."

# Update the host node with correct environment variables
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux << 'EOF'
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            properties::jsonb,
                            '{docker_environment,LOCALAI_P2P}',
                            '"true"'
                        ),
                        '{docker_environment,WORKERS_MODE}',
                        '"true"'
                    ),
                    '{docker_environment,PORT}',
                    '"8080"'
                ),
                '{docker_environment,MODELS_PATH}',
                '"/models"'
            ),
            '{docker_command}',
            '"/entrypoint-host.sh"'
        ),
        '{docker_image}',
        '"localai-host:latest"'
    ),
    '{dockerized}',
    'true'
)
WHERE name = 'localai-host'
  AND topology_id = 'e70d74bf-c12b-44cc-9e91-9f8818437004';
EOF

echo "✅ Host node updated!"
echo ""

# Read the current TOKEN from worker nodes (we'll use this as LOCALAI_P2P_TOKEN)
P2P_TOKEN=$(docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -t -c "
SELECT properties->'docker_environment'->>'TOKEN'
FROM nodes
WHERE name = 'localai-worker-1'
  AND topology_id = '$TOPOLOGY_ID'
LIMIT 1;
" | xargs)

echo "🔐 Using P2P Token from workers: ${P2P_TOKEN:0:50}..."
echo ""

# Set LOCALAI_P2P_TOKEN on the host
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
UPDATE nodes
SET properties = jsonb_set(
    properties::jsonb,
    '{docker_environment,LOCALAI_P2P_TOKEN}',
    to_jsonb('$P2P_TOKEN'::text)
)
WHERE name = 'localai-host'
  AND topology_id = '$TOPOLOGY_ID';
"

echo "🔄 Updating LocalAI Worker Nodes..."
echo ""

# Update localai-worker-1
echo "  📦 Updating localai-worker-1..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux << 'EOF'
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    properties::jsonb,
                    '{docker_environment,LOCALAI_P2P}',
                    '"true"'
                ),
                '{docker_environment,WORKER_MODE}',
                '"true"'
            ),
            '{docker_environment,WORKER_ID}',
            '"worker-1"'
        ),
        '{docker_command}',
        '"/entrypoint-worker.sh"'
    ),
    '{docker_image}',
    '"localai-worker:latest"'
) - 'docker_environment' || jsonb_build_object(
    'docker_environment',
    (properties->'docker_environment')::jsonb - 'TOKEN' ||
    jsonb_build_object('LOCALAI_P2P_TOKEN', (properties->'docker_environment'->>'TOKEN')::text)
)
WHERE name = 'localai-worker-1'
  AND topology_id = 'e70d74bf-c12b-44cc-9e91-9f8818437004';
EOF

# Update localai-worker-2
echo "  📦 Updating localai-worker-2..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux << 'EOF'
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    properties::jsonb,
                    '{docker_environment,LOCALAI_P2P}',
                    '"true"'
                ),
                '{docker_environment,WORKER_MODE}',
                '"true"'
            ),
            '{docker_environment,WORKER_ID}',
            '"worker-2"'
        ),
        '{docker_command}',
        '"/entrypoint-worker.sh"'
    ),
    '{docker_image}',
    '"localai-worker:latest"'
) - 'docker_environment' || jsonb_build_object(
    'docker_environment',
    (properties->'docker_environment')::jsonb - 'TOKEN' ||
    jsonb_build_object('LOCALAI_P2P_TOKEN', (properties->'docker_environment'->>'TOKEN')::text)
)
WHERE name = 'localai-worker-2'
  AND topology_id = 'e70d74bf-c12b-44cc-9e91-9f8818437004';
EOF

# Update worker-3
echo "  📦 Updating worker-3..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux << 'EOF'
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    properties::jsonb,
                    '{docker_environment,LOCALAI_P2P}',
                    '"true"'
                ),
                '{docker_environment,WORKER_MODE}',
                '"true"'
            ),
            '{docker_environment,WORKER_ID}',
            '"worker-3"'
        ),
        '{docker_command}',
        '"/entrypoint-worker.sh"'
    ),
    '{docker_image}',
    '"localai-worker:latest"'
) - 'docker_environment' || jsonb_build_object(
    'docker_environment',
    (properties->'docker_environment')::jsonb - 'TOKEN' ||
    jsonb_build_object('LOCALAI_P2P_TOKEN', (properties->'docker_environment'->>'TOKEN')::text)
)
WHERE name = 'worker-3'
  AND topology_id = 'e70d74bf-c12b-44cc-9e91-9f8818437004';
EOF

echo ""
echo "✅ All worker nodes updated!"
echo ""

# Display the updated configuration
echo "📊 Updated Configuration Summary:"
echo ""
echo "=== HOST NODE ==="
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
SELECT
    name,
    properties->>'docker_image' as image,
    properties->>'docker_command' as entrypoint,
    properties->'docker_environment'->>'LOCALAI_P2P' as p2p,
    properties->'docker_environment'->>'WORKERS_MODE' as workers_mode,
    properties->'docker_environment'->>'PORT' as port,
    properties->'docker_environment'->>'MODELS_PATH' as models_path,
    LEFT(properties->'docker_environment'->>'LOCALAI_P2P_TOKEN', 30) || '...' as p2p_token
FROM nodes
WHERE name = 'localai-host'
  AND topology_id = '$TOPOLOGY_ID';
" -P pager=off

echo ""
echo "=== WORKER NODES ==="
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
SELECT
    name,
    properties->>'docker_image' as image,
    properties->>'docker_command' as entrypoint,
    properties->'docker_environment'->>'LOCALAI_P2P' as p2p,
    properties->'docker_environment'->>'WORKER_MODE' as worker_mode,
    properties->'docker_environment'->>'WORKER_ID' as worker_id,
    LEFT(properties->'docker_environment'->>'LOCALAI_P2P_TOKEN', 30) || '...' as p2p_token
FROM nodes
WHERE name IN ('localai-worker-1', 'localai-worker-2', 'worker-3')
  AND topology_id = '$TOPOLOGY_ID'
ORDER BY name;
" -P pager=off

echo ""
echo "🎉 Configuration update complete!"
echo ""
echo "📌 Next steps:"
echo "   1. Stop the current emulation if running"
echo "   2. Restart the emulation to apply the new configuration"
echo ""
