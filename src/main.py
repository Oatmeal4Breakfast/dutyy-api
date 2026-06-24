from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from src.api.deps import get_uow
from src.api import user_router
from src.domain.exceptions import (
    DomainValidationError,
    UserAlreadyExistsError,
    ProjectAlreadyExistsError,
)
from src.service.user_service import UserNotFoundError
from src.db.db import create_engine_and_session
from src.config import get_config, Config
from src.logger import config_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from src.db.uow import UnitOfWork


async def lifespan(app: FastAPI):
    config: Config = get_config()
    config_logger(config)
    engine, session = create_engine_and_session(config)
    app.state.session_factory: async_sessionmaker[AsyncSession] = session
    yield
    engine.dispose()


app = FastAPI(title="dutyy-api", lifespan=lifespan)


@app.exception_handler(DomainValidationError)
async def domain_validation_exception_handler(
    request: Request, exc: DomainValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errors": exc.errors})


@app.exception_handler(UserAlreadyExistsError)
async def user_already_exist_handler(
    request: Request, exc: UserAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ProjectAlreadyExistsError)
async def project_already_exist_handler(
    request: Request, exc: ProjectAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(OperationalError)
async def operation_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "service unavailable"})


@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(
    request: Request, exc: UserNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"details": f"user {exc.user_id} not found"}
    )


app.include_router(user_router.router)


@app.get("/health")
async def health(uow: UnitOfWork = Depends(get_uow)):
    async with uow as u:
        await u.health.ping()
    return JSONResponse(content={"status": "ok"}, status_code=200)
