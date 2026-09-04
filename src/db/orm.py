from sqlalchemy import Column, ForeignKey, Table, event

from src.db.base import Base
from src.domain.api import APIKey
from src.domain.device_auth import DeviceCode
from src.domain.dutyy import Dutyy
from src.domain.project import Project
from src.domain.token import PasswordSetToken
from src.domain.user import User

metadata = Base.metadata

MAPPED_ENTITIES = (APIKey, DeviceCode, Dutyy, PasswordSetToken, Project, User)

project_user_table = Table(
    "project_user",
    metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    ),
)


def _initialize_events(entity: Dutyy | Project | User, _) -> None:
    entity.events = []


# ORM hydration bypasses the dataclass constructor. Refresh is intentionally excluded
# because resetting this transient collection could discard unpublished events.
for _entity_cls in (Project, Dutyy, User):
    event.listens_for(_entity_cls, "load")(_initialize_events)
