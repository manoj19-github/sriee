from __future__ import annotations

import asyncio
import base64
import hashlib
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from jarvis.config.settings import load_settings
from jarvis.security.desktop_auth import (
    ContractRange,
    DesktopSessionAuthenticator,
    DesktopSessionToken,
    DeviceStatus,
    InMemoryNonceStore,
)
from jarvis.security.device_identity import (
    PUBLIC_KEY_ALGORITHM,
    PUBLIC_KEY_FORMAT,
    WindowsCngDeviceKeyStore,
)
from jarvis.security.session_auth import (
    DeviceSessionProof,
    InMemorySessionAuthority,
    InMemorySessionChallengeStore,
    SessionAuthenticationError,
    SessionAuthenticationService,
    SessionDeviceRecord,
    SessionRotationConflictError,
    authenticateSession,
    buildSessionProofMessage,
    encodeSessionProofSignature,
    issueSessionChallenge,
)


NOW = datetime.now(UTC)
SECRET = "a" * 32
BACKEND_ID = "bkd_0123456789abcdef0123456789abcdef"
ACTOR_ID = "S-1-5-21-1000"
USER_SESSION_ID = "4"
CONTRACTS = ContractRange.parse("1.0.0", "2.0.0")
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def public_bytes(private_key=PRIVATE_KEY) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


def device(private_key=PRIVATE_KEY, **changes) -> SessionDeviceRecord:
    raw_public = public_bytes(private_key)
    values = {
        "device_id": f"dev_{hashlib.sha256(raw_public).hexdigest()[:32]}",
        "actor_id": ACTOR_ID,
        "public_key": encode(raw_public),
        "public_key_algorithm": PUBLIC_KEY_ALGORITHM,
        "public_key_format": PUBLIC_KEY_FORMAT,
        "status": DeviceStatus.ACTIVE,
        "session_epoch": 0,
        "contract_range": CONTRACTS,
    }
    values.update(changes)
    return SessionDeviceRecord(**values)


def service(
    *,
    authority=None,
    challenges=None,
    clock=None,
    backend_id=BACKEND_ID,
    supported=CONTRACTS,
) -> SessionAuthenticationService:
    return SessionAuthenticationService(
        authority=authority or InMemorySessionAuthority((device(),)),
        challenges=challenges or InMemorySessionChallengeStore(),
        tokens=DesktopSessionToken(SECRET),
        supported_contracts=supported,
        backend_instance_id=backend_id,
        clock=clock or (lambda: NOW),
        random_bytes=lambda size: b"s" * size,
    )


def raw_signature(private_key, message: bytes) -> bytes:
    digest = hashlib.sha256(message).digest()
    der = private_key.sign(
        digest, ec.ECDSA(utils.Prehashed(hashes.SHA256()))
    )
    r, s = utils.decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


async def proof_for(
    auth_service,
    *,
    private_key=PRIVATE_KEY,
    device_id=None,
    user_session_id=USER_SESSION_ID,
    contract_minimum="1.2.0",
    contract_maximum="1.8.0",
):
    challenge = await issueSessionChallenge(
        device_id or device(private_key).device_id, service=auth_service
    )
    unsigned = DeviceSessionProof(
        challenge_id=challenge.challenge_id,
        device_id=challenge.device_id,
        user_session_id=user_session_id,
        client_nonce=str(uuid4()),
        contract_minimum=contract_minimum,
        contract_maximum=contract_maximum,
        signature=encode(b"x" * 64),
    )
    signature = raw_signature(
        private_key, buildSessionProofMessage(challenge, unsigned)
    )
    return replace(
        unsigned, signature=encodeSessionProofSignature(signature)
    ), challenge


@pytest.mark.anyio
async def test_authenticates_device_and_issues_bound_session() -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    grant = await authenticateSession(proof, service=auth_service)

    assert grant.device_id == device().device_id
    assert grant.actor_id == ACTOR_ID
    assert grant.user_session_id == USER_SESSION_ID
    assert grant.backend_instance_id == BACKEND_ID
    assert grant.session_epoch == 1
    assert grant.contract_minimum == "1.2.0"
    assert grant.contract_maximum == "1.8.0"
    assert grant.expires_at - grant.issued_at == timedelta(minutes=5)
    claims = DesktopSessionToken(SECRET).decode(grant.access_token)
    assert claims["user_session_id"] == USER_SESSION_ID
    assert claims["backend_instance_id"] == BACKEND_ID
    assert claims["session_epoch"] == 1


