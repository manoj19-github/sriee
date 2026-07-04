"""Device-proof session establishment for Global ID 130001."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from jarvis.security.desktop_auth import (
    ContractRange,
    DesktopSessionRecord,
    DesktopSessionToken,
    DeviceStatus,
    SessionStatus,
)
from jarvis.security.device_identity import (
    DEVICE_ID_PATTERN,
    PUBLIC_KEY_ALGORITHM,
    PUBLIC_KEY_FORMAT,
)


CHALLENGE_ID_PATTERN = re.compile(r"^chl_[0-9a-f]{32}$")
BACKEND_ID_PATTERN = re.compile(r"^bkd_[0-9a-f]{32}$")
SESSION_ID_PATTERN = re.compile(r"^ses_[0-9a-f]{32}$")
NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
WINDOWS_SESSION_PATTERN = re.compile(r"^[1-9][0-9]{0,9}$")
CONTRACT_VERSION_PATTERN = re.compile(
    r"^(?:0|[1-9][0-9]{0,9})\."
    r"(?:0|[1-9][0-9]{0,9})\."
    r"(?:0|[1-9][0-9]{0,9})$"
)
PROOF_DOMAIN = "jarvis.session-proof.v1"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SessionAuthenticationError(RuntimeError):
    """A stable, secret-safe session-establishment failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS session authentication failed: {code}")


class SessionRotationConflictError(RuntimeError):
    """The device epoch changed before session rotation committed."""


@dataclass(frozen=True, slots=True)
class SessionDeviceRecord:
    device_id: str
    actor_id: str
    public_key: str
    public_key_algorithm: str
    public_key_format: str
    status: DeviceStatus
    session_epoch: int
    contract_range: ContractRange


@dataclass(frozen=True, slots=True)
class SessionChallenge:
    challenge_id: str
    server_nonce: str
    backend_instance_id: str
    device_id: str
    actor_id: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceSessionProof:
    challenge_id: str
    device_id: str
    user_session_id: str
    client_nonce: str
    contract_minimum: str
    contract_maximum: str
    signature: str


@dataclass(frozen=True, slots=True)
class SessionGrant:
    access_token: str
    token_type: str
    session_id: str
    device_id: str
    actor_id: str
    user_session_id: str
    backend_instance_id: str
    session_epoch: int
    contract_minimum: str
    contract_maximum: str
    issued_at: datetime
    expires_at: datetime
    request_nonce_required: bool = True


class SessionChallengeStore(Protocol):
    async def issue(self, challenge: SessionChallenge) -> None:
        """Persist a unique challenge until it expires or is consumed."""

    async def load(self, challenge_id: str) -> SessionChallenge | None:
        """Load a challenge without consuming it."""

    async def consume(
        self, challenge_id: str, server_nonce: str
    ) -> bool:
        """Atomically consume the exact challenge once."""


class SessionAuthority(Protocol):
    async def get_device(
        self, device_id: str
    ) -> SessionDeviceRecord | None:
        """Return current public identity and rotation epoch."""

    async def rotate_session(
        self,
        *,
        device_id: str,
        actor_id: str,
        expected_epoch: int,
        user_session_id: str,
        backend_instance_id: str,
        contract_range: ContractRange,
        issued_at: datetime,
        expires_at: datetime,
    ) -> DesktopSessionRecord:
        """Atomically revoke the prior session and advance the device epoch."""


