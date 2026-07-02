"""Desktop session authentication for Global ID 110002."""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Protocol
from uuid import UUID, uuid4

import jwt
from fastapi import Header, HTTPException, Request, status
from jwt import PyJWTError
from packaging.version import InvalidVersion, Version

from jarvis.config.settings import Settings


TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "jarvis-desktop-auth"
TOKEN_AUDIENCE = "jarvis-api"
TOKEN_TYPE = "desktop_session"
REQUIRED_CLAIMS = (
    "exp",
    "iat",
    "nbf",
    "iss",
    "aud",
    "sub",
    "jti",
    "device_id",
    "session_id",
    "session_epoch",
    "contract_min",
    "contract_max",
    "token_type",
)


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ContractRange:
    """Inclusive semantic-version range."""

    minimum: Version
    maximum: Version

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise ValueError("contract minimum cannot exceed maximum")

    @classmethod
    def parse(cls, minimum: str, maximum: str) -> ContractRange:
        try:
            return cls(Version(minimum), Version(maximum))
        except InvalidVersion as error:
            raise ValueError("invalid contract version") from error

    def contains(self, version: Version) -> bool:
        return self.minimum <= version <= self.maximum

    def intersect(self, *others: ContractRange) -> ContractRange:
        minimum = max(self.minimum, *(other.minimum for other in others))
        maximum = min(self.maximum, *(other.maximum for other in others))
        return ContractRange(minimum, maximum)


@dataclass(frozen=True, slots=True)
class DeviceRecord:
    device_id: str
    actor_id: str
    status: DeviceStatus
    session_epoch: int
    contract_range: ContractRange


@dataclass(frozen=True, slots=True)
class DesktopSessionRecord:
    session_id: str
    device_id: str
    actor_id: str
    status: SessionStatus
    session_epoch: int
    expires_at: datetime
    contract_range: ContractRange


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Immutable identity attached to a validated request."""

    actor_id: str
    device_id: str
    session_id: str
    token_id: str
    contract_version: Version
    contract_range: ContractRange
    issued_at: datetime
    expires_at: datetime
    authentication_method: str = "desktop_session_jwt"


class DeviceRegistry(Protocol):
    async def get_device(self, device_id: str) -> DeviceRecord | None:
        """Return the current device record."""


class SessionRegistry(Protocol):
    async def get_session(self, session_id: str) -> DesktopSessionRecord | None:
        """Return the current session record."""


class RequestNonceStore(Protocol):
    async def consume(
        self,
        session_id: str,
        nonce: str,
        expires_at: datetime,
    ) -> bool:
        """Atomically consume a request nonce; return false for a replay."""


class InMemoryDeviceRegistry:
    """Development/test registry with the same async contract as persistence."""

    def __init__(self, records: list[DeviceRecord] | None = None) -> None:
        self._records = {record.device_id: record for record in records or []}

    async def get_device(self, device_id: str) -> DeviceRecord | None:
        return self._records.get(device_id)


class InMemorySessionRegistry:
    """Development/test session registry."""

    def __init__(self, records: list[DesktopSessionRecord] | None = None) -> None:
        self._records = {record.session_id: record for record in records or []}

    async def get_session(self, session_id: str) -> DesktopSessionRecord | None:
        return self._records.get(session_id)


class InMemoryNonceStore:
    """Atomic in-process nonce store; production replaces this with durable TTL state."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._seen: dict[tuple[str, str], datetime] = {}
        self._lock = asyncio.Lock()

    async def consume(
        self,
        session_id: str,
        nonce: str,
        expires_at: datetime,
    ) -> bool:
        async with self._lock:
            now = self._clock()
            self._seen = {
                key: expiry
                for key, expiry in self._seen.items()
                if expiry > now
            }
            key = (session_id, nonce)
            if key in self._seen:
                return False
            self._seen[key] = expires_at
            return True


class DesktopSessionToken:
    """Issue and decode strictly constrained desktop session JWTs."""

    def __init__(
        self,
        secret: str,
        *,
        issuer: str = TOKEN_ISSUER,
        audience: str = TOKEN_AUDIENCE,
        leeway_seconds: int = 5,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("desktop token secret must contain at least 32 characters")
        if leeway_seconds < 0:
            raise ValueError("token leeway cannot be negative")
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._leeway_seconds = leeway_seconds

    def issue(
        self,
        *,
        actor_id: str,
        device_id: str,
        session_id: str,
        session_epoch: int,
        contract_range: ContractRange,
        issued_at: datetime | None = None,
        lifetime: timedelta = timedelta(minutes=5),
    ) -> str:
        now = issued_at or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("token issue time must be timezone-aware")
        if lifetime <= timedelta(0):
            raise ValueError("token lifetime must be greater than zero")
        if not all(value.strip() for value in (actor_id, device_id, session_id)):
            raise ValueError("token identity fields cannot be empty")
        payload = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": actor_id,
            "jti": str(uuid4()),
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
            "device_id": device_id,
            "session_id": session_id,
            "session_epoch": session_epoch,
            "contract_min": str(contract_range.minimum),
            "contract_max": str(contract_range.maximum),
            "token_type": TOKEN_TYPE,
        }
        return jwt.encode(payload, self._secret, algorithm=TOKEN_ALGORITHM)

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._secret,
            algorithms=[TOKEN_ALGORITHM],
            audience=self._audience,
            issuer=self._issuer,
            leeway=self._leeway_seconds,
            options={"require": list(REQUIRED_CLAIMS)},
        )