@pytest.mark.anyio
async def test_grant_works_with_existing_request_authenticator() -> None:
    authority = InMemorySessionAuthority((device(),))
    auth_service = service(authority=authority)
    proof, _ = await proof_for(auth_service)
    grant = await authenticateSession(proof, service=auth_service)
    settings = load_settings(overrides={
        "DB_HOST": "db.internal", "DB_NAME": "jarvis_test",
        "DB_USER": "jarvis_test", "DB_PASSWORD": "database-password",
        "DEFAULT_SCHEMA": "jarvis", "JWT_ACCESS_SECRET": SECRET,
        "JWT_REFRESH_SECRET": "b" * 32,
    })
    authenticator = DesktopSessionAuthenticator(
        settings=settings, devices=authority, sessions=authority,
        nonces=InMemoryNonceStore(clock=lambda: NOW),
        supported_contracts=CONTRACTS, clock=lambda: NOW,
    )
    principal = await authenticator.authenticate(
        authorization=f"Bearer {grant.access_token}",
        device_id=grant.device_id,
        contract_version="1.5.0",
        request_nonce=str(uuid4()),
    )
    assert principal.session_id == grant.session_id
    assert principal.actor_id == ACTOR_ID

    unbound = DesktopSessionToken(SECRET).issue(
        actor_id=ACTOR_ID,
        device_id=grant.device_id,
        session_id=grant.session_id,
        session_epoch=grant.session_epoch,
        contract_range=CONTRACTS,
        issued_at=NOW,
    )
    with pytest.raises(HTTPException) as caught:
        await authenticator.authenticate(
            authorization=f"Bearer {unbound}",
            device_id=grant.device_id,
            contract_version="1.5.0",
            request_nonce=str(uuid4()),
        )
    assert caught.value.status_code == 401


@pytest.mark.anyio
async def test_rotation_revokes_prior_session_and_advances_epoch() -> None:
    authority = InMemorySessionAuthority((device(),))
    auth_service = service(authority=authority)
    first_proof, _ = await proof_for(auth_service)
    first = await authenticateSession(first_proof, service=auth_service)
    second_proof, _ = await proof_for(auth_service)
    second = await authenticateSession(second_proof, service=auth_service)

    assert second.session_epoch == 2
    assert (await authority.get_session(first.session_id)).status.value == "revoked"
    assert (await authority.get_session(second.session_id)).status.value == "active"
    assert (await authority.get_device(device().device_id)).session_epoch == 2


@pytest.mark.anyio
async def test_challenge_replay_is_rejected() -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    await authenticateSession(proof, service=auth_service)
    with pytest.raises(SessionAuthenticationError) as caught:
        await authenticateSession(proof, service=auth_service)
    assert caught.value.code == "session_authentication_failed"


@pytest.mark.anyio
async def test_invalid_proof_does_not_burn_challenge() -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    tampered = replace(proof, user_session_id="5")
    with pytest.raises(SessionAuthenticationError):
        await authenticateSession(tampered, service=auth_service)
    grant = await authenticateSession(proof, service=auth_service)
    assert grant.user_session_id == USER_SESSION_ID


@pytest.mark.anyio
async def test_concurrent_replay_has_exactly_one_winner() -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    results = await asyncio.gather(
        *(authenticateSession(proof, service=auth_service) for _ in range(8)),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert all(
        not isinstance(result, Exception)
        or (
            isinstance(result, SessionAuthenticationError)
            and result.code == "session_authentication_failed"
        )
        for result in results
    )


@pytest.mark.anyio
async def test_challenge_store_is_bounded_and_purges_expired_records() -> None:
    current = NOW
    store = InMemorySessionChallengeStore(
        clock=lambda: current, max_records=2, max_per_device=2
    )
    auth_service = service(challenges=store)
    await issueSessionChallenge(device().device_id, service=auth_service)
    await issueSessionChallenge(device().device_id, service=auth_service)
    with pytest.raises(SessionAuthenticationError) as full:
        await issueSessionChallenge(device().device_id, service=auth_service)
    assert full.value.code == "device_challenge_unavailable"

    current = NOW + timedelta(seconds=31)
    later = replace(auth_service, clock=lambda: current)
    challenge = await issueSessionChallenge(
        device().device_id, service=later
    )
    assert challenge.issued_at == current


@pytest.mark.anyio
async def test_expired_challenge_is_rejected() -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    expired_service = replace(
        auth_service, clock=lambda: NOW + timedelta(seconds=31)
    )
    with pytest.raises(SessionAuthenticationError) as caught:
        await authenticateSession(proof, service=expired_service)
    assert caught.value.code == "session_authentication_failed"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field,value",
    [
        ("device_id", "dev_" + "0" * 32),
        ("client_nonce", str(uuid4()).upper()),
        ("user_session_id", ""),
        ("contract_minimum", "not-a-version"),
        ("contract_maximum", "1.0.0"),
        ("signature", encode(b"x" * 63)),
        ("signature", encode(b"\0" * 64)),
    ],
)
async def test_malformed_or_tampered_proof_fails_closed(field, value) -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    with pytest.raises(SessionAuthenticationError) as caught:
        await authenticateSession(
            replace(proof, **{field: value}), service=auth_service
        )
    assert caught.value.code == "session_authentication_failed"


@pytest.mark.anyio
async def test_wrong_private_key_is_rejected() -> None:
    auth_service = service()
    wrong_key = ec.generate_private_key(ec.SECP256R1())
    challenge = await issueSessionChallenge(
        device().device_id, service=auth_service
    )
    proof = DeviceSessionProof(
        challenge.challenge_id, challenge.device_id, USER_SESSION_ID,
        str(uuid4()), "1.0.0", "2.0.0", encode(b"x" * 64),
    )
    proof = replace(proof, signature=encode(
        raw_signature(wrong_key, buildSessionProofMessage(challenge, proof))
    ))
    with pytest.raises(SessionAuthenticationError):
        await authenticateSession(proof, service=auth_service)


