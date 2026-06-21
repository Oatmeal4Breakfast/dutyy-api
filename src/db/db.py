from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from src.config import Config
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


def create_engine_and_session(
    config: Config,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(
        config.uri, pool_size=config.pool_size, max_overflow=config.max_overflow
    )
    session: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    return (engine, session)
