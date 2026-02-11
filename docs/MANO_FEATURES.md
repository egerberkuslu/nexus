## MANO Features (Current Implementation)

This repo implements a **hybrid MANO**:
- **Local MANO** (for Mininet/Containernet runtime orchestration) via `mano-service`
- **ETSI OSM integration** (per-topology isolated OSM stacks) via `osm-connector-*` + `vimemu-*`
- **Bidirectional sync** (OSM → Project mirror + Project → OSM reconcile triggers)

### Components
- **NFVO (local)**: `mano-service` creates and tracks NS instances (`/api/mano/ns-instances`).
- **VNFM (local)**: `mano-service` manages VNF instances, exec, delete (`/api/mano/vnfm/vnf-instances`).
- **VIM (local)**: runtime inventory view (`/api/mano/vim/inventory`) and southbound actions via MCP or direct calls.
- **ETSI OSM (external NFVO)**: OSM runs as a per-topology isolated Docker stack; all OSM calls go through a topology-scoped connector service.

### ETSI OSM Integration (Per-Topology)
- Orchestrator spawns a dedicated OSM stack per topology (`/api/infrastructure/topologies/{topology_id}/osm/ensure`).
- Frontend proxies OSM native UIs per topology:
  - `/infra-proxy/osm-ng-ui/{topology_id[:8]}/`
  - `/infra-proxy/osm-light-ui/{topology_id[:8]}/`
  - Network Manager embeds these under **MANO → OSM (ETSI) → UI**.
- OSM “VIM account” points to a topology-scoped **OpenStack-like VIM emulator** (`vimemu`) which translates:
  - Nova server create/delete → add/remove dockerized hosts in the emulation
  - Neutron network/port ops → create switches and links in the emulation
  - If docker-container spawning is unavailable/unreliable, the orchestrator may fall back to creating plain hosts (still keeping the workflow functional).

### Bidirectional Data Sync
- **OSM → Project (mirror)**: `mano-service` mirrors OSM resources into Postgres (`mano_external_resource`) and also upserts core catalog/instances for unified listing.
- **Project → OSM (reconcile)**: `POST /api/mano/osm/reconcile` ensures the per-topology OSM stack exists, bootstraps VIM/SDN/WIM, then syncs mirror.

### What’s Included vs. Not Included
Included (today):
- Local NS create/terminate + operations log
- Local VNFM create/exec/delete (runtime + dry-run)
- OSM package onboarding (VNFD/NSD), NS create/instantiate/terminate/delete
- Per-topology isolated OSM UIs + same-origin proxying
- OSM ↔ Project mirroring and a UI “Mirror” view

Not included (yet):
- Full ETSI SOL005 VNFM (instantiation-level scaling, healing, etc.)
- Full OSM RO plugin development (custom RO VIM connector inside OSM itself)
- Network slicing intent/policy layer (planned separately)
