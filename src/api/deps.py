from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import Request, Depends

from src.db.uow import UnitOfWork
from src.service.user_service import UserService
from src.bus.bus import EventBus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio.session import async_sessionmaker, AsyncSession


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def get_uow(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    bus: EventBus = Depends(get_event_bus),
) -> UnitOfWork:
    return UnitOfWork(session_factory, event_bus=bus)


def get_user_service(uow: UnitOfWork = Depends(get_uow)) -> UserService:
    return UserService(uow)
