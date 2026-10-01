from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AllocationResult(BaseModel):
    declaration_id: str
    slot_id: str | None
    group_size_allocated: int
    status: Literal["ALLOCATED", "WAITLISTED", "UNALLOCATED"]
    draw_position: int | None
    seed: str
    reason: str
