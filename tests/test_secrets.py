import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError

from app.database.config_repository import ConfigRepository
from app.models.configuration import Configuration
from app.services.configuration_service import ConfigurationService
from app.services.errors import SecretStoreError
from app.services.secret_store import InMemorySecretStore, KeyringSecretStore


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self.data: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        del self.data[(service, username)]


class BrokenKeyring(MemoryKeyring):
    def get_password(self, service, username):
        raise KeyringError("sin backend")

    def set_password(self, service, username, password):
        raise KeyringError("sin backend")


class FailingStore(InMemorySecretStore):
    def __init__(self):
        super().__init__()
        self.broken = False

    def get(self, name):
        if self.broken:
            raise SecretStoreError("almacén caído")
        return super().get(name)

    def set(self, name, value):
        if self.broken:
            raise SecretStoreError("almacén caído")
        super().set(name, value)


def stored_keys(db):
    return {r["config_key"] for r in db.conn.execute("SELECT config_key FROM configuration")}


def test_token_goes_to_secret_store_not_sqlite(db):
    secrets = InMemorySecretStore()
    svc = ConfigurationService(ConfigRepository(db), secrets)
    svc.save(Configuration(hub_url="https://hub", terminal_id="T1", api_token="s3cr3t"))
    assert secrets.get("api_token") == "s3cr3t"
    assert "api_token" not in stored_keys(db)
    assert "s3cr3t" not in str(db.conn.execute("SELECT * FROM configuration").fetchall()[0:])
    assert svc.load().api_token == "s3cr3t"


def test_clearing_token_removes_it(db):
    secrets = InMemorySecretStore()
    svc = ConfigurationService(ConfigRepository(db), secrets)
    svc.save(Configuration(api_token="x"))
    svc.save(Configuration(api_token=""))
    assert secrets.get("api_token") == "" and svc.load().api_token == ""


def test_legacy_plaintext_token_is_migrated(db):
    repo = ConfigRepository(db)
    repo.set("api_token", "legacy")
    secrets = InMemorySecretStore()
    svc = ConfigurationService(repo, secrets)
    assert svc.load().api_token == "legacy"
    assert secrets.get("api_token") == "legacy"
    assert "api_token" not in stored_keys(db)
    assert svc.load().api_token == "legacy"


def test_legacy_token_kept_if_store_unavailable(db):
    repo = ConfigRepository(db)
    repo.set("api_token", "legacy")
    secrets = FailingStore()
    secrets.broken = True
    svc = ConfigurationService(repo, secrets)
    assert svc.load().api_token == "legacy"
    assert "api_token" in stored_keys(db)  # no se pierde
    secrets.broken = False
    svc.load()
    assert secrets.get("api_token") == "legacy" and "api_token" not in stored_keys(db)


def test_save_fails_without_partial_write_when_store_down(db):
    secrets = FailingStore()
    svc = ConfigurationService(ConfigRepository(db), secrets)
    secrets.broken = True
    with pytest.raises(SecretStoreError):
        svc.save(Configuration(hub_url="https://hub", api_token="x"))
    assert stored_keys(db) == set()


def test_keyring_store_roundtrip():
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    store = KeyringSecretStore("test")
    assert store.get("t") == ""
    store.set("t", "abc")
    assert store.get("t") == "abc" and backend.data == {("test", "t"): "abc"}
    store.set("t", "")
    assert store.get("t") == "" and backend.data == {}
    store.set("t", "")  # borrar lo inexistente no falla


def test_keyring_store_wraps_backend_errors():
    keyring.set_keyring(BrokenKeyring())
    store = KeyringSecretStore("test")
    with pytest.raises(SecretStoreError):
        store.get("t")
    with pytest.raises(SecretStoreError):
        store.set("t", "abc")
