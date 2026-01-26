"""Enhanced Booking Agent with multi-step conversation flow."""
from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentRequest, AgentResponse
from app.agents.booking.restaurant_service import restaurant_service
from app.agents.booking.state_manager import state_manager
from app.agents.booking.api_client import api_client
from app.agents.booking.models import BookingRequest
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class BookingAgent(BaseAgent):
    """Enhanced booking agent with state-based conversation flow."""
    
    def __init__(self):
        super().__init__(
            name="Booking Agent",
            description="Specialized in restaurant search, reservations, and dining recommendations"
        )
    
    def get_capabilities(self) -> str:
        """Get agent capabilities description."""
        return """I can help you with:
- Finding and browsing restaurants
- Making restaurant reservations
- Checking availability
- Managing booking details
"""
    
    def get_system_prompt(self) -> str:
        """Get custom system prompt for the Booking Agent's LLM."""
        return """You are the Booking Agent, a specialized AI assistant for restaurant reservations.

Your capabilities:
- Finding and browsing restaurants
- Making restaurant reservations
- Checking availability
- Managing booking details

IMPORTANT INSTRUCTIONS:
1. **Be Concise**: Keep responses brief and to the point. Avoid unnecessary explanations.

2. **Restaurant Listing**:
   - When listing restaurants, return only the name and cuisine type
   - Do not add extra commentary or explanations
   - List all the restaurants one by one

3. **Restaurant Name Extraction**:
   - When extracting restaurant names, be precise and return only the name
   - If no restaurant is mentioned, return "NONE" exactly
   - Do not add extra commentary or explanations

4. **Date and Time Parsing**:
   - Always return dates in YYYY-MM-DD format
   - Always return times in HH:MM 24-hour format
   - Handle natural language like "tomorrow", "next Friday", "7 PM" correctly
   - If you cannot extract both date AND time, return null for both

5. **JSON Responses**:
   - When asked to return JSON, return ONLY valid JSON with no additional text
   - Do not wrap JSON in markdown code blocks
   - Do not add explanations before or after the JSON

6. **Error Handling**:
   - If you cannot understand something, ask for clarification clearly
   - Do not make assumptions about missing information

Remember: Your responses are used programmatically, so precision and format adherence are critical.
"""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process booking requests with state-based workflow.
        
        Args:
            request: Agent request with query and context
            
        Returns:
            Agent response with booking information
        """
        try:
            logger.info(f"Booking Agent processing: {request.query}")
            
            # Get current booking state
            state = await state_manager.get_state(request.session_id)
            logger.info(f"Current booking state: {state.step}")
            
            # Route to appropriate handler based on current step
            if state.step == "initial":
                return await self._handle_initial_request(request, state)
            elif state.step == "restaurant_selection":
                return await self._handle_restaurant_selection(request, state)
            elif state.step == "restaurant_confirmation":
                return await self._handle_restaurant_confirmation(request, state)
            elif state.step == "date_time_selection":
                return await self._handle_datetime_selection(request, state)
            elif state.step == "collecting_guest_count":
                return await self._handle_guest_count(request, state)
            elif state.step == "collecting_name":
                return await self._handle_name(request, state)
            elif state.step == "collecting_email":
                return await self._handle_email(request, state)
            elif state.step == "collecting_phone":
                return await self._handle_phone(request, state)
            elif state.step == "confirmation":
                return await self._handle_confirmation(request, state)
            else:
                # Unknown state, reset
                await state_manager.reset_state(request.session_id)
                return await self._handle_initial_request(request, state)
                
        except Exception as e:
            logger.error(f"Error in Booking Agent: {e}", exc_info=True)
            return AgentResponse(
                agent_name=self.name,
                content="I apologize, but I encountered an error. Let's start over. Would you like to book a table?",
                metadata={"error": str(e)},
                requires_followup=True
            )
    
    async def _handle_initial_request(self, request: AgentRequest, state) -> AgentResponse:
        """Handle initial booking request."""
        query = request.query.lower()
        
        # Try to extract restaurant name from query
        restaurant_name = await self._extract_restaurant_name(query)
        
        if restaurant_name:
            # Scenario 2 & 3: User mentioned a specific restaurant
            return await self._handle_specific_restaurant(request, restaurant_name)
        else:
            # Scenario 1: Generic booking request
            return await self._list_all_restaurants(request)
    
    async def _extract_restaurant_name(self, query: str) -> str:
        """Extract restaurant name from query using LLM."""
        # Use LLM to extract restaurant name
        extraction_prompt = f"""Extract the restaurant name from this query if mentioned. 
If no restaurant name is mentioned, respond with "NONE".
Only return the restaurant name or "NONE", nothing else.

