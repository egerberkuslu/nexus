"""
Snapshot Service - Comprehensive snapshot management with Docker checkpoint support
Rebuilt with PostgreSQL + MongoDB hybrid storage and automatic scheduling
"""

import os
import sys
import logging
import asyncio
import json
import gzip
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import httpx

# Add shared module to path
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.database.postgres import get_db, init_db, SessionLocal
from shared.database.mongodb import get_mongodb, init_mongodb, health_check as mongo_health
from shared.models.snapshot import Snapshot, SnapshotSchedule, SnapshotType, SnapshotStatus
from shared.schemas.snapshot_schema import (
    SnapshotCreateRequest, SnapshotRestoreRequest, SnapshotRenameRequest,
    ScheduleCreateRequest, ScheduleUpdateRequest,
    SnapshotResponse, SnapshotDetailResponse, SnapshotProgressResponse,
    RestoreResultResponse, ScheduleResponse,
    SnapshotListResponse, ScheduleListResponse,
    SnapshotStatsResponse, SnapshotTypesResponse, SnapshotTypeInfo,
    SnapshotTypeEnum, SnapshotStatusEnum,
    CRON_PRESETS
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv("SNAPSHOT_SERVICE_PORT", "8006"))
HOST = os.getenv("SNAPSHOT_SERVICE_HOST", "0.0.0.0")
TOPOLOGY_SERVICE_URL = os.getenv("TOPOLOGY_SERVICE_URL", "http://topology-service:8001")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8002")
SNAPSHOT_STORAGE_DIR = Path(os.getenv("SNAPSHOT_STORAGE_DIR", "/var/lib/caduceus-flux/snapshots"))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")

# Import storage and scheduler after path setup
from storage.postgres_storage import PostgresSnapshotStorage
from storage.mongo_storage import MongoSnapshotStorage
from scheduler.snapshot_scheduler import get_scheduler


# ==================== Lifespan Management ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Snapshot Service...")

    try:
        # Initialize databases
        init_db()
        init_mongodb()

        # Initialize scheduler
        scheduler = get_scheduler()
        scheduler.set_snapshot_callback(execute_scheduled_snapshot)
        scheduler.set_retention_callback(apply_retention_policy)
        scheduler.start()

        # Load existing schedules
        await load_schedules_from_db()
        await mark_stale_snapshots_failed()

        logger.info(f"Snapshot Service started on {HOST}:{PORT}")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Snapshot Service...")
    scheduler = get_scheduler()
    scheduler.stop()


# ==================== FastAPI App ====================

