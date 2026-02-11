## MANO Testing

This repo includes an end-to-end smoke test that exercises:
- ETSI OSM per-topology stack (ensure + VNFD/NSD onboarding + NS lifecycle)
- Local MANO (catalog + local NS + VNFM create/exec/delete)

### Prereqs
- `docker compose up -d` (project stack running)
- Tools: `curl`, `jq`, `bash`

### Run
Pick a topology id (UUID) from `GET http://localhost:8012/api/topologies`, then:

```bash
bash scripts/mano_smoke_test.sh <topology_id>
```

If you omit `<topology_id>`, the script picks the first running topology (or the first topology available).

### What It Does
- Ensures per-topology OSM stack and syncs OSM → DB mirror (`POST /api/osm/reconcile` on `mano-service`)
- Builds ping/pong VNFD/NSD packages with a unique suffix (`examples/osm/ping-pong/build.sh`)
- Uploads packages to the topology OSM connector (`/api/osm/{topology_id}/...`)
- Creates, instantiates, terminates, and deletes an OSM NS instance
- Verifies OSM instantiation affects the emulation by checking runtime devices with `properties.openstack_server_id`
- Deletes the test packages
- Creates a local NSD + local NS (starts emulation), then:
  - creates a runtime VNF instance
  - runs an exec command
  - deletes the VNF
  - terminates the local NS

### Notes
- If the topology emulation was already running before the test, the script attempts to restart it at the end.
- The smoke test is designed to leave OSM clean (it deletes the packages/NS it created).
- If `POST /api/emulation/start` fails with `"Unable to establish gRPC connection"` (or the emulation container exits immediately), rebuild the emulation image used by the Orchestrator:
  - `cd emulation-container && docker build -f Dockerfile.simple -t caduceus-flux-emulation-container:latest .`
