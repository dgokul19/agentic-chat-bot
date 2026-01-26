"""Data models for booking agent."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import date, time


class Restaurant(BaseModel):
    """Restaurant model."""
    id: str = Field(description="Unique restaurant identifier")
    name: str = Field(description="Restaurant name")
    cuisine: str = Field(description="Cuisine type")
    location: str = Field(description="Restaurant location/address")
    description: Optional[str] = Field(default=None, description="Restaurant description")
    rating: Optional[float] = Field(default=None, description="Restaurant rating (0-5)")
    price_range: Optional[str] = Field(default=None, description="Price range ($, $$, $$$, $$$$)")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    image_url: Optional[str] = Field(default=None, description="Restaurant image URL")


class AvailabilitySlot(BaseModel):
    """Available time slot for booking."""
    date: str = Field(description="Date in YYYY-MM-DD format")
    time: str = Field(description="Time in HH:MM format")
    available: bool = Field(description="Whether slot is available")
    max_guests: Optional[int] = Field(default=None, description="Maximum guests for this slot")


class BookingRequest(BaseModel):
    """Booking request to create a reservation."""
    restaurant_id: str = Field(description="Restaurant ID")
    restaurant_name: str = Field(description="Restaurant name")
    date: str = Field(description="Booking date (YYYY-MM-DD)")
    time: str = Field(description="Booking time (HH:MM)")
    guest_count: int = Field(description="Number of guests")
    user_name: str = Field(description="Customer name")
    email: EmailStr = Field(description="Customer email")
    phone: str = Field(description="Customer phone number")


class BookingConfirmation(BaseModel):
    """Booking confirmation response."""
    confirmation_number: str = Field(description="Booking confirmation number")
    restaurant_name: str = Field(description="Restaurant name")
    date: str = Field(description="Booking date")
    time: str = Field(description="Booking time")
    guest_count: int = Field(description="Number of guests")
    user_name: str = Field(description="Customer name")
    status: Literal["confirmed", "pending", "failed"] = Field(description="Booking status")


class BookingState(BaseModel):
    """Conversation state for booking flow."""
    session_id: str = Field(description="Session identifier")
    step: Literal[
        "initial",
        "restaurant_selection",
        "restaurant_confirmation",
        "availability_check",
        "date_time_selection",
        "collecting_guest_count",
        "collecting_name",
        "collecting_email",
        "collecting_phone",
        "confirmation",
        "completed"
    ] = Field(default="initial", description="Current step in booking flow")
    
    # Restaurant selection
    restaurant_id: Optional[str] = Field(default=None, description="Selected restaurant ID")
    restaurant_name: Optional[str] = Field(default=None, description="Selected restaurant name")
    fuzzy_matches: Optional[List[Restaurant]] = Field(default=None, description="Fuzzy matched restaurants")
    
    # Availability
    available_slots: Optional[List[AvailabilitySlot]] = Field(default=None, description="Available time slots")
    
    # Booking details
    selected_date: Optional[str] = Field(default=None, description="Selected date")
    selected_time: Optional[str] = Field(default=None, description="Selected time")
    guest_count: Optional[int] = Field(default=None, description="Number of guests")
    user_name: Optional[str] = Field(default=None, description="Customer name")
    email: Optional[str] = Field(default=None, description="Customer email")
    phone: Optional[str] = Field(default=None, description="Customer phone")
    
    # Confirmation
    confirmation_number: Optional[str] = Field(default=None, description="Booking confirmation number")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "step": "initial",
                "restaurant_id": None,
                "restaurant_name": None
            }
        }
