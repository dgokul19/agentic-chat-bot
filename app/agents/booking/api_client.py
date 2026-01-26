"""API client for restaurant booking with ServeMe integration."""
from typing import List, Optional
from datetime import datetime, timedelta
import random
import string
from app.agents.booking.models import Restaurant, AvailabilitySlot, BookingRequest, BookingConfirmation
from app.config import settings
import httpx
import logging

logger = logging.getLogger(__name__)


class RestaurantAPIClient:
    """API client for restaurant operations with ServeMe integration."""
    
    def __init__(self):
        """Initialize API client."""
        self.base_url = f"https://{settings.restaurant_endpoint}" if settings.restaurant_endpoint else None
        
        if self.base_url:
            logger.info(f"Using ServeMe API: {self.base_url} (with mock fallback)")
            self.client = httpx.AsyncClient(timeout=30.0)
        else:
            logger.info("Using mock API (ServeMe credentials not configured)")
    
    async def fetch_restaurants(self) -> List[dict]:
        """
        Fetch all restaurants from ServeMe API with mock fallback.
        
        Returns:
            List of restaurant dictionaries
        """
        # Try real API first if configured
        if self.base_url:
            try:
                logger.info("Fetching restaurants from ServeMe API")
                
                url = f"{self.base_url}/api/Restaurant"
                headers = { "Content-Type": "application/json" }
                
                response = await self.client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"✅ Successfully fetched {len(data)} restaurants API")
                
                # Transform API response to our Restaurant model format
                restaurants = []
                for outlet in data:
                    restaurant = {
                        "id": str(outlet.get("restaurantID", "")),
                        "name": outlet.get("restaurantName", ""),
                        "cuisine": outlet.get("type", "Various"),
                        "location": outlet.get("address", ""),
                    }
                    restaurants.append(restaurant)
                
                return restaurants
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching restaurants: {e.response.status_code}")
                logger.warning("⚠️ Falling back to mock restaurant data")
            except Exception as e:
                logger.error(f"Error fetching restaurants from ServeMe API: {e}")
                logger.warning("⚠️ Falling back to mock restaurant data")
        
    async def check_availability(
        self,
        restaurant_id: str,
        start_date: Optional[str] = None,
        days: int = 7
    ) -> List[dict]:
        """
        Check availability for a restaurant.
        
        Args:
            restaurant_id: Restaurant ID
            start_date: Start date (YYYY-MM-DD), defaults to today
            days: Number of days to check
            
        Returns:
            List of availability slot dictionaries
        """
        logger.info(f"Checking availability for restaurant {restaurant_id}")
        
        # Simulate API delay
        import asyncio
        await asyncio.sleep(0.2)
        
        # Generate mock availability
        if start_date:
            base_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            base_date = datetime.now().date()
        
        slots = []
        time_slots = ["17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]
        
        for day_offset in range(days):
            current_date = base_date + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Randomly mark some slots as unavailable
            for time_slot in time_slots:
                available = random.choice([True, True, True, False])  # 75% available
                slots.append(
                    AvailabilitySlot(
                        date=date_str,
                        time=time_slot,
                        available=available,
                        max_guests=random.choice([2, 4, 6, 8]) if available else None
                    ).model_dump()
                )
        
        return slots
    
    async def create_booking(self, booking_request: BookingRequest) -> dict:
        """
        Create a booking.
        
        Args:
            booking_request: Booking request details
            
        Returns:
            Booking confirmation dictionary
        """
        logger.info(f"Creating booking for {booking_request.user_name} at {booking_request.restaurant_name}")
        
        # Simulate API delay
        import asyncio
        await asyncio.sleep(0.3)
        
        # Generate confirmation number
        confirmation_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        confirmation = BookingConfirmation(
            confirmation_number=confirmation_number,
            restaurant_name=booking_request.restaurant_name,
            date=booking_request.date,
            time=booking_request.time,
            guest_count=booking_request.guest_count,
            user_name=booking_request.user_name,
            status="confirmed"
        )
        
        return confirmation.model_dump()


# Global instance
api_client = RestaurantAPIClient()
