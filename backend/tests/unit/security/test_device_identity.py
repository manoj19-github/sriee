from __future__ import annotations

import asyncio
import sys
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from jarvis.security.device_identity import (
    DeviceIdentity,
    DeviceIdentityConflictError,
    DeviceKey,
    DeviceRegistrationError,
    DeviceRegistrationService,
    InMemoryDeviceIdentityRegistry,
    InteractiveUser,
    KeyProtection,
    WindowsCngDeviceKeyStore,
    WindowsInteractiveUserResolver,
    registerDeviceIdentity,
)


NOW = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)
INSTALLATION_ID = "8dc7e60f-4677-4d22-9572-a728fab88c89"
PUBLIC_KEY = b"\x04" + bytes(range(64))


class Users:
    def __init__(self, user=None, error=None) -> None:
        self.user = user or InteractiveUser("S-1-5-21-1000", "4", True)
        self.error = error

    def current_user(self):
        if self.error:
            raise self.error
        return self.user


class Keys:
    def __init__(
        self, public_key=PUBLIC_KEY, *, created=True, error=None
    ) -> None:
        self.public_key, self.created, self.error = public_key, created, error
        self.deleted: list[str] = []
        self.get_calls = 0

    def get_or_create(self, installation_id):
        self.get_calls += 1
        if self.error:
            raise self.error
        return DeviceKey(
            f"JarvisOS.Device.{UUID(installation_id).hex}",
            self.public_key, KeyProtection.TEST_ONLY, self.created,
        )

    def read_public_key(self, key_reference):
        if self.error:
            raise self.error
        return self.public_key

    def delete(self, key_reference):
        self.deleted.append(key_reference)


class Registry(InMemoryDeviceIdentityRegistry):
    def __init__(
        self, records=(), *, read_error=None, write_error=None, override=None
    ) -> None:
        super().__init__(records)
        self.read_error, self.write_error, self.override = (
            read_error, write_error, override
        )

    async def get_by_installation(self, installation_id):
        if self.read_error:
            raise self.read_error
        return await super().get_by_installation(installation_id)

    async def register_or_get(self, identity):
        if self.write_error:
            raise self.write_error
        if self.override:
            return self.override
        return await super().register_or_get(identity)


def service(*, users=None, keys=None, registry=None):
    return DeviceRegistrationService(
        users=users or Users(),
        keys=keys or Keys(),
        registry=registry or Registry(),
        clock=lambda: NOW,
    )


@pytest.mark.anyio
async def test_registers_public_identity_bound_to_os_user() -> None:
    result = await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True, service=service()
    )
    assert result.created is True
    assert result.device_id.startswith("dev_")
    assert result.actor_id == "S-1-5-21-1000"
    assert result.registration_session_id == "4"
    assert result.public_key_algorithm == "ECDSA_P256_SHA256"
    assert result.registered_at is NOW
    assert "key_reference" not in result.public_record()
    assert "registration_session_id" not in result.public_record()


@pytest.mark.anyio
@pytest.mark.parametrize("decision", [False, None, 1, "yes"])
async def test_requires_explicit_boolean_setup(decision) -> None:
    keys = Keys()
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=decision, service=service(keys=keys)
        )
    assert caught.value.code == "explicit_setup_required"
    assert keys.get_calls == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "installation_id",
    ["", "not-a-uuid", str(uuid4()).upper(),
     "00000000-0000-0000-0000-000000000000"],
)
async def test_rejects_noncanonical_non_v4_installation_ids(
    installation_id,
) -> None:
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            installation_id, explicit_setup=True, service=service()
        )
    assert caught.value.code == "installation_id_invalid"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "user",
    [
        InteractiveUser("", "4", True),
        InteractiveUser("S-1-5-21-1000", "", True),
        InteractiveUser("S-1-5-21-1000", "0", False),
    ],
)
async def test_rejects_missing_or_noninteractive_os_identity(user) -> None:
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(users=Users(user)),
        )
    assert caught.value.code == "interactive_user_required"


@pytest.mark.anyio
async def test_sanitizes_os_identity_resolution_failure() -> None:
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(users=Users(error=RuntimeError("secret detail"))),
        )
    assert caught.value.code == "interactive_user_unavailable"
    assert "secret detail" not in str(caught.value)


