from __future__ import annotations
from src.service.api_service import APIService
from typing import TYPE_CHECKING
from functools import partial

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, IntegrityError

from src.api.deps import get_uow
from src.api import user_router, auth_router, api_key_router
from src.db.uow import UnitOfWork
from src.domain.exceptions import (
    DomainValidationError,
    UserAlreadyExistsError,
    ProjectAlreadyExistsError,
)
from src.bootstrap import register_event_handlers
from src.bus.bus import EventBus
from src.service.user_service import UserNotFoundError, UserService
from src.service.device_auth_service import DeviceAuthService
from src.service.auth_service import AuthService
from src.service.email_service import EmailService
from src.db.db import create_engine_and_session
from src.config import (
    get_config,
    get_auth_service_config,
    get_email_service_config,
    get_device_auth_config,
)
from src.logger import config_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from src.config import AuthServiceConfig, Config, EmailServiceConfig


async def lifespan(app: FastAPI):
    config: Config = get_config()
    config_logger(config)
    auth_config: AuthServiceConfig = get_auth_service_config()
    email_config: EmailServiceConfig = get_email_service_config()
    engine, session_factory = create_engine_and_session(config)
    bus = EventBus()
    uow_factory: partial[UnitOfWork] = partial(UnitOfWork, session_factory, bus)
    app.state.session_factory: async_sessionmaker[AsyncSession] = session_factory
    app.state.event_bus: EventBus = bus
    app.state.auth_service = AuthService(
        uow_factory=uow_factory,
        auth_service_config=auth_config,
    )
    app.state.device_auth_service = DeviceAuthService(
        config=get_device_auth_config(), uow_factory=uow_factory
    )
    app.state.email_service = EmailService(
        email_service_config=email_config, frontend_url=config.frontend_url
    )
    app.state.user_service = UserService(uow_factory=uow_factory)
    app.state.api_service = APIService(uow_factory=uow_factory)
    register_event_handlers(
        bus, auth_service=app.state.auth_service, email_service=app.state.email_service
    )
    yield
    await bus.drain()
    await engine.dispose()


async def domain_validation_exception_handler(
    request: Request, exc: DomainValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errors": exc.errors})


async def user_already_exist_handler(
    request: Request, exc: UserAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def project_already_exist_handler(
    request: Request, exc: ProjectAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "resource conflict"})


async def operation_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "service unavailable"})


async def user_not_found_handler(
    request: Request, exc: UserNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"details": f"user {exc.user_id} not found"}
    )


async def health(uow: UnitOfWork = Depends(get_uow)) -> JSONResponse:
    async with uow as u:
        await u.health.ping()
    return JSONResponse(content={"status": "ok"}, status_code=200)


def create_app(lifespan=None) -> FastAPI:
    app = FastAPI(title="dutyy-api", lifespan=lifespan)

    app.add_exception_handler(
        DomainValidationError, domain_validation_exception_handler
    )
    app.add_exception_handler(UserAlreadyExistsError, user_already_exist_handler)
    app.add_exception_handler(ProjectAlreadyExistsError, project_already_exist_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operation_error_handler)
    app.add_exception_handler(UserNotFoundError, user_not_found_handler)

    app.include_router(user_router.router)
    app.include_router(auth_router.router)
    app.include_router(api_key_router.router)

    app.add_api_route("/health", health, methods=["GET"])

    return app


app = create_app(lifespan=lifespan)
