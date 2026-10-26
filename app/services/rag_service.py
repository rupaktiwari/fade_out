from app.services.embedding_service import embed_query
from app.services.vector_store_service import search
from app.services.llm_service import llm


def generate_answer(question: str, chat_history: list[dict]) -> str:
    """Retrieve relevant chunks, build a prompt manually, and call the LLM directly — no chain abstraction."""
    query_embedding = embed_query(question)
    retrieved_chunks = search(query_embedding, top_k=3)

    context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "No relevant context found."

    history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in chat_history)

    prompt = f"""You are a helpful assistant. Use the context below to answer the user's question.
If the context doesn't contain the answer, say you don't know — don't make things up.

Context:
{context}

Conversation so far:
{history_text}

User's question:
{question}

Answer:"""

    response = llm.invoke(prompt)
    return response.content.strip()