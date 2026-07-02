from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from packaging.version import Version

from jarvis.config.settings import Settings, load_settings
from jarvis.security.desktop_auth import (
    AuthenticatedPrincipal,
    ContractRange,
    DesktopSessionAuthenticator,
    DesktopSessionRecord,
    DesktopSessionToken,
    DeviceRecord,
    DeviceStatus,
    InMemoryDeviceRegistry,
    InMemoryNonceStore,
    InMemorySessionRegistry,
    SessionStatus,
    authenticateDesktopSession,
)


NOW = datetime.now(UTC)
ACTOR_ID = "actor-001"
DEVICE_ID = "device-001"
SESSION_ID = "session-001"
SECRET = "a" * 32
CONTRACTS = ContractRange.parse("1.0.0", "1.5.0")


def settings() -> Settings:
    return load_settings(
        overrides={
            "DB_HOST": "db.internal",
            "DB_NAME": "jarvis_test",
            "DB_USER": "jarvis_test",
            "DB_PASSWORD": "database-password",
            "DEFAULT_SCHEMA": "jarvis",
            "JWT_ACCESS_SECRET": SECRET,
            "JWT_REFRESH_SECRET": "b" * 32,
        }
    )


def device_record(
    *,
    status: DeviceStatus = DeviceStatus.ACTIVE,
    actor_id: str = ACTOR_ID,
    epoch: int = 7,
) -> DeviceRecord:
    return DeviceRecord(
        device_id=DEVICE_ID,
        actor_id=actor_id,
        status=status,
        session_epoch=epoch,
        contract_range=CONTRACTS,
    )


def session_record(
    *,
    status: SessionStatus = SessionStatus.ACTIVE,
    actor_id: str = ACTOR_ID,
    device_id: str = DEVICE_ID,
    epoch: int = 7,
    expires_at: datetime = NOW + timedelta(minutes=10),
) -> DesktopSessionRecord:
    return DesktopSessionRecord(
        session_id=SESSION_ID,
        device_id=device_id,
        actor_id=actor_id,
        status=status,
        session_epoch=epoch,
        expires_at=expires_at,
        contract_range=CONTRACTS,
    )


def authenticator(
    *,
    device: DeviceRecord | None = None,
    session: DesktopSessionRecord | None = None,
) -> DesktopSessionAuthenticator:
    return DesktopSessionAuthenticator(
        settings=settings(),
        devices=InMemoryDeviceRegistry([device or device_record()]),
        sessions=InMemorySessionRegistry([session or session_record()]),
        nonces=InMemoryNonceStore(),
        supported_contracts=ContractRange.parse("1.1.0", "2.0.0"),
    )


def token(
    *,
    issued_at: datetime = NOW,
    lifetime: timedelta = timedelta(minutes=5),
    actor_id: str = ACTOR_ID,
    device_id: str = DEVICE_ID,
    epoch: int = 7,
    contracts: ContractRange = CONTRACTS,
) -> str:
    return DesktopSessionToken(SECRET).issue(
        actor_id=actor_id,
        device_id=device_id,
        session_id=SESSION_ID,
        session_epoch=epoch,
        contract_range=contracts,
        issued_at=issued_at,
        lifetime=lifetime,
    )


def headers(
    session_token: str | None = None,
    *,
    device_id: str = DEVICE_ID,
    contract_version: str = "1.2.0",
    nonce: str | None = None,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {session_token or token()}",
        "X-Device-Id": device_id,
        "X-Contract-Version": contract_version,
        "X-Request-Nonce": nonce or str(uuid4()),
    }


def application(
    session_authenticator: DesktopSessionAuthenticator | None,
) -> FastAPI:
    app = FastAPI()
    if session_authenticator is not None:
        app.state.desktop_authenticator = session_authenticator

    @app.get("/protected")
    async def protected(
        request: Request,
        principal: Annotated[
            AuthenticatedPrincipal,
            Depends(authenticateDesktopSession),
        ],
    ) -> dict[str, str]:
        assert request.state.principal is principal
        return {
            "actor_id": principal.actor_id,
            "device_id": principal.device_id,
            "session_id": principal.session_id,
            "contract_version": str(principal.contract_version),
        }

    return app


