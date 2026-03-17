import os

import pytest

from tests.unit.service_import import activate_service_app


@pytest.mark.unit
def test_tasks_acl_and_domain() -> None:
    activate_service_app(os.path.join(os.path.dirname(__file__), "..", "..", "services", "tasks"))

    from app.acl import PROJECT_ROLES, can_write, is_owner
    from app.domain import validate_status, validate_transition

    assert PROJECT_ROLES == {"owner", "maintainer", "viewer"}

    assert can_write("owner") is True
    assert can_write("maintainer") is True
    assert can_write("viewer") is False

    assert is_owner("owner") is True
    assert is_owner("maintainer") is False

    for s in ("todo", "in_progress", "done", "canceled"):
        validate_status(s)

    with pytest.raises(ValueError):
        validate_status("blocked")

    validate_transition("todo", "in_progress")

    with pytest.raises(ValueError):
        validate_transition("todo", "done")
