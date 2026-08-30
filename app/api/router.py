from fastapi import APIRouter

from app.api.routes import briefs, chat, health, memories, projects, tasks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(projects.router)
api_router.include_router(briefs.router)
api_router.include_router(memories.router)
api_router.include_router(tasks.router)
api_router.include_router(projects.events_router)
