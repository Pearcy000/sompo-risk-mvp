import json
import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from .ingestion import connect, ingest, audit
from .audit import verify
from .validation import InvalidEvent

app = FastAPI(title="Sompo Risk MVP", version="0.1.0")


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    equipment_id: str
    timestamp: str
    region: str
    operation_type: str
    speed_kmh: float
    maintenance_days: int
    engine_temp_c: float | None = None
    rain_mm: float | None = None
    hard_brakes: int = 0


class Decision(BaseModel):
    decision: str


def database():
    return connect(os.getenv("SOMPO_DB", "sompo.db"))


def role(authorization: str = Header(default="")):
    # Tokens de demonstração configurados por ambiente; em produção, usar identidade e RBAC centralizados.
    token = authorization.removeprefix("Bearer ")
    roles = {os.getenv("SOMPO_OPERATOR_TOKEN", "demo-operator"): "operator",
             os.getenv("SOMPO_MANAGER_TOKEN", "demo-manager"): "manager",
             os.getenv("SOMPO_ANALYST_TOKEN", "demo-analyst"): "analyst"}
    if token not in roles:
        raise HTTPException(401, "Token inválido")
    return roles[token]


@app.get("/")
def home():
    return FileResponse(Path(__file__).resolve().parent.parent / "dashboard" / "index.html")


@app.post("/events")
def create_event(event: Event, user=Depends(role)):
    db = database()
    try:
        return ingest(db, event.model_dump())
    except InvalidEvent as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        db.close()


@app.get("/scores")
def scores(user=Depends(role)):
    if user == "operator":
        raise HTTPException(403, "Perfil sem acesso à visão de frota")
    db = database()
    try:
        rows = db.execute("SELECT e.equipment_id,e.region,e.operation_type,e.timestamp,s.score,s.level,s.factors,s.model_version FROM scores s JOIN events e USING(event_id) ORDER BY e.timestamp DESC LIMIT 200").fetchall()
        return [{**dict(row), "factors": json.loads(row["factors"])} for row in rows]
    finally:
        db.close()


@app.get("/equipment/{equipment_id}")
def equipment(equipment_id: str, user=Depends(role)):
    db = database()
    try:
        rows = db.execute("SELECT e.event_id,e.timestamp,s.score,s.level,s.factors FROM events e JOIN scores s USING(event_id) WHERE e.equipment_id=? ORDER BY e.timestamp DESC LIMIT 100", (equipment_id,)).fetchall()
        return [{**dict(row), "factors": json.loads(row["factors"])} for row in rows]
    finally:
        db.close()


@app.post("/events/{event_id}/decisions")
def decide(event_id: str, payload: Decision, user=Depends(role)):
    if user not in {"operator", "manager"}:
        raise HTTPException(403, "Perfil sem permissão")
    if not payload.decision.strip():
        raise HTTPException(422, "Decisão vazia")
    db = database()
    try:
        with db:
            if not db.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
                raise HTTPException(404, "Evento não encontrado")
            db.execute("INSERT INTO decisions(event_id,actor,decision,created_at) VALUES (?,?,?,datetime('now'))", (event_id, user, payload.decision.strip()))
            audit(db, "decision", {"event_id": event_id, "actor": user})
        return {"status": "recorded"}
    finally:
        db.close()


@app.get("/reports/summary")
def summary(user=Depends(role)):
    if user == "operator":
        raise HTTPException(403, "Perfil sem acesso aos relatórios de frota")
    db = database()
    try:
        groupings = {}
        for name, column in (("region", "region"), ("operation", "operation_type"), ("equipment", "equipment_id")):
            groupings[name] = [dict(row) for row in db.execute(
                f"SELECT e.{column} AS name, COUNT(*) AS events, ROUND(AVG(s.score),1) AS avg_score, SUM(CASE WHEN s.level='alta' THEN 1 ELSE 0 END) AS high_alerts FROM events e JOIN scores s USING(event_id) GROUP BY e.{column} ORDER BY avg_score DESC")]
        trend = [dict(row) for row in db.execute(
            "SELECT substr(e.timestamp,1,10) AS date, ROUND(AVG(s.score),1) AS avg_score, COUNT(*) AS events FROM events e JOIN scores s USING(event_id) GROUP BY substr(e.timestamp,1,10) ORDER BY date")]
        return {"by": groupings, "trend": trend, "audit_valid": verify(db), "scope": "dados armazenados no MVP; não há horas de operação para calcular alertas por mil horas"}
    finally:
        db.close()


@app.get("/audit/integrity")
def integrity(user=Depends(role)):
    if user != "analyst":
        raise HTTPException(403, "Perfil sem permissão")
    db = database()
    try:
        return {"valid": verify(db), "entries": db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]}
    finally:
        db.close()
