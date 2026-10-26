from langchain_huggingface import HuggingFaceEmbeddings

_embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn a list of chunks into their embedding vectors."""
    return _embedding_model.embed_documents(texts)


def embed_query(text: str) -> list[float]:
    """Turn a single search query into its embedding vector."""
    return _embedding_model.embed_query(text)