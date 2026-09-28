import pytest
from app.ingestion import connect, ingest
from app.validation import InvalidEvent


def event(**changes):
    base = dict(event_id="evt-test", equipment_id="EQ-001", timestamp="2026-09-18T12:00:00Z", region="Sul", operation_type="urbana", speed_kmh=50, engine_temp_c=None, rain_mm=0, maintenance_days=3, hard_brakes=0)
    return {**base, **changes}


def test_ingest_duplicate_and_audit(tmp_path):
    db = connect(tmp_path / "test.db")
    first = ingest(db, event())
    second = ingest(db, event())
    assert first["status"] == "created"
    assert second["status"] == "duplicate"
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 2
    assert first["factors"][0].startswith("Temperatura ausente")


def test_reject_out_of_range(tmp_path):
    db = connect(tmp_path / "test.db")
    with pytest.raises(InvalidEvent):
        ingest(db, event(speed_kmh=250))
    assert db.execute("SELECT count(*) FROM rejections").fetchone()[0] == 1


def test_high_priority(tmp_path):
    db = connect(tmp_path / "test.db")
    result = ingest(db, event(speed_kmh=140, engine_temp_c=150, maintenance_days=60, hard_brakes=10, rain_mm=30))
    assert result["level"] == "alta"


def test_missing_rain_flag(tmp_path):
    from app.features import extract
    db = connect(tmp_path / "test.db")
    result = ingest(db, event(rain_mm=None))
    assert result["status"] == "created"
    assert extract(event(rain_mm=None))["rain_missing"] == 1
