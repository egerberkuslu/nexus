#!/usr/bin/env bash
set -euo pipefail

MCP_URL="${MCP_URL:-http://localhost:8012}"
MANO_URL="${MANO_URL:-http://localhost:8015}"
ORCH_URL="${ORCH_URL:-http://localhost:8002}"

TOPOLOGY_ID="${1:-${TOPOLOGY_ID:-}}"

log() { printf '%s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing dependency: $1"
}

need curl
need jq
need bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pick_topology() {
  local payload
  payload="$(curl -fsS "${MCP_URL}/api/topologies")"
  local running
  running="$(echo "$payload" | jq -r '[.[] | select(.emulation_status=="running")] | first | .id // empty')"
  if [[ -n "$running" ]]; then
    echo "$running"
    return 0
  fi
  local any
  any="$(echo "$payload" | jq -r 'first | .id // empty')"
  if [[ -n "$any" ]]; then
    echo "$any"
    return 0
  fi
  return 1
}

if [[ -z "$TOPOLOGY_ID" ]]; then
  TOPOLOGY_ID="$(pick_topology || true)"
fi
[[ -n "$TOPOLOGY_ID" ]] || die "No topology id provided and none found via ${MCP_URL}/api/topologies"

ID8="${TOPOLOGY_ID:0:8}"
log "Using topology: ${TOPOLOGY_ID} (${ID8})"

INITIAL_EMU_STATUS="$(curl -fsS "${MCP_URL}/api/topologies/${TOPOLOGY_ID}" | jq -r '.emulation_status // "unknown"')"
log "Initial emulation status: ${INITIAL_EMU_STATUS}"

log "Ensuring per-topology ETSI OSM stack + syncing mirror…"
curl -fsS -X POST "${MANO_URL}/api/osm/reconcile" \
  -H 'Content-Type: application/json' \
  -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"ensure_osm_stack\":true,\"sync_after\":true}" \
  | jq -e '.errors | length == 0' >/dev/null || die "OSM reconcile returned errors"

log "Waiting for per-topology OSM API to become ready…"
for _ in $(seq 1 45); do
  if curl -fsS "${MCP_URL}/api/osm/${TOPOLOGY_ID}/projects" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "${MCP_URL}/api/osm/${TOPOLOGY_ID}/projects" >/dev/null 2>&1 || die "OSM API not ready (projects endpoint unreachable)"

OSM_SUFFIX="$(date +%s)"
log "OSM demo: build ping/pong packages (suffix=${OSM_SUFFIX})"
(cd "${ROOT_DIR}/examples/osm/ping-pong" && bash ./build.sh "${OSM_SUFFIX}") >/dev/null

DIST="${ROOT_DIR}/examples/osm/ping-pong/dist"
PING_PKG="${DIST}/caduceus-ping-vnfd-${OSM_SUFFIX}.tar.gz"
PONG_PKG="${DIST}/caduceus-pong-vnfd-${OSM_SUFFIX}.tar.gz"
NSD_PKG="${DIST}/caduceus-pingpong-nsd-${OSM_SUFFIX}.tar.gz"

[[ -f "$PING_PKG" ]] || die "Missing $PING_PKG"
[[ -f "$PONG_PKG" ]] || die "Missing $PONG_PKG"
[[ -f "$NSD_PKG" ]] || die "Missing $NSD_PKG"

VNFD_PING_ID=""
VNFD_PONG_ID=""
NSD_ID=""
OSM_NS_ID=""

cleanup_osm() {
  set +e
  if [[ -n "$OSM_NS_ID" ]]; then
    curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-instances/${OSM_NS_ID}/terminate" \
      -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1 || true
    curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-instances/${OSM_NS_ID}" >/dev/null 2>&1 || true
  fi
  [[ -n "$NSD_ID" ]] && curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/nsd-packages/${NSD_ID}" >/dev/null 2>&1 || true
  [[ -n "$VNFD_PING_ID" ]] && curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/vnfd-packages/${VNFD_PING_ID}" >/dev/null 2>&1 || true
  [[ -n "$VNFD_PONG_ID" ]] && curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/vnfd-packages/${VNFD_PONG_ID}" >/dev/null 2>&1 || true
  set -e
}

