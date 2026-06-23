from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import Request, Depends

from src.db.uow import UnitOfWork
from src.service.user_service import UserService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio.session import async_sessionmaker, AsyncSession


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def get_uow(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> UnitOfWork:
    return UnitOfWork(session_factory)


def get_user_service(uow: UnitOfWork = Depends(get_uow)) -> UserService:
    return UserService(uow)