Query: "{query}"

Restaurant name:"""
        
        try:
            messages = [{"role": "user", "content": extraction_prompt}]
            response = await self.llm.generate_response(messages, system_prompt=self.get_system_prompt())
            restaurant_name = response.strip()
            
            if restaurant_name.upper() == "NONE" or not restaurant_name:
                return None
            
            return restaurant_name
        except Exception as e:
            logger.error(f"Error extracting restaurant name: {e}")
            return None
    
    async def _handle_specific_restaurant(self, request: AgentRequest, restaurant_name: str) -> AgentResponse:
        """Handle request with specific restaurant name (Scenario 2 & 3)."""
        # Try fuzzy matching
        matched_restaurant = await restaurant_service.find_restaurant_by_name(restaurant_name, threshold=75.0)
        
        if matched_restaurant:
            # High confidence match
            await state_manager.update_state(
                request.session_id,
                step="restaurant_confirmation",
                restaurant_id=matched_restaurant.id,
                restaurant_name=matched_restaurant.name
            )
            
            content = f"I found **{matched_restaurant.name}** ({matched_restaurant.cuisine}, {matched_restaurant.location}). Is this the restaurant you'd like to book?"
            
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "restaurant_confirmation", "restaurant_id": matched_restaurant.id},
                requires_followup=True
            )
        else:
            # No good match, try to find similar ones
            similar = await restaurant_service.find_similar_restaurants(restaurant_name, limit=3, threshold=60.0)
            
            if similar:
                # Show similar options
                await state_manager.update_state(
                    request.session_id,
                    step="restaurant_selection",
                    fuzzy_matches=[r for r, score in similar]
                )
                
                content = f"I couldn't find an exact match for '{restaurant_name}'. Did you mean one of these?\n\n"
                for idx, (restaurant, score) in enumerate(similar, 1):
                    content += f"{idx}. **{restaurant.name}** - {restaurant.cuisine}, {restaurant.location}\n"
                content += "\nPlease select a restaurant by number or name."
                
                return AgentResponse(
                    agent_name=self.name,
                    content=content,
                    metadata={"intent": "restaurant_selection", "fuzzy_matches": len(similar)},
                    requires_followup=True
                )
            else:
                # No matches at all, show all restaurants
                return await self._list_all_restaurants(request)
    
    async def _list_all_restaurants(self, request: AgentRequest) -> AgentResponse:
        """List all available restaurants (Scenario 1)."""
        restaurants = await restaurant_service.get_all_restaurants()
        
        if not restaurants:
            content = "I apologize, but I couldn't retrieve the restaurant list at the moment. Please try again later."
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"error": "no_restaurants"},
                requires_followup=False
            )
        
        # Update state
        await state_manager.update_state(request.session_id, step="restaurant_selection")
        
        # Format restaurant list - display one by one with details
        content = "I'd be happy to help you book a table! Here are our available restaurants:\n\n"
        
        for idx, restaurant in enumerate(restaurants, 1):
            content += f"**{idx}. {restaurant.name}**  \n"
            content += f"• Cuisine: {restaurant.cuisine}  \n"
            content += f"• Location: {restaurant.location}  \n"
            if restaurant.rating:
                content += f"• Rating: ⭐ {restaurant.rating}  \n"
            if restaurant.price_range:
                content += f"• Price: {restaurant.price_range}  \n"
            if restaurant.description:
                content += f"• {restaurant.description}  \n"
            content += "\n"
        
        content += "Please select a restaurant by number or name."
        
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"intent": "restaurant_list", "count": len(restaurants)},
            requires_followup=True
        )
    
    async def _handle_restaurant_selection(self, request: AgentRequest, state) -> AgentResponse:
        """Handle restaurant selection from list."""
        query = request.query.strip()
        
        # Try to parse as number
        if query.isdigit():
            selection_num = int(query)
            restaurants = await restaurant_service.get_all_restaurants()
            
            if 1 <= selection_num <= len(restaurants):
                selected = restaurants[selection_num - 1]
                return await self._proceed_with_restaurant(request, selected)
        
        # Try to match by name
        matched = await restaurant_service.find_restaurant_by_name(query, threshold=70.0)
        if matched:
            return await self._proceed_with_restaurant(request, matched)
        
        # Couldn't understand selection
        content = "I didn't quite catch that. Please select a restaurant by entering its number (1, 2, 3...) or name."
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"error": "invalid_selection"},
            requires_followup=True
        )
    
    async def _handle_restaurant_confirmation(self, request: AgentRequest, state) -> AgentResponse:
        """Handle confirmation of fuzzy-matched restaurant."""
        query = request.query.lower()
        
        # Check for positive confirmation
        if any(word in query for word in ["yes", "yeah", "yep", "correct", "right", "sure"]):
            # Confirmed, proceed to availability
            restaurant = await restaurant_service.get_restaurant_by_id(state.restaurant_id)
            return await self._proceed_with_restaurant(request, restaurant)
        elif any(word in query for word in ["no", "nope", "wrong", "different"]):
            # Not confirmed, show all restaurants
            await state_manager.update_state(request.session_id, step="initial")
            return await self._list_all_restaurants(request)
        else:
            # Unclear response
            content = "Please confirm: Is this the correct restaurant? (Yes/No)"
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "confirmation_needed"},
                requires_followup=True
            )
    
    async def _proceed_with_restaurant(self, request: AgentRequest, restaurant) -> AgentResponse:
        """Proceed with selected restaurant - check availability."""
        # Fetch availability
        availability_data = await api_client.check_availability(restaurant.id)
        
        # Filter only available slots
        from app.agents.booking.models import AvailabilitySlot
        available_slots = [AvailabilitySlot(**slot) for slot in availability_data if slot["available"]]
        
        if not available_slots:
            content = f"I'm sorry, but **{restaurant.name}** doesn't have any available slots at the moment. Would you like to choose a different restaurant?"
            await state_manager.update_state(request.session_id, step="initial")
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"error": "no_availability"},
                requires_followup=True
            )
        
        # Update state with restaurant and availability
        await state_manager.update_state(
            request.session_id,
            step="date_time_selection",
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            available_slots=available_slots
        )
        
        # Format availability by date
        slots_by_date = {}
        for slot in available_slots[:21]:  # Show first 3 days (7 slots per day)
            if slot.date not in slots_by_date:
                slots_by_date[slot.date] = []
            slots_by_date[slot.date].append(slot.time)
        
        content = f"Great choice! **{restaurant.name}** has the following availability:\n\n"
        for date, times in list(slots_by_date.items())[:3]:
            # Format date nicely
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%A, %B %d")
            content += f"**{formatted_date}**: {', '.join(times[:5])}\n"
        
        content += "\nPlease tell me your preferred date and time (e.g., 'Tomorrow at 7 PM' or '2026-01-25 at 19:00')."
        
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"intent": "availability_shown", "restaurant_id": restaurant.id},
            requires_followup=True
        )
    
    async def _handle_datetime_selection(self, request: AgentRequest, state) -> AgentResponse:
        """Handle date and time selection."""
        # Use LLM to extract date and time
        extracted = await self._extract_datetime(request.query)
        
        if not extracted or not extracted.get("date") or not extracted.get("time"):
            content = "I couldn't understand the date and time. Please specify like 'Tomorrow at 7 PM' or '2026-01-25 at 19:00'."
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"error": "invalid_datetime"},
                requires_followup=True
            )
        
        # Validate against available slots
        selected_date = extracted["date"]
        selected_time = extracted["time"]
        
        # Check if slot is available
        slot_available = any(
            slot.date == selected_date and slot.time == selected_time and slot.available
            for slot in state.available_slots
        )
        
        if not slot_available:
            content = f"I'm sorry, but {selected_date} at {selected_time} is not available. Please choose from the available times shown above."
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"error": "slot_unavailable"},
                requires_followup=True
            )
        
        # Update state and ask for guest count
        await state_manager.update_state(
            request.session_id,
            step="collecting_guest_count",
            selected_date=selected_date,
            selected_time=selected_time
        )
        
        content = f"Perfect! I'll reserve a table for {selected_date} at {selected_time}. How many guests will be joining you?"
        
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"intent": "datetime_confirmed"},
            requires_followup=True
        )
    
    async def _extract_datetime(self, query: str) -> dict:
        """Extract date and time from query using LLM."""
        prompt = f"""Extract the date and time from this query.
