from pydantic import BaseModel, EmailStr


class BookingDetails(BaseModel):
    name: str
    email: EmailStr
    date: str
    time: str