app = FastAPI(
    title="Caduceus-Flux Snapshot Service",
    description="Comprehensive snapshot management with Docker checkpoint support",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Dependencies ====================

def get_postgres_storage(db: Session = Depends(get_db)) -> PostgresSnapshotStorage:
    """Get PostgreSQL storage instance"""
    return PostgresSnapshotStorage(db)


def get_mongo_storage() -> MongoSnapshotStorage:
    """Get MongoDB storage instance"""
    return MongoSnapshotStorage()


# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    mongo_status = mongo_health()
    scheduler = get_scheduler()

    return {
        "status": "healthy",
        "service": "snapshot",
        "version": "2.0.0",
        "mongodb": mongo_status,
        "scheduler_running": scheduler.is_running,
        "active_jobs": len(scheduler.list_jobs()),
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== Snapshot CRUD ====================

@app.post("/api/snapshots", response_model=SnapshotResponse, status_code=201)
async def create_snapshot(
    request: SnapshotCreateRequest,
    background_tasks: BackgroundTasks,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage),
    mongo_storage: MongoSnapshotStorage = Depends(get_mongo_storage)
):
    """Create a new snapshot"""
    try:
        # Create snapshot record in PostgreSQL (status: PENDING)
        snapshot = pg_storage.create_snapshot(request)

        # Start background task for actual snapshot creation
        background_tasks.add_task(
            create_snapshot_background,
            snapshot.id,
            request.model_dump()
        )

        # Publish event
        await publish_event("snapshot.created", {
            "snapshot_id": snapshot.id,
            "name": snapshot.name,
            "type": request.snapshot_type.value
        })

        return _snapshot_to_response(snapshot)

    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/snapshots/stats", response_model=SnapshotStatsResponse)
async def get_snapshot_stats(
    topology_id: Optional[str] = Query(None),
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Get snapshot statistics"""
    stats = pg_storage.get_stats(topology_id)
    return SnapshotStatsResponse(**stats)


@app.get("/api/snapshots/types", response_model=SnapshotTypesResponse)
async def get_snapshot_types():
    """Get available snapshot types and their info"""
    criu_available = False
    docker_experimental = False

    try:
        import docker  # type: ignore
        import subprocess

        client = docker.from_env()
        info = client.info()
        docker_experimental = bool(info.get("ExperimentalBuild", False))

        # Check if CRIU is actually available
        try:
            result = subprocess.run(
                ['criu', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            criu_available = (result.returncode == 0)
            if criu_available:
                logger.info(f"CRIU is available: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("CRIU not found or timeout")
            criu_available = False
    except Exception as e:
        logger.warning(f"Error checking CRIU availability: {e}")

    types = [
        SnapshotTypeInfo(
            type=SnapshotTypeEnum.TOPOLOGY_ONLY,
            name="Topology Only",
            description="Quick export of topology structure only",
            estimated_size="1-10 KB",
            estimated_duration="~1 second",
            requires_criu=False,
            requires_running_emulation=False
        ),
        SnapshotTypeInfo(
            type=SnapshotTypeEnum.DOCKER_COMMIT,
            name="Docker Commit",
            description="Filesystem snapshot using docker commit",
            estimated_size="100-500 MB",
            estimated_duration="~30 seconds",
            requires_criu=False,
            requires_running_emulation=True
        ),
        SnapshotTypeInfo(
            type=SnapshotTypeEnum.CRIU_LIVE,
            name="CRIU Live",
            description="Live process checkpoint using CRIU",
            estimated_size="100-300 MB",
            estimated_duration="~1 minute",
            requires_criu=True,
            requires_running_emulation=True
        ),
        SnapshotTypeInfo(
            type=SnapshotTypeEnum.HYBRID_FULL,
            name="Hybrid Full",
            description="Combined Docker commit + CRIU checkpoint",
            estimated_size="200-700 MB",
            estimated_duration="~2 minutes",
            requires_criu=False,  # CRIU optional
            requires_running_emulation=True
        ),
    ]

    return SnapshotTypesResponse(
        types=types,
        criu_available=criu_available,
        docker_experimental=docker_experimental
    )


@app.get("/api/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    topology_id: Optional[str] = Query(None),
    snapshot_type: Optional[SnapshotTypeEnum] = Query(None),
    status: Optional[SnapshotStatusEnum] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """List snapshots with filtering"""
    offset = (page - 1) * per_page
    snapshots, total = pg_storage.list_snapshots(
        topology_id=topology_id,
        snapshot_type=snapshot_type,
        status=status,
        limit=per_page,
        offset=offset
    )

    return SnapshotListResponse(
        items=[_snapshot_to_response(s) for s in snapshots],
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


# ==================== Schedule CRUD ====================

@app.post("/api/snapshots/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    request: ScheduleCreateRequest,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Create a new snapshot schedule"""
    # Validate cron expression
    scheduler = get_scheduler()
    valid, error = scheduler.validate_cron_expression(request.cron_expression)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {error}")

    # Create schedule
    schedule = pg_storage.create_schedule(request)

    # Add to scheduler
    scheduler.add_schedule(schedule)

    # Calculate next run
    next_run = scheduler.get_next_run_time(schedule.cron_expression) if schedule.is_active else None
    schedule.next_run_at = next_run
    pg_storage.db.commit()
    pg_storage.db.refresh(schedule)

    return _schedule_to_response(schedule)


@app.get("/api/snapshots/schedules", response_model=ScheduleListResponse)
async def list_schedules(
    topology_id: Optional[str] = Query(None),
    active_only: bool = Query(False),
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """List all schedules"""
    schedules = pg_storage.list_schedules(topology_id, active_only)
    return ScheduleListResponse(
        items=[_schedule_to_response(s) for s in schedules],
        total=len(schedules)
    )


@app.get("/api/snapshots/schedules/presets")
async def get_cron_presets():
    """Get common cron expression presets"""
    return [{"label": p.label, "cron": p.cron, "description": p.description} for p in CRON_PRESETS]


@app.get("/api/snapshots/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Get schedule details"""
    schedule = pg_storage.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return _schedule_to_response(schedule)


@app.put("/api/snapshots/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Update a schedule"""
    # Validate cron if provided
    if request.cron_expression:
        scheduler = get_scheduler()
        valid, error = scheduler.validate_cron_expression(request.cron_expression)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {error}")

    schedule = pg_storage.update_schedule(schedule_id, request)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Update scheduler
    scheduler = get_scheduler()
    if request.is_active is False:
        scheduler.remove_schedule(schedule_id)
    else:
        scheduler.add_schedule(schedule)

    # Recompute next run time in DB
    if schedule.is_active:
        schedule.next_run_at = scheduler.get_next_run_time(schedule.cron_expression)
    else:
        schedule.next_run_at = None
    pg_storage.db.commit()
    pg_storage.db.refresh(schedule)

    return _schedule_to_response(schedule)


@app.delete("/api/snapshots/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Delete a schedule"""
    # Remove from scheduler first
    scheduler = get_scheduler()
    scheduler.remove_schedule(schedule_id)

    # Delete from database
    if not pg_storage.delete_schedule(schedule_id):
        raise HTTPException(status_code=404, detail="Schedule not found")


@app.post("/api/snapshots/schedules/{schedule_id}/trigger", response_model=SnapshotResponse)
async def trigger_schedule(
    schedule_id: str,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Manually trigger a scheduled snapshot"""
    schedule = pg_storage.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Trigger the schedule
    scheduler = get_scheduler()
    snapshot_id = await scheduler.trigger_now(schedule_id)

    if not snapshot_id:
        raise HTTPException(status_code=500, detail="Failed to trigger snapshot")

    snapshot = pg_storage.get_snapshot(snapshot_id)
    return _snapshot_to_response(snapshot)


# ==================== Snapshot Detail/Actions ====================

@app.get("/api/snapshots/{snapshot_id}", response_model=SnapshotDetailResponse)
async def get_snapshot(
    snapshot_id: str,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage),
    mongo_storage: MongoSnapshotStorage = Depends(get_mongo_storage)
):
    """Get snapshot details"""
    snapshot = pg_storage.get_snapshot_with_history(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Get restore history
    history = pg_storage.get_restore_history(snapshot_id)

    response = _snapshot_to_detail_response(snapshot)
    response.restore_history = [
        {
            "id": h.id,
            "restored_at": h.restored_at.isoformat() if h.restored_at else None,
            "status": h.status,
            "duration_seconds": h.duration_seconds,
            "error_message": h.error_message
        }
        for h in history
    ]

    return response


@app.patch("/api/snapshots/{snapshot_id}", response_model=SnapshotResponse)
async def rename_snapshot(
    snapshot_id: str,
    request: SnapshotRenameRequest,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Rename a snapshot"""
    snapshot = pg_storage.rename_snapshot(snapshot_id, request.name)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return _snapshot_to_response(snapshot)


@app.delete("/api/snapshots/{snapshot_id}", status_code=204)
async def delete_snapshot(
    snapshot_id: str,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage),
    mongo_storage: MongoSnapshotStorage = Depends(get_mongo_storage)
):
    """Delete a snapshot"""
    snapshot = pg_storage.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Delete from MongoDB
    if snapshot.mongo_state_id:
        mongo_storage.delete_state(snapshot_id)

    # Delete from PostgreSQL
    pg_storage.delete_snapshot(snapshot_id)

    # Publish event
    await publish_event("snapshot.deleted", {"snapshot_id": snapshot_id})


@app.post("/api/snapshots/{snapshot_id}/restore", response_model=RestoreResultResponse)
async def restore_snapshot(
    snapshot_id: str,
    request: SnapshotRestoreRequest,
    background_tasks: BackgroundTasks,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage),
    mongo_storage: MongoSnapshotStorage = Depends(get_mongo_storage)
):
    """Restore from a snapshot"""
    snapshot = pg_storage.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    if not snapshot.can_restore:
        raise HTTPException(
            status_code=400,
            detail=f"Snapshot cannot be restored (status: {snapshot.status.value})"
        )

    # Update status
    pg_storage.update_snapshot_status(snapshot_id, SnapshotStatus.RESTORING)

    # Publish event
    await publish_event("snapshot.restore.started", {"snapshot_id": snapshot_id})

    # Start restore in background
    background_tasks.add_task(
        restore_snapshot_background,
        snapshot_id,
        request.model_dump()
    )

    return RestoreResultResponse(
        snapshot_id=snapshot_id,
        success=True,
        status="restoring"
    )


@app.get("/api/snapshots/{snapshot_id}/progress")
async def get_snapshot_progress(snapshot_id: str):
    """Get snapshot operation progress (SSE)"""
    async def event_generator():
        while True:
            # Get current status from database
            db = SessionLocal()
            try:
                storage = PostgresSnapshotStorage(db)
                snapshot = storage.get_snapshot(snapshot_id)

                if not snapshot:
                    yield f"data: {{'error': 'Snapshot not found'}}\n\n"
                    break

                progress = {
                    "snapshot_id": snapshot_id,
                    "status": snapshot.status.value,
                    "progress_percent": _calculate_progress(snapshot),
                    "current_step": _get_current_step(snapshot),
                    "error_message": snapshot.error_message
                }

                yield f"data: {progress}\n\n"

                if snapshot.status in [SnapshotStatus.CAPTURED, SnapshotStatus.FAILED,
                                       SnapshotStatus.RESTORED]:
                    break

            finally:
                db.close()

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@app.get("/api/snapshots/{snapshot_id}/download")
async def download_snapshot(
    snapshot_id: str,
    pg_storage: PostgresSnapshotStorage = Depends(get_postgres_storage)
):
    """Download snapshot as file"""
    snapshot = pg_storage.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    if not snapshot.checkpoint_path or not os.path.exists(snapshot.checkpoint_path):
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    path = Path(snapshot.checkpoint_path)
    suffix = ''.join(path.suffixes) or ''
    filename = f"{snapshot.name}{suffix}"
    if path.name.endswith('.gz'):
        media_type = "application/gzip"
    elif path.suffix == ".json":
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        str(path),
        filename=filename,
        media_type=media_type
    )


# ==================== Background Tasks ====================

async def create_snapshot_background(
    snapshot_id: str,
    request_data: Dict[str, Any],
):
    """Background task for snapshot creation"""
    db = SessionLocal()
    storage = PostgresSnapshotStorage(db)
    mongo_storage = MongoSnapshotStorage()

    try:
        request = SnapshotCreateRequest(**request_data)

        # Update status to capturing
        storage.update_snapshot_status(snapshot_id, SnapshotStatus.CAPTURING)

        start_time = datetime.utcnow()
        if request.snapshot_type == SnapshotTypeEnum.TOPOLOGY_ONLY:
            result = await _capture_topology_only(snapshot_id, request)
        elif request.snapshot_type == SnapshotTypeEnum.DOCKER_COMMIT:
            result = await _capture_docker_commit(snapshot_id, request)
        elif request.snapshot_type == SnapshotTypeEnum.CRIU_LIVE:
            result = await _capture_criu_live(snapshot_id, request)
        elif request.snapshot_type == SnapshotTypeEnum.HYBRID_FULL:
            result = await _capture_hybrid_full(snapshot_id, request)
        else:
            raise Exception(f"Unsupported snapshot type: {request.snapshot_type}")

        duration_seconds = (datetime.utcnow() - start_time).total_seconds()

        # Store state data in MongoDB
        mongo_id = mongo_storage.create_state(
            snapshot_id=snapshot_id,
            topology_id=request.topology_id,
            topology_data=result.get("topology_data", {}),
            network_state=result.get("network_state"),
            docker_snapshots=result.get("docker_images"),
            criu_checkpoints=result.get("criu_checkpoints")
        )

        # Update PostgreSQL record
        snapshot_record = storage.get_snapshot(snapshot_id)
        merged_metadata = dict((snapshot_record.extra_metadata or {}) if snapshot_record else {})
        merged_metadata.update(result.get("extra_metadata") or {})

        storage.update_snapshot_status(
            snapshot_id,
            SnapshotStatus.CAPTURED,
            mongo_state_id=mongo_id,
            checkpoint_path=result.get("snapshot_path"),
            size_bytes=result.get("size_bytes", 0),
            device_count=result.get("devices_captured", 0),
            container_count=result.get("containers_captured", 0),
            criu_available=result.get("criu_available", False),
            capture_duration_seconds=duration_seconds,
            extra_metadata=merged_metadata,
        )

        # Publish success event
        await publish_event("snapshot.captured", {
            "snapshot_id": snapshot_id,
            "size_mb": result.get("size_bytes", 0) / 1024 / 1024,
            "duration_seconds": duration_seconds
        })

        logger.info(f"Snapshot {snapshot_id} created successfully")

    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}")
        storage.update_snapshot_status(
            snapshot_id,
            SnapshotStatus.FAILED,
            error_message=str(e)
        )

        await publish_event("snapshot.failed", {
            "snapshot_id": snapshot_id,
            "error": str(e)
        })
    finally:
        db.close()


async def restore_snapshot_background(
    snapshot_id: str,
    request_data: Dict[str, Any],
):
    """Background task for snapshot restoration."""
    db = SessionLocal()
    storage = PostgresSnapshotStorage(db)
    mongo_storage = MongoSnapshotStorage()

    start_time = datetime.utcnow()
    try:
        request = SnapshotRestoreRequest(**request_data)
        snapshot = storage.get_snapshot(snapshot_id)
        if not snapshot:
            raise Exception("Snapshot not found")

        target_topology_id = request.target_topology_id or snapshot.topology_id
        warnings: list[str] = []

        state_doc = mongo_storage.get_state(snapshot_id) or {}
        topology_data = state_doc.get("topology") or {}
        topo_nodes = topology_data.get("nodes") if isinstance(topology_data, dict) else []
        if not isinstance(topo_nodes, list):
            topo_nodes = []

        if request.stop_existing_emulation:
            try:
                await _stop_running_emulation_if_any(target_topology_id)
            except Exception as exc:
                warnings.append(f"Could not stop existing emulation cleanly: {exc}")

        # Start (or restart) emulation for target topology.
        start_payload = {"topology_id": target_topology_id, "options": {}}
        async with httpx.AsyncClient(timeout=180.0) as client:
            start_resp = await client.post(f"{ORCHESTRATOR_URL}/api/emulation/start", json=start_payload)
            if start_resp.status_code >= 400:
                raise Exception(
                    f"Failed to start target topology {target_topology_id}: "
                    f"HTTP {start_resp.status_code} {start_resp.text[:300]}"
                )
            start_json = start_resp.json() or {}
            if not bool(start_json.get("success")):
                raise Exception(start_json.get("message") or "Emulation start failed during restore")

        # CRIU/Docker low-level restore hooks are environment-dependent; keep explicit warning instead of hard fail.
        if request.restore_criu_checkpoints and state_doc.get("criu_checkpoints"):
            warnings.append(
                "CRIU checkpoint entries were detected, but direct low-level checkpoint restore is "
                "skipped in snapshot-service; emulation was restarted to a consistent topology state."
            )
        if request.restore_docker_images and state_doc.get("docker_snapshots"):
            warnings.append(
                "Docker image snapshot entries were detected; runtime was restarted using topology state."
            )
        if request.restore_network_state and state_doc.get("network_state"):
            warnings.append(
                "Detailed network runtime state replay (routes/flows/ARP) is not yet automated in snapshot-service."
            )

        duration = (datetime.utcnow() - start_time).total_seconds()
        storage.add_restore_history(
            snapshot_id=snapshot_id,
            status="success",
            duration_seconds=duration,
            target_topology_id=target_topology_id,
            devices_restored=len(topo_nodes),
            containers_restored=0,
            network_state_restored=False,
            warnings=warnings,
            rollback_performed=False,
        )
        storage.update_snapshot(
            snapshot_id,
            restored_at=datetime.utcnow(),
            status=SnapshotStatus.RESTORED,
            error_message=None,
        )

        await publish_event(
            "snapshot.restore.completed",
            {
                "snapshot_id": snapshot_id,
                "target_topology_id": target_topology_id,
                "duration_seconds": duration,
                "warnings": warnings,
            },
        )
    except Exception as e:
        logger.error(f"Snapshot restoration failed: {e}")

        duration = (datetime.utcnow() - start_time).total_seconds()
        storage.add_restore_history(
            snapshot_id=snapshot_id,
            status="failed",
            duration_seconds=duration,
            error_message=str(e)
        )

        storage.update_snapshot_status(
            snapshot_id,
            SnapshotStatus.CAPTURED,  # Revert status
            error_message=str(e),
        )

        await publish_event(
            "snapshot.restore.failed",
            {
                "snapshot_id": snapshot_id,
                "error": str(e),
                "duration_seconds": duration,
            },
        )
    finally:
        db.close()


async def execute_scheduled_snapshot(schedule_id: str) -> Optional[str]:
    """Execute a scheduled snapshot (called by scheduler)"""
    db = SessionLocal()
    try:
        storage = PostgresSnapshotStorage(db)
        schedule = storage.get_schedule(schedule_id)

        if not schedule or not schedule.is_active:
            return None

        # Create snapshot request
        snapshot_name = f"{schedule.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        request = SnapshotCreateRequest(
            name=snapshot_name,
            topology_id=schedule.topology_id or "global",
            snapshot_type=SnapshotTypeEnum(schedule.snapshot_type.value),
            compression=schedule.compression,
            target_containers=schedule.target_containers,
            include_routing_tables=schedule.include_routing_tables,
            include_flow_tables=schedule.include_flow_tables,
            include_arp_tables=schedule.include_arp_tables,
            description=f"Scheduled snapshot from '{schedule.name}'"
        )

        # Create snapshot
        snapshot = storage.create_snapshot(request)

        # Update schedule
        scheduler = get_scheduler()
        next_run = scheduler.get_next_run_time(schedule.cron_expression)
        storage.update_schedule_last_run(schedule_id, snapshot.id, next_run)

        # Start background capture
        await create_snapshot_background(snapshot.id, request.model_dump())

        return snapshot.id

    except Exception as e:
        logger.error(f"Scheduled snapshot failed: {e}")
        storage.increment_schedule_failure(schedule_id)
        return None
    finally:
        db.close()


async def apply_retention_policy(schedule_id: str):
    """Apply retention policy for a schedule"""
    db = SessionLocal()
    try:
        storage = PostgresSnapshotStorage(db)
        mongo_storage = MongoSnapshotStorage()

        schedule = storage.get_schedule(schedule_id)
        if not schedule:
            return

        # Get snapshots to delete based on count
        to_delete = storage.get_snapshots_for_retention(
            schedule_id,
            schedule.retention_count
        )

        for snapshot in to_delete:
            # Delete from MongoDB
            if snapshot.mongo_state_id:
                mongo_storage.delete_state(snapshot.id)

            # Delete from PostgreSQL
            storage.delete_snapshot(snapshot.id)

            logger.info(f"Deleted snapshot {snapshot.id} (retention policy)")

    except Exception as e:
        logger.error(f"Retention policy failed: {e}")
    finally:
        db.close()


async def load_schedules_from_db():
    """Load existing schedules into scheduler on startup"""
    db = SessionLocal()
    try:
        storage = PostgresSnapshotStorage(db)
        schedules = storage.list_schedules(active_only=True)

        scheduler = get_scheduler()
        for schedule in schedules:
            scheduler.add_schedule(schedule)
            schedule.next_run_at = scheduler.get_next_run_time(schedule.cron_expression)

        db.commit()

        logger.info(f"Loaded {len(schedules)} schedules from database")

    except Exception as e:
        logger.error(f"Failed to load schedules: {e}")
    finally:
        db.close()


# ==================== Snapshot Capture Implementations ====================

def _safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "item"


async def _fetch_topology(topology_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}")
        resp.raise_for_status()
        return resp.json()


async def _resolve_target_containers(topology_id: str, include_stopped: bool = True) -> List[str]:
    """Resolve containers related to a topology (best-effort)."""
    # Prefer orchestrator (tracks active emulation container name).
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/api/emulation/containers",
                params={"topology_id": topology_id, "include_stopped": include_stopped},
            )
            if resp.status_code == 200:
                items = resp.json().get("items", []) or []
                names = [i.get("name") for i in items if i.get("name")]
                if names:
                    return names
    except Exception:
        pass

    # Fallback: inspect Docker directly.
    try:
        import docker  # type: ignore
        client = docker.from_env()
        containers = client.containers.list(all=include_stopped)
        prefix = f"caduceus-emu-{topology_id[:8]}"
        names: list[str] = []
        for c in containers:
            name = getattr(c, "name", "")
            if not name:
                continue
            labels = getattr(c, "labels", {}) or {}
            labeled_topology_id = labels.get("caduceus.topology_id")
            if labeled_topology_id == topology_id or name.startswith(prefix):
                names.append(name)
        return names
    except Exception:
        return []


async def _find_running_emulation(topology_id: str) -> Optional[Dict[str, Any]]:
    """Return active running emulation record for a topology."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{ORCHESTRATOR_URL}/api/emulation/active")
            if resp.status_code != 200:
                return None
            emulations = (resp.json() or {}).get("emulations") or []
            for item in emulations:
                if str(item.get("topology_id") or "") != str(topology_id):
                    continue
                if str(item.get("status") or "").lower() == "running":
                    return item
    except Exception:
        return None
    return None


async def _wait_for_topology_stop(topology_id: str, timeout_seconds: float = 120.0) -> bool:
    """Wait until topology has no running emulation."""
    started = datetime.utcnow()
    while (datetime.utcnow() - started).total_seconds() < timeout_seconds:
        running = await _find_running_emulation(topology_id)
        if not running:
            return True
        await asyncio.sleep(2.0)
    return False


async def _stop_running_emulation_if_any(topology_id: str) -> Dict[str, Any]:
    """
    Stop the running emulation (if present) and wait until it is down.
    """
    current = await _find_running_emulation(topology_id)
    if not current:
        return {"stopped": False, "message": "No running emulation found"}

    emulation_id = str(current.get("emulation_id") or "").strip()
    if not emulation_id:
        return {"stopped": False, "message": "Running emulation has no emulation_id"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/api/emulation/stop/{emulation_id}",
            json={"cleanup": True},
        )
        if resp.status_code >= 400:
            raise Exception(f"Failed to stop emulation {emulation_id}: HTTP {resp.status_code} {resp.text[:300]}")

    stopped = await _wait_for_topology_stop(topology_id)
    if not stopped:
        raise Exception(f"Timed out waiting for topology {topology_id} emulation to stop")
    return {"stopped": True, "emulation_id": emulation_id}


def _docker_checkpoint_support_reason(container_name: str) -> Optional[str]:
    """
    Check whether docker checkpoint/restore is usable in current environment.
    Returns None if supported, otherwise returns a human-readable reason.
    """
    import subprocess

    try:
        criu = subprocess.run(
            ["criu", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if criu.returncode != 0:
            return (criu.stderr or criu.stdout or "CRIU command failed").strip()
    except FileNotFoundError:
        return "CRIU is not installed in snapshot-service"
    except Exception as exc:
        return f"Unable to execute CRIU: {exc}"

    try:
        import docker  # type: ignore
        client = docker.from_env()
        info = client.info() or {}
        if not bool(info.get("ExperimentalBuild", False)):
            return "Docker daemon experimental checkpoint support is disabled"
    except Exception as exc:
        return f"Docker daemon capability probe failed: {exc}"

    # At this point CRIU is present and Docker reports experimental mode; treat checkpoint support as available.
    return None


async def _capture_topology_only(snapshot_id: str, request: SnapshotCreateRequest) -> Dict[str, Any]:
    topology_id = request.topology_id
    if not topology_id:
        raise Exception("topology_id is required for topology-only snapshots")

    topology_data = await _fetch_topology(topology_id)
    nodes = topology_data.get("nodes", []) or []

    snapshot_dir = SNAPSHOT_STORAGE_DIR / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{snapshot_id}.json.gz"

    payload = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.utcnow().isoformat(),
        "snapshot_type": request.snapshot_type.value,
        "topology": topology_data,
        "options": {
            "include_routing_tables": request.include_routing_tables,
            "include_flow_tables": request.include_flow_tables,
            "include_arp_tables": request.include_arp_tables,
        },
    }

    with gzip.open(snapshot_path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)

    size_bytes = snapshot_path.stat().st_size
    return {
        "success": True,
        "snapshot_path": str(snapshot_path),
        "size_bytes": size_bytes,
        "devices_captured": len(nodes),
        "containers_captured": 0,
        "criu_available": False,
        "topology_data": topology_data,
        "network_state": None,
        "docker_images": None,
        "criu_checkpoints": None,
        "extra_metadata": {
            "requested_snapshot_type": SnapshotTypeEnum.TOPOLOGY_ONLY.value,
            "effective_snapshot_type": SnapshotTypeEnum.TOPOLOGY_ONLY.value,
        },
    }


def _docker_commit_and_export(snapshot_id: str, container_names: List[str]) -> Dict[str, Any]:
    import docker  # type: ignore

    client = docker.from_env()

    snapshot_dir = SNAPSHOT_STORAGE_DIR / snapshot_id
    images_dir = snapshot_dir / "images"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    docker_images: list[dict[str, Any]] = []
    total_size = 0

    for name in container_names:
        container = client.containers.get(name)
        safe_name = _safe_slug(name)
        repo = "caduceus-snapshots"
        tag = f"{snapshot_id}-{safe_name}"
        image = container.commit(repository=repo, tag=tag)

        tar_path = images_dir / f"{safe_name}.tar"
        with open(tar_path, "wb") as f:
            for chunk in image.save(named=True):
                f.write(chunk)

        size_bytes = tar_path.stat().st_size
        total_size += size_bytes

        docker_images.append({
            "container_name": name,
            "image_id": getattr(image, "id", None),
            "image_ref": f"{repo}:{tag}",
            "tar_path": str(tar_path),
            "size_bytes": size_bytes,
        })

    # Metadata file (downloadable) describing committed images.
    meta_path = snapshot_dir / "docker_commit.json.gz"
    with gzip.open(meta_path, "wt", encoding="utf-8") as f:
        json.dump({"snapshot_id": snapshot_id, "docker_images": docker_images}, f)

    total_size += meta_path.stat().st_size

    return {
        "docker_images": docker_images,
        "size_bytes": total_size,
        "snapshot_path": str(meta_path),
        "containers_captured": len(container_names),
    }


async def _capture_criu_live(snapshot_id: str, request: SnapshotCreateRequest) -> Dict[str, Any]:
    """Capture CRIU live checkpoint of running containers"""
    import subprocess

    topology_id = request.topology_id
    if not topology_id:
        raise Exception("topology_id is required for CRIU snapshots")

    # Get containers to checkpoint
    container_names = request.target_containers or await _resolve_target_containers(topology_id)
    if not container_names:
        raise Exception("No containers found for this topology. Start the emulation first.")

    # Verify checkpoint support. If unavailable, gracefully fall back to docker commit snapshot.
    support_reason = _docker_checkpoint_support_reason(container_names[0])
    if support_reason:
        logger.warning(
            "CRIU live snapshot requested but docker checkpoint is unavailable; "
            "falling back to docker_commit capture. reason=%s",
            support_reason,
        )
        fallback = await _capture_docker_commit(snapshot_id, request)
        extra = dict(fallback.get("extra_metadata") or {})
        extra.update({
            "requested_snapshot_type": SnapshotTypeEnum.CRIU_LIVE.value,
            "effective_snapshot_type": SnapshotTypeEnum.DOCKER_COMMIT.value,
            "criu_fallback_reason": support_reason,
        })
        fallback["extra_metadata"] = extra
        fallback["criu_available"] = False
        fallback["criu_checkpoints"] = {}
        return fallback

    snapshot_dir = SNAPSHOT_STORAGE_DIR / snapshot_id
    checkpoint_dir = snapshot_dir / "criu_checkpoints"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    criu_checkpoints = []
    total_size = 0

    import docker
    client = docker.from_env()

    for container_name in container_names:
        try:
            container = client.containers.get(container_name)
            checkpoint_name = f"{snapshot_id}_{container_name}"

            logger.info(f"Creating CRIU checkpoint for container {container_name}")

            # Docker checkpoint create command
            cmd = [
                'docker', 'checkpoint', 'create',
                '--leave-running',
                container_name,
                checkpoint_name
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                logger.error(f"CRIU checkpoint failed for {container_name}: {result.stderr}")
                raise Exception(f"CRIU checkpoint failed: {result.stderr}")

            # Get checkpoint directory (Docker stores in /var/lib/docker/containers/<id>/checkpoints/)
            container_info = client.api.inspect_container(container.id)
            container_id = container_info['Id']
            checkpoint_path = f"/var/lib/docker/containers/{container_id}/checkpoints/{checkpoint_name}"

            # Calculate checkpoint size
            try:
                size_result = subprocess.run(
                    ['du', '-sb', checkpoint_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if size_result.returncode == 0:
                    size_bytes = int(size_result.stdout.split()[0])
                    total_size += size_bytes
                else:
                    size_bytes = 0
            except Exception:
                size_bytes = 0

            criu_checkpoints.append({
                'container_name': container_name,
                'container_id': container_id,
                'checkpoint_name': checkpoint_name,
                'checkpoint_path': checkpoint_path,
                'size_bytes': size_bytes
            })

            logger.info(f"CRIU checkpoint created for {container_name}: {checkpoint_name}")

        except Exception as e:
            logger.error(f"Failed to checkpoint container {container_name}: {e}")
            raise

    # Get topology data
    topology_data = await _fetch_topology(topology_id)

    # Create metadata file
    meta_path = snapshot_dir / "criu_live.json.gz"
    metadata = {
        'snapshot_id': snapshot_id,
        'snapshot_type': 'criu_live',
        'created_at': datetime.utcnow().isoformat(),
        'topology': topology_data,
        'criu_checkpoints': criu_checkpoints
    }

    with gzip.open(meta_path, "wt", encoding="utf-8") as f:
        json.dump(metadata, f)

    total_size += meta_path.stat().st_size

    extra_metadata = {
        "requested_snapshot_type": SnapshotTypeEnum.CRIU_LIVE.value,
        "effective_snapshot_type": SnapshotTypeEnum.CRIU_LIVE.value,
    }

    return {
        'success': True,
        'snapshot_path': str(meta_path),
        'size_bytes': total_size,
        'devices_captured': len(topology_data.get("nodes", []) or []),
        'containers_captured': len(container_names),
        'criu_available': True,
        'topology_data': topology_data,
        'network_state': None,
        'docker_images': None,
        'criu_checkpoints': criu_checkpoints,
        'extra_metadata': extra_metadata,
    }


async def _capture_hybrid_full(snapshot_id: str, request: SnapshotCreateRequest) -> Dict[str, Any]:
    """Capture hybrid snapshot with both Docker commit and CRIU checkpoint"""
    import subprocess

    topology_id = request.topology_id
    if not topology_id:
        raise Exception("topology_id is required for hybrid snapshots")

    if not Path("/var/run/docker.sock").exists():
        raise Exception("Docker socket not available in snapshot-service container")

    container_names = request.target_containers or await _resolve_target_containers(topology_id)
    if not container_names:
        raise Exception("No containers found for this topology. Start the emulation first.")

    # First, create Docker commit snapshots
    docker_result = await asyncio.to_thread(_docker_commit_and_export, snapshot_id, container_names)

    # Then, create CRIU checkpoints
    snapshot_dir = SNAPSHOT_STORAGE_DIR / snapshot_id
    checkpoint_dir = snapshot_dir / "criu_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    criu_checkpoints = []
    criu_total_size = 0
    criu_available = True
    support_reason = _docker_checkpoint_support_reason(container_names[0])
    if support_reason:
        criu_available = False
        logger.warning(
            "Hybrid snapshot requested but docker checkpoint is unavailable; "
            "continuing with docker_commit part only. reason=%s",
            support_reason,
        )

    import docker
    client = docker.from_env()

    if criu_available:
        for container_name in container_names:
            try:
                container = client.containers.get(container_name)
                checkpoint_name = f"{snapshot_id}_{container_name}"

                logger.info(f"Creating CRIU checkpoint for container {container_name}")

                cmd = [
                    'docker', 'checkpoint', 'create',
                    '--leave-running',
                    container_name,
                    checkpoint_name
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

                if result.returncode != 0:
                    logger.warning(f"CRIU checkpoint failed for {container_name}: {result.stderr}")
                    continue

                container_info = client.api.inspect_container(container.id)
                container_id = container_info['Id']
                checkpoint_path = f"/var/lib/docker/containers/{container_id}/checkpoints/{checkpoint_name}"

                try:
                    size_result = subprocess.run(
                        ['du', '-sb', checkpoint_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if size_result.returncode == 0:
                        size_bytes = int(size_result.stdout.split()[0])
                        criu_total_size += size_bytes
                    else:
                        size_bytes = 0
                except Exception:
                    size_bytes = 0

                criu_checkpoints.append({
                    'container_name': container_name,
                    'container_id': container_id,
                    'checkpoint_name': checkpoint_name,
                    'checkpoint_path': checkpoint_path,
                    'size_bytes': size_bytes
                })

            except Exception as e:
                logger.warning(f"Failed to checkpoint container {container_name}: {e}")

    # Get topology data
    topology_data = await _fetch_topology(topology_id)

    # Create hybrid metadata file
    meta_path = snapshot_dir / "hybrid_full.json.gz"
    metadata = {
        'snapshot_id': snapshot_id,
        'snapshot_type': 'hybrid_full',
        'created_at': datetime.utcnow().isoformat(),
        'topology': topology_data,
        'docker_images': docker_result['docker_images'],
        'criu_checkpoints': criu_checkpoints
    }

    with gzip.open(meta_path, "wt", encoding="utf-8") as f:
        json.dump(metadata, f)

    total_size = docker_result['size_bytes'] + criu_total_size + meta_path.stat().st_size
    extra_metadata = {
        "requested_snapshot_type": SnapshotTypeEnum.HYBRID_FULL.value,
        "effective_snapshot_type": SnapshotTypeEnum.HYBRID_FULL.value if criu_available else SnapshotTypeEnum.DOCKER_COMMIT.value,
    }
    if support_reason:
        extra_metadata["criu_fallback_reason"] = support_reason

    return {
        'success': True,
        'snapshot_path': str(meta_path),
        'size_bytes': total_size,
        'devices_captured': len(topology_data.get("nodes", []) or []),
        'containers_captured': len(container_names),
        'criu_available': criu_available and bool(criu_checkpoints),
        'topology_data': topology_data,
        'network_state': None,
        'docker_images': docker_result['docker_images'],
        'criu_checkpoints': criu_checkpoints,
        'extra_metadata': extra_metadata,
    }


async def _capture_docker_commit(snapshot_id: str, request: SnapshotCreateRequest) -> Dict[str, Any]:
    topology_id = request.topology_id
    if not topology_id:
        raise Exception("topology_id is required for docker snapshots")

    if not Path("/var/run/docker.sock").exists():
        raise Exception("Docker socket not available in snapshot-service container")

    container_names = request.target_containers or await _resolve_target_containers(topology_id)
    if not container_names:
        raise Exception("No containers found for this topology. Start the emulation first.")

    docker_result = await asyncio.to_thread(_docker_commit_and_export, snapshot_id, container_names)
    topology_data = await _fetch_topology(topology_id)

    return {
        "success": True,
        "snapshot_path": docker_result["snapshot_path"],
        "size_bytes": docker_result["size_bytes"],
        "devices_captured": len(topology_data.get("nodes", []) or []),
        "containers_captured": docker_result["containers_captured"],
        "criu_available": False,
        "topology_data": topology_data,
        "network_state": None,
        "docker_images": docker_result["docker_images"],
        "criu_checkpoints": None,
        "extra_metadata": {
            "requested_snapshot_type": SnapshotTypeEnum.DOCKER_COMMIT.value,
            "effective_snapshot_type": SnapshotTypeEnum.DOCKER_COMMIT.value,
        },
    }


async def mark_stale_snapshots_failed(max_age_minutes: int = 15):
    """Mark long-running CAPTURING snapshots as failed (avoid stuck UI)."""
    db = SessionLocal()
    try:
        storage = PostgresSnapshotStorage(db)
        cutoff = datetime.utcnow().timestamp() - (max_age_minutes * 60)
        snapshots, _ = storage.list_snapshots(status=SnapshotStatusEnum.CAPTURING, limit=500, offset=0)
        for s in snapshots:
            created_ts = (s.created_at or datetime.utcnow()).timestamp()
            if created_ts < cutoff:
                storage.update_snapshot_status(
                    s.id,
                    SnapshotStatus.FAILED,
                    error_message="Snapshot timed out while capturing",
                )
    except Exception as e:
        logger.warning("Failed to mark stale snapshots: %s", e)
    finally:
        db.close()


# ==================== Event Publishing ====================

async def publish_event(event_type: str, data: Dict[str, Any]):
    """Publish event to RabbitMQ (placeholder)"""
    # TODO: Implement RabbitMQ publishing
    logger.info(f"Event: {event_type} - {data}")


# ==================== Helper Functions ====================

def _snapshot_to_response(snapshot: Snapshot) -> SnapshotResponse:
    """Convert Snapshot model to response"""
    return SnapshotResponse(
        id=snapshot.id,
        name=snapshot.name,
        topology_id=snapshot.topology_id,
        emulation_id=snapshot.emulation_id,
        snapshot_type=SnapshotTypeEnum(snapshot.snapshot_type.value),
        status=SnapshotStatusEnum(snapshot.status.value),
        description=snapshot.description,
        size_bytes=snapshot.size_bytes or 0,
        size_mb=snapshot.size_mb,
        compressed=snapshot.compressed,
        device_count=snapshot.device_count or 0,
        container_count=snapshot.container_count or 0,
        criu_available=snapshot.criu_available,
        created_at=snapshot.created_at,
        captured_at=snapshot.captured_at,
        error_message=snapshot.error_message
    )


def _snapshot_to_detail_response(snapshot: Snapshot) -> SnapshotDetailResponse:
    """Convert Snapshot model to detail response"""
    return SnapshotDetailResponse(
        id=snapshot.id,
        name=snapshot.name,
        topology_id=snapshot.topology_id,
        emulation_id=snapshot.emulation_id,
        snapshot_type=SnapshotTypeEnum(snapshot.snapshot_type.value),
        status=SnapshotStatusEnum(snapshot.status.value),
        description=snapshot.description,
        size_bytes=snapshot.size_bytes or 0,
        size_mb=snapshot.size_mb,
        compressed=snapshot.compressed,
        device_count=snapshot.device_count or 0,
        container_count=snapshot.container_count or 0,
        criu_available=snapshot.criu_available,
        created_at=snapshot.created_at,
        captured_at=snapshot.captured_at,
        error_message=snapshot.error_message,
        mongo_state_id=snapshot.mongo_state_id,
        checkpoint_path=snapshot.checkpoint_path,
        target_containers=snapshot.target_containers,
        capture_duration_seconds=snapshot.capture_duration_seconds,
        restored_at=snapshot.restored_at,
        expires_at=snapshot.expires_at,
        extra_metadata=snapshot.extra_metadata or {}
    )


def _schedule_to_response(schedule: SnapshotSchedule) -> ScheduleResponse:
    """Convert SnapshotSchedule model to response"""
    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        topology_id=schedule.topology_id,
        target_containers=schedule.target_containers,
        cron_expression=schedule.cron_expression,
        snapshot_type=SnapshotTypeEnum(schedule.snapshot_type.value),
        is_active=schedule.is_active,
        retention_count=schedule.retention_count,
        retention_days=schedule.retention_days,
        compression=schedule.compression,
        include_routing_tables=schedule.include_routing_tables,
        include_flow_tables=schedule.include_flow_tables,
        include_arp_tables=schedule.include_arp_tables,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        last_snapshot_id=schedule.last_snapshot_id,
        run_count=schedule.run_count,
        failure_count=schedule.failure_count,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        description=schedule.description
    )


def _calculate_progress(snapshot: Snapshot) -> int:
    """Calculate progress percentage based on status"""
    progress_map = {
        SnapshotStatus.PENDING: 0,
        SnapshotStatus.CAPTURING: 50,
        SnapshotStatus.CAPTURED: 100,
        SnapshotStatus.FAILED: 0,
        SnapshotStatus.RESTORING: 50,
        SnapshotStatus.RESTORED: 100,
    }
    return progress_map.get(snapshot.status, 0)


def _get_current_step(snapshot: Snapshot) -> str:
    """Get current step description"""
    step_map = {
        SnapshotStatus.PENDING: "Waiting to start",
        SnapshotStatus.CAPTURING: "Capturing snapshot",
        SnapshotStatus.CAPTURED: "Capture complete",
        SnapshotStatus.FAILED: "Failed",
        SnapshotStatus.RESTORING: "Restoring snapshot",
        SnapshotStatus.RESTORED: "Restore complete",
    }
    return step_map.get(snapshot.status, "Unknown")


# ==================== Main ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
