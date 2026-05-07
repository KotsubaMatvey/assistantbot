from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AssistantJob:
    id: str
    user_id: int
    schedule_type: str
    schedule_value: str
    delivery_mode: str
    message: str
    next_run_at: datetime
    enabled: bool = True
    created_at: datetime | None = None


@dataclass(frozen=True)
class AssistantJobRun:
    job_id: str
    user_id: int
    ran_at: datetime
    ok: bool
    detail: str


class AssistantJobStore:
    def __init__(self, vault_path: str, *, timezone_name: str = "Europe/Moscow") -> None:
        self.root = Path(vault_path).expanduser() / "jobs"
        self.jobs_path = self.root / "jobs.json"
        self.runs_path = self.root / "runs.json"
        self.timezone = ZoneInfo(timezone_name)

    def add_job(
        self,
        *,
        user_id: int,
        schedule_type: str,
        schedule_value: str,
        message: str,
        delivery_mode: str = "message",
        now: datetime | None = None,
    ) -> AssistantJob:
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("job message is empty")
        current = (now or datetime.now(UTC)).astimezone(UTC)
        normalized_type = schedule_type.strip().lower()
        next_run_at = next_run(
            schedule_type=normalized_type,
            schedule_value=schedule_value,
            now=current,
            timezone=self.timezone,
        )
        job = AssistantJob(
            id=secrets.token_hex(4),
            user_id=user_id,
            schedule_type=normalized_type,
            schedule_value=schedule_value.strip(),
            delivery_mode=_normalize_delivery_mode(delivery_mode),
            message=clean_message,
            next_run_at=next_run_at,
            created_at=current,
        )
        jobs = self.list_jobs()
        jobs.append(job)
        self._write_jobs(jobs)
        return job

    def list_jobs(self, *, user_id: int | None = None) -> list[AssistantJob]:
        if not self.jobs_path.exists():
            return []
        raw = json.loads(self.jobs_path.read_text(encoding="utf-8"))
        jobs = [_job_from_dict(item) for item in raw]
        if user_id is not None:
            jobs = [job for job in jobs if job.user_id == user_id]
        jobs.sort(key=lambda job: job.next_run_at)
        return jobs

    def due_jobs(self, *, now: datetime | None = None) -> list[AssistantJob]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        return [job for job in self.list_jobs() if job.enabled and job.next_run_at <= current]

    def record_run(
        self,
        *,
        job: AssistantJob,
        ok: bool,
        detail: str,
        now: datetime | None = None,
    ) -> AssistantJob:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        runs = self.list_runs()
        runs.append(
            AssistantJobRun(
                job_id=job.id,
                user_id=job.user_id,
                ran_at=current,
                ok=ok,
                detail=detail[:500],
            )
        )
        self._write_runs(runs[-200:])

        jobs = self.list_jobs()
        updated_job = _advance_job(job, now=current, timezone=self.timezone)
        updated_jobs = [updated_job if existing.id == job.id else existing for existing in jobs]
        self._write_jobs(updated_jobs)
        return updated_job

    def list_runs(self, *, user_id: int | None = None, limit: int = 20) -> list[AssistantJobRun]:
        if not self.runs_path.exists():
            return []
        raw = json.loads(self.runs_path.read_text(encoding="utf-8"))
        runs = [_run_from_dict(item) for item in raw]
        if user_id is not None:
            runs = [run for run in runs if run.user_id == user_id]
        runs.sort(key=lambda run: run.ran_at, reverse=True)
        return runs[:limit]

    def delete_job(self, *, user_id: int, job_id: str) -> bool:
        jobs = self.list_jobs()
        remaining = [job for job in jobs if not (job.user_id == user_id and job.id == job_id)]
        if len(remaining) == len(jobs):
            return False
        self._write_jobs(remaining)
        return True

    def _write_jobs(self, jobs: list[AssistantJob]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs_path.write_text(
            json.dumps([_job_to_dict(job) for job in jobs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_runs(self, runs: list[AssistantJobRun]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_path.write_text(
            json.dumps([_run_to_dict(run) for run in runs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def parse_job_request(text: str) -> tuple[str, str, str, str]:
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 3:
        raise ValueError(
            "Использование: /job_add daily 09:00 <текст> или /job_add every 60 <текст>"
        )
    delivery_mode, message = _split_delivery_mode(parts[2])
    return parts[0], parts[1], delivery_mode, message


def next_run(
    *,
    schedule_type: str,
    schedule_value: str,
    now: datetime,
    timezone: ZoneInfo,
) -> datetime:
    current = now.astimezone(timezone)
    if schedule_type == "daily":
        hour, minute = _parse_clock(schedule_value)
        candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= current:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)
    if schedule_type == "every":
        minutes = int(schedule_value)
        if minutes <= 0:
            raise ValueError("every interval must be positive minutes")
        return (now.astimezone(UTC) + timedelta(minutes=minutes)).astimezone(UTC)
    if schedule_type == "once":
        parsed = datetime.fromisoformat(schedule_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone)
        due_at = parsed.astimezone(UTC)
        if due_at <= now.astimezone(UTC):
            raise ValueError("once timestamp is in the past")
        return due_at
    raise ValueError("schedule type must be daily, every, or once")


def _split_delivery_mode(text: str) -> tuple[str, str]:
    head, _, tail = text.strip().partition(" ")
    if head in DELIVERY_MODES and tail.strip():
        return head, tail.strip()
    return "message", text.strip()


DELIVERY_MODES = {
    "message",
    "digest",
    "rss",
    "doctor",
    "silent",
    "markets",
    "morning",
    "price_alerts",
}


def _normalize_delivery_mode(value: str) -> str:
    normalized = value.strip().lower() or "message"
    if normalized not in DELIVERY_MODES:
        raise ValueError(
            "delivery mode must be message, digest, rss, doctor, silent, markets, "
            "morning, or price_alerts"
        )
    return normalized


def _advance_job(job: AssistantJob, *, now: datetime, timezone: ZoneInfo) -> AssistantJob:
    if job.schedule_type == "once":
        return AssistantJob(
            id=job.id,
            user_id=job.user_id,
            schedule_type=job.schedule_type,
            schedule_value=job.schedule_value,
            delivery_mode=job.delivery_mode,
            message=job.message,
            next_run_at=job.next_run_at,
            enabled=False,
            created_at=job.created_at,
        )
    return AssistantJob(
        id=job.id,
        user_id=job.user_id,
        schedule_type=job.schedule_type,
        schedule_value=job.schedule_value,
        delivery_mode=job.delivery_mode,
        message=job.message,
        next_run_at=next_run(
            schedule_type=job.schedule_type,
            schedule_value=job.schedule_value,
            now=now,
            timezone=timezone,
        ),
        enabled=job.enabled,
        created_at=job.created_at,
    )


def _parse_clock(value: str) -> tuple[int, int]:
    hour_text, separator, minute_text = value.partition(":")
    if not separator:
        raise ValueError("daily schedule must use HH:MM")
    hour = int(hour_text)
    minute = int(minute_text)
    if hour > 23 or minute > 59:
        raise ValueError("invalid daily schedule time")
    return hour, minute


def _job_to_dict(job: AssistantJob) -> dict[str, object]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "schedule_type": job.schedule_type,
        "schedule_value": job.schedule_value,
        "delivery_mode": job.delivery_mode,
        "message": job.message,
        "next_run_at": job.next_run_at.isoformat(),
        "enabled": job.enabled,
        "created_at": (job.created_at or datetime.now(UTC)).isoformat(),
    }


def _job_from_dict(raw: dict[str, object]) -> AssistantJob:
    return AssistantJob(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        schedule_type=str(raw["schedule_type"]),
        schedule_value=str(raw["schedule_value"]),
        delivery_mode=str(raw.get("delivery_mode", "message")),
        message=str(raw["message"]),
        next_run_at=datetime.fromisoformat(str(raw["next_run_at"])).astimezone(UTC),
        enabled=bool(raw.get("enabled", True)),
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )


def _run_to_dict(run: AssistantJobRun) -> dict[str, object]:
    return {
        "job_id": run.job_id,
        "user_id": run.user_id,
        "ran_at": run.ran_at.isoformat(),
        "ok": run.ok,
        "detail": run.detail,
    }


def _run_from_dict(raw: dict[str, object]) -> AssistantJobRun:
    return AssistantJobRun(
        job_id=str(raw["job_id"]),
        user_id=int(str(raw["user_id"])),
        ran_at=datetime.fromisoformat(str(raw["ran_at"])).astimezone(UTC),
        ok=bool(raw["ok"]),
        detail=str(raw["detail"]),
    )
