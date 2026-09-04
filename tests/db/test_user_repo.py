from uuid import UUID

import pytest

from src.domain.exceptions import UserAlreadyExistsError
from src.domain.user import User, UserStatus, UserSummary
from src.repository.user_repo import UserRepo
from tests.conftest import make_user


@pytest.mark.integration
class TestUserRepo:
    async def test_add_and_retrieve_user_by_id(self, session, user):
        repo = UserRepo(session)
        result: User | None = await repo.get_by_id(user.id)

        assert result is not None
        assert result.first_name == user.first_name
        assert isinstance(result, User)

    async def test_add_and_retrieve_user_by_id_returns_none(self, session):
        repo = UserRepo(session)
        user = make_user()
        result: User | None = await repo.get_by_id(user.id)

        assert result is None

    async def test_add_and_retrieve_all_users(self, session, user):
        repo = UserRepo(session)
        user_2: User = make_user(
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
        )

        await repo.add(user_2)

        results: list[UserSummary] = await repo.get_all()

        assert len(results) == 2
        assert isinstance(results[0], UserSummary)

    async def test_retrieve_users_from_empty_table(self, session):
        repo = UserRepo(session)

        results: list[UserSummary] = await repo.get_all()

        assert isinstance(results, list)
        assert len(results) == 0

    async def test_update_user(self, session, db_roundtrip):
        repo = UserRepo(session)
        user: User = make_user()

        user_id: UUID = user.id

        await repo.add(user)

        user.update_first_name("Jermaine")

        await repo.update(user)

        await db_roundtrip()
        results: User | None = await repo.get_by_id(user_id)

        assert results is not None
        assert isinstance(results, User)
        assert results.first_name == "Jermaine"
        assert results.id == user_id

    async def test_update_user_raises_integretiy_error(self, session):
        repo = UserRepo(session)

        user: User = make_user()
        await repo.add(user)

        with pytest.raises(UserAlreadyExistsError):
            user.first_name = None
            await repo.update(user)

    async def test_delete_user_success(self, session, db_roundtrip):
        repo = UserRepo(session)
        user: User = make_user()

        await repo.add(user)

        result: User | None = await repo.get_by_id(user.id)

        assert result is not None
        assert isinstance(result, User)

        await repo.delete(user)

        await db_roundtrip()
        result: User | None = await repo.get_by_id(user.id)

        assert result is None

    async def test_get_by_id_after_roundtrip_hits_the_database(
        self, session, user, db_roundtrip
    ):
        repo = UserRepo(session)
        await db_roundtrip()

        result: User | None = await repo.get_by_id(user.id)

        assert result is not None
        assert result is not user
        assert result.id == user.id
        assert result.email == user.email

    async def test_get_by_id_returns_the_identity_mapped_instance(self, session, user):
        repo = UserRepo(session)

        assert await repo.get_by_id(user.id) is user

    async def test_loaded_user_can_collect_domain_events(
        self, session, user, db_roundtrip
    ):
        """ORM hydration skips __init__, so `events` comes from the load listener."""
        repo = UserRepo(session)
        await db_roundtrip()

        loaded: User | None = await repo.get_by_id(user.id)
        assert loaded is not None
        assert loaded.events == []

        loaded.update_status(UserStatus.BLOCKED)

        assert len(loaded.events) == 1

    async def test_get_users_by_project_id(self, session, project, user):
        repo = UserRepo(session)
        result = await repo.get_users_by_project_id(project.id)

        assert len(result) == 1
        assert isinstance(result[0], UserSummary)
        assert result[0].id == user.id

    async def test_get_users_by_project_id_returns_empty_list(self, session, project):
        from uuid import uuid7

        repo = UserRepo(session)
        result = await repo.get_users_by_project_id(uuid7())

        assert isinstance(result, list)
        assert len(result) == 0

    async def test_get_users_by_project_id_multiple_users(self, session, project, user):
        from sqlalchemy import insert

        from src.db.orm import project_user_table
        from tests.conftest import make_user

        repo = UserRepo(session)

        second_user = make_user(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        await repo.add(second_user)
        await session.execute(
            insert(project_user_table).values(
                project_id=project.id, user_id=second_user.id
            )
        )

        result = await repo.get_users_by_project_id(project.id)

        assert len(result) == 2
        ids = {u.id for u in result}
        assert user.id in ids
        assert second_user.id in ids
