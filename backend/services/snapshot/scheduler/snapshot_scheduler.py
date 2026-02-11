"""
Snapshot scheduler using APScheduler
Manages automatic snapshot creation with cron-based scheduling
"""

import logging
import asyncio
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from croniter import croniter

from shared.models.snapshot import SnapshotSchedule, SnapshotType
from shared.schemas.snapshot_schema import SnapshotCreateRequest, SnapshotTypeEnum

logger = logging.getLogger(__name__)


class SnapshotScheduler:
    """
    Manages automatic snapshot scheduling using APScheduler
    """

    def __init__(self):
        # Configure job stores and executors
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': True,  # Combine multiple missed executions
            'max_instances': 1,  # Only one instance per job at a time
            'misfire_grace_time': 60 * 5  # 5 minutes grace time for misfires
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Callback for creating snapshots
        self._snapshot_callback: Optional[Callable] = None

        # Callback for applying retention policy
        self._retention_callback: Optional[Callable] = None

        # Track active jobs
        self._active_jobs: Dict[str, str] = {}  # schedule_id -> job_id

    def set_snapshot_callback(self, callback: Callable):
        """Set the callback function for creating snapshots"""
        self._snapshot_callback = callback

    def set_retention_callback(self, callback: Callable):
        """Set the callback function for applying retention policy"""
        self._retention_callback = callback

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Snapshot scheduler started")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Snapshot scheduler stopped")

    def add_schedule(self, schedule: SnapshotSchedule) -> bool:
        """
        Add or update a snapshot schedule

        Args:
            schedule: SnapshotSchedule model instance

        Returns:
            True if schedule was added successfully
        """
        try:
            job_id = f"snapshot_schedule_{schedule.id}"

            # Remove existing job if present
            if job_id in self._active_jobs.values():
                self.remove_schedule(schedule.id)

            if not schedule.is_active:
                logger.info(f"Schedule {schedule.id} is inactive, not adding to scheduler")
                return True

            # Parse cron expression and create trigger
            trigger = CronTrigger.from_crontab(schedule.cron_expression)

            # Add job to scheduler
            self.scheduler.add_job(
                self._execute_scheduled_snapshot,
                trigger=trigger,
                id=job_id,
                name=schedule.name,
                args=[schedule.id],
                replace_existing=True
            )

            self._active_jobs[schedule.id] = job_id

            # Calculate and log next run time
            next_run = self.get_next_run_time(schedule.cron_expression)
            logger.info(
                f"Added schedule '{schedule.name}' ({schedule.id}) "
                f"with cron '{schedule.cron_expression}', next run: {next_run}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to add schedule {schedule.id}: {e}")
            return False

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule from the scheduler"""
        try:
            job_id = f"snapshot_schedule_{schedule_id}"

            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            if schedule_id in self._active_jobs:
                del self._active_jobs[schedule_id]

            logger.info(f"Removed schedule {schedule_id} from scheduler")
            return True

        except Exception as e:
            logger.error(f"Failed to remove schedule {schedule_id}: {e}")
            return False

    def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule"""
        try:
            job_id = f"snapshot_schedule_{schedule_id}"
            job = self.scheduler.get_job(job_id)

            if job:
                self.scheduler.pause_job(job_id)
                logger.info(f"Paused schedule {schedule_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to pause schedule {schedule_id}: {e}")
            return False

    def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule"""
        try:
            job_id = f"snapshot_schedule_{schedule_id}"
            job = self.scheduler.get_job(job_id)

            if job:
                self.scheduler.resume_job(job_id)
                logger.info(f"Resumed schedule {schedule_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to resume schedule {schedule_id}: {e}")
            return False

    async def trigger_now(self, schedule_id: str) -> Optional[str]:
        """
        Manually trigger a scheduled snapshot immediately

        Returns:
            Snapshot ID if successful, None otherwise
        """
        try:
            logger.info(f"Manually triggering schedule {schedule_id}")
            return await self._execute_scheduled_snapshot(schedule_id)

        except Exception as e:
            logger.error(f"Failed to trigger schedule {schedule_id}: {e}")
            return None

    async def _execute_scheduled_snapshot(self, schedule_id: str) -> Optional[str]:
        """
        Execute a scheduled snapshot

        This is called by APScheduler when a schedule triggers
        """
        if not self._snapshot_callback:
            logger.error("No snapshot callback configured")
            return None

        try:
            logger.info(f"Executing scheduled snapshot for schedule {schedule_id}")

            # Call the snapshot creation callback
            # The callback should return the created snapshot ID
            snapshot_id = await self._snapshot_callback(schedule_id)

            if snapshot_id:
                logger.info(
                    f"Successfully created scheduled snapshot {snapshot_id} "
                    f"for schedule {schedule_id}"
                )

                # Apply retention policy if callback is set
                if self._retention_callback:
                    await self._retention_callback(schedule_id)

            return snapshot_id

        except Exception as e:
            logger.error(f"Failed to execute scheduled snapshot: {e}")
            return None

    def get_next_run_time(self, cron_expression: str) -> Optional[datetime]:
        """Calculate the next run time for a cron expression"""
        try:
            cron = croniter(cron_expression, datetime.utcnow())
            return cron.get_next(datetime)
        except Exception as e:
            logger.error(f"Invalid cron expression '{cron_expression}': {e}")
            return None

    def get_previous_run_time(self, cron_expression: str) -> Optional[datetime]:
        """Calculate the previous run time for a cron expression"""
        try:
            cron = croniter(cron_expression, datetime.utcnow())
            return cron.get_prev(datetime)
        except Exception as e:
            logger.error(f"Invalid cron expression '{cron_expression}': {e}")
            return None

    def validate_cron_expression(self, cron_expression: str) -> tuple[bool, str]:
        """
        Validate a cron expression

        Returns:
            (is_valid, error_message)
        """
        try:
            # Try to create a trigger
            CronTrigger.from_crontab(cron_expression)

            # Calculate next run to ensure it works
            next_run = self.get_next_run_time(cron_expression)
            if not next_run:
                return False, "Could not calculate next run time"

            return True, ""

        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Invalid cron expression: {e}"

    def get_human_readable_schedule(self, cron_expression: str) -> str:
        """Convert cron expression to human-readable format"""
        # Simple mapping for common patterns
        patterns = {
            "* * * * *": "Every minute",
            "0 * * * *": "Every hour",
            "0 */2 * * *": "Every 2 hours",
            "0 */4 * * *": "Every 4 hours",
            "0 */6 * * *": "Every 6 hours",
            "0 */12 * * *": "Every 12 hours",
            "0 0 * * *": "Every day at midnight",
            "0 6 * * *": "Every day at 6:00 AM",
            "0 12 * * *": "Every day at noon",
            "0 18 * * *": "Every day at 6:00 PM",
            "0 0 * * 0": "Every Sunday at midnight",
            "0 0 * * 1": "Every Monday at midnight",
            "0 0 1 * *": "First day of every month",
        }

        if cron_expression in patterns:
            return patterns[cron_expression]

        # Parse and describe
        try:
            parts = cron_expression.split()
            if len(parts) != 5:
                return cron_expression

            minute, hour, day, month, weekday = parts

            desc = []

            # Minute
            if minute == "*":
                desc.append("every minute")
            elif minute.startswith("*/"):
                desc.append(f"every {minute[2:]} minutes")
            elif minute == "0":
                pass  # Don't mention 0 minutes
            else:
                desc.append(f"at minute {minute}")

            # Hour
            if hour == "*":
                if "every minute" not in desc:
                    desc.append("every hour")
            elif hour.startswith("*/"):
                desc.append(f"every {hour[2:]} hours")
            else:
                desc.append(f"at {hour}:{'00' if minute == '0' else minute}")

            # Day of month
            if day != "*":
                if day.startswith("*/"):
                    desc.append(f"every {day[2:]} days")
                else:
                    desc.append(f"on day {day}")

            # Month
            if month != "*":
                months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                if month.isdigit() and 1 <= int(month) <= 12:
                    desc.append(f"in {months[int(month)]}")

            # Day of week
            if weekday != "*":
                days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                if weekday.isdigit() and 0 <= int(weekday) <= 6:
                    desc.append(f"on {days[int(weekday)]}")

            return " ".join(desc) if desc else cron_expression

        except Exception:
            return cron_expression

    def get_job_status(self, schedule_id: str) -> Dict[str, Any]:
        """Get status of a scheduled job"""
        job_id = f"snapshot_schedule_{schedule_id}"
        job = self.scheduler.get_job(job_id)

        if not job:
            return {
                "exists": False,
                "schedule_id": schedule_id
            }

        return {
            "exists": True,
            "schedule_id": schedule_id,
            "job_id": job_id,
            "name": job.name,
            "next_run_time": job.next_run_time,
            "pending": job.pending
        }

    def list_jobs(self) -> list:
        """List all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "pending": job.pending
            })
        return jobs

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.scheduler.running


# Singleton instance
_scheduler_instance: Optional[SnapshotScheduler] = None


def get_scheduler() -> SnapshotScheduler:
    """Get the singleton scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SnapshotScheduler()
    return _scheduler_instance


# Export
__all__ = ['SnapshotScheduler', 'get_scheduler']
