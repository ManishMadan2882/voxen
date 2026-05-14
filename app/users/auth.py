from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from users.user_model import User

# Sentinel external_id for the local dev user. Replaced by the Clerk subject claim
# once JWT-based authentication is wired in.
LOCAL_DEV_EXTERNAL_ID = "local-dev-user"
LOCAL_DEV_EMAIL = "dev@local"
LOCAL_DEV_NAME = "Local Dev"


async def _get_or_create_local_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.external_id == LOCAL_DEV_EXTERNAL_ID))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(external_id=LOCAL_DEV_EXTERNAL_ID, email=LOCAL_DEV_EMAIL, name=LOCAL_DEV_NAME)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(select(User).where(User.external_id == LOCAL_DEV_EXTERNAL_ID))
        user = result.scalar_one()
    else:
        await db.refresh(user)
    return user


async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    # Dev shim: always resolves to the local user. Swap this body for Clerk JWT
    # verification (decode token, look up/create user by `sub` claim) when ready.
    return await _get_or_create_local_user(db)
