from __future__ import annotations

import asyncio
import http.client
import json
import os
import shutil
import socket
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.schemas.system import (
    ByteUsage,
    ContainerStatus,
    ServiceStatus,
    SystemHealth,
    SystemStatusResponse,
    VpsStatus,
)

HEALTHY_LIMIT = 80.0
CRITICAL_LIMIT = 90.0
MAX_CONTAINERS = 50


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 1.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        connection.connect(self.socket_path)
        self.sock = connection


def usage_health(percent: float) -> SystemHealth:
    if percent > CRITICAL_LIMIT:
        return "CRITICAL"
    if percent >= HEALTHY_LIMIT:
        return "ATTENTION"
    return "HEALTHY"


def overall_system_health(
    vps: VpsStatus,
    services: list[ServiceStatus],
    containers: list[ContainerStatus],
) -> SystemHealth:
    metric_health = [
        usage_health(vps.cpu_percent),
        usage_health(vps.memory.percent),
        usage_health(vps.disk.percent),
    ]
    if "CRITICAL" in metric_health or any(service.status == "DOWN" for service in services):
        return "CRITICAL"
    if any(
        container.status != "running" or container.health == "unhealthy" for container in containers
    ):
        return "CRITICAL"
    if "ATTENTION" in metric_health or any(
        service.status in {"DEGRADED", "UNKNOWN"} for service in services
    ):
        return "ATTENTION"
    return "HEALTHY"


def _percentage(used: int, total: int) -> float:
    return round((used / total * 100) if total else 0.0, 1)


def _cpu_times() -> tuple[int, int]:
    values = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    times = [int(value) for value in values]
    idle = times[3] + (times[4] if len(times) > 4 else 0)
    return sum(times), idle


def calculate_cpu_percent(first: tuple[int, int], second: tuple[int, int]) -> float:
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (total_delta - idle_delta) / total_delta * 100)), 1)


def _collect_cpu_percent() -> float:
    first = _cpu_times()
    time.sleep(0.1)
    return calculate_cpu_percent(first, _cpu_times())


def _memory_usage() -> ByteUsage:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, raw_value = line.split(":", 1)
        values[key] = int(raw_value.strip().split()[0]) * 1024
    total = values["MemTotal"]
    available = values["MemAvailable"]
    used = total - available
    return ByteUsage(
        used_bytes=used,
        total_bytes=total,
        available_bytes=available,
        percent=_percentage(used, total),
    )


def _disk_usage(path: str) -> ByteUsage:
    usage = shutil.disk_usage(path)
    return ByteUsage(
        used_bytes=usage.used,
        total_bytes=usage.total,
        available_bytes=usage.free,
        percent=_percentage(usage.used, usage.total),
    )


def _hostname(hostname_file: str) -> str:
    try:
        value = Path(hostname_file).read_text().strip()
        if value:
            return value[:255]
    except OSError:
        pass
    return socket.gethostname()


def _vps_status(settings: Settings) -> VpsStatus:
    uptime = float(Path("/proc/uptime").read_text().split()[0])
    try:
        load_average = [round(value, 2) for value in os.getloadavg()]
    except OSError:
        load_average = []
    return VpsStatus(
        hostname=_hostname(settings.telemetry_hostname_file),
        uptime_seconds=int(uptime),
        cpu_percent=_collect_cpu_percent(),
        load_average=load_average,
        memory=_memory_usage(),
        disk=_disk_usage(settings.telemetry_disk_path),
    )


def _http_status(name: str, url: str, timeout: float) -> ServiceStatus:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = response.status
        if 200 <= code < 400:
            return ServiceStatus(name=name, status="HEALTHY")
        return ServiceStatus(name=name, status="DEGRADED", detail=f"HTTP {code}")
    except urllib.error.HTTPError as exc:
        return ServiceStatus(name=name, status="DEGRADED", detail=f"HTTP {exc.code}")
    except (OSError, urllib.error.URLError, TimeoutError):
        return ServiceStatus(name=name, status="DOWN", detail="Unreachable")


def _docker_get(socket_path: str, path: str) -> object:
    connection = UnixHTTPConnection(socket_path, timeout=1.0)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise OSError(f"Docker API returned {response.status}")
        return json.loads(response.read())
    finally:
        connection.close()


def _parse_started_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value or value.startswith("0001-"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _container_statuses(socket_path: str) -> tuple[bool, list[ContainerStatus]]:
    try:
        documents = _docker_get(socket_path, "/v1.41/containers/json?all=1")
        if not isinstance(documents, list):
            return False, []
        containers = []
        for document in documents[:MAX_CONTAINERS]:
            if not isinstance(document, dict):
                continue
            names = document.get("Names") or []
            name = names[0].lstrip("/") if names else str(document.get("Id", ""))[:12]
            inspect = _docker_get(
                socket_path,
                f"/v1.41/containers/{document.get('Id', '')}/json",
            )
            state = inspect.get("State", {}) if isinstance(inspect, dict) else {}
            health_data = state.get("Health") if isinstance(state, dict) else None
            health = health_data.get("Status") if isinstance(health_data, dict) else None
            containers.append(
                ContainerStatus(
                    name=name,
                    status=str(document.get("State", "unknown")).lower(),
                    health=health,
                    started_at=_parse_started_at(state.get("StartedAt")),
                )
            )
        return True, sorted(containers, key=lambda item: item.name)
    except (OSError, ValueError, json.JSONDecodeError, http.client.HTTPException):
        return False, []


async def _database_status(session: AsyncSession) -> ServiceStatus:
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=1.0)
        return ServiceStatus(name="PostgreSQL", status="HEALTHY")
    except Exception:
        return ServiceStatus(name="PostgreSQL", status="DOWN", detail="Connection failed")


class SystemTelemetryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def collect(self, session: AsyncSession) -> SystemStatusResponse:
        vps_task = asyncio.to_thread(_vps_status, self.settings)
        docker_task = asyncio.to_thread(_container_statuses, self.settings.telemetry_docker_socket)
        http_tasks = [
            asyncio.to_thread(
                _http_status,
                name,
                url,
                self.settings.telemetry_http_timeout_seconds,
            )
            for name, url in (
                ("Nginx", self.settings.telemetry_nginx_url),
                ("Office Project frontend", self.settings.telemetry_office_frontend_url),
                ("Office Project backend", self.settings.telemetry_office_backend_url),
            )
        ]
        vps, docker_result, database, *http_services = await asyncio.gather(
            vps_task,
            docker_task,
            _database_status(session),
            *http_tasks,
        )
        docker_available, containers = docker_result
        services = [
            ServiceStatus(name="AI Playground API", status="HEALTHY"),
            database,
            *http_services,
        ]
        return SystemStatusResponse(
            status=overall_system_health(vps, services, containers),
            vps=vps,
            services=services,
            containers=containers,
            docker_available=docker_available,
            updated_at=datetime.now(UTC),
        )
