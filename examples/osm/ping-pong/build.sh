#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"

mkdir -p "$DIST_DIR"

SUFFIX="${1:-${OSM_PKG_SUFFIX:-}}"

if [[ -z "$SUFFIX" ]]; then
  tar -czf "$DIST_DIR/caduceus-ping-vnfd.tar.gz" -C "$ROOT_DIR/packages" ping_vnfd
  tar -czf "$DIST_DIR/caduceus-pong-vnfd.tar.gz" -C "$ROOT_DIR/packages" pong_vnfd
  tar -czf "$DIST_DIR/caduceus-pingpong-nsd.tar.gz" -C "$ROOT_DIR/packages" pingpong_nsd
else
  WORK_DIR="$(mktemp -d)"
  trap 'rm -rf "$WORK_DIR"' EXIT

  cp -R "$ROOT_DIR/packages/ping_vnfd" "$WORK_DIR/ping_vnfd"
  cp -R "$ROOT_DIR/packages/pong_vnfd" "$WORK_DIR/pong_vnfd"
  cp -R "$ROOT_DIR/packages/pingpong_nsd" "$WORK_DIR/pingpong_nsd"

  # Keep VNFD/NSD IDs unique so OSM accepts multiple uploads without conflicts.
  # VNFD IDs
  sed -i \
    -e "s/caduceus-ping-vnf/caduceus-ping-vnf-${SUFFIX}/g" \
    "$WORK_DIR/ping_vnfd/ping_vnfd.yaml"
  sed -i \
    -e "s/caduceus-pong-vnf/caduceus-pong-vnf-${SUFFIX}/g" \
    "$WORK_DIR/pong_vnfd/pong_vnfd.yaml"

  # NSD ID + references to VNFD IDs
  sed -i \
    -e "s/caduceus-pingpong-ns/caduceus-pingpong-ns-${SUFFIX}/g" \
    -e "s/caduceus-ping-vnf/caduceus-ping-vnf-${SUFFIX}/g" \
    -e "s/caduceus-pong-vnf/caduceus-pong-vnf-${SUFFIX}/g" \
    "$WORK_DIR/pingpong_nsd/pingpong_nsd.yaml"

  tar -czf "$DIST_DIR/caduceus-ping-vnfd-${SUFFIX}.tar.gz" -C "$WORK_DIR" ping_vnfd
  tar -czf "$DIST_DIR/caduceus-pong-vnfd-${SUFFIX}.tar.gz" -C "$WORK_DIR" pong_vnfd
  tar -czf "$DIST_DIR/caduceus-pingpong-nsd-${SUFFIX}.tar.gz" -C "$WORK_DIR" pingpong_nsd
fi

echo "Built:"
ls -1 "$DIST_DIR" | sed 's/^/ - /'
