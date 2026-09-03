from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import registry, relationship

from src.domain.api import APIKey, APIKeyStatus
from src.domain.device_auth import DeviceCode, DeviceCodeStatus, KeyLifetime
from src.domain.dutyy import Dutyy, DutyyStatus
from src.domain.project import Project, ProjectStatus, PublishingStatus
from src.domain.token import PasswordSetToken
from src.domain.user import User, UserStatus

mapper_registry = registry()
metadata = MetaData()


dutyy_table = Table(
    "dutyys",
    metadata,
    Column("title", String, nullable=False),
    Column("details", Text, nullable=True),
    Column("status", Enum(DutyyStatus), nullable=False),
    Column("created_date", DateTime(timezone=True), nullable=False),
    Column("modified_date", DateTime(timezone=True), nullable=True),
    Column("completed_date", DateTime(timezone=True), nullable=True),
    Column(
        "project_id",
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("id", UUID, primary_key=True),
)

projects_table = Table(
    "projects",
    metadata,
    Column("name", String, nullable=False, unique=True),
    Column("owner_id", UUID, nullable=False),
    Column("status", Enum(ProjectStatus), nullable=False),
    Column("publishing_status", Enum(PublishingStatus), nullable=False),
    Column("created_date", DateTime(timezone=True), nullable=False),
    Column("published_date", DateTime(timezone=True), nullable=True),
    Column("completed_date", DateTime(timezone=True), nullable=True),
    Column("modified_date", DateTime(timezone=True), nullable=True),
    Column("id", UUID, primary_key=True),
)

users_table = Table(
    "users",
    metadata,
    Column("first_name", String, nullable=False),
    Column("last_name", String, nullable=False),
    Column("email", CITEXT, nullable=False, unique=True),
    Column("created_date", DateTime(timezone=True), nullable=False),
    Column("last_login", DateTime(timezone=True), nullable=True),
    Column("password_hash", String, nullable=True),
    Column("modified_date", DateTime(timezone=True), nullable=True),
    Column("status", Enum(UserStatus), nullable=False),
    Column("id", UUID, primary_key=True),
)

api_key_table = Table(
    "api_keys",
    metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("key_hash", String, nullable=False),
    Column("name", String, nullable=False),
    Column("status", Enum(APIKeyStatus), nullable=False),
    Column("last_used", DateTime(timezone=True), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("created_date", DateTime(timezone=True), nullable=False),
    Column("id", UUID, primary_key=True),
)

Index(
    "uq_api_keys_active_name",
    api_key_table.c.user_id,
    api_key_table.c.name,
    unique=True,
    postgresql_where=(api_key_table.c.status == APIKeyStatus.ACTIVE),
)

password_set_tokens_table = Table(
    "password_token",
    metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("token_hash", String, nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_date", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True), nullable=True),
    Column("id", UUID, primary_key=True),
)

project_user_table = Table(
    "project_user",
    metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    ),
)

device_auth_code_table = Table(
    "device_auth_code",
    metadata,
    Column(
        "hashed_device_code",
        String,
        primary_key=True,
    ),
    Column("user_code", String, nullable=False, unique=True, index=True),
    Column("status", Enum(DeviceCodeStatus), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("key_name", String, nullable=False),
    Column("key_lifetime", Enum(KeyLifetime), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
)

mapper_registry.map_imperatively(Dutyy, dutyy_table)
mapper_registry.map_imperatively(
    Project,
    projects_table,
    properties={
        "dutyys": relationship(Dutyy, lazy="raise", cascade="all, delete-orphan")
    },
)
mapper_registry.map_imperatively(User, users_table)
mapper_registry.map_imperatively(APIKey, api_key_table)
mapper_registry.map_imperatively(PasswordSetToken, password_set_tokens_table)
mapper_registry.map_imperatively(DeviceCode, device_auth_code_table)


@event.listens_for(Project, "load")
def initialize_project_events(project: Project, _) -> None:
    project.events = []
