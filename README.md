# Fade Out — A RAG

A FastAPI backend for document ingestion and conversational RAG, with interview booking handled through the same chat endpoint. Documents get chunked, embedded, and stored in Qdrant; conversations are tracked per session in Redis; document metadata and bookings are stored in PostgreSQL.

## Architecture

FastAPI handles the HTTP layer. Uploaded documents are split using one of two chunking strategies, embedded with a HuggingFace sentence-transformer model (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim), and stored as vectors in Qdrant under a `documents` collection with cosine similarity.

Chat runs through a single endpoint that first checks whether the latest message looks like a booking request. If so, it extracts name, email, date, and time via an LLM call and saves the booking to Postgres. Otherwise, it falls back to retrieval-augmented generation: embed the question, pull the top matching chunks from Qdrant, and generate an answer with the LLM, grounded in that retrieved text rather than a prebuilt chain abstraction. The LLM itself is `openai/gpt-oss-120b`, served through Groq.

Each conversation's history lives in Redis, keyed by a client-supplied `session_id`, so follow-up questions and multi-turn booking both work without the client having to resend prior context.

**Document ingestion:**

```mermaid
flowchart LR
    Client["Client<br/>POST /documents/upload"] --> Ingestion["ingestion.py<br/>upload_document()"]
    Ingestion --> Extract["text_extraction.py<br/>extract_text()"]
    Extract --> Chunk["chunking.py<br/>fixed / recursive"]
    Chunk --> Embed["embedding_service.py<br/>MiniLM, 384-dim"]
    Embed --> VectorStore["vector_store_service.py<br/>upsert_chunks()"]

    Ingestion -.->|INSERT Document row| Postgres[("PostgreSQL<br/>documents table")]
    VectorStore -.->|store vectors| Qdrant[("Qdrant<br/>documents collection")]
```

**Chat — booking and RAG branch from the same endpoint:**

```mermaid
flowchart TD
    Client["Client<br/>POST /chat"] --> Chat["chat.py<br/>chat()"]
    Chat --> Redis1["Redis<br/>get_history()"]
    Redis1 --> Booking["booking_service.py<br/>extract_booking_intent()<br/>Groq LLM call"]
    Booking -->|wants_booking: true| SaveBooking["booking_service.py<br/>save_booking()<br/>→ Postgres, with dedup check"]
    Booking -->|wants_booking: false| RAG["rag_service.py<br/>① Qdrant search()<br/>② Groq llm.invoke()"]
    SaveBooking --> Reply["chat.py<br/>build reply"]
    RAG --> Reply
    Reply --> Redis2["Redis<br/>append_message() x2"]
    Redis2 --> Done["Client<br/>ChatResponse"]

    classDef llm stroke:#a8541f,stroke-width:2px;
    class Booking,RAG llm;
```

The two outlined boxes are where the app actually calls the LLM — everything else is deterministic code.

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
- A free [Groq API key](https://console.groq.com)

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your own Groq API key:

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/palm_mind_task
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
GROQ_API_KEY=your_groq_api_key_here
```

Postgres is mapped to host port 5433 instead of the default 5432, since many dev machines already run Postgres locally on that port. Change `docker-compose.yml` and `DATABASE_URL` together if that's not an issue for you.

### 4. Start the supporting services

```bash
docker compose up -d
```

Gives Postgres, Redis, and Qdrant a few seconds to initialize before the app connects to them.

### 5. Run the API

```bash
uv run uvicorn app.main:app --reload
```

The server runs at `http://localhost:8000`. Swagger docs are at `http://localhost:8000/docs`.

## API Reference

### `POST /documents/upload`

Uploads a `.txt` or `.pdf` document, chunks it, embeds the chunks, and stores them in Qdrant.

| Field | Type | Description |
|---|---|---|
| `file` | file | `.txt` or `.pdf` document |
| `chunking_strategy` | string | `"fixed"` or `"recursive"` |

```bash
curl -X POST "http://localhost:8000/documents/upload" \
  -F "file=@yourfile.txt" \
  -F "chunking_strategy=recursive"
```

```json
{"document_id": 1, "filename": "yourfile.txt", "chunk_count": 8, "chunking_strategy": "recursive"}
```

### `POST /chat`

One endpoint, two behaviors depending on the message. A general question gets answered via RAG against whatever's been uploaded. A booking request gets its name/email/date/time extracted (across multiple turns if needed), confirmed, and saved — duplicate bookings for the same email/date/time are caught and rejected rather than re-inserted.

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Identifier for this conversation. Reuse it to continue; use a new one for a fresh conversation with no shared history |
| `message` | string | The user's message |

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo1", "message": "What is this document about?"}'
```

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo1", "message": "Book an interview for Jane Doe, jane@example.com, 2026-11-10 at 3pm."}'
```

```json
{"reply": "Your interview is booked for 2026-11-10 at 3pm. A confirmation will be sent to jane@example.com."}
```

## Design notes

The booking-intent check looks only at the user's most recent message, not the conversation as a whole. Early on, this caused a real bug: once a booking was completed, any later unrelated question in the same session still got misread as a new booking attempt, because the old booking's details were still sitting in the history. Scoping the check to the latest message fixed that, and a duplicate check (matching on email, date, and time) now catches re-triggered bookings before they hit the database as a second row.

`session_id` is entirely client-driven — it's just a string the caller picks, with no server-side session creation. This keeps the API simple but means there's no built-in session expiry beyond Redis's own TTL on the stored history (24 hours).

## Known limitations

- Duplicate-booking prevention matches on (email, date, time) only — it doesn't check for scheduling conflicts between different people requesting the same slot.
- Conversation history is sent to the LLM in full on every message, with no truncation or summarization. A long-running session's prompt grows unbounded until Redis's 24-hour TTL expires or the model's context window is exceeded.
- No automated test suite — verified through manual end-to-end testing (document upload, RAG retrieval, multi-turn booking, cross-session isolation, invalid input handling).
- No authentication or rate limiting (out of scope for this task).