@pytest.mark.anyio
async def test_swapped_public_identity_is_rejected() -> None:
    wrong_key = ec.generate_private_key(ec.SECP256R1())
    authority = InMemorySessionAuthority((
        device(public_key=encode(public_bytes(wrong_key))),
    ))
    auth_service = service(authority=authority)
    proof, _ = await proof_for(auth_service)
    with pytest.raises(SessionAuthenticationError):
        await authenticateSession(proof, service=auth_service)


@pytest.mark.anyio
async def test_revoked_and_unknown_devices_get_generic_challenge_failure() -> None:
    revoked = InMemorySessionAuthority((
        device(status=DeviceStatus.REVOKED),
    ))
    for authority, device_id in (
        (revoked, device().device_id),
        (InMemorySessionAuthority(), "dev_" + "0" * 32),
    ):
        with pytest.raises(SessionAuthenticationError) as caught:
            await issueSessionChallenge(
                device_id, service=service(authority=authority)
            )
        assert caught.value.code == "device_challenge_unavailable"


@pytest.mark.anyio
async def test_contract_intersection_and_no_overlap() -> None:
    auth_service = service(
        supported=ContractRange.parse("1.5.0", "2.5.0")
    )
    proof, _ = await proof_for(
        auth_service, contract_minimum="1.0.0", contract_maximum="1.7.0"
    )
    grant = await authenticateSession(proof, service=auth_service)
    assert (grant.contract_minimum, grant.contract_maximum) == (
        "1.5.0", "1.7.0"
    )

    another = service(supported=ContractRange.parse("3.0.0", "4.0.0"))
    proof, _ = await proof_for(another)
    with pytest.raises(SessionAuthenticationError):
        await authenticateSession(proof, service=another)


@pytest.mark.anyio
async def test_backend_instance_binding_is_enforced() -> None:
    auth_service = service()
    proof, _ = await proof_for(auth_service)
    other = replace(
        auth_service,
        backend_instance_id="bkd_ffffffffffffffffffffffffffffffff",
    )
    with pytest.raises(SessionAuthenticationError):
        await authenticateSession(proof, service=other)


class FailingChallenges(InMemorySessionChallengeStore):
    async def load(self, challenge_id):
        raise RuntimeError("sensitive storage detail")


@pytest.mark.anyio
async def test_storage_failures_are_sanitized() -> None:
    good_service = service()
    proof, challenge = await proof_for(good_service)
    failing = replace(good_service, challenges=FailingChallenges())
    with pytest.raises(SessionAuthenticationError) as caught:
        await authenticateSession(proof, service=failing)
    assert caught.value.code == "session_authentication_unavailable"
    assert "sensitive storage detail" not in str(caught.value)
    assert challenge.server_nonce not in str(caught.value)


class ConflictingAuthority(InMemorySessionAuthority):
    async def rotate_session(self, **kwargs):
        raise SessionRotationConflictError


@pytest.mark.anyio
async def test_rotation_conflict_is_explicit_and_safe() -> None:
    authority = ConflictingAuthority((device(),))
    auth_service = service(authority=authority)
    proof, _ = await proof_for(auth_service)
    with pytest.raises(SessionAuthenticationError) as caught:
        await authenticateSession(proof, service=auth_service)
    assert caught.value.code == "session_rotation_conflict"


def test_lifetime_and_backend_configuration_bounds() -> None:
    with pytest.raises(ValueError):
        replace(service(), challenge_lifetime=timedelta(seconds=4))
    with pytest.raises(ValueError):
        replace(service(), session_lifetime=timedelta(minutes=11))
    with pytest.raises(ValueError):
        replace(service(), backend_instance_id="backend")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CNG integration")
@pytest.mark.anyio
async def test_live_cng_key_proves_device_without_private_export() -> None:
    installation_id = str(uuid4())
    store = WindowsCngDeviceKeyStore("JarvisOS.SessionProofTest")
    key = store.get_or_create(installation_id)
    try:
        live_device = device()
        live_device = replace(
            live_device,
            device_id=(
                f"dev_{hashlib.sha256(key.public_key).hexdigest()[:32]}"
            ),
            public_key=encode(key.public_key),
        )
        auth_service = service(
            authority=InMemorySessionAuthority((live_device,))
        )
        challenge = await issueSessionChallenge(
            live_device.device_id, service=auth_service
        )
        proof = DeviceSessionProof(
            challenge.challenge_id, live_device.device_id, USER_SESSION_ID,
            str(uuid4()), "1.0.0", "2.0.0", encode(b"x" * 64),
        )
        signature = store.sign(
            key.key_reference,
            buildSessionProofMessage(challenge, proof),
        )
        grant = await authenticateSession(
            replace(proof, signature=encode(signature)),
            service=auth_service,
        )
        assert grant.device_id == live_device.device_id
        assert not hasattr(key, "private_key")
    finally:
        store.delete(key.key_reference)
