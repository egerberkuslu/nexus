#!/usr/bin/env bash
set -euo pipefail

MCP_HUB_URL=${MCP_HUB_URL:-http://localhost:8018}
SERVER_NAME=${SERVER_NAME:-grafana}
SERVER_BASE_URL=${SERVER_BASE_URL:-http://localhost:3001}

cat <<MSG
MCP Tool Hub smoke test
- MCP_HUB_URL: ${MCP_HUB_URL}
- SERVER_NAME: ${SERVER_NAME}
- SERVER_BASE_URL: ${SERVER_BASE_URL}
MSG

echo "[1/4] List available profiles"
curl -sS "${MCP_HUB_URL}/api/mcp/profiles" | head -n 20 || true

echo "[2/4] Register server"
curl -sS -X PUT "${MCP_HUB_URL}/api/mcp/servers/${SERVER_NAME}" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"${SERVER_NAME}\",\"base_url\":\"${SERVER_BASE_URL}\",\"read_only\":true}" \
  | head -n 40

echo "[3/4] List registry"
curl -sS "${MCP_HUB_URL}/api/mcp/servers" | head -n 40

echo "[4/4] Proxy /api/health"
curl -sS -X POST "${MCP_HUB_URL}/api/mcp/proxy" \
  -H 'Content-Type: application/json' \
  -d "{\"server\":\"${SERVER_NAME}\",\"method\":\"GET\",\"path\":\"/api/health\"}" \
  | head -n 80
