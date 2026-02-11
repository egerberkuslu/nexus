# Control Config (Unified JSON Control Plane)

This project includes a **Config Service** (`config-service`, port `8016`) that lets you orchestrate **MANO + SDN + emulation/network actions** using a single JSON payload.

The UI entry point is:

- `Network Manager → Config → Control Config (MANO + SDN + Network)`
- If you don’t see the tab buttons (too many tabs), use the **Jump to tab** dropdown in Network Manager and pick `Configuration`.

## API

All endpoints are reachable through the gateway:

- `GET /api/config/template?topology_id=<uuid>`
- `POST /api/config/validate`
- `POST /api/config/apply`

## JSON Schema

Current schema id:

- `caduceus.control-config.v1`

Top-level fields:

- `schema`: string (required)
- `topology_id`: string (optional; used as default for actions)
- `dry_run`: boolean (optional; default `false`)
- `actions`: list of `{ id?, kind, params?, dry_run? }`

## Supported `kind` values (v1)

- `topology.infra.ensure`
- `topology.osm.ensure`
- `emulation.start`
- `emulation.stop`
- `network_config.apply`
- `device.exec`
- `sdn.controller.start`
- `sdn.controller.stop`
- `sdn.controller.restart`
- `sdn.controller.exec`
- `mano.ns.create`
- `mano.ns.terminate`
- `mano.vnf.create`
- `mano.vnf.delete`
- `mano.vnf.exec`
- `mcp.request` (advanced passthrough to MCP `/api/*`)

## Example

```json
{
  "schema": "caduceus.control-config.v1",
  "topology_id": "87c7be42-9a37-43bd-b686-05e366968845",
  "dry_run": true,
  "actions": [
    { "id": "infra", "kind": "topology.infra.ensure" },
    { "id": "osm", "kind": "topology.osm.ensure" },
    { "id": "emu", "kind": "emulation.start", "params": { "options": {} } },
    {
      "id": "net",
      "kind": "network_config.apply",
      "params": {
        "config": {
          "schema": "caduceus.network-config.v1",
          "topology_id": "87c7be42-9a37-43bd-b686-05e366968845",
          "name": "Demo: routing tweak",
          "description": "Example network config payload",
          "defaults": { "dns_servers": [], "sysctls": {}, "commands": [] },
          "devices": [
            { "name": "router-1", "kind": "router", "sysctls": { "net.ipv4.ip_forward": "1" } }
          ]
        }
      }
    },
    { "id": "ctrl", "kind": "sdn.controller.restart", "params": { "controller_id": "controller-1" } }
  ]
}
```

## Proof It Affects The Emulation

This is a concrete “config → runtime behavior” check using Linux routing:

1. Disable routing on a router: `net.ipv4.ip_forward=0`
2. Observe: ping between subnets fails
3. Apply Control Config to set `net.ipv4.ip_forward=1`
4. Observe: ping succeeds

Commands (via the gateway):

```bash
TOPOLOGY_ID="59ccc74e-799a-49b0-b310-055d28c08389"

# 1) Disable forwarding
curl -sS -X POST http://localhost/api/emulation/execute \
  -H 'Content-Type: application/json' \
  -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"device\":\"router-4\",\"command\":\"sysctl -w net.ipv4.ip_forward=0\"}"

# 2) Ping should FAIL
curl -sS -X POST http://localhost/api/emulation/execute \
  -H 'Content-Type: application/json' \
  -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"device\":\"host-2\",\"command\":\"ping -c 1 -W 1 10.0.5.2\"}"

# 3) Apply Control Config (routing on)
curl -sS -X POST http://localhost/api/config/apply \
  -H 'Content-Type: application/json' \
  -d '{
    "schema":"caduceus.control-config.v1",
    "topology_id":"59ccc74e-799a-49b0-b310-055d28c08389",
    "dry_run":false,
    "actions":[
      {
        "id":"ipfwd",
        "kind":"network_config.apply",
        "params":{
          "config":{
            "devices":[{"name":"router-4","sysctls":{"net.ipv4.ip_forward":"1"}}]
          }
        }
      }
    ]
  }'

# 4) Ping should SUCCEED
curl -sS -X POST http://localhost/api/emulation/execute \
  -H 'Content-Type: application/json' \
  -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"device\":\"host-2\",\"command\":\"ping -c 1 -W 1 10.0.5.2\"}"
```

### Alternative Proof (sysctl-only, no ping needed)

If your topology doesn’t have multiple subnets to ping across, you can still prove that Control Config affects the runtime by changing a sysctl and reading it back:

```bash
TOPOLOGY_ID="59ccc74e-799a-49b0-b310-055d28c08389"

# Read current value
curl -sS -X POST http://localhost/api/emulation/execute \
  -H 'Content-Type: application/json' \
  -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"device\":\"router-4\",\"command\":\"sysctl net.ipv4.conf.all.rp_filter\"}"

# Apply Control Config (set rp_filter=1)
curl -sS -X POST http://localhost/api/config/apply \
  -H 'Content-Type: application/json' \
  -d '{
    "schema":"caduceus.control-config.v1",
    "topology_id":"59ccc74e-799a-49b0-b310-055d28c08389",
    "dry_run":false,
    "actions":[
      {
        "id":"sysctl-rpfilter",
        "kind":"network_config.apply",
        "params":{
          "config":{
            "schema":"caduceus.network-config.v1",
            "devices":[{"name":"router-4","sysctls":{"net.ipv4.conf.all.rp_filter":"1"}}]
          }
        }
      }
    ]
  }'

# Read again (should now be 1)
curl -sS -X POST http://localhost/api/emulation/execute \
  -H 'Content-Type: application/json' \
  -d "{\"topology_id\":\"${TOPOLOGY_ID}\",\"device\":\"router-4\",\"command\":\"sysctl net.ipv4.conf.all.rp_filter\"}"
```
