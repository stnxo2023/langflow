from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from langflow.services.database.models.user.model import User, UserUpdate
from langflow.services.deps import get_session


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.exec(select(User).where(User.username == username)).first()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.exec(select(User).where(User.id == user_id)).first()


def update_user(user_db: User | None, user: UserUpdate, db: Session = Depends(get_session)) -> User:
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    # user_db_by_username = get_user_by_username(db, user.username)
    # if user_db_by_username and user_db_by_username.id != user_id:
    #     raise HTTPException(status_code=409, detail="Username already exists")

    user_data = user.model_dump(exclude_unset=True)
    changed = False
    for attr, value in user_data.items():
        if hasattr(user_db, attr) and value is not None:
            setattr(user_db, attr, value)
            changed = True

    if not changed:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED, detail="Nothing to update")

    user_db.updated_at = datetime.now(timezone.utc)
    flag_modified(user_db, "updated_at")

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    return user_db


def update_user_last_login_at(user_id: UUID, db: Session = Depends(get_session)):
    try:
        user_data = UserUpdate(last_login_at=datetime.now(timezone.utc))
        user = get_user_by_id(db, user_id)
        return update_user(user, user_data, db)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).debug("Error updating user last login at")
