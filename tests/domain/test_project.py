import pytest

from typing import Any
from uuid import UUID, uuid7
from datetime import timedelta, datetime, UTC


from src.domain.project import Project
from src.domain.dutyy import Dutyy
from src.domain.project import ProjectStatus, PublishingStatus
from src.domain.events import (
    ProjectCompleted,
    ProjectPublished,
    DutyyAdded,
    DutyyRemoved,
)
from src.domain.exceptions import (
    DomainValidationError,
    DutyyAssignedError,
    DutyyNotAssignedError,
)


owner_id = uuid7()


def make_project(**kwargs) -> Project:
    defaults: dict[str, Any] = {"name": "test project ", "owner_id": owner_id}
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

    assert len(project.events) == 1
    assert isinstance(project.events[0], ProjectCompleted)


def test_update_status_abandoned() -> None:
    project = make_project()

    project.update_status(ProjectStatus.ABANDONED)

    assert project.status == ProjectStatus.ABANDONED
    assert project.modified_date is not None

    time_diff = datetime.now(UTC) - project.modified_date
    assert time_diff < timedelta(seconds=1)

    assert len(project.events) == 0


def test_add_dutyy_success() -> None:
    project = make_project()

    dutyy = make_dutyy(project_id=project.id)

    assert len(project.dutyys) == 0

    project.add_dutyy(dutyy)

    assert len(project.dutyys) == 1
    assert len(project.events) == 1
    assert isinstance(project.events[0], DutyyAdded)


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
    assert any(isinstance(e, DutyyRemoved) for e in project.events)


def test_delete_dutyy_fails() -> None:
    project = make_project()
    with pytest.raises(DutyyNotAssignedError):
        dutyy = make_dutyy(project_id=project.id)
        project.delete_dutyy(dutyy)


def test_transfer_ownership_success() -> None:
    project = make_project()

    new_owner = uuid7()

    project.transfer_ownership(new_owner)

    assert project.owner_id == new_owner


def test_transfer_ownership_idempotent() -> None:
    project = make_project()

    project.transfer_ownership(owner_id)

    assert project.modified_date is None


def test_transfer_ownership_appends_event() -> None:
    from src.domain.events import OwnershipTransferred

    project = make_project()
    new_owner = uuid7()

    project.transfer_ownership(new_owner)

    assert len(project.events) == 1
    assert isinstance(project.events[0], OwnershipTransferred)
    assert project.events[0].new_owner == new_owner


def test_update_status_complete_not_reversible() -> None:
    project = make_project()

    project.update_status(ProjectStatus.COMPLETE)

    with pytest.raises(DomainValidationError):
        project.update_status(ProjectStatus.NEW)


def test_new_project_defaults_to_draft() -> None:
    project = make_project()

    assert project.publishing_status == PublishingStatus.DRAFT
    assert project.published_date is None


def test_publish_success() -> None:
    project = make_project()

    project.publish()

    assert project.publishing_status == PublishingStatus.PUBLISHED
    assert project.published_date is not None

    time_diff = datetime.now(UTC) - project.published_date
    assert time_diff < timedelta(seconds=1)

    # publish reuses _touch(), so the two timestamps are the same instant
    assert project.published_date == project.modified_date


def test_publish_appends_event() -> None:
    project = make_project()

    project.publish()

    assert len(project.events) == 1
    event = project.events[0]
    assert isinstance(event, ProjectPublished)
    assert event.project_id == project.id
    assert event.name == project.name
    assert event.owner_id == project.owner_id
    assert event.published_date == project.published_date


def test_publish_idempotent() -> None:
    project = make_project()

    project.publish()
    first_published_date = project.published_date

    project.publish()

    assert len(project.events) == 1
    assert project.published_date == first_published_date


def test_unpublish_success() -> None:
    project = make_project()
    project.publish()

    project.unpublish()

    assert project.publishing_status == PublishingStatus.DRAFT
    assert project.modified_date is not None

    time_diff = datetime.now(UTC) - project.modified_date
    assert time_diff < timedelta(seconds=1)


def test_unpublish_retains_published_date() -> None:
    # Intentional: unpublishing moves status back to DRAFT but keeps
    # published_date as a historical "last published at" marker.
    project = make_project()
    project.publish()
    published_date = project.published_date

    project.unpublish()

    assert project.publishing_status == PublishingStatus.DRAFT
    assert project.published_date == published_date


def test_unpublish_idempotent_on_draft() -> None:
    project = make_project()

    project.unpublish()

    assert project.publishing_status == PublishingStatus.DRAFT
    assert project.modified_date is None
    assert len(project.events) == 0


def test_publish_is_orthogonal_to_status() -> None:
    project = make_project()

    project.update_status(ProjectStatus.COMPLETE)
    project.publish()

    assert project.status == ProjectStatus.COMPLETE
    assert project.publishing_status == PublishingStatus.PUBLISHED


def test_delete_dutyy_specific_when_multiple_exist() -> None:
    project = make_project()
    dutyy_1 = make_dutyy(project_id=project.id)
    dutyy_2 = make_dutyy(project_id=project.id, title="Second Dutyy")

    project.add_dutyy(dutyy_1)
    project.add_dutyy(dutyy_2)

    assert len(project.dutyys) == 2

    project.delete_dutyy(dutyy_1)

    assert len(project.dutyys) == 1
    assert project.dutyys[0].id == dutyy_2.id
