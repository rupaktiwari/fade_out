from fastapi import FastAPI

from app.db.postgres import Base, engine
from app.db import models  # noqa: F401 — registers the tables with SQLAlchemy
from app.services.vector_store_service import ensure_collection
from app.api.routes import ingestion, chat

app = FastAPI(title="Palm Mind AI — Document RAG & Booking API")

Base.metadata.create_all(bind=engine)
ensure_collection()

app.include_router(ingestion.router, tags=["Ingestion"])
app.include_router(chat.router, tags=["Chat"])


@app.get("/health")
def health_check():
    return {"status": "ok"}