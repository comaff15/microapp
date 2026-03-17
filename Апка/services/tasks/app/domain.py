ALLOWED_STATUSES = {"todo", "in_progress", "done", "canceled"}


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "todo": {"in_progress", "canceled"},
    "in_progress": {"done", "canceled"},
    "done": set(),
    "canceled": set(),
}


def validate_status(status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status}")


def validate_transition(old: str, new: str) -> None:
    validate_status(old)
    validate_status(new)
    if old == new:
        return
    if new not in _ALLOWED_TRANSITIONS.get(old, set()):
        raise ValueError(f"Invalid transition: {old} -> {new}")
