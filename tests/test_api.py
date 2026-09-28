from fastapi.testclient import TestClient
from app.api import app
from app.ingestion import connect, ingest
from app.audit import verify


def sample(event_id="api-test", **kw):
    return {"event_id": event_id, "equipment_id": "EQ-042", "timestamp": "2026-09-18T12:00:00Z", "region": "Sudeste", "operation_type": "urbana", "speed_kmh": 82, "engine_temp_c": 112, "rain_mm": 3, "maintenance_days": 22, "hard_brakes": 7, **kw}


def test_api_access_and_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMPO_DB", str(tmp_path / "api.db"))
    client = TestClient(app)
    assert client.get("/scores").status_code == 401
    assert client.get("/scores", headers={"Authorization": "Bearer demo-operator"}).status_code == 403
    result = client.post("/events", json=sample(), headers={"Authorization": "Bearer demo-operator"})
    assert result.status_code == 200, result.text
    assert client.post("/events", json=sample(), headers={"Authorization": "Bearer demo-operator"}).json()["status"] == "duplicate"
    assert len(client.get("/scores", headers={"Authorization": "Bearer demo-manager"}).json()) == 1
    report = client.get("/reports/summary", headers={"Authorization": "Bearer demo-manager"})
    assert report.status_code == 200
    assert report.json()["by"]["region"][0]["name"] == "Sudeste"
    assert report.json()["audit_valid"] is True
    assert client.get("/audit/integrity", headers={"Authorization": "Bearer demo-manager"}).status_code == 403
    assert client.get("/audit/integrity", headers={"Authorization": "Bearer demo-analyst"}).json()["valid"] is True
    assert client.post("/events/api-test/decisions", json={"decision":"Encaminhado para manutenção"}, headers={"Authorization":"Bearer demo-operator"}).status_code == 200
    assert client.get("/equipment/EQ-042", headers={"Authorization":"Bearer demo-operator"}).json()[0]["event_id"] == "api-test"


def test_invalid_and_tampered_log(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMPO_DB", str(tmp_path / "api.db"))
    client = TestClient(app)
    invalid = sample("bad", speed_kmh=250)
    assert client.post("/events", json=invalid, headers={"Authorization":"Bearer demo-operator"}).status_code == 422
    db = connect(tmp_path / "api.db")
    assert db.execute("SELECT count(*) FROM rejections").fetchone()[0] == 1
    assert verify(db)
    db.execute("UPDATE audit_log SET record='{}'")
    db.commit()
    assert not verify(db)


def test_api_rejects_unexpected_personal_field(tmp_path, monkeypatch):
    monkeypatch.setenv("SOMPO_DB", str(tmp_path / "api.db"))
    client = TestClient(app)
    payload = sample("private-field")
    payload["driver_name"] = "Pessoa Teste"
    response = client.post("/events", json=payload, headers={"Authorization": "Bearer demo-operator"})
    assert response.status_code == 422
