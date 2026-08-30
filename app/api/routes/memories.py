from fastapi import APIRouter

from app.api.dependencies import DbSessionDep
from app.schemas.projects import ProjectMemoryRead, ProjectMemoryUpdate
from app.services.memories import get_memory, update_memory

router = APIRouter(prefix="/projects/{project_id}/memory", tags=["project memory"])


@router.get("", response_model=ProjectMemoryRead)
async def memory(project_id: str, session: DbSessionDep) -> ProjectMemoryRead:
    return await get_memory(session, project_id)


@router.put("", response_model=ProjectMemoryRead)
async def replace_memory(
    project_id: str, payload: ProjectMemoryUpdate, session: DbSessionDep
) -> ProjectMemoryRead:
    return await update_memory(session, project_id, payload)
