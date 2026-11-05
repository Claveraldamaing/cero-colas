"""Validated payload for portal patient identification."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.integrations.hospital import LIMA


class IdentificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero_documento: str = Field(pattern=r"^[0-9]{8}$")
    fecha_nacimiento: date
    consent: bool
    challenge_id: str = Field(min_length=1, max_length=100)
    challenge_answer: str = Field(min_length=1, max_length=100)

    @field_validator("fecha_nacimiento")
    @classmethod
    def birthday_not_in_future(cls, value):
        if value > datetime.now(LIMA).date():
            raise ValueError("La fecha de nacimiento no puede estar en el futuro.")
        return value
