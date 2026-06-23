from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from src.api.deps import get_uow
from src.domain.exceptions import (
    DomainValidationError,
    UserAlreadyExistsError,
    ProjectAlreadyExistsError,
)
from src.db.db import create_engine_and_session
from src.config import get_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from src.db.uow import UnitOfWork

app = FastAPI(title="dutyy-api")


async def lifespan(app: FastAPI):
    engine, session = create_engine_and_session(get_config())
    app.state.session_factory: async_sessionmaker[AsyncSession] = session
    yield
    engine.dispose()


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


@app.get("/")
async def root():
    return {"message": "hello world"}


@app.get("/health")
async def health(uow: UnitOfWork = Depends(get_uow)):
    async with uow as u:
        try:
            await u.health.ping()
            return JSONResponse(content={"status": "ok"}, status_code=200)
        except Exception:
            return JSONResponse(content={"status": "unavailable"}, status_code=503)
