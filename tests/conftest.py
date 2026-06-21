import asyncio
import pytest

from uuid import UUID
from typing import Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

from src.db.orm import metadata
from src.repository.user_repo import UserRepo
from src.repository.dutyy_repo import DutyRepo
from src.repository.project_repo import ProjectRepo
from src.repository.api_repository import APIRepo
from src.domain.user import User
from src.domain.project import Project
from src.domain.dutyy import Dutyy
from src.domain.api import APIKey

TEST_DB_URI = "postgresql+psycopg://test:test@localhost:5433/test_db"


def make_user(**kwargs) -> User:
    defaults: dict[str, Any] = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
    }
    return User(**{**defaults, **kwargs})


def make_project(owner_id: UUID, **kwargs) -> Project:
    defaults: dict[str, Any] = {
        "name": "Test",
        "owner_id": owner_id,
    }
    return Project(**{**defaults, **kwargs})


def make_api_key(user_id: UUID, **kwargs) -> APIKey:
    defaults: dict[str, Any] = {
        "user_id": user_id,
        "key_hash": "hashed_key_abc123",
        "name": "macbook",
    }
    return APIKey(**{**defaults, **kwargs})


def make_dutyy(project_id: UUID, **kwargs) -> Dutyy:
    defaults: dict[str, Any] = {"title": "Test Dutyy", "project_id": project_id}
    return Dutyy(**{**defaults, **kwargs})


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


@pytest.fixture
async def user(session) -> User:
    user_repo = UserRepo(session)
    u = make_user()
    await user_repo.add(u)
    return u


@pytest.fixture
async def project(session, user) -> Project:
    project_repo = ProjectRepo(session)
    p = make_project(user.id)
    await project_repo.add(p)
    return p


@pytest.fixture
async def api_key(session, user) -> APIKey:
    repo = APIRepo(session)
    key = make_api_key(user.id)
    await repo.add(key)
    return key


@pytest.fixture
async def dutyy(session, project) -> Dutyy:
    dutyy_repo = DutyRepo(session)
    d = make_dutyy(project.id)
    await dutyy_repo.add(d)
    return d
