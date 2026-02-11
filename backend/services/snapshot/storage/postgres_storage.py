"""
PostgreSQL storage layer for snapshot metadata
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from shared.models.snapshot import (
    Snapshot, SnapshotRestoreHistory, SnapshotSchedule,
    SnapshotType, SnapshotStatus
)
from shared.schemas.snapshot_schema import (
    SnapshotCreateRequest, ScheduleCreateRequest, ScheduleUpdateRequest,
    SnapshotStatusEnum, SnapshotTypeEnum
)

logger = logging.getLogger(__name__)


class PostgresSnapshotStorage:
    """
    PostgreSQL storage operations for snapshot metadata
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== Snapshot Operations ====================

    def create_snapshot(self, request: SnapshotCreateRequest) -> Snapshot:
        """Create a new snapshot record"""
        snapshot = Snapshot(
            id=str(uuid4()),
            topology_id=request.topology_id,
            emulation_id=request.emulation_id,
            name=request.name,
            description=request.description,
            snapshot_type=SnapshotType(request.snapshot_type.value),
            status=SnapshotStatus.PENDING,
            compressed=request.compression,
            target_containers=request.target_containers,
            extra_metadata={
                "include_routing_tables": request.include_routing_tables,
                "include_flow_tables": request.include_flow_tables,
                "include_arp_tables": request.include_arp_tables,
            }
        )

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(f"Created snapshot record: {snapshot.id} ({snapshot.name})")
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID"""
        return self.db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()

    def get_snapshot_with_history(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot with restore history loaded"""
        return self.db.query(Snapshot)\
            .filter(Snapshot.id == snapshot_id)\
            .first()

    def list_snapshots(
        self,
        topology_id: Optional[str] = None,
        snapshot_type: Optional[SnapshotTypeEnum] = None,
        status: Optional[SnapshotStatusEnum] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[Snapshot], int]:
        """List snapshots with filtering"""
        query = self.db.query(Snapshot)

        # Apply filters
        filters = []
        if topology_id:
            filters.append(Snapshot.topology_id == topology_id)
        if snapshot_type:
            filters.append(Snapshot.snapshot_type == SnapshotType(snapshot_type.value))
        if status:
            filters.append(Snapshot.status == SnapshotStatus(status.value))

        if filters:
            query = query.filter(and_(*filters))

        # Get total count
        total = query.count()

        # Apply ordering and pagination
        snapshots = query.order_by(desc(Snapshot.created_at))\
            .offset(offset)\
            .limit(limit)\
            .all()

        return snapshots, total

    def update_snapshot_status(
        self,
        snapshot_id: str,
        status: SnapshotStatus,
        error_message: Optional[str] = None,
        **kwargs
    ) -> Optional[Snapshot]:
        """Update snapshot status and optional fields"""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return None

        snapshot.status = status

        if error_message:
            snapshot.error_message = error_message

        # Update optional fields
        if status == SnapshotStatus.CAPTURED:
            snapshot.captured_at = datetime.utcnow()

        for key, value in kwargs.items():
            if hasattr(snapshot, key):
                setattr(snapshot, key, value)

        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(f"Updated snapshot {snapshot_id} status to {status.value}")
        return snapshot

    def update_snapshot(
        self,
        snapshot_id: str,
        **kwargs
    ) -> Optional[Snapshot]:
        """Update snapshot fields"""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return None

        for key, value in kwargs.items():
            if hasattr(snapshot, key):
                setattr(snapshot, key, value)

        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def rename_snapshot(self, snapshot_id: str, new_name: str) -> Optional[Snapshot]:
        """Rename a snapshot"""
        return self.update_snapshot(snapshot_id, name=new_name)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return False

        self.db.delete(snapshot)
        self.db.commit()

        logger.info(f"Deleted snapshot: {snapshot_id}")
        return True

    def get_stats(self, topology_id: Optional[str] = None) -> Dict[str, Any]:
        """Get snapshot statistics"""
        query = self.db.query(Snapshot)

        if topology_id:
            query = query.filter(Snapshot.topology_id == topology_id)

        total = query.count()
        total_size = query.with_entities(func.sum(Snapshot.size_bytes)).scalar() or 0

        # By type
        by_type = {}
        for snap_type in SnapshotType:
            count = query.filter(Snapshot.snapshot_type == snap_type).count()
            by_type[snap_type.value] = count

        # By status
        by_status = {}
        for snap_status in SnapshotStatus:
            count = query.filter(Snapshot.status == snap_status).count()
            by_status[snap_status.value] = count

        # CRIU enabled count
        criu_count = query.filter(Snapshot.criu_available == True).count()

        # Oldest and newest
        oldest = query.order_by(Snapshot.created_at).first()
        newest = query.order_by(desc(Snapshot.created_at)).first()

        # Active schedules
        active_schedules = self.db.query(SnapshotSchedule)\
            .filter(SnapshotSchedule.is_active == True).count()

        return {
            "total_snapshots": total,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024) if total_size else 0,
            "by_type": by_type,
            "by_status": by_status,
            "criu_enabled_count": criu_count,
            "oldest_snapshot": oldest.created_at if oldest else None,
            "newest_snapshot": newest.created_at if newest else None,
            "active_schedules": active_schedules
        }

    # ==================== Restore History Operations ====================

    def add_restore_history(
        self,
        snapshot_id: str,
        status: str,
        restored_by: Optional[str] = None,
        target_topology_id: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        devices_restored: int = 0,
        containers_restored: int = 0,
        network_state_restored: bool = False,
        error_message: Optional[str] = None,
        warnings: Optional[List[str]] = None,
        rollback_performed: bool = False
    ) -> SnapshotRestoreHistory:
        """Add a restore history entry"""
        history = SnapshotRestoreHistory(
            id=str(uuid4()),
            snapshot_id=snapshot_id,
            status=status,
            restored_by=restored_by,
            target_topology_id=target_topology_id,
            duration_seconds=duration_seconds,
            devices_restored=devices_restored,
            containers_restored=containers_restored,
            network_state_restored=network_state_restored,
            error_message=error_message,
            warnings=warnings or [],
            rollback_performed=rollback_performed
        )

        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)

        # Update snapshot restored_at
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot and status == "success":
            snapshot.restored_at = datetime.utcnow()
            snapshot.status = SnapshotStatus.RESTORED
            self.db.commit()

        logger.info(f"Added restore history for snapshot {snapshot_id}: {status}")
        return history

    def get_restore_history(self, snapshot_id: str) -> List[SnapshotRestoreHistory]:
        """Get restore history for a snapshot"""
        return self.db.query(SnapshotRestoreHistory)\
            .filter(SnapshotRestoreHistory.snapshot_id == snapshot_id)\
            .order_by(desc(SnapshotRestoreHistory.restored_at))\
            .all()

    # ==================== Schedule Operations ====================

    def create_schedule(self, request: ScheduleCreateRequest) -> SnapshotSchedule:
        """Create a new snapshot schedule"""
        schedule = SnapshotSchedule(
            id=str(uuid4()),
            name=request.name,
            description=request.description,
            topology_id=request.topology_id,
            target_containers=request.target_containers,
            cron_expression=request.cron_expression,
            snapshot_type=SnapshotType(request.snapshot_type.value),
            is_active=True,
            retention_count=request.retention_count,
            retention_days=request.retention_days,
            compression=request.compression,
            include_routing_tables=request.include_routing_tables,
            include_flow_tables=request.include_flow_tables,
            include_arp_tables=request.include_arp_tables
        )

        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)

        logger.info(f"Created schedule: {schedule.id} ({schedule.name})")
        return schedule

    def get_schedule(self, schedule_id: str) -> Optional[SnapshotSchedule]:
        """Get a schedule by ID"""
        return self.db.query(SnapshotSchedule)\
            .filter(SnapshotSchedule.id == schedule_id)\
            .first()

    def list_schedules(
        self,
        topology_id: Optional[str] = None,
        active_only: bool = False
    ) -> List[SnapshotSchedule]:
        """List all schedules"""
        query = self.db.query(SnapshotSchedule)

        if topology_id:
            query = query.filter(
                or_(
                    SnapshotSchedule.topology_id == topology_id,
                    SnapshotSchedule.topology_id == None  # Global schedules
                )
            )

        if active_only:
            query = query.filter(SnapshotSchedule.is_active == True)

        return query.order_by(desc(SnapshotSchedule.created_at)).all()

    def update_schedule(
        self,
        schedule_id: str,
        request: ScheduleUpdateRequest
    ) -> Optional[SnapshotSchedule]:
        """Update a schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None

        # Update fields if provided
        if request.name is not None:
            schedule.name = request.name
        if request.cron_expression is not None:
            schedule.cron_expression = request.cron_expression
        if request.snapshot_type is not None:
            schedule.snapshot_type = SnapshotType(request.snapshot_type.value)
        if request.is_active is not None:
            schedule.is_active = request.is_active
        if request.retention_count is not None:
            schedule.retention_count = request.retention_count
        if request.retention_days is not None:
            schedule.retention_days = request.retention_days
        if request.target_containers is not None:
            schedule.target_containers = request.target_containers
        if request.compression is not None:
            schedule.compression = request.compression
        if request.include_routing_tables is not None:
            schedule.include_routing_tables = request.include_routing_tables
        if request.include_flow_tables is not None:
            schedule.include_flow_tables = request.include_flow_tables
        if request.include_arp_tables is not None:
            schedule.include_arp_tables = request.include_arp_tables
        if request.description is not None:
            schedule.description = request.description

        self.db.commit()
        self.db.refresh(schedule)

        logger.info(f"Updated schedule: {schedule_id}")
        return schedule

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return False

        self.db.delete(schedule)
        self.db.commit()

        logger.info(f"Deleted schedule: {schedule_id}")
        return True

    def update_schedule_last_run(
        self,
        schedule_id: str,
        snapshot_id: str,
        next_run_at: Optional[datetime] = None
    ) -> Optional[SnapshotSchedule]:
        """Update schedule after a run"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None

        schedule.last_run_at = datetime.utcnow()
        schedule.last_snapshot_id = snapshot_id
        schedule.run_count += 1
        if next_run_at:
            schedule.next_run_at = next_run_at

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def increment_schedule_failure(self, schedule_id: str) -> Optional[SnapshotSchedule]:
        """Increment failure count for a schedule"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None

        schedule.failure_count += 1
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def get_snapshots_for_retention(
        self,
        schedule_id: str,
        keep_count: int
    ) -> List[Snapshot]:
        """Get snapshots that should be deleted based on retention policy"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return []

        # Get all captured snapshots for this schedule's topology
        query = self.db.query(Snapshot)\
            .filter(Snapshot.topology_id == schedule.topology_id)\
            .filter(Snapshot.status == SnapshotStatus.CAPTURED)\
            .order_by(desc(Snapshot.created_at))

        # Get snapshots beyond retention count
        all_snapshots = query.all()
        return all_snapshots[keep_count:] if len(all_snapshots) > keep_count else []


# Export
__all__ = ['PostgresSnapshotStorage']
