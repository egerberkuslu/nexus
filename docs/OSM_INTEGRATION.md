## ETSI OSM Integration (Isolated)

This project integrates with ETSI OSM by running OSM as an isolated Docker stack and connecting to it via an internal adapter service: `osm-connector-service`.

### Architecture
- Frontend → MCP gateway → `osm-connector-service` (`/api/osm/*`)
- Frontend → MCP gateway → `osm-connector-<topology>` (`/api/osm/{topology_id}/*`) for per-topology isolated OSM
- Frontend → MCP gateway → `mano-service` (`/api/mano/*`) for local (Mininet) MANO flows
- `osm-connector-service` → OSM NBI (SOL005) over HTTP

### Required Environment Variables
Set these in `.env` (or your shell) before running `docker compose up`:
- `OSM_NBI_URL` (example: `http://osm-nbi:9999/osm`)
- Auth (choose one):
  - `OSM_TOKEN` (preferred for automation), OR
  - `OSM_USERNAME` + `OSM_PASSWORD` (+ optional `OSM_PROJECT_ID`)

### Networking (Current Setup)
This repo runs OSM as an **isolated internal Docker network** (`osm-network`) and connects to it through `osm-connector-service`:
- `osm-connector-service` is dual-homed (`caduceus-network` + `osm-network`)
- all `osm-*` containers live only on `osm-network` (not reachable directly from the host)
- the UI talks to OSM via MCP (`http://localhost:8012/api/osm/*`)

If you want to run OSM separately, the supported alternative is:
- keep `osm-connector-service` pointing at your external NBI via `OSM_NBI_URL`
- keep routing/UI unchanged (still goes through MCP + connector)

### Per-Topology OSM (Like Isolated Infrastructure)
For “each topology has its own OSM MANO”, the Orchestrator can spawn a dedicated OSM stack per topology:
- Ensure: `POST /api/infrastructure/topologies/{topology_id}/osm/ensure`
- Status: `GET /api/infrastructure/topologies/{topology_id}/osm/status`
- Stop: `POST /api/infrastructure/topologies/{topology_id}/osm/stop`
- Purge: `POST /api/infrastructure/topologies/{topology_id}/osm/purge`

When ensured, MCP routes topology-scoped calls like:
- `GET /api/osm/{topology_id}/projects` → service `osm-connector-{topology_id[:8]}`

### UI
Network Manager → **MANO** tab → **OSM (ETSI)** card:
- Overview: shows Projects + VIM Accounts
- Packages: upload/list/delete VNFD/NSD packages (best-effort across OSM versions)
- NS: create/instantiate/terminate/delete NS instances
- Mirror: browse the OSM→DB mirror (`mano_external_resource`)
- UI: embeds the native ETSI OSM UI (NG-UI / Light UI) via `/infra-proxy/*` for the selected topology
- Sync: **Ensure + Sync** (project→OSM bootstrap + OSM→DB mirror) and **Sync OSM → DB** (mirror only)

### Bidirectional Sync (OSM ↔ Project)
The platform keeps an internal mirror of OSM resources so the project can query a consistent view and stay in sync:
- OSM → Project (pull mirror): `mano-service` periodically mirrors per-topology OSM state into Postgres (`mano_external_resource`).
- Project → OSM (push/reconcile): `mano-service` can trigger the Orchestrator to ensure/bootstrap an isolated OSM stack, then mirror it back.

Automation defaults (no “Sync” button needed):
- When you open Network Manager → MANO with a selected topology, the UI auto-ensures the topology’s isolated OSM stack (if missing) and triggers an initial OSM→DB mirror sync.
- The Orchestrator also auto-reconciles isolated OSM bootstrap (VIM/WIM/SDN) on key lifecycle events (emulation start, infra ensure, controller start/restart). Toggle with `OSM_AUTO_BOOTSTRAP_ISOLATED` (default: true).
- Mirror cadence is controlled by `MANO_OSM_MIRROR_INTERVAL_SECONDS` (default: 30).

Useful endpoints (via MCP):
- `POST /api/mano/osm/reconcile` (ensure + sync)
- `POST /api/mano/osm/sync` (sync only)
- `GET /api/mano/osm/mirror/stats`
- `GET /api/mano/osm/mirror/resources`

