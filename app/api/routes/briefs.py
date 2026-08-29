from fastapi import APIRouter, status

from app.api.dependencies import DbSessionDep
from app.schemas.projects import (
    BriefTaskLink,
    ProjectBriefCreate,
    ProjectBriefRead,
    ProjectBriefUpdate,
)
from app.services.briefs import (
    create_brief,
    get_brief,
    link_brief_task,
    list_briefs,
    update_brief,
)

router = APIRouter(prefix="/projects/{project_id}/briefs", tags=["project briefs"])


@router.get("", response_model=list[ProjectBriefRead])
async def briefs(project_id: str, session: DbSessionDep) -> list[ProjectBriefRead]:
    return await list_briefs(session, project_id)


@router.post("", response_model=ProjectBriefRead, status_code=status.HTTP_201_CREATED)
async def new_brief(
    project_id: str, payload: ProjectBriefCreate, session: DbSessionDep
) -> ProjectBriefRead:
    return await create_brief(session, project_id, payload)


@router.get("/{brief_id}", response_model=ProjectBriefRead)
async def brief(project_id: str, brief_id: str, session: DbSessionDep) -> ProjectBriefRead:
    return await get_brief(session, project_id, brief_id)


@router.patch("/{brief_id}", response_model=ProjectBriefRead)
async def edit_brief(
    project_id: str,
    brief_id: str,
    payload: ProjectBriefUpdate,
    session: DbSessionDep,
) -> ProjectBriefRead:
    return await update_brief(session, project_id, brief_id, payload)


@router.post("/{brief_id}/link-task", response_model=ProjectBriefRead)
async def link_task(
    project_id: str,
    brief_id: str,
    payload: BriefTaskLink,
    session: DbSessionDep,
) -> ProjectBriefRead:
    return await link_brief_task(session, project_id, brief_id, payload)
