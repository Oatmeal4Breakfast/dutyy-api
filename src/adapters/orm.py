from __future__ import annotations
from typing import TYPE_CHECKING
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

from src.domain.dutyy import DutyyStatus, Dutyy
from src.domain.project import ProjectStatus, Project

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Any
    from uuid import UUID

mapper_registry = registry()
metadata = MetaData()


dutyy_table = Table(
    "dutyys",
    metadata,
    Column("title", String, nullable=False),
    Column("details", Text, nullable=True),
    Column("status", Enum(DutyyStatus), nullable=False),
    Column("created_date", DateTime, nullable=False),
    Column("modified_date", DateTime, nullable=True),
    Column("completed_date", DateTime, nullable=True),
    Column("project_id", ForeignKey("projects.id"), nullable=False),
    Column("id", UUID, primary_key=True),
)

projects_table = Table(
    "projects",
    metadata,
    Column("name", String, nullable=False, unique=True),
    Column("status", Enum(ProjectStatus), nullable=False),
    Column("created_date", DateTime, nullable=False),
    Column("completed_date", DateTime, nullable=True),
    Column("id", UUID, primary_key=True),
)

mapper_registry.map_imperatively(Dutyy, dutyy_table)
mapper_registry.map_imperatively(
    Project, projects_table, properties={"dutyys": relationship(Dutyy, lazy="raise")}
)
