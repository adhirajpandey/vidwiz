from fastapi import Depends
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.database import get_db
from src.exceptions import NotFoundError
from src.moments import service as moments_service
from src.moments.models import Moment
from src.moments.schemas import MomentIdPath


def get_moment_or_404(
    path: MomentIdPath = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> Moment:
    moment = moments_service.get_for_user(db, user_id, path.moment_id)
    if not moment:
        raise NotFoundError("Moment not found")
    return moment
