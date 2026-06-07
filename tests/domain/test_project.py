from dns.ttl import make
import pytest

from typing import Any
from uuid import UUID
from datetime import timedelta, datetime, UTC


from src.domain.project import Project
from src.domain.dutyy import Dutyy
from src.domain.enums import ProjectStatus
from src.domain.exceptions import (
    DomainValidationError,
    DutyyAssignedError,
    DutyyNotAssignedError,
)


def make_project(**kwargs) -> Project:
    defaults: dict[str, Any] = {"name": "test project "}
    return Project(**{**defaults, **kwargs})


def make_dutyy(**kwargs) -> Dutyy:
    defaults: dict[str, Any] = {
        "title": "Test Dutyy",
        "project_id": UUID("12345678-1234-5678-1234-567812345678"),
    }
    return Dutyy(**{**defaults, **kwargs})


def test_create_project_success() -> None:
    project = make_project()

    time_diff = datetime.now(UTC) - project.created_date
    assert time_diff < timedelta(seconds=1)
    assert isinstance(project, Project)
    assert project.name == "test project"


def test_create_project_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_project(name="   ")


def test_update_name_sucess() -> None:
    project = make_project()

    project.update_name(name="Updated name    ")

    assert project.modified_date is not None

    time_diff = datetime.now(UTC) - project.modified_date
    assert time_diff < timedelta(seconds=1)

    assert project.name == "updated name"


def test_update_name_empty_string_fails() -> None:
    project = make_project()
    with pytest.raises(DomainValidationError):
        project.update_name("    ")


def test_update_status_idempotent() -> None:
    project = make_project()

    project.update_status(ProjectStatus.NEW)

    assert project.modified_date is None


def test_update_status_sucess() -> None:
    project = make_project()
    project.update_status(ProjectStatus.IN_PROGRESS)

    assert project.modified_date is not None

    time_diff = datetime.now(UTC) - project.modified_date

    assert time_diff < timedelta(seconds=1)

    assert project.status == ProjectStatus.IN_PROGRESS


def test_update_status_not_reversable() -> None:
    project = make_project()

    project.update_status(ProjectStatus.IN_PROGRESS)

    assert project.status == ProjectStatus.IN_PROGRESS

    with pytest.raises(DomainValidationError):
        project.update_status(ProjectStatus.NEW)


def test_update_status_complete() -> None:
    project = make_project()

    project.update_status(ProjectStatus.COMPLETE)

    assert project.status == ProjectStatus.COMPLETE

    assert project.completed_date is not None

    time_diff = datetime.now(UTC) - project.completed_date
    assert time_diff < timedelta(seconds=1)


def test_add_dutyy_success() -> None:
    project = make_project()

    dutyy = make_dutyy(project_id=project.id)

    assert len(project.dutyys) == 0

    project.add_dutyy(dutyy)

    assert len(project.dutyys) == 1


def test_add_same_dutyy_fails() -> None:
    project = make_project()
    dutyy = make_dutyy(project_id=project.id)
    project.add_dutyy(dutyy)

    with pytest.raises(DutyyAssignedError):
        project.add_dutyy(dutyy)


def test_delete_dutyy_sucess() -> None:
    project = make_project()

    dutyy = make_dutyy(project_id=project.id)

    assert len(project.dutyys) == 0

    project.add_dutyy(dutyy)

    assert len(project.dutyys) == 1

    project.delete_dutyy(dutyy)

    assert len(project.dutyys) == 0


def test_delete_dutyy_fails() -> None:
    project = make_project()
    with pytest.raises(DutyyNotAssignedError):
        dutyy = make_dutyy(project_id=project.id)
        project.delete_dutyy(dutyy)