@pytest.mark.anyio
async def test_repeat_registration_is_idempotent() -> None:
    registry, keys = Registry(), Keys()
    first = await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True,
        service=service(keys=keys, registry=registry),
    )
    second = await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True,
        service=service(keys=keys, registry=registry),
    )
    assert first.device_id == second.device_id
    assert second.created is False
    assert keys.get_calls == 1


@pytest.mark.anyio
async def test_existing_install_cannot_be_rebound() -> None:
    registry = Registry()
    await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True, service=service(registry=registry)
    )
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(
                users=Users(InteractiveUser("S-1-5-21-2000", "5", True)),
                registry=registry,
            ),
        )
    assert caught.value.code == "device_identity_conflict"


@pytest.mark.anyio
async def test_existing_registration_requires_matching_local_key() -> None:
    registered = await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True, service=service()
    )
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(
                keys=Keys(b"\x04" + b"x" * 64, created=False),
                registry=Registry((registered,)),
            ),
        )
    assert caught.value.code == "device_key_mismatch"


@pytest.mark.anyio
async def test_new_key_is_deleted_when_registry_write_fails() -> None:
    keys = Keys(created=True)
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(
                keys=keys,
                registry=Registry(write_error=RuntimeError("db detail")),
            ),
        )
    assert caught.value.code == "device_registration_failed"
    assert keys.deleted == [f"JarvisOS.Device.{UUID(INSTALLATION_ID).hex}"]
    assert "db detail" not in str(caught.value)


@pytest.mark.anyio
async def test_preexisting_key_is_not_deleted_after_registry_failure() -> None:
    keys = Keys(created=False)
    with pytest.raises(DeviceRegistrationError):
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(
                keys=keys, registry=Registry(write_error=RuntimeError)
            ),
        )
    assert keys.deleted == []


@pytest.mark.anyio
async def test_registry_conflict_deletes_new_key_and_fails_closed() -> None:
    keys = Keys()
    good = await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True, service=service()
    )
    conflicting = replace(good, actor_id="S-1-5-21-2000")
    with pytest.raises(DeviceRegistrationError) as caught:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(keys=keys, registry=Registry(override=conflicting)),
        )
    assert caught.value.code == "device_identity_conflict"
    assert len(keys.deleted) == 1


@pytest.mark.anyio
async def test_registry_enforces_unique_device_identity() -> None:
    registry = InMemoryDeviceIdentityRegistry()
    first = await registerDeviceIdentity(
        INSTALLATION_ID, explicit_setup=True, service=service(registry=registry)
    )
    other = replace(
        first, installation_id="2274718b-1ef8-46d8-bc1e-f9d448c93b62"
    )
    with pytest.raises(DeviceIdentityConflictError):
        await registry.register_or_get(other)


@pytest.mark.anyio
async def test_concurrent_registration_converges() -> None:
    registry, keys = InMemoryDeviceIdentityRegistry(), Keys(created=False)
    results = await asyncio.gather(*(
        registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(keys=keys, registry=registry),
        )
        for _ in range(8)
    ))
    assert len({result.device_id for result in results}) == 1
    assert sum(result.created for result in results) == 1


@pytest.mark.anyio
async def test_malformed_key_and_naive_clock_fail_safely() -> None:
    with pytest.raises(DeviceRegistrationError) as malformed:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True,
            service=service(keys=Keys(b"not-a-key")),
        )
    assert malformed.value.code == "device_registration_failed"
    naive_service = replace(service(), clock=lambda: datetime(2026, 7, 5))
    with pytest.raises(DeviceRegistrationError) as naive:
        await registerDeviceIdentity(
            INSTALLATION_ID, explicit_setup=True, service=naive_service
        )
    assert naive.value.code == "device_registration_failed"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CNG integration")
def test_windows_cng_key_is_persistent_and_public_only() -> None:
    installation_id = str(uuid4())
    store = WindowsCngDeviceKeyStore("JarvisOS.DeviceTest")
    first = store.get_or_create(installation_id)
    try:
        second = store.get_or_create(installation_id)
        assert first.created is True
        assert second.created is False
        assert first.public_key == second.public_key
        assert len(first.public_key) == 65
        assert first.protection is KeyProtection.WINDOWS_CNG_USER_NON_EXPORTABLE
        assert not hasattr(first, "private_key")
    finally:
        store.delete(first.key_reference)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows session integration")
def test_windows_user_resolver_returns_token_sid_and_session() -> None:
    user = WindowsInteractiveUserResolver().current_user()
    assert user.actor_id.startswith("S-1-")
    assert user.session_id.isdigit()
    assert user.interactive is True
