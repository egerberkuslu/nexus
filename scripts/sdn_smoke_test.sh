#!/usr/bin/env bash
set -euo pipefail

MCP_URL="${MCP_URL:-http://localhost:8012}"
ORCH_URL="${ORCH_URL:-http://localhost:8002}"

TOPOLOGY_ID="${1:-${TOPOLOGY_ID:-}}"

log() { printf '%s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "Missing dependency: $1"; }

need curl
need jq

if [[ -z "$TOPOLOGY_ID" ]]; then
  die "Usage: bash scripts/sdn_smoke_test.sh <topology_id> (or set TOPOLOGY_ID=...)"
fi

log "Topology: ${TOPOLOGY_ID}"

ensure_emulation() {
  local status
  status="$(curl -fsS "${MCP_URL}/api/topologies/${TOPOLOGY_ID}" | jq -r '.emulation_status // "unknown"')"
  if [[ "$status" == "running" ]]; then
    return 0
  fi
  log "Emulation not running in topology-service status (${status}); starting via MCP…"
  curl -fsS -X POST "${MCP_URL}/api/emulation/start" \
    -H 'Content-Type: application/json' \
    -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"options\":{}}" >/dev/null
}

exec_dev() {
  local dev="$1"; shift
  local cmd="$*"
  curl -fsS -X POST "${ORCH_URL}/api/emulation/execute" \
    -H 'Content-Type: application/json' \
    -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"device\":\"${dev}\",\"command\":\"${cmd}\"}"
}

ensure_emulation

devices_json="$(curl -fsS "${ORCH_URL}/api/emulation/devices?topology_id=${TOPOLOGY_ID}")"
switch_name="$(echo "$devices_json" | jq -r '.devices[] | select(.device_type=="switch") | .runtime_name' | head -n 1)"
[[ -n "$switch_name" ]] || die "No switch device found in emulation devices list"

mapfile -t hosts < <(echo "$devices_json" | jq -r '.devices[] | select(.device_type=="host" and (.ip|type=="string") and (.ip|length>0)) | .runtime_name')
[[ "${#hosts[@]}" -ge 1 ]] || die "No host devices found with IPs"

strip_cidr() { printf '%s' "${1%%/*}"; }

src_host="${hosts[0]}"
src_ip="$(echo "$devices_json" | jq -r --arg n "$src_host" '.devices[] | select(.runtime_name==$n) | .ip' | head -n 1)"
src_ip="$(strip_cidr "$src_ip")"

dst_ip=""
dst_host=""
for candidate in "${hosts[@]}"; do
  [[ "$candidate" == "$src_host" ]] && continue
  ip="$(echo "$devices_json" | jq -r --arg n "$candidate" '.devices[] | select(.runtime_name==$n) | .ip' | head -n 1)"
  ip="$(strip_cidr "$ip")"
  [[ -n "$ip" ]] || continue
  code="$(exec_dev "$src_host" "ping -c1 -W1 ${ip}" | jq -r '.exit_code')"
  if [[ "$code" == "0" ]]; then
    dst_ip="$ip"
    dst_host="$candidate"
    break
  fi
done

[[ -n "$dst_ip" ]] || die "Could not find a reachable host-to-host ping pair (from ${src_host})"

orig_fail="$(exec_dev "$switch_name" "ovs-vsctl get-fail-mode ${switch_name}" | jq -r '.stdout' | tr -d '\r\n')"
orig_ctrl="$(exec_dev "$switch_name" "ovs-vsctl get-controller ${switch_name}" | jq -r '.stdout' | tr -d '\r\n')"

[[ -n "$orig_ctrl" ]] || die "Switch ${switch_name} has no controller configured (ovs-vsctl get-controller empty)"

log "Switch: ${switch_name}"
log "Controller: ${orig_ctrl}"
log "Fail-mode: ${orig_fail}"
log "Ping pair: ${src_host} (${src_ip}) -> ${dst_host} (${dst_ip})"

log "Setting fail-mode=secure and removing controller (expected: ping fails)…"
exec_dev "$switch_name" "ovs-vsctl set-fail-mode ${switch_name} secure" >/dev/null
exec_dev "$switch_name" "ovs-ofctl -O OpenFlow13 del-flows ${switch_name}" >/dev/null
exec_dev "$switch_name" "ovs-vsctl del-controller ${switch_name}" >/dev/null

code_fail="$(exec_dev "$src_host" "ping -c1 -W1 ${dst_ip}" | jq -r '.exit_code')"
if [[ "$code_fail" == "0" ]]; then
  log "WARNING: Ping still succeeded without controller; SDN enforcement proof is weak for this topology."
else
  log "Ping without controller failed as expected (exit_code=${code_fail})"
fi

log "Restoring controller and verifying ping succeeds…"
exec_dev "$switch_name" "ovs-vsctl set-controller ${switch_name} ${orig_ctrl}" >/dev/null
sleep 2
code_ok="$(exec_dev "$src_host" "ping -c1 -W1 ${dst_ip}" | jq -r '.exit_code')"
[[ "$code_ok" == "0" ]] || die "Ping did not recover after restoring controller (exit_code=${code_ok})"

log "Restoring fail-mode to ${orig_fail}…"
exec_dev "$switch_name" "ovs-vsctl set-fail-mode ${switch_name} ${orig_fail}" >/dev/null

flows="$(exec_dev "$switch_name" "ovs-ofctl -O OpenFlow13 dump-flows ${switch_name} | wc -l" | jq -r '.stdout' | tr -d '\r\n')"
log "Flow lines (incl header): ${flows}"

log "SDN smoke test: OK"

