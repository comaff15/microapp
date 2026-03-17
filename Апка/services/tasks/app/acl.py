PROJECT_ROLES = {"owner", "maintainer", "viewer"}


def can_write(role: str) -> bool:
    return role in ("owner", "maintainer")


def is_owner(role: str) -> bool:
    return role == "owner"
