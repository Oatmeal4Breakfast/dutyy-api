from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import FastAPI
from src.db.db import create_engine_and_session
from src.config import get_config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

app = FastAPI(title="dutyy-api")


async def lifespan(app: FastAPI):
    engine, session = create_engine_and_session(get_config())
    app.state.session_factory: async_sessionmaker[AsyncSession] = session
    yield
    engine.dispose()


@app.get("/")
async def root():
    return {"message": "hello world"}
