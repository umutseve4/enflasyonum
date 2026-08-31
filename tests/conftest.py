import base64

import pytest

TEST_OWNER_USERNAME = "owner"
TEST_OWNER_TOKEN = "test-owner-token"


def _basic_auth_value(username: str, token: str) -> str:
    raw = f"{username}:{token}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


@pytest.fixture(autouse=True)
def _set_owner_auth_env(monkeypatch):
    monkeypatch.setenv("ENFLASYONUM_OWNER_USERNAME", TEST_OWNER_USERNAME)
    monkeypatch.setenv("ENFLASYONUM_OWNER_TOKEN", TEST_OWNER_TOKEN)


@pytest.fixture()
def owner_auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Basic {_basic_auth_value(TEST_OWNER_USERNAME, TEST_OWNER_TOKEN)}"
    }
