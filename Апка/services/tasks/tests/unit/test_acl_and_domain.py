import pytest

from app.acl import PROJECT_ROLES, can_write, is_owner
from app.domain import validate_status, validate_transition


@pytest.mark.unit
def test_project_roles_contains_expected_roles() -> None:
    assert PROJECT_ROLES == {"owner", "maintainer", "viewer"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "role,expected",
    [
        ("owner", True),
        ("maintainer", True),
        ("viewer", False),
        ("unknown", False),
        ("", False),
    ],
)
def test_can_write(role: str, expected: bool) -> None:
    assert can_write(role) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "role,expected",
    [
        ("owner", True),
        ("maintainer", False),
        ("viewer", False),
        ("unknown", False),
    ],
)
def test_is_owner(role: str, expected: bool) -> None:
    assert is_owner(role) is expected


@pytest.mark.unit
@pytest.mark.parametrize("status", ["todo", "in_progress", "done", "canceled"])
def test_validate_status_accepts_known_values(status: str) -> None:
    validate_status(status)


@pytest.mark.unit
def test_validate_status_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match=r"Invalid status"):
        validate_status("blocked")


@pytest.mark.unit
@pytest.mark.parametrize(
    "old,new",
    [
        ("todo", "in_progress"),
        ("todo", "canceled"),
        ("in_progress", "done"),
        ("in_progress", "canceled"),
        ("done", "done"),
    ],
)
def test_validate_transition_allows_valid_transitions(old: str, new: str) -> None:
    validate_transition(old, new)


@pytest.mark.unit
@pytest.mark.parametrize(
    "old,new",
    [
        ("todo", "done"),
        ("done", "in_progress"),
        ("canceled", "todo"),
    ],
)
def test_validate_transition_rejects_invalid_transitions(old: str, new: str) -> None:
    with pytest.raises(ValueError, match=r"Invalid transition"):
        validate_transition(old, new)


@pytest.mark.unit
def test_validate_transition_rejects_invalid_status_in_old_or_new() -> None:
    with pytest.raises(ValueError, match=r"Invalid status"):
        validate_transition("todo", "blocked")

    with pytest.raises(ValueError, match=r"Invalid status"):
        validate_transition("blocked", "todo")
