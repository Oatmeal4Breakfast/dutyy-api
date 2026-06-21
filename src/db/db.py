from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from src.config import get_config

if TYPE_CHECKING:
    from src.config import Config


_engine: AsyncEngine | None = None
_session_local: async_sessionmaker[AsyncSession] | None = None


def get_session_local() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_local
    if _session_local is None:
        config: Config = get_config()
        _engine = create_async_engine(
            config.uri, pool_size=config.pool_size, max_overflow=config.max_overflow
        )
        _session_local = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_local
