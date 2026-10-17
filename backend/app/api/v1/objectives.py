from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import LearningObjective, User
from app.schemas.objective import ObjectiveOut

router = APIRouter(tags=["objectives"])


@router.get("/objectives", response_model=list[ObjectiveOut])
def list_objectives(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[LearningObjective]:
    return list(
        db.scalars(
            select(LearningObjective)
            .options(selectinload(LearningObjective.prerequisites))
            .order_by(LearningObjective.code)
        )
    )
