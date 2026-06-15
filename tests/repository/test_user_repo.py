import pytest
from typing import Any

from src.repository.user_repo import UserRepo
from src.domain.user import User


def make_user(**kwargs) -> User:
    defaults: dict[str, Any] = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "id": "019ec8c2-9640-7369-b7f6-b3da9524d7c2",
    }
    return User(**{**defaults, **kwargs})


@pytest.mark.integration
async def test_add_and_retrieve_user(session):
    repo = UserRepo(session)
    user: User = make_user()

    await repo.add(user)

    result: User | None = await repo.get_by_id(user.id)

    assert result is not None
    assert result.first_name == user.first_name
