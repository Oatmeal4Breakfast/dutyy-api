from functools import partial
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio.session import AsyncSession, async_sessionmaker

from src.bus.bus import EventBus
from src.config import WebSessionConfig
from src.db.uow import UnitOfWork
from src.domain.api import APIKey
from src.domain.user import UserStatus, UserSummary
from src.service.api_service import APIService
from src.service.auth_service import (
    AuthContext,
    AuthService,
    CredentialMethod,
    SessionState,
)
from src.service.device_auth_service import DeviceAuthService
from src.service.project_service import ProjectService
from src.service.user_service import UserNotFoundError, UserService


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


def get_web_session_config(request: Request) -> WebSessionConfig:
    return request.app.state.web_session_config


def get_uow(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    bus: EventBus = Depends(get_event_bus),
) -> UnitOfWork:
    return UnitOfWork(session_factory, event_bus=bus)


def get_project_service(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory)
    ],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> ProjectService:
    uow_factory = partial(UnitOfWork, session_factory, event_bus)
    return ProjectService(uow_factory)


async def get_current_user(
    request: Request,
    config: Annotated[WebSessionConfig, Depends(get_web_session_config)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserSummary:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    token: str | None = request.cookies.get(config.cookie_name)
    if token is None:
        raise credentials_exception

    session_state: SessionState | None = await service.get_session_user(token)
    if session_state is None:
        raise credentials_exception

    return session_state.user_summary


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


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


async def get_optional_api_key(
    request: Request, api_service: Annotated[APIService, Depends(get_api_service)]
) -> APIKey | None:
    token: str | None = request.headers.get("X-API-Key")

    if token is None:
        return None

    return await api_service.verify(token)


async def get_optional_session(
    request: Request,
    config: Annotated[WebSessionConfig, Depends(get_web_session_config)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionState | None:
    cookie: str | None = request.cookies.get(config.cookie_name)

    if cookie is None:
        return None
    return await auth_service.get_session_user(cookie)


async def get_auth_context(
    request: Request,
    config: Annotated[WebSessionConfig, Depends(get_web_session_config)],
    api_key: Annotated[APIKey | None, Depends(get_optional_api_key)],
    session: Annotated[SessionState | None, Depends(get_optional_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> AuthContext:

    cookie_presence: bool = config.cookie_name in request.cookies
    api_key_presence: bool = "X-API-Key" in request.headers

    if cookie_presence and api_key_presence:
        raise _unauthorized()
    if api_key is not None:
        try:
            key_user = await user_service.get_user_by_id(api_key.user_id)
        except UserNotFoundError:
            raise _unauthorized()
        if key_user.status != UserStatus.ACTIVE:
            raise _unauthorized()
        return AuthContext(
            user=key_user,
            method=CredentialMethod.API,
            credential_id=api_key.id,
        )
    if session is None:
        raise _unauthorized()

    return AuthContext(
        user=session.user_summary,
        method=CredentialMethod.SESSION,
        credential_id=session.session_id,
    )


def require_session(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    if ctx.method != CredentialMethod.SESSION:
        raise _unauthorized(detail="Invalid session")
    return ctx


def require_api_key(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    if ctx.method != CredentialMethod.API:
        raise _unauthorized(detail="Invalid API Key")
    return ctx
