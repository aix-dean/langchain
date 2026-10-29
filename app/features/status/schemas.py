from typing import Literal
from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    vision_model: str = Field(description="Configured image-reading model.")
    judge_model: str = Field(description="Configured chat/judgment model.")
    embedding_model: str = Field(description="Model used to embed guideline queries.")
    collection: str = Field(description="ASC collection; MACEA uploads use a separate collection.")
    ollama: bool = Field(description="Whether the generation Ollama service responded.")
    missing_models: list[str] = Field(description="Configured models not found on the generation Ollama service.")
    qdrant: bool = Field(description="Whether the ASC vector store could be opened and counted.")
    passages: int = Field(description="Number of passages in the ASC collection.")
    judge_tools: bool = Field(description="Whether the judge advertises tool support.")
    device: Literal['CPU', 'GPU'] | None = Field(description="Device inferred from resident generation-service models; null when none is detected.")
    busy: bool = Field(description="Whether any AI job is running, including warm-up.")
    context_limit_chars: int = Field(description="Character budget for conversation context.")
    context_limit_tokens: int = Field(description="Estimated token budget for conversation context.")
    active_jobs: int = Field(default=0, description="Currently running AI jobs, including warm-up.")
    queued_jobs: int = Field(default=0, description="AI jobs waiting for an available slot.")
    max_concurrent_jobs: int = Field(default=2, description="Maximum simultaneous AI jobs in this worker.")
