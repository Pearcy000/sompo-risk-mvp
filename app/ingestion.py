import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .validation import validate, InvalidEvent
from .features import extract
from .alerts import explain, classify
from .audit import chain, digest

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL, timestamp TEXT NOT NULL, region TEXT NOT NULL, operation_type TEXT NOT NULL, payload TEXT NOT NULL, input_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scores (event_id TEXT PRIMARY KEY REFERENCES events(event_id), score INTEGER NOT NULL, level TEXT NOT NULL, factors TEXT NOT NULL, model_version TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rejections (id INTEGER PRIMARY KEY, event_id TEXT, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(event_id), actor TEXT NOT NULL, decision TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY, correlation_id TEXT NOT NULL, action TEXT NOT NULL, record TEXT NOT NULL, previous_hash TEXT NOT NULL, entry_hash TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def connect(path):
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    return db


def audit(db, action, record, correlation_id=None):
    previous = db.execute("SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prior = previous[0] if previous else ""
    entry = {"action": action, **record}
    db.execute("INSERT INTO audit_log(correlation_id,action,record,previous_hash,entry_hash,created_at) VALUES (?,?,?,?,?,?)",
               (correlation_id or str(uuid.uuid4()), action, json.dumps(entry, sort_keys=True), prior, chain(prior, entry), datetime.now(timezone.utc).isoformat()))


def score_event(event, model_path="models/risk_model.joblib"):
    from .model import predict
    probability, version = predict(extract(event), model_path)
    score = round(100 * probability)
    level, recommendation = classify(score)
    return {"event_id": event["event_id"], "equipment_id": event["equipment_id"], "score": score,
            "level": level, "recommendation": recommendation, "factors": explain(event), "model_version": version}


def ingest(db, raw, model_path="models/risk_model.joblib"):
    correlation_id = str(uuid.uuid4())
    try:
        event = validate(raw)
        existing = db.execute("SELECT payload FROM events WHERE event_id=?", (event["event_id"],)).fetchone()
        if existing:
            audit(db, "duplicate", {"event_id": event["event_id"]}, correlation_id)
            db.commit()
            score = db.execute("SELECT * FROM scores WHERE event_id=?", (event["event_id"],)).fetchone()
            return {"status": "duplicate", "score": dict(score) if score else None}
        result = score_event(event, model_path)
        now = datetime.now(timezone.utc).isoformat()
        with db:
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)", (event["event_id"], event["equipment_id"], event["timestamp"], event["region"], event["operation_type"], json.dumps(event), digest(event)))
            db.execute("INSERT INTO scores VALUES (?,?,?,?,?,?)", (event["event_id"], result["score"], result["level"], json.dumps(result["factors"]), result["model_version"], now))
            audit(db, "scored", {"event_id": event["event_id"], "score": result["score"], "model_version": result["model_version"], "input_hash": digest(event)}, correlation_id)
        return {"status": "created", "correlation_id": correlation_id, **result}
    except InvalidEvent as exc:
        with db:
            db.execute("INSERT INTO rejections(event_id,reason,created_at) VALUES (?,?,?)", (str(raw.get("event_id", "")), str(exc), datetime.now(timezone.utc).isoformat()))
            audit(db, "rejected", {"event_id": str(raw.get("event_id", "")), "reason": str(exc)}, correlation_id)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--db", default="sompo.db")
    parser.add_argument("--model", default="models/risk_model.joblib")
    args = parser.parse_args()
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = [rows]
    db = connect(args.db)
    for row in rows:
        try:
            print(json.dumps(ingest(db, row, args.model), ensure_ascii=False))
        except InvalidEvent as exc:
            print(json.dumps({"event_id": row.get("event_id"), "error": str(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
