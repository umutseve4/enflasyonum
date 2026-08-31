from fastapi.testclient import TestClient

from enflasyonum import __version__
from enflasyonum.main import app

client = TestClient(app)


def test_health_returns_200_and_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_unknown_route_returns_404():
    resp = client.get("/does-not-exist")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Basic"
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["pragma"] == "no-cache"
    assert "authorization" in resp.headers["vary"].lower()