trap cleanup_osm EXIT

log "OSM demo: upload VNFD packages…"
VNFD_PING_ID="$(curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/vnfd-packages/upload" -F "package=@${PING_PKG}" | jq -r '._id // .id')"
VNFD_PONG_ID="$(curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/vnfd-packages/upload" -F "package=@${PONG_PKG}" | jq -r '._id // .id')"
[[ -n "$VNFD_PING_ID" && -n "$VNFD_PONG_ID" ]] || die "VNFD upload failed"

log "OSM demo: upload NSD package…"
NSD_ID="$(curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/nsd-packages/upload" -F "package=@${NSD_PKG}" | jq -r '._id // .id')"
[[ -n "$NSD_ID" ]] || die "NSD upload failed"

log "OSM demo: create + instantiate NS (connector auto-fills instantiate params when omitted)…"
OSM_NS_NAME="smoke-osm-${OSM_SUFFIX}"
OSM_NS_ID="$(curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-instances" \
  -H 'Content-Type: application/json' \
  -d "{\"nsd_id\":\"${NSD_ID}\",\"name\":\"${OSM_NS_NAME}\"}" | jq -r '._id // .id')"
[[ -n "$OSM_NS_ID" ]] || die "OSM NS create failed"

poll_op() {
  local op_id="$1"
  local label="${2:-op}"
  local state=""
  for _ in $(seq 1 90); do
    state="$(curl -fsS "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-lcm-op-occs/${op_id}" | jq -r '.operationState // .status // ""')"
    [[ -n "$state" ]] || state="UNKNOWN"
    if [[ "$state" == "COMPLETED" ]]; then
      log "OSM ${label}: COMPLETED (${op_id})"
      return 0
    fi
    if [[ "$state" == "FAILED" ]]; then
      log "OSM ${label}: FAILED (${op_id})"
      curl -fsS "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-lcm-op-occs/${op_id}" | jq . >&2 || true
      return 1
    fi
    sleep 2
  done
  die "Timeout waiting for OSM ${label} (${op_id})"
}

OP_INST="$(curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-instances/${OSM_NS_ID}/instantiate" -H 'Content-Type: application/json' -d '{}' | jq -r '.id // ._id')"
[[ -n "$OP_INST" ]] || die "OSM instantiate did not return an operation id"
poll_op "$OP_INST" "instantiate"

log "OSM demo: verify instantiation affects the emulation (vimemu → orchestrator)…"
OSM_EMU_COUNT="$(curl -fsS "${ORCH_URL}/api/emulation/devices?topology_id=${TOPOLOGY_ID}" | jq '[.devices[] | select(.properties.openstack_server_id!=null)] | length')"
log "OSM demo: openstack_server_id devices in emulation = ${OSM_EMU_COUNT}"
[[ "${OSM_EMU_COUNT}" -ge 1 ]] || die "Expected at least 1 openstack_server_id device in emulation after OSM instantiate"

OP_TERM="$(curl -fsS -X POST "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-instances/${OSM_NS_ID}/terminate" -H 'Content-Type: application/json' -d '{}' | jq -r '.id // ._id')"
[[ -n "$OP_TERM" ]] || die "OSM terminate did not return an operation id"
poll_op "$OP_TERM" "terminate"

log "OSM demo: verify termination removed emulation devices (best-effort)…"
for _ in $(seq 1 20); do
  OSM_EMU_COUNT="$(curl -fsS "${ORCH_URL}/api/emulation/devices?topology_id=${TOPOLOGY_ID}" | jq '[.devices[] | select(.properties.openstack_server_id!=null)] | length')"
  [[ "${OSM_EMU_COUNT}" -eq 0 ]] && break
  sleep 1
done
log "OSM demo: openstack_server_id devices after terminate = ${OSM_EMU_COUNT}"

