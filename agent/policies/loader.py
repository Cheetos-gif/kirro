"""Load YAML policy files. Policies are data; the state machine and validators read them."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

POLICY_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def load_policy(name: str) -> dict:
    with open(POLICY_DIR / f"{name}.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
