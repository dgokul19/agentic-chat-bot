"""State manager for booking conversation flow."""
from typing import Optional
from app.agents.booking.models import BookingState
from app.config import settings
import json
import logging

logger = logging.getLogger(__name__)


class BookingStateManager:
    """Manages booking conversation state per session."""
    
    def __init__(self):
        """Initialize state manager."""
        self.redis_client = None
        self.use_redis = False
        self.local_states = {}  # In-memory fallback
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection if available."""
        if settings.environment == "production":
            try:
                import redis.asyncio as aioredis
                self.redis_client = aioredis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password if settings.redis_password else None,
                    decode_responses=True
                )
                self.use_redis = True
                logger.info("Booking state manager using Redis")
            except Exception as e:
                logger.warning(f"Redis not available for state management: {e}")
                self.use_redis = False
        else:
            logger.info("Booking state manager using in-memory storage (development mode)")
            self.use_redis = False
    
    def _get_state_key(self, session_id: str) -> str:
        """Get Redis key for session state."""
        return f"booking_state:{session_id}"
    
    async def get_state(self, session_id: str) -> BookingState:
        """
        Get booking state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            BookingState object
        """
        try:
            if self.use_redis:
                key = self._get_state_key(session_id)
                state_json = await self.redis_client.get(key)
                
                if state_json:
                    state_data = json.loads(state_json)
                    return BookingState(**state_data)
                else:
                    # No state exists, create new
                    return BookingState(session_id=session_id)
            else:
                # Use local storage
                if session_id in self.local_states:
                    return self.local_states[session_id]
                else:
                    return BookingState(session_id=session_id)
                    
        except Exception as e:
            logger.error(f"Error getting booking state: {e}")
            # Return fresh state on error
            return BookingState(session_id=session_id)
    
    async def update_state(
        self,
        session_id: str,
        **updates
    ) -> BookingState:
        """
        Update booking state for a session.
        
        Args:
            session_id: Session identifier
            **updates: Fields to update
            
        Returns:
            Updated BookingState object
        """
        try:
            # Get current state
            state = await self.get_state(session_id)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            
            # Save updated state
            if self.use_redis:
                key = self._get_state_key(session_id)
                state_json = state.model_dump_json()
                # Set with 30 minute TTL
                await self.redis_client.setex(key, 1800, state_json)
            else:
                self.local_states[session_id] = state
            
            logger.info(f"Updated booking state for session {session_id}: step={state.step}")
            return state
            
        except Exception as e:
            logger.error(f"Error updating booking state: {e}")
            raise
    
    async def reset_state(self, session_id: str):
        """
        Reset booking state for a session.
        
        Args:
            session_id: Session identifier
        """
        try:
            if self.use_redis:
                key = self._get_state_key(session_id)
                await self.redis_client.delete(key)
            else:
                if session_id in self.local_states:
                    del self.local_states[session_id]
            
            logger.info(f"Reset booking state for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error resetting booking state: {e}")
    
    async def set_step(self, session_id: str, step: str) -> BookingState:
        """
        Set the current step in booking flow.
        
        Args:
            session_id: Session identifier
            step: New step name
            
        Returns:
            Updated BookingState object
        """
        return await self.update_state(session_id, step=step)
    
    def validate_step_transition(self, current_step: str, next_step: str) -> bool:
        """
        Validate if step transition is allowed.
        
        Args:
            current_step: Current step
            next_step: Proposed next step
            
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            "initial": ["restaurant_selection", "restaurant_confirmation"],
            "restaurant_selection": ["restaurant_confirmation", "availability_check"],
            "restaurant_confirmation": ["availability_check", "restaurant_selection"],
            "availability_check": ["date_time_selection"],
            "date_time_selection": ["collecting_guest_count"],
            "collecting_guest_count": ["collecting_name"],
            "collecting_name": ["collecting_email"],
            "collecting_email": ["collecting_phone"],
            "collecting_phone": ["confirmation"],
            "confirmation": ["completed", "collecting_guest_count"],  # Allow restart on confirmation
            "completed": ["initial"]  # Allow new booking
        }
        
        allowed = valid_transitions.get(current_step, [])
        return next_step in allowed


# Global instance
state_manager = BookingStateManager()
