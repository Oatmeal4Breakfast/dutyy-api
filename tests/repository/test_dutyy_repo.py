import pytest
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy.exc import IntegrityError

from src.repository.dutyy_repo import DutyRepo
from src.domain.dutyy import Dutyy


def make_dutyy(**kwargs) -> Dutyy:
    defaults: dict[str, Any] = {
        "title": "Test Duty",
    }
