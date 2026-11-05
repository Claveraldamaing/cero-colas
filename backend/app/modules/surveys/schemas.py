"""Validated payloads for local satisfaction surveys."""
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SurveyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ease_score: int = Field(strict=True)
    satisfaction_score: int = Field(strict=True)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value):
        if value:
            value = value.strip()
            # Comments are intentionally optional and must not collect identifiers.
            if re.search(r"(?<!\d)\d{8}(?!\d)", value) or re.search(r"\b\d{4}-\d{2}-\d{2}\b", value):
                raise ValueError("No incluyas DNI ni fechas de nacimiento en el comentario.")
            return value or None
        return None
