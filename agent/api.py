"""KIRRO Core HTTP surface (port 8080). Thin wrappers over Engine; no logic of its own.

Scaffold: endpoints exist so the Pine Labs platform / Gnani post-call action can be pointed at them.
Wiring to the real platform is TODO (docs/connectors.md). State is in memory per process.
"""
from __future__ import annotations

import os
import uuid
from datetime import date

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.core import Engine
from agent.state.store import Store
from agent.tools.toolset import state_view
from connectors.gnani.extract import extract_intake
from connectors.registry import build_connectors
from logging_.decision_log import DecisionLog


class FieldIn(BaseModel):
    user_text: str
    field: str
    evidence: str


class TextIn(BaseModel):
    text: str = ""


class EventIn(BaseModel):
    type: str
    event_id: str | None = None
    release_id: str | None = None


class GnaniPostCall(BaseModel):
    transcript: str
    clientReferenceId: str | None = None


def create_core(mock_url: str | None = None, log_dir: str = "logs", client: httpx.Client | None = None) -> FastAPI:
    app = FastAPI(title="KIRRO Core", version="0.1.0")
    run_id = f"core-{uuid.uuid4().hex[:8]}"
    client = client or httpx.Client(base_url=mock_url or os.environ.get("MOCK_SERVER_URL", "http://localhost:8081"))
    catalogue = client.get("/venue/catalogue").json()["events"] if client else []
    eng = Engine(build_connectors(client, run_id), Store(), DecisionLog(run_id, log_dir), catalogue)

    def get(did: str):
        try:
            return eng.store.get(did)
        except KeyError:
            raise HTTPException(404, "unknown declaration") from None

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "kirro-core", "run_id": run_id}

    @app.post("/declarations")
    def create():
        d = eng.new_declaration()
        return {"declaration_id": d.declaration_id, **state_view(d)}

    @app.get("/declarations/{did}")
    def show(did: str):
        return state_view(get(did))

    @app.post("/declarations/{did}/fields")
    def field(did: str, body: FieldIn):
        d = get(did)
        eng.receive_user_turn(d, body.user_text, source="user_text")
        return eng.set_field(d, body.field, body.evidence, decided_by="code")

    @app.post("/declarations/{did}/readback")
    def readback(did: str, body: TextIn):
        d = get(did)
        if not d.readback_presented:
            return eng.present_readback(d)
        return eng.confirm_readback(d, body.text.strip().lower() in ("yes", "y", "haan"), decided_by="code")

    @app.post("/declarations/{did}/authorise")
    def authorise(did: str):
        return eng.request_authorisation(get(did), decided_by="code")

    @app.post("/declarations/{did}/cancel")
    def cancel(did: str):
        return eng.cancel(get(did), "cancelled via API", decided_by="code", source="user_text")

    @app.post("/declarations/{did}/events")
    def event(did: str, body: EventIn):
        return eng.on_event(get(did), body.model_dump())

    @app.post("/intake/gnani")
    def intake_gnani(body: GnaniPostCall):
        """Post-call action target. TODO(platform): fetch the full transcript via Gnani conversations/logs using
        clientReferenceId; today we only run the deterministic extractor over the posted text."""
        ex = extract_intake(body.transcript, today=date.today(), catalogue=catalogue)
        return {"language": ex.language, "candidates": [c.__dict__ for c in ex.candidates]}

    return app


def app_factory() -> FastAPI:  # uvicorn --factory agent.api:app_factory
    return create_core()
