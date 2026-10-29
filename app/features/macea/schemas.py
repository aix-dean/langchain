"""Bounded contracts for case facts supplied by the applicant, never guideline uploads."""
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Task = Literal['find_service', 'draft_letter', 'review_letter', 'submission_checklist', 'respond_comments', 'requirements']
Topic = Literal['unsure', 'signage', 'renovation', 'exterior_works', 'work_at_height', 'sidewalk_scaffolding', 'vehicle', 'road_closure', 'utilities', 'drone', 'construction', 'development']
ShortText = Annotated[str, Field(max_length=500)]


class Facts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    applicant: ShortText = ''
    role: ShortText = ''
    address: ShortText = ''
    scope: str = Field(default='', max_length=2500)
    schedule: ShortText = ''
    contractor: ShortText = ''
    signatory: ShortText = ''
    attachments: str = Field(default='', max_length=2000)
    letter: str = Field(default='', max_length=8000)
    reviewer_comments: str = Field(default='', max_length=4000)


class CaseContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    authority: Literal['macea'] = 'macea'
    task: Task
    topic: Topic = 'unsure'
    facts: Facts = Field(default_factory=Facts)


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(max_length=6000)


class AssistanceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: CaseContext
    message: str = Field(min_length=1, max_length=4000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def bounded_context(self):
        if not self.message.strip():
            raise ValueError('Describe what you want help with.')
        if len(json.dumps(self.model_dump(), ensure_ascii=False, separators=(',', ':'))) > 24000:
            raise ValueError('This request is too long. Shorten the letter or start a new chat.')
        return self
