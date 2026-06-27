from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import registry, relationship
from sqlalchemy import (
    String,
    UUID,
    ForeignKey,
    DateTime,
    Text,
    Enum,
    Table,
    Column,
    MetaData,
)
from src.domain.dutyy import Dutyy, DutyyStatus
from src.domain.project import Project, ProjectStatus
from src.domain.user import User, UserStatus
from src.domain.api import APIKey, APIKeyStatus


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
    Column("project_id", ForeignKey("projects.id"), nullable=False, index=True),
    Column("id", UUID, primary_key=True),
)

projects_table = Table(
    "projects",
    metadata,
    Column("name", String, nullable=False, unique=True),
    Column("owner_id", UUID, nullable=False),
    Column("status", Enum(ProjectStatus), nullable=False),
    Column("created_date", DateTime(timezone=True), nullable=False),
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
    Column("salt", String, nullable=True),
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

project_user_table = Table(
    "project_user",
    metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    ),
)
mapper_registry.map_imperatively(Dutyy, dutyy_table)
mapper_registry.map_imperatively(
    Project, projects_table, properties={"dutyys": relationship(Dutyy, lazy="raise")}
)
mapper_registry.map_imperatively(User, users_table)
mapper_registry.map_imperatively(APIKey, api_key_table)
