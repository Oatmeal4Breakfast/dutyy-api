import pytest
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from src.repository.user_repo import UserRepo
from src.domain.user import User
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

        results: list[User] = await repo.get_all()

        assert len(results) == 2
        assert isinstance(results[0], User)

    async def test_retrieve_users_from_empty_table(self, session):
        repo = UserRepo(session)

        results: list[User] = await repo.get_all()

        assert isinstance(results, list)
        assert len(results) == 0

    async def test_update_user(self, session):
        repo = UserRepo(session)
        user: User = make_user()

        user_id: UUID = user.id

        await repo.add(user)

        user.update_first_name("Jermaine")

        await repo.update(user)

        results: User | None = await repo.get_by_id(user.id)

        assert results is not None
        assert isinstance(results, User)
        assert results.first_name == "Jermaine"
        assert results.id == user_id

    async def test_update_user_raises_integretiy_error(self, session):
        repo = UserRepo(session)

        user: User = make_user()
        await repo.add(user)

        with pytest.raises(IntegrityError):
            user.first_name = None
            await repo.update(user)

    async def test_delete_user_success(self, session):
        repo = UserRepo(session)
        user: User = make_user()

        await repo.add(user)

        result: User | None = await repo.get_by_id(user.id)

        assert result is not None
        assert isinstance(result, User)

        await repo.delete(user)

        result: User | None = await repo.get_by_id(user.id)

        assert result is None

    async def test_get_users_by_project_id(self, session, project, user):
        repo = UserRepo(session)
        result = await repo.get_users_by_project_id(project.id)

        assert len(result) == 1
        assert isinstance(result[0], User)
        assert result[0].id == user.id
