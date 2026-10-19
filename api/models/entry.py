from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4

class EntryCreate(BaseModel):
    """Model for creating a new journal entry (user input)."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work: str = Field(
        min_length=1,
        max_length=256,
        description="What did you work on today?",
        json_schema_extra={"example": "Studied FastAPI and built my first API endpoints"}
    )
    struggle: str = Field(
        min_length=1,
        max_length=256,
        description="What's one thing you struggled with today?",
        json_schema_extra={"example": "Understanding async/await syntax and when to use it"}
    )
    intention: str = Field(
        min_length=1,
        max_length=256,
        description="What will you study/work on tomorrow?",
        json_schema_extra={"example": "Practice PostgreSQL queries and database design"}
    )

class EntryUpdate(BaseModel):
    """Only supplied journal fields may be changed; explicit nulls are invalid."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work: str | None = Field(default=None, min_length=1, max_length=256)
    struggle: str | None = Field(default=None, min_length=1, max_length=256)
    intention: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("work", "struggle", "intention")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Journal fields cannot be null")
        return value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Supply at least one journal field")
        return self


class Entry(BaseModel):
    
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the entry (UUID)."
    )
    work: str = Field(
        ...,
        max_length=256,
        description="What did you work on today?"
    )
    struggle: str = Field(
        ...,
        max_length=256,
        description="What’s one thing you struggled with today?"
    )
    intention: str = Field(
        ...,
        max_length=256,
        description="What will you study/work on tomorrow?"
    )
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the entry was created."
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the entry was last updated."
    )

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }
