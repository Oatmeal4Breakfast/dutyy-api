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
from src.domain.enums import DutyyStatus, ProjectStatus
from src.domain.dutyy import Dutyy
from src.domain.project import Project


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
    Column("project_id", ForeignKey("projects.id"), nullable=False),
    Column("id", UUID, primary_key=True),
)

projects_table = Table(
    "projects",
    metadata,
    Column("name", String, nullable=False, unique=True),
    Column("status", Enum(ProjectStatus), nullable=False),
    Column("created_date", DateTime(timezone=True), nullable=False),
    Column("completed_date", DateTime(timezone=True), nullable=True),
    Column("modified_date", DateTime(timezone=True), nullable=True),
    Column("id", UUID, primary_key=True),
)

mapper_registry.map_imperatively(Dutyy, dutyy_table)
mapper_registry.map_imperatively(
    Project, projects_table, properties={"dutyys": relationship(Dutyy, lazy="raise")}
)
