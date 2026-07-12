import django_select2

from django_select2 import db_client, memcache_client, memcache_wrapped_db_client
from django_select2.models import KeyMap


def test_key_map_string_representation():
    assert str(KeyMap(key="alpha", value="beta")) == "alpha => beta"


def test_db_client_set_creates_and_updates(monkeypatch):
    class DoesNotExist(Exception):
        pass

    class FakeKeyMap:
        def __init__(self):
            self.saved = False

        def save(self):
            self.saved = True
            store[self.key] = self

    class Manager:
        def get(self, key):
            if key not in store:
                raise DoesNotExist
            return store[key]

    FakeKeyMap.DoesNotExist = DoesNotExist
    store = {}
    FakeKeyMap.objects = Manager()
    monkeypatch.setattr(db_client, "KeyMap", FakeKeyMap)

    client = db_client.Client()
    assert client.get("missing") is None

    client.set("one", "1")
    assert store["one"].saved is True
    assert client.get("one") == "1"

    client.set("one", "updated")
    assert client.get("one") == "updated"


def test_memcache_client_normalizes_keys_and_delegates(monkeypatch):
    class FakeMemcacheModule:
        class Client:
            def __init__(self, hosts):
                self.hosts = hosts
                self.values = {}

            def set(self, key, value, expiry):
                self.values[(key, expiry)] = value

            def get(self, key):
                for (stored_key, _expiry), value in self.values.items():
                    if stored_key == key:
                        return value
                return None

    monkeypatch.setattr(memcache_client, "memcache", FakeMemcacheModule)
    client = memcache_client.Client("cache", "11212", expiry=10)

    assert client.host == "cache:11212"
    assert client.normalize_key("with spaces") == "with-spaces"
    client.set("with spaces", "value")
    assert client.get("with spaces") == "value"


def test_wrapped_client_uses_cache_then_database(monkeypatch):
    class FakeCache:
        def __init__(self, hostname, port, expiry):
            self.values = {}
            self.init_args = (hostname, port, expiry)

        def set(self, key, value):
            self.values[key] = value

        def get(self, key):
            return self.values.get(key)

    class FakeDb:
        def __init__(self):
            self.values = {"db-only": "from-db"}
            self.set_calls = []

        def set(self, key, value):
            self.set_calls.append((key, value))
            self.values[key] = value

        def get(self, key):
            return self.values.get(key)

    fake_db = FakeDb()

    class FakeCacheModule:
        Client = FakeCache

    class FakeDbModule:
        Client = lambda self=None: fake_db

    monkeypatch.setattr(django_select2, "memcache_client", FakeCacheModule)
    monkeypatch.setattr(django_select2, "db_client", FakeDbModule)

    client = memcache_wrapped_db_client.Client("cache", "11212", 10)

    client.set("both", "value")
    assert fake_db.values["both"] == "value"
    assert client.cache.get("both") == "value"
    assert client.get("both") == "value"
    assert client.get("db-only") == "from-db"
    assert client.cache.get("db-only") == "from-db"


def test_wrapped_client_can_run_without_cache(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.values = {}

        def set(self, key, value):
            self.values[key] = value

        def get(self, key):
            return self.values.get(key)

    fake_db = FakeDb()

    class FakeDbModule:
        Client = lambda self=None: fake_db

    monkeypatch.setattr(django_select2, "db_client", FakeDbModule)
    client = memcache_wrapped_db_client.Client(None, None)

    client.set("key", "value")
    assert client.cache is None
    assert client.get("key") == "value"
