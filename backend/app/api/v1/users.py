from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models import User
from app.schemas.user import UserOut

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def read_current_user(user: User = Depends(get_current_user)) -> User:
    return user
