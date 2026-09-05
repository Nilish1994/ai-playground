from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ServiceHealth = Literal["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"]
SystemHealth = Literal["HEALTHY", "ATTENTION", "CRITICAL"]


class ByteUsage(BaseModel):
    used_bytes: int
    total_bytes: int
    available_bytes: int
    percent: float


class VpsStatus(BaseModel):
    hostname: str
    uptime_seconds: int
    cpu_percent: float
    load_average: list[float]
    memory: ByteUsage
    disk: ByteUsage


class ServiceStatus(BaseModel):
    name: str
    status: ServiceHealth
    detail: str | None = None


class ContainerStatus(BaseModel):
    name: str
    status: str
    health: str | None = None
    started_at: datetime | None = None


class SystemStatusResponse(BaseModel):
    status: SystemHealth
    vps: VpsStatus
    services: list[ServiceStatus]
    containers: list[ContainerStatus]
    docker_available: bool
    updated_at: datetime