def test_authenticates_and_binds_immutable_principal() -> None:
    session_authenticator = authenticator()

    with TestClient(application(session_authenticator)) as client:
        response = client.get("/protected", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "actor_id": ACTOR_ID,
        "device_id": DEVICE_ID,
        "session_id": SESSION_ID,
        "contract_version": "1.2.0",
    }

    frozen = AuthenticatedPrincipal(
        actor_id=ACTOR_ID,
        device_id=DEVICE_ID,
        session_id=SESSION_ID,
        token_id="token",
        contract_version=Version("1.2.0"),
        contract_range=CONTRACTS,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(FrozenInstanceError):
        frozen.actor_id = "changed"


def test_loopback_request_without_credentials_is_not_trusted() -> None:
    with TestClient(application(authenticator())) as client:
        response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_desktop_session"
    assert response.headers["www-authenticate"] == "Bearer"


def test_tampered_and_expired_tokens_are_rejected() -> None:
    valid_token = token()
    tampered = valid_token[:-2] + ("aa" if valid_token[-2:] != "aa" else "bb")
    expired = token(
        issued_at=NOW - timedelta(minutes=10),
        lifetime=timedelta(minutes=1),
    )

    with TestClient(application(authenticator())) as client:
        tampered_response = client.get("/protected", headers=headers(tampered))
        expired_response = client.get("/protected", headers=headers(expired))

    assert tampered_response.status_code == 401
    assert expired_response.status_code == 401


def test_unsigned_token_and_token_missing_required_claim_are_rejected() -> None:
    payload = jwt.decode(token(), options={"verify_signature": False})
    unsigned = jwt.encode(payload, key="", algorithm="none")
    payload.pop("device_id")
    missing_claim = jwt.encode(payload, SECRET, algorithm="HS256")

    with TestClient(application(authenticator())) as client:
        unsigned_response = client.get("/protected", headers=headers(unsigned))
        missing_claim_response = client.get(
            "/protected",
            headers=headers(missing_claim),
        )

    assert unsigned_response.status_code == 401
    assert missing_claim_response.status_code == 401


@pytest.mark.parametrize(
    ("device", "session"),
    [
        (device_record(status=DeviceStatus.REVOKED), session_record()),
        (device_record(), session_record(status=SessionStatus.REVOKED)),
        (device_record(epoch=8), session_record()),
        (device_record(), session_record(actor_id="other-actor")),
        (device_record(), session_record(device_id="other-device")),
        (
            device_record(),
            session_record(expires_at=NOW - timedelta(seconds=1)),
        ),
    ],
)
def test_registry_revocation_and_binding_mismatches_are_rejected(
    device: DeviceRecord,
    session: DesktopSessionRecord,
) -> None:
    with TestClient(application(authenticator(device=device, session=session))) as client:
        response = client.get("/protected", headers=headers())

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_desktop_session"


def test_device_header_must_match_signed_device() -> None:
    with TestClient(application(authenticator())) as client:
        response = client.get(
            "/protected",
            headers=headers(device_id="other-device"),
        )

    assert response.status_code == 401


def test_contract_mismatch_returns_upgrade_required_without_consuming_nonce() -> None:
    request_nonce = str(uuid4())
    request_headers = headers(contract_version="2.5.0", nonce=request_nonce)

    with TestClient(application(authenticator())) as client:
        rejected = client.get("/protected", headers=request_headers)
        accepted = client.get(
            "/protected",
            headers=request_headers | {"X-Contract-Version": "1.2.0"},
        )

    assert rejected.status_code == 426
    assert rejected.json()["detail"]["code"] == "contract_version_unsupported"
    assert accepted.status_code == 200


def test_replayed_request_nonce_is_rejected() -> None:
    request_headers = headers()

    with TestClient(application(authenticator())) as client:
        first = client.get("/protected", headers=request_headers)
        replay = client.get("/protected", headers=request_headers)

    assert first.status_code == 200
    assert replay.status_code == 401


def test_missing_authenticator_fails_as_unavailable() -> None:
    with TestClient(application(None)) as client:
        response = client.get("/protected", headers=headers())

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "desktop_authentication_unavailable"