log "OSM demo: delete NS + packages…"
curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/ns-instances/${OSM_NS_ID}" >/dev/null
OSM_NS_ID=""
curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/nsd-packages/${NSD_ID}" >/dev/null
NSD_ID=""
curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/vnfd-packages/${VNFD_PING_ID}" >/dev/null
VNFD_PING_ID=""
curl -fsS -X DELETE "${MCP_URL}/api/osm/${TOPOLOGY_ID}/vnfd-packages/${VNFD_PONG_ID}" >/dev/null
VNFD_PONG_ID=""

trap - EXIT

log "Local MANO demo: create NSD + local NS + VNFM VNF + exec + delete…"
LOCAL_SUFFIX="$(date +%s)"
LOCAL_NSD_NAME="smoke-local-nsd-${LOCAL_SUFFIX}"
LOCAL_NS_NAME="smoke-local-ns-${LOCAL_SUFFIX}"
LOCAL_VNF_NAME="smoke-local-vnf-${LOCAL_SUFFIX}"

LOCAL_NSD_PAYLOAD="$(
  jq -n \
    --arg name "$LOCAL_NSD_NAME" \
    --arg topo "$TOPOLOGY_ID" \
    --arg suffix "$LOCAL_SUFFIX" \
    '{
      name: $name,
      descriptor: {
        topology_id: $topo,
        vnfs: [
          {
            name: ("smoke-nsd-vnf-" + $suffix),
            device_type: "container",
            properties: {
              dockerized: true,
              docker_image: "alpine:3.19",
              command: "sleep 36000"
            }
          }
        ]
      }
    }'
)"

LOCAL_NSD_ID="$(curl -fsS -X POST "${MANO_URL}/api/catalog/nsds" -H 'Content-Type: application/json' -d "${LOCAL_NSD_PAYLOAD}" | jq -r '.id')"
[[ -n "$LOCAL_NSD_ID" ]] || die "Local NSD create failed"

LOCAL_NS_ID="$(curl -fsS -X POST "${MANO_URL}/api/ns-instances" -H 'Content-Type: application/json' -d "{\"name\":\"${LOCAL_NS_NAME}\",\"topology_id\":\"${TOPOLOGY_ID}\",\"nsd_id\":\"${LOCAL_NSD_ID}\",\"backend\":\"local\",\"dry_run\":false}" | jq -r '.id')"
[[ -n "$LOCAL_NS_ID" ]] || die "Local NS create failed"

LOCAL_VNF_ID="$(curl -fsS -X POST "${MANO_URL}/api/vnfm/vnf-instances" -H 'Content-Type: application/json' -d "{\"ns_instance_id\":\"${LOCAL_NS_ID}\",\"name\":\"${LOCAL_VNF_NAME}\",\"device_type\":\"container\",\"properties\":{\"dockerized\":true,\"docker_image\":\"alpine:3.19\",\"command\":\"sleep 36000\"}}" | jq -r '.id')"
[[ -n "$LOCAL_VNF_ID" ]] || die "Local VNF create failed"

curl -fsS -X POST "${MANO_URL}/api/vnfm/vnf-instances/${LOCAL_VNF_ID}/exec" -H 'Content-Type: application/json' -d '{"command":"echo smoke-ok"}' | jq -e '.ok == true' >/dev/null || die "Local VNF exec failed"

curl -fsS -X DELETE "${MANO_URL}/api/vnfm/vnf-instances/${LOCAL_VNF_ID}" >/dev/null || die "Local VNF delete failed"

curl -fsS -X POST "${MANO_URL}/api/ns-instances/${LOCAL_NS_ID}/terminate" -H 'Content-Type: application/json' -d '{"reason":"smoke test"}' >/dev/null || true

if [[ "$INITIAL_EMU_STATUS" == "running" ]]; then
  log "Restoring emulation (was running before test)…"
  curl -fsS -X POST "${MCP_URL}/api/emulation/start" -H 'Content-Type: application/json' -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"options\":{}}" >/dev/null || true
fi

log "MANO smoke test: OK"
