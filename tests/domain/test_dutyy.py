import pytest
from typing import Any
from uuid import UUID

from src.domain.dutyy import Dutyy
from src.domain.enums import DutyyStatus
from src.domain.exceptions import DomainValidationError


def make_dutyy(**kwargs) -> Dutyy:
    defaults: dict[str, Any] = {
        "title": "Test Dutyy",
        "project_id": UUID("12345678-1234-5678-1234-567812345678"),
    }
    return Dutyy(**{**defaults, **kwargs})


def test_create_dutyy_success() -> None:
    dutyy = make_dutyy()

    assert isinstance(dutyy, Dutyy)
    assert dutyy.title == "test dutyy"


def test_create_dutyy_empty_title_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_dutyy(title="")


def test_update_title_success() -> None:
    dutyy = make_dutyy()
    dutyy.update_title(new_title="Updated Title ")

    assert dutyy.title == "updated title"
    assert dutyy.modified_date is not None


def test_update_title_fails_on_empty_string() -> None:
    dutyy = make_dutyy()
    with pytest.raises(DomainValidationError):
        dutyy.update_title("")


def test_update_project_id_success() -> None:
    dutyy = make_dutyy()

    new_uuid = UUID("12345678-1234-5678-1234-567812345679")
    dutyy.update_project_id(new_uuid)

    assert dutyy.project_id == new_uuid
    assert dutyy.modified_date is not None


def test_update_status_to_in_progress() -> None:
    dutyy = make_dutyy()

    assert dutyy.status == DutyyStatus.NEW

    dutyy.update_status(DutyyStatus.IN_PROGRESS)

    assert dutyy.status == DutyyStatus.IN_PROGRESS
    assert dutyy.modified_date is not None
    assert dutyy.completed_date is None


def test_update_status_to_complete() -> None:
    dutyy = make_dutyy()

    assert dutyy.status == DutyyStatus.NEW

    dutyy.update_status(DutyyStatus.COMPLETE)

    assert dutyy.status == DutyyStatus.COMPLETE
    assert dutyy.modified_date is not None
    assert dutyy.completed_date is not None
    assert len(dutyy.events) == 1


def test_update_details_not_none() -> None:
    dutyy = make_dutyy()

    assert dutyy.details is None

    dutyy.update_details("Test test test  ")

    assert dutyy.details == "Test test test"
    assert dutyy.modified_date is not None
