"""Validated HTTP payloads for the auth module."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_email(value: str):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Ingresa un correo electrónico válido.")
    return value


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChallengeInput(StrictInput):
    challenge_id: str = Field(min_length=1, max_length=64)
    challenge_answer: str = Field(min_length=1, max_length=16)


class LoginInput(ChallengeInput):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    _email = field_validator("email")(normalize_email)


class RegisterInput(LoginInput):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Ingresa tu nombre.")
        return value


class Preferences(StrictInput):
    email_notifications: bool = Field(default=True, strict=True)
    language: Literal["es"] = "es"
    theme: Literal["system", "light", "dark"] = "system"


class ProfileInput(StrictInput):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    preferences: Preferences | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        if value is None:
            return value
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Ingresa tu nombre.")
        return value


class PasswordInput(StrictInput):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ForgotInput(ChallengeInput):
    email: str = Field(max_length=254)
    _email = field_validator("email")(normalize_email)


class ResetInput(StrictInput):
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class AccountInput(StrictInput):
    active: bool | None = Field(default=None, strict=True)
    role: Literal["PACIENTE", "ADMIN"] | None = None
