import json

from app.schemas.booking import BookingDetails
from app.services.llm_service import llm
from app.db.postgres import SessionLocal
from app.db.models import Booking


EXTRACTION_PROMPT = """You are helping schedule an interview during an ongoing conversation.

Conversation so far:
{conversation}

Based ONLY on the user's most recent message, determine if they are currently trying to book an interview
or are in the middle of providing booking details for an active booking request.
If the most recent message is unrelated to booking (e.g. a general question), set "wants_booking" to false —
even if a booking was already completed earlier in this same conversation.

Respond ONLY with valid JSON, no other text, in exactly this format:
{{"wants_booking": true or false, "name": string or null, "email": string or null, "date": string or null, "time": string or null}}
"""

def extract_booking_intent(conversation_text: str) -> dict:
    """Ask the LLM whether the user wants to book, and pull out whatever fields are present so far."""
    prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)
    response = llm.invoke(prompt)
    try:
        return json.loads(response.content.strip())
    except json.JSONDecodeError:
        return {"wants_booking": False, "name": None, "email": None, "date": None, "time": None}


def save_booking(details: BookingDetails) -> bool:
    """Write a completed booking to Postgres, skipping if an identical one already exists.
    Returns True if a new row was inserted, False if a duplicate was found and skipped.
    """
    db = SessionLocal()
    try:
        existing = db.query(Booking).filter(
            Booking.email == details.email,
            Booking.interview_date == details.date,
            Booking.interview_time == details.time,
        ).first()

        if existing:
            return False

        db.add(Booking(
            name=details.name,
            email=details.email,
            interview_date=details.date,
            interview_time=details.time,
        ))
        db.commit()
        return True
    finally:
        db.close()