### ETSI OSM Native UIs (Optional)
This repo also includes OSM's native web UIs as separate containers:
- OSM NG-UI: `http://localhost:${OSM_NG_UI_PORT:-8091}` (proxies `/osm/*` to `osm-nbi:9999`)
- OSM Light UI: `http://localhost:${OSM_LIGHT_UI_PORT:-8092}` (uses `OSM_SERVER=nbi`)

### Per-Topology ETSI OSM Native UIs
When you ensure per-topology OSM (`POST /api/infrastructure/topologies/{topology_id}/osm/ensure`), the Orchestrator also starts topology-scoped UI containers and the frontend exposes them via same-origin proxies (no per-topology host ports needed):
- NG-UI: `http://localhost:${FRONTEND_PORT:-3000}/infra-proxy/osm-ng-ui/{topology_id[:8]}/`
- Light UI: `http://localhost:${FRONTEND_PORT:-3000}/infra-proxy/osm-light-ui/{topology_id[:8]}/`

Default credentials (dev):
- Username: `admin`
- Password: `admin`

If you changed these previously and persistent volumes are still present, either update the connector envs or purge the topology OSM stack to reset state.

### Notes / Compatibility
- OSM NBI endpoints vary slightly between releases; `osm-connector-service` provides both:
  - convenience endpoints (`/api/osm/*`), and
  - a generic authenticated proxy (`/api/osm/proxy/{path}`) / upload proxy (`/api/osm/proxy-upload/{path}`) for any missing NBI call.
- Some OSM endpoints default to YAML; `osm-connector-service` sends `Accept: application/json` to normalize responses.
- Some OSM deployments require `nsName` + `nsdId` during NS instantiate; the UI and `mano-service` add these fields when missing.
- The topology-scoped `osm-connector-*` also auto-fills required instantiate fields when you call instantiate with `{}`.
- For isolated per-topology OSM stacks, NBI storage is configured to use Mongo/GridFS to avoid `"storage exception ... cannot be opened"` errors when the UI requests package content.

### Troubleshooting
- If per-topology OSM containers show `(unhealthy)` with `/bin/sh: 1: curl: not found`, re-run `POST /api/infrastructure/topologies/{topology_id}/osm/ensure` once. The Orchestrator recreates RO/NBI/NG-UI with healthchecks that don’t depend on `curl`.

### vimemu mapping conventions (OpenStack-like)
When the per-topology stack is ensured, the Orchestrator registers an OpenStack VIM account that points to a topology-scoped `vimemu`:
- VIM type: `openstack`
- Keystone v2 auth URL: `http://caduceus-osm-topo-<id8>-vimemu:6001/v2.0`

The `vimemu-service` translates common OpenStack operations into Mininet/Containernet runtime actions:
- **VNFD `sw-image-desc[*]` → docker image**
  - `vimemu` exposes a minimal Glance API. It ships with a few preloaded image names:
    - `netshoot` → `nicolaka/netshoot:latest`
    - `ubuntu-22.04` → `ubuntu:22.04`
    - `alpine-3.19` → `alpine:3.19`
  - You can also set the image name to a docker image string (e.g. `docker://alpine:3.19`).
- **NSD VLDs / VNFD connection points → Neutron**
  - Each VLD becomes a Neutron network/subnet/ports.
  - `vimemu` materializes each created Neutron network as an `osm-net-<id8>` switch inside the running emulation.

Example packages are provided in `examples/osm/ping-pong/README.md:1`.

Notes:
- `vimemu` ships with “KB-flavor” variants (e.g. `m1.micro-kb` with `ram=262144`) because some OSM/RO builds request RAM in KB.
- The Orchestrator no longer force-recreates `vimemu` on every `osm/ensure` call to avoid breaking ongoing RO/NS operations.

### Validation: Prove OSM Affects The Emulation

Run the smoke test on a topology (it onboards packages, instantiates an NS, and asserts that runtime devices appear in the emulation with `properties.openstack_server_id`):

```bash
bash scripts/mano_smoke_test.sh <topology_id>
```

To prove the SDN controller affects the dataplane (by temporarily setting OVS fail-mode to `secure` and showing ping fails without controller, then succeeds with controller restored):

```bash
bash scripts/sdn_smoke_test.sh <topology_id>
```
