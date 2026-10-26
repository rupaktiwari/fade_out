from langchain_groq import ChatGroq

from app.core.config import settings

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.groq_api_key,
    temperature=0,
)