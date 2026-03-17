import time

import pytest
from jose import jwt

from app.core.config import settings
from app.security import create_access_token, decode_token, hash_password, verify_password


@pytest.mark.unit
def test_hash_password_and_verify_password_roundtrip() -> None:
    password = "S3cure!Passw0rd"
    password_hash = hash_password(password)

    assert password_hash
    assert password_hash != password

    assert verify_password(password, password_hash) is True
    assert verify_password("wrong", password_hash) is False


@pytest.mark.unit
def test_create_access_token_contains_subject_and_exp() -> None:
    token = create_access_token("user-123")
    payload = decode_token(token)

    assert payload["sub"] == "user-123"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


@pytest.mark.unit
def test_decode_token_rejects_tampered_token() -> None:
    token = create_access_token("user-123")
    header, payload, signature = token.split(".")

    # flip one bit in payload part (still base64url-ish)
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join([header, tampered_payload, signature])

    with pytest.raises(Exception):
        decode_token(tampered)


@pytest.mark.unit
def test_decode_token_rejects_expired_token() -> None:
    now = int(time.time())
    payload = {"sub": "user-123", "iat": now - 10, "exp": now - 1}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    with pytest.raises(Exception):
        decode_token(token)
