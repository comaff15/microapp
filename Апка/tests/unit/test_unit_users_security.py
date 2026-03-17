import os
import time

import pytest
from jose import jwt

from tests.unit.service_import import activate_service_app


@pytest.mark.unit
def test_users_security_hash_and_verify_password() -> None:
    activate_service_app(os.path.join(os.path.dirname(__file__), "..", "..", "services", "users"))

    from app.security import hash_password, verify_password

    password = "S3cure!Passw0rd"
    password_hash = hash_password(password)

    assert password_hash
    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong", password_hash) is False


@pytest.mark.unit
def test_users_security_token_roundtrip_and_expired() -> None:
    activate_service_app(os.path.join(os.path.dirname(__file__), "..", "..", "services", "users"))

    from app.core.config import settings
    from app.security import create_access_token, decode_token

    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["exp"] > payload["iat"]

    now = int(time.time())
    expired = jwt.encode(
        {"sub": "user-123", "iat": now - 10, "exp": now - 1},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(Exception):
        decode_token(expired)
