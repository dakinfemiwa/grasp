from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.objectives import router as objectives_router
from app.api.v1.practice import router as practice_router
from app.api.v1.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(objectives_router)
api_router.include_router(practice_router)
