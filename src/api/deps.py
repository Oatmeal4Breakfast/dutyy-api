from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio.session import AsyncSession, async_sessionmaker

from src.bus.bus import EventBus
from src.db.uow import UnitOfWork
from src.domain.api import APIKey
from src.domain.user import User, UserSummary
from src.service.api_service import APIService
from src.service.auth_service import AuthService
from src.service.device_auth_service import DeviceAuthService
from src.service.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/dutyy/api/v1/auth/login")


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_device_auth_service(request: Request) -> DeviceAuthService:
    return request.app.state.device_auth_service


def get_user_service(request: Request) -> UserService:
    return request.app.state.user_service


def get_api_service(request: Request) -> APIService:
    return request.app.state.api_service


def get_uow(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    bus: EventBus = Depends(get_event_bus),
) -> UnitOfWork:
    return UnitOfWork(session_factory, event_bus=bus)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserSummary:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    current_user: User | None = await service.get_current_user(token)
    if current_user is None:
        raise credentials_exception

    return current_user.to_summary()


async def get_api_key(
    request: Request, service: Annotated[APIService, Depends(get_api_service)]
) -> APIKey:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate api key",
        headers={"WWW-Authenticate": "X-API-Key"},
    )

    raw_key: str | None = request.headers.get("X-API-Key")
    if raw_key is None:
        raise credentials_exception

    api_key: APIKey | None = await service.verify(raw_key=raw_key)
    if api_key is None:
        raise credentials_exception

    return api_key


async def get_api_key_user(
    key: Annotated[APIKey, Depends(get_api_key)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserSummary:
    return await service.get_user_by_id(user_id=key.user_id)
