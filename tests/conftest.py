import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from src.db.orm import metadata

TEST_DB_URI = "postgresql+psycopg://test:test@localhost:5433/test_db"


@pytest.fixture(scope="session")
def engine():
    return create_async_engine(TEST_DB_URI)


@pytest.fixture(scope="session")
def setup_tables(engine):
    async def _create():
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
            await conn.run_sync(metadata.create_all)

    async def _drop():
        async with engine.begin() as conn:
            await conn.run_sync(metadata.drop_all)

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


@pytest.fixture
async def session(engine, setup_tables):
    async with AsyncSession(engine) as s:
        await s.begin()
        yield s
        await s.rollback()