class DesktopSessionAuthenticator:
    """Validate token, registries, contract compatibility, and request nonce."""

    def __init__(
        self,
        *,
        settings: Settings,
        devices: DeviceRegistry,
        sessions: SessionRegistry,
        nonces: RequestNonceStore,
        supported_contracts: ContractRange,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._tokens = DesktopSessionToken(
            settings.jwt_access_secret.get_secret_value()
        )
        self._devices = devices
        self._sessions = sessions
        self._nonces = nonces
        self._supported_contracts = supported_contracts
        self._clock = clock or (lambda: datetime.now(UTC))

    async def authenticate(
        self,
        *,
        authorization: str | None,
        device_id: str | None,
        contract_version: str | None,
        request_nonce: str | None,
    ) -> AuthenticatedPrincipal:
        try:
            token = self._extract_bearer(authorization)
            header_device_id = self._required_text(device_id)
            selected_contract = Version(self._required_text(contract_version))
            nonce = self._parse_nonce(request_nonce)
            claims = self._tokens.decode(token)

            if claims["token_type"] != TOKEN_TYPE:
                raise ValueError("invalid token type")
            if not hmac.compare_digest(str(claims["device_id"]), header_device_id):
                raise ValueError("device mismatch")

            token_range = ContractRange.parse(
                str(claims["contract_min"]),
                str(claims["contract_max"]),
            )
            device = await self._devices.get_device(header_device_id)
            session = await self._sessions.get_session(str(claims["session_id"]))
            self._validate_records(claims, device, session)

            assert device is not None
            assert session is not None
            try:
                effective_range = self._supported_contracts.intersect(
                    token_range,
                    device.contract_range,
                    session.contract_range,
                )
            except ValueError:
                raise _ContractMismatch from None
            if not effective_range.contains(selected_contract):
                raise _ContractMismatch

            expires_at = datetime.fromtimestamp(int(claims["exp"]), UTC)
            issued_at = datetime.fromtimestamp(int(claims["iat"]), UTC)
            if session.expires_at <= self._clock():
                raise ValueError("session expired")
            if not await self._nonces.consume(
                session.session_id,
                nonce,
                expires_at,
            ):
                raise ValueError("request replay")

            return AuthenticatedPrincipal(
                actor_id=str(claims["sub"]),
                device_id=header_device_id,
                session_id=session.session_id,
                token_id=str(claims["jti"]),
                contract_version=selected_contract,
                contract_range=effective_range,
                issued_at=issued_at,
                expires_at=expires_at,
            )
        except _ContractMismatch:
            raise HTTPException(
                status_code=status.HTTP_426_UPGRADE_REQUIRED,
                detail={"code": "contract_version_unsupported"},
            ) from None
        except (PyJWTError, InvalidVersion, TypeError, ValueError, KeyError):
            raise self._unauthorized() from None

    @staticmethod
    def _extract_bearer(authorization: str | None) -> str:
        if authorization is None:
            raise ValueError("missing authorization")
        scheme, separator, token = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not token
            or " " in token
        ):
            raise ValueError("invalid authorization")
        return token

    @staticmethod
    def _required_text(value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("missing header")
        return value.strip()

    @staticmethod
    def _parse_nonce(value: str | None) -> str:
        nonce = DesktopSessionAuthenticator._required_text(value)
        parsed = UUID(nonce)
        if str(parsed) != nonce.lower():
            raise ValueError("non-canonical nonce")
        return str(parsed)

    @staticmethod
    def _validate_records(
        claims: dict[str, Any],
        device: DeviceRecord | None,
        session: DesktopSessionRecord | None,
    ) -> None:
        if device is None or session is None:
            raise ValueError("unknown identity")
        if device.status is not DeviceStatus.ACTIVE:
            raise ValueError("inactive device")
        if session.status is not SessionStatus.ACTIVE:
            raise ValueError("inactive session")

        actor_id = str(claims["sub"])
        device_id = str(claims["device_id"])
        session_epoch = int(claims["session_epoch"])
        if not (
            hmac.compare_digest(device.actor_id, actor_id)
            and hmac.compare_digest(session.actor_id, actor_id)
            and hmac.compare_digest(session.device_id, device_id)
            and session.session_id == str(claims["session_id"])
            and device.session_epoch == session_epoch
            and session.session_epoch == session_epoch
        ):
            raise ValueError("registry mismatch")

    @staticmethod
    def _unauthorized() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_desktop_session"},
            headers={"WWW-Authenticate": "Bearer"},
        )


class _ContractMismatch(Exception):
    pass


async def authenticate_desktop_session(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: Annotated[str | None, Header()] = None,
    x_request_nonce: Annotated[str | None, Header()] = None,
) -> AuthenticatedPrincipal:
    """FastAPI dependency that binds a validated principal to request state."""

    authenticator = getattr(request.app.state, "desktop_authenticator", None)
    if not isinstance(authenticator, DesktopSessionAuthenticator):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "desktop_authentication_unavailable"},
        )
    principal = await authenticator.authenticate(
        authorization=authorization,
        device_id=x_device_id,
        contract_version=x_contract_version,
        request_nonce=x_request_nonce,
    )
    request.state.principal = principal
    return principal


async def authenticateDesktopSession(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_device_id: Annotated[str | None, Header()] = None,
    x_contract_version: Annotated[str | None, Header()] = None,
    x_request_nonce: Annotated[str | None, Header()] = None,
) -> AuthenticatedPrincipal:
    """Canonical function-map entry point for Global ID 110002."""

    return await authenticate_desktop_session(
        request=request,
        authorization=authorization,
        x_device_id=x_device_id,
        x_contract_version=x_contract_version,
        x_request_nonce=x_request_nonce,
    )
