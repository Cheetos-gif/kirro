"""Builds the connector set from config/connectors.yaml and env. Real vs mock is config, not code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from connectors.base import NotConfiguredConnector
from connectors.delhivery.mock import DelhiveryMockConnector, build_real_delhivery
from connectors.gnani.platform import build_gnani
from connectors.inventory.venue import VenueInventoryConnector
from connectors.pine_labs.mock import PineLabsMockConnector
from connectors.pine_labs.sandbox import build_sandbox_connector

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "connectors.yaml"


@dataclass
class Connectors:
    inventory: object
    pine_labs: object
    delhivery: object
    gnani: object


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def build_connectors(client: httpx.Client, run_id: str, env: dict | None = None,
                     config: dict | None = None) -> Connectors:
    """`client` points at the mock server (in-process TestClient or http://localhost:8081)."""
    env = dict(os.environ if env is None else env)
    config = config or load_config()
    modes = {k: env.get(f"{k.upper()}_MODE", v.get("mode", "mock")) for k, v in config["connectors"].items()}
    pine = (PineLabsMockConnector(client, run_id) if modes["pine_labs"] == "mock"
            else build_sandbox_connector(env))
    delh = (DelhiveryMockConnector(client, run_id) if modes["delhivery"] == "mock"
            else build_real_delhivery(env))
    gnani = (NotConfiguredConnector("gnani.mock", "gnani", "voice is simulated in evals; no mock call path")
             if modes["gnani"] == "mock" else build_gnani(env))
    return Connectors(VenueInventoryConnector(client, run_id), pine, delh, gnani)
