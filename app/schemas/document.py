from enum import Enum

from pydantic import BaseModel


class ChunkingStrategy(str, Enum):
    fixed = "fixed"
    recursive = "recursive"


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    chunk_count: int
    chunking_strategy: ChunkingStrategy