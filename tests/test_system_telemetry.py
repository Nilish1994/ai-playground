from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.schemas.system import ByteUsage, ContainerStatus, ServiceStatus, VpsStatus
from app.services import system_telemetry
from app.services.system_telemetry import (
    SystemTelemetryService,
    _container_statuses,
    _percentage,
    calculate_cpu_percent,
    overall_system_health,
    usage_health,
)


class HealthySession:
    async def execute(self, _statement):
        return 1


class FailedSession:
    async def execute(self, _statement):
        raise RuntimeError("database password=do-not-expose")


def vps(cpu=12.0, memory=30.0, disk=40.0) -> VpsStatus:
    def usage(percent):
        total = 1_000
        used = int(total * percent / 100)
        return ByteUsage(
            used_bytes=used,
            total_bytes=total,
            available_bytes=total - used,
            percent=percent,
        )

    return VpsStatus(
        hostname="test-vps",
        uptime_seconds=12345,
        cpu_percent=cpu,
        load_average=[0.1, 0.2, 0.3],
        memory=usage(memory),
        disk=usage(disk),
    )


def settings() -> Settings:
    return Settings(
        _env_file=None,
        telemetry_nginx_url="http://nginx.test",
        telemetry_office_frontend_url="http://frontend.test",
        telemetry_office_backend_url="http://backend.test/api/health",
    )


def test_memory_disk_and_cpu_calculations() -> None:
    assert _percentage(800, 1_000) == 80.0
    assert _percentage(10, 0) == 0.0
    assert calculate_cpu_percent((100, 40), (200, 60)) == 80.0
    assert calculate_cpu_percent((100, 40), (100, 40)) == 0.0


@pytest.mark.parametrize(
    ("percent", "expected"),
    [(79.9, "HEALTHY"), (80.0, "ATTENTION"), (90.0, "ATTENTION"), (90.1, "CRITICAL")],
)
def test_threshold_calculation(percent, expected) -> None:
    assert usage_health(percent) == expected


def test_overall_health_calculation() -> None:
    services = [ServiceStatus(name="API", status="HEALTHY")]
    assert overall_system_health(vps(), services, []) == "HEALTHY"
    assert overall_system_health(vps(memory=85), services, []) == "ATTENTION"
    assert overall_system_health(vps(disk=95), services, []) == "CRITICAL"
    assert (
        overall_system_health(vps(), [ServiceStatus(name="Database", status="DOWN")], [])
        == "CRITICAL"
    )
    assert (
        overall_system_health(
            vps(), services, [ContainerStatus(name="api", status="running", health="unhealthy")]
        )
        == "CRITICAL"
    )


def test_docker_unavailable_is_handled_safely(monkeypatch) -> None:
    def unavailable(_socket, _path):
        raise OSError("socket unavailable")

    monkeypatch.setattr(system_telemetry, "_docker_get", unavailable)
    available, containers = _container_statuses("/missing/docker.sock")
    assert available is False
    assert containers == []


def test_docker_response_excludes_secrets(monkeypatch) -> None:
    def docker_get(_socket, path):
        if path.endswith("containers/json?all=1"):
            return [
                {
                    "Id": "abc123",
                    "Names": ["/safe-container"],
                    "State": "running",
                    "Secret": "API_KEY=do-not-expose",
                }
            ]
        return {
            "State": {
                "StartedAt": "2026-08-31T10:00:00Z",
                "Health": {"Status": "healthy", "Log": ["password=hidden"]},
            },
            "Config": {"Env": ["OPENAI_API_KEY=do-not-expose"]},
        }

    monkeypatch.setattr(system_telemetry, "_docker_get", docker_get)
    available, containers = _container_statuses("/var/run/docker.sock")
    serialized = containers[0].model_dump_json()
    assert available is True
    assert containers[0].name == "safe-container"
    assert containers[0].health == "healthy"
    assert "do-not-expose" not in serialized
    assert "password" not in serialized


@pytest.mark.asyncio
async def test_system_status_response_shape(monkeypatch) -> None:
    monkeypatch.setattr(system_telemetry, "_vps_status", lambda _settings: vps())
    monkeypatch.setattr(
        system_telemetry,
        "_container_statuses",
        lambda _socket: (
            True,
            [
                ContainerStatus(
                    name="api",
                    status="running",
                    health="healthy",
                    started_at=datetime.now(UTC),
                )
            ],
        ),
    )
    monkeypatch.setattr(
        system_telemetry,
        "_http_status",
        lambda name, _url, _timeout: ServiceStatus(name=name, status="HEALTHY"),
    )

    result = await SystemTelemetryService(settings()).collect(HealthySession())

    assert result.status == "HEALTHY"
    assert result.vps.hostname == "test-vps"
    assert {service.name for service in result.services} == {
        "AI Playground API",
        "PostgreSQL",
        "Nginx",
        "Office Project frontend",
        "Office Project backend",
    }
    assert result.docker_available is True
    assert result.containers[0].name == "api"
    assert result.updated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_service_failure_does_not_fail_status_or_expose_error(monkeypatch) -> None:
    monkeypatch.setattr(system_telemetry, "_vps_status", lambda _settings: vps())
    monkeypatch.setattr(system_telemetry, "_container_statuses", lambda _socket: (False, []))
    monkeypatch.setattr(
        system_telemetry,
        "_http_status",
        lambda name, _url, _timeout: ServiceStatus(
            name=name,
            status="DOWN" if name == "Nginx" else "HEALTHY",
            detail="Unreachable" if name == "Nginx" else None,
        ),
    )

    result = await SystemTelemetryService(settings()).collect(FailedSession())
    serialized = result.model_dump_json()

    assert result.status == "CRITICAL"
    assert next(item for item in result.services if item.name == "PostgreSQL").status == "DOWN"
    assert next(item for item in result.services if item.name == "Nginx").status == "DOWN"
    assert "do-not-expose" not in serialized
    assert "password" not in serialized
