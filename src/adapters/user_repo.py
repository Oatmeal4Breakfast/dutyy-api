from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import Select, update, delete

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.interfaces.abstract_repository import AbstractRepository
from src.adapters.orm import users_table
from src.domain import User
from src.logger import get_logger

logger = get_logger(__name__)


class UserRepo(AbstractRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
