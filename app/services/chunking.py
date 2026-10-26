from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.schemas.document import ChunkingStrategy


def chunk_text(
    text: str,
    strategy: ChunkingStrategy,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    if strategy == ChunkingStrategy.fixed:
        return _fixed_size_chunks(text, chunk_size, chunk_overlap)
    elif strategy == ChunkingStrategy.recursive:
        return _recursive_chunks(text, chunk_size, chunk_overlap)
    raise ValueError(f"Unknown chunking strategy: {strategy}")


def _fixed_size_chunks(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Blind sliding window: cuts every N characters, no regard for sentence/word boundaries."""
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - chunk_overlap
    return [c for c in chunks if c.strip()]


def _recursive_chunks(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Structure-aware: tries to split on paragraph, then sentence, then word boundaries first."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)