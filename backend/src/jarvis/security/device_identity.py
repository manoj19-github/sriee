"""Per-install device identity registration for Global ID 130000."""

from __future__ import annotations

import asyncio
import base64
import ctypes
import hashlib
import re
import struct
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


DEVICE_ID_PATTERN = re.compile(r"^dev_[0-9a-f]{32}$")
WINDOWS_SID_PATTERN = re.compile(r"^S-1-(?:\d+-){1,14}\d+$")
PUBLIC_KEY_ALGORITHM = "ECDSA_P256_SHA256"
PUBLIC_KEY_FORMAT = "SEC1_UNCOMPRESSED"


class DeviceRegistrationError(RuntimeError):
    """A sanitized, stable registration failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"JARVIS device registration failed: {code}")


class DeviceIdentityConflictError(RuntimeError):
    """The install or device identity is already bound differently."""


class KeyProtection(StrEnum):
    WINDOWS_CNG_USER_NON_EXPORTABLE = "windows_cng_user_non_exportable"
    TEST_ONLY = "test_only"


@dataclass(frozen=True, slots=True)
class InteractiveUser:
    actor_id: str
    session_id: str
    interactive: bool


@dataclass(frozen=True, slots=True)
class DeviceKey:
    key_reference: str
    public_key: bytes
    protection: KeyProtection
    created: bool


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_id: str
    installation_id: str
    actor_id: str
    registration_session_id: str
    public_key: str
    public_key_algorithm: str
    public_key_format: str
    key_reference: str
    key_protection: KeyProtection
    registered_at: datetime
    created: bool = True

    def __post_init__(self) -> None:
        if not DEVICE_ID_PATTERN.fullmatch(self.device_id):
            raise ValueError("invalid device identity")
        UUID(self.installation_id)
        if not self.actor_id or not self.registration_session_id:
            raise ValueError("identity binding cannot be empty")
        if self.registered_at.tzinfo is None:
            raise ValueError("registration time must be timezone-aware")
        if self.public_key_algorithm != PUBLIC_KEY_ALGORITHM:
            raise ValueError("unsupported public-key algorithm")
        if self.public_key_format != PUBLIC_KEY_FORMAT:
            raise ValueError("unsupported public-key format")
        public_key = _decode_public_key(self.public_key)
        if _derive_device_id(public_key) != self.device_id:
            raise ValueError("device identity does not match public key")

    def public_record(self) -> dict[str, str]:
        """Return the database-safe public registration fields."""

        return {
            "device_id": self.device_id,
            "installation_id": self.installation_id,
            "actor_id": self.actor_id,
            "public_key": self.public_key,
            "public_key_algorithm": self.public_key_algorithm,
            "public_key_format": self.public_key_format,
            "key_protection": self.key_protection.value,
            "registered_at": self.registered_at.isoformat(),
        }


class UserSessionResolver(Protocol):
    def current_user(self) -> InteractiveUser:
        """Resolve the trusted current OS user and session."""


class DeviceKeyStore(Protocol):
    def get_or_create(self, installation_id: str) -> DeviceKey:
        """Return a per-user installation key, creating it if absent."""

    def delete(self, key_reference: str) -> None:
        """Delete newly created key material after a failed registration."""

    def read_public_key(self, key_reference: str) -> bytes:
        """Read public material without exposing the private key."""


class DeviceIdentityRegistry(Protocol):
    async def get_by_installation(
        self, installation_id: str
    ) -> DeviceIdentity | None:
        """Return the registered identity for an installation."""

    async def register_or_get(
        self, identity: DeviceIdentity
    ) -> DeviceIdentity:
        """Atomically store an identity or return the existing record."""


class InMemoryDeviceIdentityRegistry:
    """Atomic in-process registry used by tests and local development."""

    def __init__(self, records: tuple[DeviceIdentity, ...] = ()) -> None:
        self._by_installation = {
            record.installation_id: record for record in records
        }
        self._by_device = {record.device_id: record for record in records}
        self._lock = asyncio.Lock()

    async def get_by_installation(
        self, installation_id: str
    ) -> DeviceIdentity | None:
        return self._by_installation.get(installation_id)

    async def register_or_get(
        self, identity: DeviceIdentity
    ) -> DeviceIdentity:
        async with self._lock:
            existing = self._by_installation.get(identity.installation_id)
            if existing is not None:
                return replace(existing, created=False)
            device_owner = self._by_device.get(identity.device_id)
            if device_owner is not None:
                raise DeviceIdentityConflictError
            self._by_installation[identity.installation_id] = identity
            self._by_device[identity.device_id] = identity
            return identity


@dataclass(frozen=True, slots=True)
class DeviceRegistrationService:
    users: UserSessionResolver
    keys: DeviceKeyStore
    registry: DeviceIdentityRegistry
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)


async def registerDeviceIdentity(
    installation_id: str,
    *,
    explicit_setup: bool,
    service: DeviceRegistrationService,
) -> DeviceIdentity:
    """Create and bind one non-exportable identity after explicit setup."""

    canonical_installation_id = _canonical_installation_id(installation_id)
    if explicit_setup is not True:
        raise DeviceRegistrationError("explicit_setup_required")

    try:
        user = service.users.current_user()
    except Exception:
        raise DeviceRegistrationError("interactive_user_unavailable") from None
    if not user.interactive or not user.actor_id or not user.session_id:
        raise DeviceRegistrationError("interactive_user_required")

    try:
        existing = await service.registry.get_by_installation(
            canonical_installation_id
        )
    except Exception:
        raise DeviceRegistrationError("device_registry_unavailable") from None
    if existing is not None:
        _validate_existing(existing, user, service.keys)
        return replace(existing, created=False)

    key: DeviceKey | None = None
    try:
        key = service.keys.get_or_create(canonical_installation_id)
        public_key = _validate_public_key(key.public_key)
        registered_at = service.clock()
        if registered_at.tzinfo is None:
            raise ValueError("clock must return an aware time")
        candidate = DeviceIdentity(
            device_id=_derive_device_id(public_key),
            installation_id=canonical_installation_id,
            actor_id=user.actor_id,
            registration_session_id=user.session_id,
            public_key=_encode_public_key(public_key),
            public_key_algorithm=PUBLIC_KEY_ALGORITHM,
            public_key_format=PUBLIC_KEY_FORMAT,
            key_reference=key.key_reference,
            key_protection=key.protection,
            registered_at=registered_at,
        )
        stored = await service.registry.register_or_get(candidate)
        if (
            stored.actor_id != user.actor_id
            or stored.device_id != candidate.device_id
            or stored.public_key != candidate.public_key
            or stored.key_reference != candidate.key_reference
        ):
            raise DeviceIdentityConflictError
        return stored
    except DeviceIdentityConflictError:
        if key is not None and key.created:
            _delete_quietly(service.keys, key.key_reference)
        raise DeviceRegistrationError("device_identity_conflict") from None
    except DeviceRegistrationError:
        raise
    except Exception:
        if key is not None and key.created:
            _delete_quietly(service.keys, key.key_reference)
        raise DeviceRegistrationError("device_registration_failed") from None


def _validate_existing(
    identity: DeviceIdentity,
    user: InteractiveUser,
    keys: DeviceKeyStore,
) -> None:
    if identity.actor_id != user.actor_id:
        raise DeviceRegistrationError("device_identity_conflict")
    try:
        public_key = _validate_public_key(
            keys.read_public_key(identity.key_reference)
        )
    except Exception:
        raise DeviceRegistrationError("device_key_unavailable") from None
    if (
        _encode_public_key(public_key) != identity.public_key
        or _derive_device_id(public_key) != identity.device_id
    ):
        raise DeviceRegistrationError("device_key_mismatch")


def _canonical_installation_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise DeviceRegistrationError("installation_id_invalid") from None
    if parsed.version != 4 or str(parsed) != value:
        raise DeviceRegistrationError("installation_id_invalid")
    return str(parsed)


def _validate_public_key(public_key: bytes) -> bytes:
    if (
        not isinstance(public_key, bytes)
        or len(public_key) != 65
        or public_key[0] != 4
    ):
        raise ValueError("invalid P-256 public key")
    return public_key


def _derive_device_id(public_key: bytes) -> str:
    return f"dev_{hashlib.sha256(public_key).hexdigest()[:32]}"


def _encode_public_key(public_key: bytes) -> str:
    return base64.urlsafe_b64encode(public_key).rstrip(b"=").decode("ascii")


def _decode_public_key(value: str) -> bytes:
    try:
        padding = "=" * (-len(value) % 4)
        return _validate_public_key(
            base64.b64decode(
                value + padding,
                altchars=b"-_",
                validate=True,
            )
        )
    except (TypeError, ValueError):
        raise ValueError("invalid encoded public key") from None


def _delete_quietly(keys: DeviceKeyStore, key_reference: str) -> None:
    try:
        keys.delete(key_reference)
    except Exception:
        pass


if sys.platform == "win32":
    from ctypes import wintypes

    _ncrypt = ctypes.WinDLL("ncrypt")
    _advapi32 = ctypes.WinDLL("advapi32")
    _kernel32 = ctypes.WinDLL("kernel32")

    _ncrypt.NCryptOpenStorageProvider.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.LPCWSTR,
        wintypes.DWORD,
    ]
    _ncrypt.NCryptOpenKey.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _ncrypt.NCryptCreatePersistedKey.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _ncrypt.NCryptSetProperty.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _ncrypt.NCryptGetProperty.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    _ncrypt.NCryptFinalizeKey.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    _ncrypt.NCryptExportKey.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
    ]
    _ncrypt.NCryptDeleteKey.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    _ncrypt.NCryptFreeObject.argtypes = [ctypes.c_void_p]
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.GetCurrentProcessId.restype = wintypes.DWORD
    _kernel32.ProcessIdToSessionId.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    _kernel32.LocalFree.restype = wintypes.HLOCAL
    _advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    _advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]


class WindowsCngDeviceKeyStore:
    """Current-user CNG store with persisted private-key export disabled."""

    _provider_name = "Microsoft Software Key Storage Provider"
    _algorithm = "ECDSA_P256"
    _public_blob_type = "ECCPUBLICBLOB"
    _export_policy = "Export Policy"
    _silent_flag = 0x00000040
    _not_found = {0x80090011, 0x80090016}

    def __init__(self, namespace: str = "JarvisOS.Device") -> None:
        if sys.platform != "win32":
            raise OSError("Windows CNG is unavailable on this platform")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9.]{2,63}", namespace):
            raise ValueError("invalid CNG key namespace")
        self._namespace = namespace

    def get_or_create(self, installation_id: str) -> DeviceKey:
        key_reference = f"{self._namespace}.{UUID(installation_id).hex}"
        provider = self._open_provider()
        key = ctypes.c_void_p()
        created = False
        try:
            status = _ncrypt.NCryptOpenKey(
                provider,
                ctypes.byref(key),
                key_reference,
                0,
                self._silent_flag,
            )
            if status != 0 and self._unsigned(status) not in self._not_found:
                self._check(status)
            if status != 0:
                self._check(
                    _ncrypt.NCryptCreatePersistedKey(
                        provider,
                        ctypes.byref(key),
                        self._algorithm,
                        key_reference,
                        0,
                        self._silent_flag,
                    )
                )
                created = True
                export_policy = wintypes.DWORD(0)
                self._check(
                    _ncrypt.NCryptSetProperty(
                        key,
                        self._export_policy,
                        ctypes.byref(export_policy),
                        ctypes.sizeof(export_policy),
                        self._silent_flag,
                    )
                )
                self._check(_ncrypt.NCryptFinalizeKey(key, self._silent_flag))
            if self._read_export_policy(key) != 0:
                raise OSError("CNG private-key export policy is not disabled")
            return DeviceKey(
                key_reference=key_reference,
                public_key=self._export_public(key),
                protection=KeyProtection.WINDOWS_CNG_USER_NON_EXPORTABLE,
                created=created,
            )
        except Exception:
            if created and key.value:
                _ncrypt.NCryptDeleteKey(key, self._silent_flag)
                key = ctypes.c_void_p()
            raise
        finally:
            if key.value:
                _ncrypt.NCryptFreeObject(key)
            _ncrypt.NCryptFreeObject(provider)

    def read_public_key(self, key_reference: str) -> bytes:
        provider = self._open_provider()
        key = ctypes.c_void_p()
        try:
            self._check(
                _ncrypt.NCryptOpenKey(
                    provider,
                    ctypes.byref(key),
                    key_reference,
                    0,
                    self._silent_flag,
                )
            )
            return self._export_public(key)
        finally:
            if key.value:
                _ncrypt.NCryptFreeObject(key)
            _ncrypt.NCryptFreeObject(provider)

    def delete(self, key_reference: str) -> None:
        provider = self._open_provider()
        key = ctypes.c_void_p()
        try:
            status = _ncrypt.NCryptOpenKey(
                provider,
                ctypes.byref(key),
                key_reference,
                0,
                self._silent_flag,
            )
            if status != 0 and self._unsigned(status) in self._not_found:
                return
            self._check(status)
            self._check(_ncrypt.NCryptDeleteKey(key, self._silent_flag))
            key = ctypes.c_void_p()
        finally:
            if key.value:
                _ncrypt.NCryptFreeObject(key)
            _ncrypt.NCryptFreeObject(provider)

    def _open_provider(self) -> ctypes.c_void_p:
        provider = ctypes.c_void_p()
        self._check(
            _ncrypt.NCryptOpenStorageProvider(
                ctypes.byref(provider),
                self._provider_name,
                0,
            )
        )
        return provider

    def _export_public(self, key: ctypes.c_void_p) -> bytes:
        size = wintypes.DWORD()
        self._check(
            _ncrypt.NCryptExportKey(
                key,
                None,
                self._public_blob_type,
                None,
                None,
                0,
                ctypes.byref(size),
                self._silent_flag,
            )
        )
        blob = (ctypes.c_ubyte * size.value)()
        self._check(
            _ncrypt.NCryptExportKey(
                key,
                None,
                self._public_blob_type,
                None,
                blob,
                size.value,
                ctypes.byref(size),
                self._silent_flag,
            )
        )
        raw = bytes(blob[: size.value])
        if len(raw) != 72:
            raise OSError("unexpected CNG P-256 public-key size")
        magic, coordinate_size = struct.unpack("<II", raw[:8])
        if magic != 0x31534345 or coordinate_size != 32:
            raise OSError("unexpected CNG P-256 coordinate size")
        return b"\x04" + raw[8:]

    def _read_export_policy(self, key: ctypes.c_void_p) -> int:
        policy = wintypes.DWORD()
        size = wintypes.DWORD()
        self._check(
            _ncrypt.NCryptGetProperty(
                key,
                self._export_policy,
                ctypes.byref(policy),
                ctypes.sizeof(policy),
                ctypes.byref(size),
                self._silent_flag,
            )
        )
        if size.value != ctypes.sizeof(policy):
            raise OSError("unexpected CNG export-policy size")
        return policy.value

    @staticmethod
    def _unsigned(status: int) -> int:
        return status & 0xFFFFFFFF

    @classmethod
    def _check(cls, status: int) -> None:
        if status != 0:
            raise OSError(
                f"Windows CNG operation failed ({cls._unsigned(status):08X})"
            )


class WindowsInteractiveUserResolver:
    """Resolve the current process token SID and interactive Windows session."""

    _token_query = 0x0008
    _token_user = 1

    def current_user(self) -> InteractiveUser:
        if sys.platform != "win32":
            raise OSError("Windows identity is unavailable")
        token = wintypes.HANDLE()
        if not _advapi32.OpenProcessToken(
            _kernel32.GetCurrentProcess(),
            self._token_query,
            ctypes.byref(token),
        ):
            raise ctypes.WinError()
        try:
            size = wintypes.DWORD()
            _advapi32.GetTokenInformation(
                token, self._token_user, None, 0, ctypes.byref(size)
            )
            buffer = ctypes.create_string_buffer(size.value)
            if not _advapi32.GetTokenInformation(
                token,
                self._token_user,
                buffer,
                size,
                ctypes.byref(size),
            ):
                raise ctypes.WinError()
            sid_pointer = ctypes.cast(
                buffer, ctypes.POINTER(ctypes.c_void_p)
            ).contents.value
            sid_text = wintypes.LPWSTR()
            if not _advapi32.ConvertSidToStringSidW(
                sid_pointer, ctypes.byref(sid_text)
            ):
                raise ctypes.WinError()
            try:
                actor_id = sid_text.value
            finally:
                _kernel32.LocalFree(sid_text)
        finally:
            _kernel32.CloseHandle(token)

        session_id = wintypes.DWORD()
        if not _kernel32.ProcessIdToSessionId(
            _kernel32.GetCurrentProcessId(),
            ctypes.byref(session_id),
        ):
            raise ctypes.WinError()
        if not WINDOWS_SID_PATTERN.fullmatch(actor_id):
            raise OSError("Windows returned an invalid token SID")
        return InteractiveUser(
            actor_id=actor_id,
            session_id=str(session_id.value),
            interactive=session_id.value != 0,
        )
