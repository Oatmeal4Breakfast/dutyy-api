from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer

from src.db.uow import UnitOfWork
from src.service.user_service import UserService
from src.service.auth_service import AuthService
from src.bus.bus import EventBus
from src.config import get_auth_service_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio.session import async_sessionmaker, AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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


def get_auth_service(
    event_bus: EventBus = Depends(get_event_bus),
    session: async_sessionmaker = Depends(get_session_factory),
    auth_service_config=Depends(get_auth_service_config),
) -> AuthService:
    return AuthService(
        session_factory=session,
        event_bus=event_bus,
        auth_service_config=auth_service_config,
    )
