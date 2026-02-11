#!/bin/bash
# Fix LocalAI Topology Environment Variables and Entrypoints
# Based on topology: e70d74bf-c12b-44cc-9e91-9f8818437004

TOPOLOGY_ID="e70d74bf-c12b-44cc-9e91-9f8818437004"
POSTGRES_CONTAINER="caduceus-postgres"

echo "🔧 Fixing LocalAI Topology Configuration..."
echo ""

# Get the P2P token
P2P_TOKEN=$(docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -t -c "
SELECT properties->'docker_environment'->>'TOKEN'
FROM nodes
WHERE name = 'localai-worker-1'
  AND topology_id = '$TOPOLOGY_ID'
LIMIT 1;
" | xargs)

echo "🔐 P2P Token: ${P2P_TOKEN:0:50}..."
echo ""

# Update HOST node with all environment variables
echo "🔄 Updating localai-host..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        properties::jsonb,
        '{docker_command}',
        '\"/entrypoint-host.sh\"'
    ),
    '{docker_environment}',
    '{
        \"LOCALAI_P2P\": \"true\",
        \"LOCALAI_P2P_TOKEN\": \"$P2P_TOKEN\",
        \"WORKERS_MODE\": \"true\",
        \"PORT\": \"8080\",
        \"MODELS_PATH\": \"/models\",
        \"DEBUG\": \"true\",
        \"BUILD_BACKENDS\": \"true\",
        \"PRELOAD_BACKENDS\": \"llama-cpp\",
        \"P2P_NETWORK\": \"p2p\",
        \"LOG_LEVEL\": \"info\",
        \"GALLERIES\": \"[{\\\"name\\\":\\\"model-gallery\\\",\\\"url\\\":\\\"github:go-skynet/model-gallery/index.yaml\\\"}]\",
        \"PRELOAD_MODELS\": \"[{\\\"url\\\":\\\"github:go-skynet/model-gallery/tinyllama-1.1b.yaml\\\",\\\"name\\\":\\\"tinyllama\\\"}]\"
    }'::jsonb
)
WHERE name = 'localai-host'
  AND topology_id = '$TOPOLOGY_ID';
"
echo "✅ localai-host updated!"

# Update WORKER-1
echo "🔄 Updating localai-worker-1..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        properties::jsonb,
        '{docker_command}',
        '\"/entrypoint-worker.sh\"'
    ),
    '{docker_environment}',
    '{
        \"LOCALAI_P2P\": \"true\",
        \"LOCALAI_P2P_TOKEN\": \"$P2P_TOKEN\",
        \"WORKER_MODE\": \"true\",
        \"WORKER_ID\": \"worker-1\"
    }'::jsonb
)
WHERE name = 'localai-worker-1'
  AND topology_id = '$TOPOLOGY_ID';
"
echo "✅ localai-worker-1 updated!"

# Update WORKER-2
echo "🔄 Updating localai-worker-2..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        properties::jsonb,
        '{docker_command}',
        '\"/entrypoint-worker.sh\"'
    ),
    '{docker_environment}',
    '{
        \"LOCALAI_P2P\": \"true\",
        \"LOCALAI_P2P_TOKEN\": \"$P2P_TOKEN\",
        \"WORKER_MODE\": \"true\",
        \"WORKER_ID\": \"worker-2\"
    }'::jsonb
)
WHERE name = 'localai-worker-2'
  AND topology_id = '$TOPOLOGY_ID';
"
echo "✅ localai-worker-2 updated!"

# Update WORKER-3
echo "🔄 Updating worker-3..."
docker exec $POSTGRES_CONTAINER psql -U caduceus -d caduceus_flux -c "
UPDATE nodes
SET properties = jsonb_set(
    jsonb_set(
        properties::jsonb,
        '{docker_command}',
        '\"/entrypoint-worker.sh\"'
    ),
    '{docker_environment}',
    '{
        \"LOCALAI_P2P\": \"true\",
        \"LOCALAI_P2P_TOKEN\": \"$P2P_TOKEN\",
        \"WORKER_MODE\": \"true\",
        \"WORKER_ID\": \"worker-3\"
    }'::jsonb
)
WHERE name = 'worker-3'
  AND topology_id = '$TOPOLOGY_ID';
"
echo "✅ worker-3 updated!"

echo ""
echo "📊 Final Configuration:"
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
echo "🎉 All nodes configured successfully!"
echo ""
echo "📌 Configuration Details:"
echo ""
echo "HOST (localai-host):"
echo "  • LOCALAI_P2P=true"
echo "  • WORKERS_MODE=true"
echo "  • PORT=8080"
echo "  • MODELS_PATH=/models"
echo "  • Entrypoint: /entrypoint-host.sh"
echo ""
echo "WORKERS (localai-worker-1, localai-worker-2, worker-3):"
echo "  • LOCALAI_P2P=true"
echo "  • WORKER_MODE=true"
echo "  • WORKER_ID=worker-{1,2,3}"
echo "  • Entrypoint: /entrypoint-worker.sh"
echo ""
