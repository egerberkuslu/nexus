## OSM Ping/Pong Example (vimemu-compatible)

This example onboards 2 VNFs (`ping`, `pong`) and 1 NS that connects them on a single VLD.

### Mapping conventions (this repo)
- VNFD `sw-image-desc[*].name` / `sw-image-desc[*].image` → **docker image** via `vimemu-service` Glance emulation.
  - Recommended: use the preloaded image name `netshoot` (maps to `nicolaka/netshoot:latest`).
  - Alternative: set the image name to a docker image string (e.g. `docker://alpine:3.19`).
- VNFD `virtual-compute-desc[*].virtual-memory.size` → **OpenStack flavor RAM** (GiB → MiB conversion happens in RO).
  - This example uses `0.25` GiB (≈ 256 MiB) which matches the preloaded `m1.micro` flavor in `vimemu-service`.
- NSD `vld.*` / VNFD connection points → **Neutron networks/ports** via `vimemu-service` Neutron emulation.
  - Each VLD becomes a Neutron network (materialized as an `osm-net-<id8>` switch inside the Mininet emulation).

### Build packages
From repo root:
- `bash examples/osm/ping-pong/build.sh`
- Optional: pass a suffix to generate unique VNFD/NSD IDs (avoids OSM 409 conflicts on repeated uploads):
  - `bash examples/osm/ping-pong/build.sh $(date +%s)`
  - or `OSM_PKG_SUFFIX=smoketest bash examples/osm/ping-pong/build.sh`

Outputs:
- `examples/osm/ping-pong/dist/caduceus-ping-vnfd.tar.gz`
- `examples/osm/ping-pong/dist/caduceus-pong-vnfd.tar.gz`
- `examples/osm/ping-pong/dist/caduceus-pingpong-nsd.tar.gz`

### Upload & instantiate (recommended path)
1) Ensure the topology OSM stack is running:
   - UI: Network Manager → MANO → OSM (ETSI) → **Start / Ensure**
2) Upload VNFDs + NSD:
   - UI: Network Manager → MANO → OSM (ETSI) → **Packages**
3) Create + instantiate NS:
   - UI: Network Manager → MANO → OSM (ETSI) → **NS**
   - Select `vimAccountId` = `mininet-<topology_id8>`

### Inspect in the emulation
Once instantiated, you should see new dockerized hosts and an `osm-net-...` switch in the topology runtime devices.
