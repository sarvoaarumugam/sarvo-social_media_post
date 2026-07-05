"""Schemas for the scripting stage: the strict structured-output model the LLM
must fill, plus the API request/response DTOs for the human-review checkpoint.
"""

from pydantic import BaseModel, Field

from app.models.episode import Blueprint, DialogueTurn, EpisodeStatus


class BlueprintRead(BaseModel):
    """The strategist's plan, returned for your review before scripting."""

    episode_id: str
    status: EpisodeStatus
    topic: str
    blueprint: Blueprint | None
    cost_usd: float


class GeneratedScript(BaseModel):
    """Strict schema the model is forced to return — guarantees clean dialogue."""

    turns: list[DialogueTurn]


class ScriptGenerateRequest(BaseModel):
    """Optional body for POST .../script — override the episode's duration just for
    this generation. Omit the body entirely to use the episode's stored duration.
    """

    duration_minutes: float | None = Field(default=None, ge=1, le=30)


class ScriptRead(BaseModel):
    """What the API returns when you view/generate a script (the review payload)."""

    episode_id: str
    status: EpisodeStatus
    topic: str
    hosts: list[str]
    target_minutes: float
    word_count: int
    est_minutes: float  # estimated spoken length of what was actually generated
    cost_usd: float
    turns: list[DialogueTurn]


class ScriptUpdate(BaseModel):
    """Manual correction: replace the dialogue with your edited version."""

    turns: list[DialogueTurn]
