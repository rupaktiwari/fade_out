from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.booking import BookingDetails
from app.services import memory_service, booking_service, rag_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    history = memory_service.get_history(request.session_id)

    conversation_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    conversation_text += f"\nuser: {request.message}"

    booking_info = booking_service.extract_booking_intent(conversation_text)

    if booking_info.get("wants_booking"):
        missing = [f for f in ("name", "email", "date", "time") if not booking_info.get(f)]
        if missing:
            reply = f"Sure, I can help book that. Could you provide your {', '.join(missing)}?"
        else:
            try:
                details = BookingDetails(**{k: booking_info[k] for k in ("name", "email", "date", "time")})
            except ValueError:
                reply = "I couldn't quite validate those details — could you double-check your email and try again?"
            else:
                was_created = booking_service.save_booking(details)
                if was_created:
                    reply = f"Your interview is booked for {details.date} at {details.time}. A confirmation will be sent to {details.email}."
                else:
                    reply = f"You already have an interview booked for {details.date} at {details.time} — no need to book it again!"
    else:
        reply = rag_service.generate_answer(request.message, history)

    memory_service.append_message(request.session_id, "user", request.message)
    memory_service.append_message(request.session_id, "assistant", reply)

    return ChatResponse(reply=reply)