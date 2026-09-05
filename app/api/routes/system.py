from fastapi import APIRouter

from app.api.dependencies import DbSessionDep, SettingsDep
from app.schemas.system import SystemStatusResponse
from app.services.system_telemetry import SystemTelemetryService

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(
    session: DbSessionDep,
    settings: SettingsDep,
) -> SystemStatusResponse:
    return await SystemTelemetryService(settings).collect(session)
