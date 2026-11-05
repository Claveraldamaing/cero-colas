"""Validated payloads for administrative account management."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool | None = Field(default=None, strict=True)
    role: Literal["PACIENTE", "ADMIN"] | None = None
