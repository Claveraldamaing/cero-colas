from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AppointmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specialty_id: str = Field(min_length=1, max_length=100)
    slot_id: str = Field(min_length=1, max_length=500)
    reference_id: str = Field(min_length=1, max_length=100)
    contact_phone: str = Field(pattern=r"^([0-9]{7}|[0-9]{9})$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,128}$")


class AvailabilityResponse(BaseModel):
    date: date
    available_slots: int = Field(ge=0)


class SlotResponse(BaseModel):
    slot_id: str
    date: date
    start_time: str
    end_time: str
    office: str
    doctor: str
