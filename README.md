# Palm Mind Task — Document RAG & Interview Booking API

A FastAPI backend that ingests documents into a vector store, answers questions about them using retrieval-augmented generation (RAG), and handles interview booking as part of the same conversational flow — with persistent chat memory across turns.

## Requirements coverage

| Requirement | Status | Where |
|---|---|---|
| Upload `.pdf` / `.txt` files | ✅ | `POST /documents/upload` — `app/api/routes/ingestion.py`, text extraction in `app/services/text_extraction.py` |
| Two selectable chunking strategies | ✅ | `app/services/chunking.py` — `fixed` and `recursive`, chosen via the `chunking_strategy` request field |
| Generate embeddings & store in a vector DB (Pinecone/Qdrant/Weaviate/Milvus) | ✅ | `app/services/embedding_service.py` (HuggingFace `sentence-transformers`) → `app/services/vector_store_service.py` (**Qdrant**) |
| Save metadata in SQL/NoSQL DB | ✅ | `app/db/models.py` / `app/db/postgres.py` — document id, filename, chunk count stored in **PostgreSQL** |
| Custom RAG (no `RetrievalQAChain`) | ✅ | `app/services/rag_service.py` — manual embed → Qdrant search → hand-built prompt string → direct `llm.invoke()`; no LangChain chain abstraction used anywhere |
| Redis for chat memory | ✅ | `app/services/memory_service.py` — session history read/written per `session_id` |
| Multi-turn queries | ✅ | Full session history is passed into both the RAG prompt and the booking-intent extraction on every turn |
| Interview booking (name, email, date, time) via LLM | ✅ | `app/services/booking_service.py` — `extract_booking_intent()` uses the LLM to pull structured fields from the conversation |
| Store booking info | ✅ | `app/db/models.py` `Booking` model, persisted via `save_booking()` in PostgreSQL |
| No FAISS / Chroma | ✅ | Qdrant used instead (an explicitly permitted option) |
| No UI | ✅ | Pure REST API, no frontend |
| No `RetrievalQAChain` | ✅ | See `rag_service.py` — confirmed manual implementation |
| Clean, modular, typed code | ✅ | Responsibilities split by file (ingestion, chunking, embeddings, vector store, LLM, memory, RAG, booking); Pydantic schemas for request/response validation; type hints on all service functions |

## Architecture

- **FastAPI** — HTTP API layer
- **Qdrant** — vector store for document embeddings (collection: `documents`, 384-dim vectors, cosine distance)
- **Redis** — per-session chat history, keyed by `session_id`
- **PostgreSQL** — stores document metadata and interview bookings
- **Embeddings** — `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (HuggingFace, via `langchain-huggingface`)
- **LLM** — `openai/gpt-oss-120b`, served via Groq (`langchain-groq`), temperature 0
- **Chunking** — `langchain-text-splitters`, with a choice of `fixed`-size or `recursive` (paragraph/sentence-aware) splitting per upload

## Project structure

```
app/
├── main.py                        # FastAPI app entrypoint
├── core/
│   └── config.py                  # Settings (env vars)
├── api/routes/
│   ├── chat.py                    # POST /chat — RAG answers + booking flow
│   └── ingestion.py                # POST /documents/upload
├── db/
│   ├── models.py                  # SQLAlchemy models (Document, Booking)
│   └── postgres.py                # DB session setup
├── schemas/
│   ├── booking.py
│   ├── chat.py
│   └── document.py
└── services/
    ├── booking_service.py         # LLM-based booking intent extraction + save
    ├── chunking.py                # fixed / recursive text splitting
    ├── embedding_service.py       # HuggingFace embedding model
    ├── llm_service.py             # Groq LLM client
    ├── memory_service.py          # Redis-backed session history
    ├── rag_service.py             # retrieval + answer generation (custom, no chain)
    ├── text_extraction.py         # .txt / .pdf text extraction
    └── vector_store_service.py    # Qdrant upsert / search
```

## Setup

### 1. Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker (for Postgres, Redis, Qdrant)
- A free [Groq API key](https://console.groq.com) for the LLM

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your own Groq API key:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/palm_mind_task
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
GROQ_API_KEY=your_groq_api_key_here
```

Note: Postgres is mapped to host port **5433** (not the default 5432), to avoid colliding with a locally installed Postgres instance. Adjust `docker-compose.yml` and `DATABASE_URL` together if your setup differs.

### 4. Start the supporting services

```bash
docker compose up -d
```

This brings up Postgres, Redis, and Qdrant. Give it a few seconds to finish initializing.

### 5. Run the API

```bash
uv run uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. Interactive API docs (Swagger UI) are available at `http://localhost:8000/docs`.

## API Reference

### `POST /documents/upload`

Uploads a document (`.txt` or `.pdf`), splits it into chunks, embeds them, and stores them in Qdrant.

**Request:** `multipart/form-data`
| Field | Type | Description |
|---|---|---|
| `file` | file | `.txt` or `.pdf` document |
| `chunking_strategy` | string | `"fixed"` or `"recursive"` |

**Example:**
```bash
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@yourfile.txt" \
  -F "chunking_strategy=recursive"
```

**Response:**
```json
{"document_id": 1, "filename": "yourfile.txt", "chunk_count": 8, "chunking_strategy": "recursive"}
```

### `POST /chat`

Handles two things through one endpoint, depending on message content:
1. **General questions** — answered using RAG against whatever's been uploaded to Qdrant, using session history for context on follow-ups.
2. **Interview booking** — detects booking intent from the latest message, extracts name/email/date/time (across multiple turns if needed), confirms the booking, and prevents duplicate bookings for the same email/date/time.

**Request:** `application/json`
| Field | Type | Description |
|---|---|---|
| `session_id` | string | Client-chosen identifier grouping a conversation; reuse it to keep context, use a new one for a fresh conversation |
| `message` | string | The user's message |

**Example — RAG question:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo1", "message": "What is this document about?"}'
```

**Example — booking:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo1", "message": "Book an interview for Jane Doe, jane@example.com, 2026-11-10 at 3pm."}'
```

**Response:**
```json
{"reply": "Your interview is booked for 2026-11-10 at 3pm. A confirmation will be sent to jane@example.com."}
```

## Design notes

- **Session memory** is entirely client-driven: `session_id` is just a string you choose. The same id continues a conversation (full history pulled from Redis); a new id starts fresh with no shared state.
- **Booking intent detection** is scoped to the user's *most recent* message specifically, so an unrelated question later in the same session (after a booking is already completed) doesn't get misread as a new booking attempt just because old booking details are still present in the conversation history.
- **Duplicate booking prevention**: before inserting a new booking, the app checks for an existing row with the same email, date, and time, and skips the insert (returning a friendly message instead) if one already exists.
- **Chunking strategy** is configurable per upload (`fixed` vs `recursive`), letting you compare how each affects retrieval quality on a given document.

## Known limitations

- Duplicate-booking prevention only matches on (email, date, time) — it doesn't yet check for scheduling conflicts across different people requesting the same slot.
- No automated test suite; verified via manual end-to-end testing (document upload, RAG retrieval, multi-turn booking, cross-session isolation, invalid input handling).
- No authentication or rate limiting (out of scope for this task).