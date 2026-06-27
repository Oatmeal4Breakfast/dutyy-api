from __future__ import annotations

import secrets
import string
from typing import LiteralString

from pwdlib import PasswordHash

from src.domain.events import UserCreated
from src.db.uow import AbstractUnitOfWork
from src.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, uow: AbstractUnitOfWork) -> None:
        self._uow = uow
        self._valid_characters: LiteralString = (
            string.ascii_letters + string.digits + string.punctuation
        )
        self._password_hash: PasswordHash = PasswordHash.recommended()

    def generate_random_password(self, event: UserCreated) -> str:
        return "".join(secrets.choice(self._valid_characters) for _ in range(12))

    def hash_password(self, plain_password: str) -> str:
        return self._password_hash.hash(password=plain_password)