Return ONLY a JSON object with "date" (YYYY-MM-DD format) and "time" (HH:MM format).
If you cannot extract both, return {{"date": null, "time": null}}.

Today is {datetime.now().strftime("%Y-%m-%d")}.

Query: "{query}"

JSON:"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.generate_response(messages, system_prompt=self.get_system_prompt())
            
            # Parse JSON response
            import json
            result = json.loads(response.strip())
            return result
        except Exception as e:
            logger.error(f"Error extracting datetime: {e}")
            return {}
    
    async def _handle_guest_count(self, request: AgentRequest, state) -> AgentResponse:
        """Handle guest count collection."""
        # Extract number from query
        numbers = re.findall(r'\d+', request.query)
        
        if numbers:
            guest_count = int(numbers[0])
            
            if 1 <= guest_count <= 20:
                await state_manager.update_state(
                    request.session_id,
                    step="collecting_name",
                    guest_count=guest_count
                )
                
                content = f"Table for {guest_count}, noted! May I have your name please?"
                return AgentResponse(
                    agent_name=self.name,
                    content=content,
                    metadata={"intent": "guest_count_collected"},
                    requires_followup=True
                )
        
        content = "Please provide the number of guests (e.g., '4 people' or just '4')."
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"error": "invalid_guest_count"},
            requires_followup=True
        )
    
    async def _handle_name(self, request: AgentRequest, state) -> AgentResponse:
        """Handle name collection."""
        name = request.query.strip()
        
        if len(name) >= 2:
            await state_manager.update_state(
                request.session_id,
                step="collecting_email",
                user_name=name
            )
            
            content = f"Thank you, {name}! What's the best email to send the confirmation?"
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "name_collected"},
                requires_followup=True
            )
        
        content = "Please provide your name."
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"error": "invalid_name"},
            requires_followup=True
        )
    
    async def _handle_email(self, request: AgentRequest, state) -> AgentResponse:
        """Handle email collection."""
        email = request.query.strip()
        
        # Basic email validation
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            await state_manager.update_state(
                request.session_id,
                step="collecting_phone",
                email=email
            )
            
            content = "Got it! And your phone number?"
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "email_collected"},
                requires_followup=True
            )
        
        content = "Please provide a valid email address."
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"error": "invalid_email"},
            requires_followup=True
        )
    
    async def _handle_phone(self, request: AgentRequest, state) -> AgentResponse:
        """Handle phone collection and show confirmation."""
        phone = request.query.strip()
        
        # Basic phone validation (digits and common separators)
        if re.match(r'^[\d\s\-\(\)]+$', phone) and len(re.findall(r'\d', phone)) >= 10:
            await state_manager.update_state(
                request.session_id,
                step="confirmation",
                phone=phone
            )
            
            # Show booking summary
            content = f"""Let me confirm your booking details:

**Restaurant**: {state.restaurant_name}
**Date**: {state.selected_date}
**Time**: {state.selected_time}
**Guests**: {state.guest_count}
**Name**: {state.user_name}
**Email**: {state.email}
**Phone**: {phone}

Is this correct? (Yes/No)"""
            
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "confirmation_shown"},
                requires_followup=True
            )
        
        content = "Please provide a valid phone number."
        return AgentResponse(
            agent_name=self.name,
            content=content,
            metadata={"error": "invalid_phone"},
            requires_followup=True
        )
    
    async def _handle_confirmation(self, request: AgentRequest, state) -> AgentResponse:
        """Handle final confirmation and create booking."""
        query = request.query.lower()
        
        if any(word in query for word in ["yes", "yeah", "yep", "correct", "confirm"]):
            # Create booking
            booking_request = BookingRequest(
                restaurant_id=state.restaurant_id,
                restaurant_name=state.restaurant_name,
                date=state.selected_date,
                time=state.selected_time,
                guest_count=state.guest_count,
                user_name=state.user_name,
                email=state.email,
                phone=state.phone
            )
            
            confirmation = await api_client.create_booking(booking_request)
            
            # Update state to completed
            await state_manager.update_state(
                request.session_id,
                step="completed",
                confirmation_number=confirmation["confirmation_number"]
            )
            
            content = f"""🎉 Excellent! Your booking is confirmed!

**Confirmation Number**: {confirmation['confirmation_number']}
**Restaurant**: {state.restaurant_name}
**Date**: {state.selected_date}
**Time**: {state.selected_time}
**Guests**: {state.guest_count}

You'll receive a confirmation email at {state.email} shortly.
Looking forward to seeing you at {state.restaurant_name}!"""
            
            # Reset state after a moment
            import asyncio
            asyncio.create_task(self._reset_state_delayed(request.session_id))
            
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={
                    "intent": "booking_confirmed",
                    "confirmation_number": confirmation["confirmation_number"]
                },
                requires_followup=False
            )
        elif any(word in query for word in ["no", "nope", "wrong", "change"]):
            # User wants to change something
            await state_manager.update_state(request.session_id, step="collecting_guest_count")
            content = "No problem! Let's update your details. How many guests will be joining you?"
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "restart_details"},
                requires_followup=True
            )
        else:
            content = "Please confirm: Is the booking information correct? (Yes/No)"
            return AgentResponse(
                agent_name=self.name,
                content=content,
                metadata={"intent": "confirmation_needed"},
                requires_followup=True
            )
    
    async def _reset_state_delayed(self, session_id: str):
        """Reset state after a delay."""
        import asyncio
        await asyncio.sleep(5)
        await state_manager.reset_state(session_id)


# Global booking agent instance
booking_agent = BookingAgent()