class InMemorySessionChallengeStore:
    """Atomic challenge store for tests and single-process development."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
        max_records: int = 1024,
        max_per_device: int = 4,
    ) -> None:
        if max_records < 1 or max_per_device < 1:
            raise ValueError("challenge limits must be positive")
        if max_per_device > max_records:
            raise ValueError("per-device limit cannot exceed global limit")
        self._records: dict[str, SessionChallenge] = {}
        self._lock = asyncio.Lock()
        self._clock = clock
        self._max_records = max_records
        self._max_per_device = max_per_device

    async def issue(self, challenge: SessionChallenge) -> None:
        async with self._lock:
            now = self._clock()
            self._records = {
                challenge_id: record
                for challenge_id, record in self._records.items()
                if record.expires_at > now
            }
            if challenge.challenge_id in self._records:
                raise ValueError("challenge collision")
            if len(self._records) >= self._max_records:
                raise ValueError("challenge capacity reached")
            if sum(
                record.device_id == challenge.device_id
                for record in self._records.values()
            ) >= self._max_per_device:
                raise ValueError("device challenge capacity reached")
            self._records[challenge.challenge_id] = challenge

    async def load(self, challenge_id: str) -> SessionChallenge | None:
        async with self._lock:
            return self._records.get(challenge_id)

    async def consume(
        self, challenge_id: str, server_nonce: str
    ) -> bool:
        async with self._lock:
            challenge = self._records.get(challenge_id)
            if challenge is None or not hmac.compare_digest(
                challenge.server_nonce, server_nonce
            ):
                return False
            del self._records[challenge_id]
            return True


class InMemorySessionAuthority:
    """Atomic rotating authority compatible with desktop request auth."""

    def __init__(
        self, devices: tuple[SessionDeviceRecord, ...] = ()
    ) -> None:
        self._devices = {device.device_id: device for device in devices}
        self._sessions: dict[str, DesktopSessionRecord] = {}
        self._active_session_by_device: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_device(
        self, device_id: str
    ) -> SessionDeviceRecord | None:
        return self._devices.get(device_id)

    async def get_session(
        self, session_id: str
    ) -> DesktopSessionRecord | None:
        return self._sessions.get(session_id)

    async def rotate_session(
        self,
        *,
        device_id: str,
        actor_id: str,
        expected_epoch: int,
        user_session_id: str,
        backend_instance_id: str,
        contract_range: ContractRange,
        issued_at: datetime,
        expires_at: datetime,
    ) -> DesktopSessionRecord:
        async with self._lock:
            self._sessions = {
                session_id: record
                for session_id, record in self._sessions.items()
                if (
                    record.status is SessionStatus.ACTIVE
                    or record.expires_at > issued_at
                )
            }
            device = self._devices.get(device_id)
            if (
                device is None
                or device.status is not DeviceStatus.ACTIVE
                or not hmac.compare_digest(device.actor_id, actor_id)
                or device.session_epoch != expected_epoch
            ):
                raise SessionRotationConflictError

            prior_id = self._active_session_by_device.get(device_id)
            if prior_id is not None:
                prior = self._sessions[prior_id]
                self._sessions[prior_id] = replace(
                    prior, status=SessionStatus.REVOKED
                )

            next_epoch = expected_epoch + 1
            self._devices[device_id] = replace(
                device, session_epoch=next_epoch
            )
            session = DesktopSessionRecord(
                session_id=f"ses_{uuid4().hex}",
                device_id=device_id,
                actor_id=actor_id,
                status=SessionStatus.ACTIVE,
                session_epoch=next_epoch,
                expires_at=expires_at,
                contract_range=contract_range,
                user_session_id=user_session_id,
                backend_instance_id=backend_instance_id,
            )
            self._sessions[session.session_id] = session
            self._active_session_by_device[device_id] = session.session_id
            return session


@dataclass(frozen=True, slots=True)
class SessionAuthenticationService:
    authority: SessionAuthority
    challenges: SessionChallengeStore
    tokens: DesktopSessionToken
    supported_contracts: ContractRange
    backend_instance_id: str
    clock: Callable[[], datetime] = _utc_now
    random_bytes: Callable[[int], bytes] = secrets.token_bytes
    challenge_lifetime: timedelta = timedelta(seconds=30)
    session_lifetime: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if not BACKEND_ID_PATTERN.fullmatch(self.backend_instance_id):
            raise ValueError("invalid backend instance identity")
        if not timedelta(seconds=5) <= self.challenge_lifetime <= timedelta(
            minutes=2
        ):
            raise ValueError("challenge lifetime out of bounds")
        if not timedelta(seconds=30) <= self.session_lifetime <= timedelta(
            minutes=10
        ):
            raise ValueError("session lifetime out of bounds")


async def issueSessionChallenge(
    device_id: str,
    *,
    service: SessionAuthenticationService,
) -> SessionChallenge:
    """Issue a short-lived challenge bound to a registered active device."""

    if not isinstance(device_id, str) or not DEVICE_ID_PATTERN.fullmatch(
        device_id
    ):
        raise SessionAuthenticationError("device_challenge_unavailable")
    try:
        device = await service.authority.get_device(device_id)
        now = service.clock()
        if now.tzinfo is None:
            raise ValueError("clock must be timezone-aware")
        if device is None or device.status is not DeviceStatus.ACTIVE:
            raise ValueError("inactive device")
        challenge = SessionChallenge(
            challenge_id=f"chl_{uuid4().hex}",
            server_nonce=_encode_bytes(service.random_bytes(32)),
            backend_instance_id=service.backend_instance_id,
            device_id=device.device_id,
            actor_id=device.actor_id,
            issued_at=now,
            expires_at=now + service.challenge_lifetime,
        )
        _validate_challenge(challenge)
        await service.challenges.issue(challenge)
        return challenge
    except SessionAuthenticationError:
        raise
    except Exception:
        raise SessionAuthenticationError(
            "device_challenge_unavailable"
        ) from None


async def authenticateSession(
    proof: DeviceSessionProof,
    *,
    service: SessionAuthenticationService,
) -> SessionGrant:
    """Verify a device proof, consume its challenge and rotate the session."""

    try:
        _validate_proof_shape(proof)
        challenge = await service.challenges.load(proof.challenge_id)
        now = service.clock()
        if now.tzinfo is None:
            raise ValueError("clock must be timezone-aware")
        if challenge is None:
            raise ValueError("unknown challenge")
        _validate_challenge(challenge)
        if not challenge.issued_at <= now < challenge.expires_at:
            raise ValueError("expired challenge")
        if (
            not hmac.compare_digest(challenge.device_id, proof.device_id)
            or not hmac.compare_digest(
                challenge.backend_instance_id,
                service.backend_instance_id,
            )
        ):
            raise ValueError("challenge binding mismatch")

        device = await service.authority.get_device(proof.device_id)
        if device is None or device.status is not DeviceStatus.ACTIVE:
            raise ValueError("inactive device")
        if not hmac.compare_digest(device.actor_id, challenge.actor_id):
            raise ValueError("actor binding mismatch")
        if (
            device.public_key_algorithm != PUBLIC_KEY_ALGORITHM
            or device.public_key_format != PUBLIC_KEY_FORMAT
        ):
            raise ValueError("unsupported device key")
        public_key_bytes = _decode_bytes(
            device.public_key, expected_size=65
        )
        expected_device_id = (
            f"dev_{hashlib.sha256(public_key_bytes).hexdigest()[:32]}"
        )
        if not hmac.compare_digest(expected_device_id, device.device_id):
            raise ValueError("public identity mismatch")

        requested = ContractRange.parse(
            proof.contract_minimum, proof.contract_maximum
        )
        negotiated = service.supported_contracts.intersect(
            device.contract_range, requested
        )
        message = buildSessionProofMessage(challenge, proof)
        _verify_device_signature(
            device.public_key, proof.signature, message
        )
        if not await service.challenges.consume(
            challenge.challenge_id, challenge.server_nonce
        ):
            raise ValueError("challenge replay")

        expires_at = now + service.session_lifetime
        session = await service.authority.rotate_session(
            device_id=device.device_id,
            actor_id=device.actor_id,
            expected_epoch=device.session_epoch,
            user_session_id=proof.user_session_id,
            backend_instance_id=service.backend_instance_id,
            contract_range=negotiated,
            issued_at=now,
            expires_at=expires_at,
        )
        _validate_rotated_session(
            session,
            device=device,
            proof=proof,
            service=service,
            contract_range=negotiated,
            expires_at=expires_at,
        )
        access_token = service.tokens.issue(
            actor_id=device.actor_id,
            device_id=device.device_id,
            session_id=session.session_id,
            session_epoch=session.session_epoch,
            contract_range=negotiated,
            issued_at=now,
            lifetime=service.session_lifetime,
            user_session_id=proof.user_session_id,
            backend_instance_id=service.backend_instance_id,
        )
        return SessionGrant(
            access_token=access_token,
            token_type="Bearer",
            session_id=session.session_id,
            device_id=device.device_id,
            actor_id=device.actor_id,
            user_session_id=proof.user_session_id,
            backend_instance_id=service.backend_instance_id,
            session_epoch=session.session_epoch,
            contract_minimum=str(negotiated.minimum),
            contract_maximum=str(negotiated.maximum),
            issued_at=now,
            expires_at=expires_at,
        )
    except SessionRotationConflictError:
        raise SessionAuthenticationError(
            "session_rotation_conflict"
        ) from None
    except (InvalidSignature, TypeError, ValueError, KeyError):
        raise SessionAuthenticationError(
            "session_authentication_failed"
        ) from None
    except SessionAuthenticationError:
        raise
    except Exception:
        raise SessionAuthenticationError(
            "session_authentication_unavailable"
        ) from None


def buildSessionProofMessage(
    challenge: SessionChallenge,
    proof: DeviceSessionProof,
) -> bytes:
    """Return the canonical proof transcript signed by the desktop key."""

    payload = {
        "actor_id": challenge.actor_id,
        "backend_instance_id": challenge.backend_instance_id,
        "challenge_id": challenge.challenge_id,
        "client_nonce": proof.client_nonce,
        "contract_maximum": proof.contract_maximum,
        "contract_minimum": proof.contract_minimum,
        "device_id": proof.device_id,
        "domain": PROOF_DOMAIN,
        "server_nonce": challenge.server_nonce,
        "user_session_id": proof.user_session_id,
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _validate_challenge(challenge: SessionChallenge) -> None:
    if (
        not CHALLENGE_ID_PATTERN.fullmatch(challenge.challenge_id)
        or not NONCE_PATTERN.fullmatch(challenge.server_nonce)
        or not BACKEND_ID_PATTERN.fullmatch(challenge.backend_instance_id)
        or not DEVICE_ID_PATTERN.fullmatch(challenge.device_id)
        or not challenge.actor_id
        or challenge.issued_at.tzinfo is None
        or challenge.expires_at.tzinfo is None
        or challenge.expires_at <= challenge.issued_at
    ):
        raise ValueError("invalid challenge")
    if len(_decode_bytes(challenge.server_nonce, expected_size=32)) != 32:
        raise ValueError("invalid challenge nonce")


def _validate_proof_shape(proof: DeviceSessionProof) -> None:
    if (
        not CHALLENGE_ID_PATTERN.fullmatch(proof.challenge_id)
        or not DEVICE_ID_PATTERN.fullmatch(proof.device_id)
        or not WINDOWS_SESSION_PATTERN.fullmatch(proof.user_session_id)
        or not CONTRACT_VERSION_PATTERN.fullmatch(
            proof.contract_minimum
        )
        or not CONTRACT_VERSION_PATTERN.fullmatch(
            proof.contract_maximum
        )
    ):
        raise ValueError("invalid proof")
    nonce = UUID(proof.client_nonce)
    if nonce.version != 4 or str(nonce) != proof.client_nonce:
        raise ValueError("invalid client nonce")
    _decode_bytes(proof.signature, expected_size=64)


def _validate_rotated_session(
    session: DesktopSessionRecord,
    *,
    device: SessionDeviceRecord,
    proof: DeviceSessionProof,
    service: SessionAuthenticationService,
    contract_range: ContractRange,
    expires_at: datetime,
) -> None:
    if (
        not SESSION_ID_PATTERN.fullmatch(session.session_id)
        or session.status is not SessionStatus.ACTIVE
        or not hmac.compare_digest(session.device_id, device.device_id)
        or not hmac.compare_digest(session.actor_id, device.actor_id)
        or session.session_epoch != device.session_epoch + 1
        or session.expires_at != expires_at
        or session.contract_range != contract_range
        or not hmac.compare_digest(
            session.user_session_id, proof.user_session_id
        )
        or not hmac.compare_digest(
            session.backend_instance_id, service.backend_instance_id
        )
    ):
        raise ValueError("invalid rotated session")


def _verify_device_signature(
    encoded_public_key: str,
    encoded_signature: str,
    message: bytes,
) -> None:
    public_bytes = _decode_bytes(encoded_public_key, expected_size=65)
    if public_bytes[0] != 4:
        raise ValueError("invalid public key")
    public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), public_bytes
    )
    raw_signature = _decode_bytes(encoded_signature, expected_size=64)
    r = int.from_bytes(raw_signature[:32], "big")
    s = int.from_bytes(raw_signature[32:], "big")
    if r == 0 or s == 0:
        raise ValueError("invalid signature")
    der_signature = utils.encode_dss_signature(r, s)
    digest = hashlib.sha256(message).digest()
    public_key.verify(
        der_signature,
        digest,
        ec.ECDSA(utils.Prehashed(hashes.SHA256())),
    )


def encodeSessionProofSignature(signature: bytes) -> str:
    """Encode the fixed-width raw P-256 signature returned by Windows CNG."""

    if not isinstance(signature, bytes) or len(signature) != 64:
        raise ValueError("P-256 signature must be 64 bytes")
    return _encode_bytes(signature)


def _encode_bytes(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise TypeError("value must be bytes")
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_bytes(value: str, *, expected_size: int) -> bytes:
    if not isinstance(value, str):
        raise TypeError("encoded value must be text")
    expected_encoded_size = (expected_size * 8 + 5) // 6
    if len(value) != expected_encoded_size:
        raise ValueError("invalid encoded value")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(
            value + padding, altchars=b"-_", validate=True
        )
    except (ValueError, TypeError):
        raise ValueError("invalid base64url value") from None
    if len(decoded) != expected_size or _encode_bytes(decoded) != value:
        raise ValueError("invalid encoded value")
    return decoded
