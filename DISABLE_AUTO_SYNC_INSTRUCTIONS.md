# Instructions to Disable Auto-Sync Event Handlers

To complete the migration to button-triggered apply, you need to disable the auto-sync event handlers in the orchestrator service.

## File to Edit
`/backend/services/orchestrator/main.py`

## Step 1: Comment Out Event Handler Functions

Find and comment out these 6 functions (approximately lines 2021-2280):

1. `handle_topology_node_updated()` - Lines ~2021-2066
2. `handle_topology_link_updated()` - Lines ~2068-2112
3. `handle_topology_node_added()` - Lines ~2114-2156
4. `handle_topology_node_deleted()` - Lines ~2158-2200
5. `handle_topology_link_added()` - Lines ~2202-2242
6. `handle_topology_link_deleted()` - Lines ~2245-2280

**Method**: Add `# DISABLED: ` comment at the start of each function and comment out all lines.

Example:
```python
# DISABLED: Auto-sync removed in favor of button-triggered apply
# def handle_topology_node_updated(message: Dict):
#     """Handle node updates - sync changes to running emulation."""
#     logger.info(f"Topology node updated: {message}")
#     topology_id = message.get('topology_id')
#     ... (rest of function commented out)
```

## Step 2: Keep Only Topology Lifecycle Handlers

**Keep these handlers active** (they're for topology creation/deletion, not device/link changes):
- `handle_topology_created()` - Keep active
- `handle_topology_deleted()` - Keep active
- `handle_topology_updated()` - Keep active (for full topology refresh)

## Step 3: Remove RabbitMQ Consumer Bindings

In the `startup_event()` function (around line ~1355), find where event handlers are registered and comment out these bindings:

```python
# DISABLED bindings for auto-sync (button-triggered apply replaces these)
# rabbitmq_consumer.bind_routing_key("topology.node.updated")
# rabbitmq_consumer.bind_routing_key("topology.link.updated")
# rabbitmq_consumer.bind_routing_key("topology.node.added")
# rabbitmq_consumer.bind_routing_key("topology.node.deleted")
# rabbitmq_consumer.bind_routing_key("topology.link.added")
# rabbitmq_consumer.bind_routing_key("topology.link.deleted")

# DISABLED callback registrations
# rabbitmq_consumer.register_callback("topology.node.updated", handle_topology_node_updated)
# rabbitmq_consumer.register_callback("topology.link.updated", handle_topology_link_updated)
# rabbitmq_consumer.register_callback("topology.node.added", handle_topology_node_added)
# rabbitmq_consumer.register_callback("topology.node.deleted", handle_topology_node_deleted)
# rabbitmq_consumer.register_callback("topology.link.added", handle_topology_link_added)
# rabbitmq_consumer.register_callback("topology.link.deleted", handle_topology_link_deleted)
```

**Keep these active**:
```python
rabbitmq_consumer.bind_routing_key("topology.created")
rabbitmq_consumer.bind_routing_key("topology.updated")
rabbitmq_consumer.bind_routing_key("topology.deleted")

rabbitmq_consumer.register_callback("topology.created", handle_topology_created)
rabbitmq_consumer.register_callback("topology.updated", handle_topology_updated)
rabbitmq_consumer.register_callback("topology.deleted", handle_topology_deleted)
```

## Alternative: Use a Feature Flag

If you want to keep both modes available, add a feature flag at the top of the file:

```python
# Feature flag: Set to False to disable auto-sync and use button-triggered apply only
AUTO_SYNC_ENABLED = os.getenv("AUTO_SYNC_ENABLED", "false").lower() == "true"
```

Then wrap the event handler registration in the startup event:

```python
if AUTO_SYNC_ENABLED:
    # Register auto-sync event handlers
    rabbitmq_consumer.bind_routing_key("topology.node.updated")
    # ... etc
else:
    logger.info("Auto-sync DISABLED - using button-triggered apply only")
```

## Verification

After making changes:

1. Restart orchestrator service:
   ```bash
   docker compose restart orchestrator-service
   ```

2. Check logs to confirm:
   ```bash
   docker logs caduceus-orchestrator-service | grep "DISABLED\|Auto-sync"
   ```

3. Test that device/link changes in UI don't automatically apply to Mininet
4. Test the new `/api/orchestrator/apply-changes` endpoint

## Next Steps

After disabling auto-sync:
1. Add the new `POST /api/orchestrator/apply-changes` endpoint
2. Update topology service with batch-update endpoint
3. Update frontend with staged changes + Apply button
