"""Booking executor agent for restaurant reservation execution."""
from app.agents.base_executor import BaseExecutor
from app.models.plan_schemas import (
    ExecutorRequest, ExecutorResponse, ActionPlan, ActionStep
)
from app.agents.booking.restaurant_service import restaurant_service
from app.agents.booking.api_client import api_client
from app.agents.booking.state_manager import state_manager
from app.agents.booking.models import BookingRequest, Restaurant
from typing import Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class BookingExecutor(BaseExecutor):
    """Executor agent for restaurant booking domain."""
    
    def __init__(self):
        """Initialize the booking executor."""
        super().__init__(
            domain="booking",
            description="Executes restaurant reservation workflows including search, validation, and booking creation"
        )
        self.execution_context = {}  # Store execution state per session
    
    def get_execution_capabilities(self) -> str:
        """Get booking executor capabilities."""
        return """I can execute:
- Restaurant searches and lookups
- Table availability checks
- Customer information collection
- Reservation creation and confirmation
- Multi-step booking workflows
"""
    
    async def execute(self, request: ExecutorRequest) -> ExecutorResponse:
        """
        Execute a booking action plan.
        
        Args:
            request: Executor request with plan and optional user input
            
        Returns:
            Executor response with results
        """
        try:
            # Get or initialize execution context
            session_id = request.session_id
            if session_id not in self.execution_context:
                self.execution_context[session_id] = {
                    "completed_steps": [],
                    "collected_data": {},
                    "plan_id": request.plan.plan_id
                }
            
            context = self.execution_context[session_id]
            
            # Get booking state
            booking_state = await state_manager.get_state(session_id)
            context["booking_state"] = booking_state
            
            # Determine current step
            if request.current_step_id:
                # Continue from current step with user input
                current_step = next(
                    (s for s in request.plan.steps if s.step_id == request.current_step_id),
                    None
                )
                if current_step and request.user_input:
                    # Process user input for current step
                    execution_result = await self._process_user_input(
                        current_step,
                        request.user_input,
                        context
                    )
                    
                    if execution_result.get("success"):
                        context["completed_steps"].append(current_step.step_id)
            
            # Get next step to execute
            next_step = self._get_next_step(
                request.plan,
                context["completed_steps"],
                request.current_step_id
            )
            
            if not next_step:
                # Plan completed
                return await self._create_completion_response(request.plan, context)
            
            # Execute the next step
            execution_result = await self._execute_step(
                next_step,
                request.user_input,
                context
            )
            
            # Generate response
            response_content = await self._generate_response(
                next_step,
                execution_result,
                context
            )
            
            # Determine if step is complete or needs user input
            if execution_result.get("success") and not execution_result.get("requires_user_input"):
                context["completed_steps"].append(next_step.step_id)
                
                # Get the next step after this one
                following_step = self._get_next_step(
                    request.plan,
                    context["completed_steps"],
                    next_step.step_id
                )
                
                return ExecutorResponse(
                    content=response_content,
                    completed_steps=context["completed_steps"],
                    current_step_id=next_step.step_id,
                    next_step_id=following_step.step_id if following_step else None,
                    plan_completed=self._is_plan_complete(request.plan, context["completed_steps"]),
                    requires_user_input=following_step is not None and following_step.action_type == "collect_info",
                    metadata={
                        "step_type": next_step.action_type,
                        "collected_data": context.get("collected_data", {})
                    }
                )
            else:
                # Step needs user input
                return ExecutorResponse(
                    content=response_content,
                    completed_steps=context["completed_steps"],
                    current_step_id=next_step.step_id,
                    next_step_id=next_step.step_id,
                    plan_completed=False,
                    requires_user_input=True,
                    metadata={
                        "step_type": next_step.action_type,
                        "awaiting_input": execution_result.get("awaiting_input", "user_response")
                    }
                )
            
        except Exception as e:
            logger.error(f"Error in booking executor: {e}")
            return await self._handle_error(e, next_step if 'next_step' in locals() else None, request.context)
    
    async def _execute_step(
        self,
        step: ActionStep,
        user_input: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single booking step."""
        logger.info(f"Executing booking step: {step.step_id} - {step.action_type}")
        
        if step.action_type == "search":
            return await self._execute_search(step, context)
        elif step.action_type == "validate":
            return await self._execute_validation(step, context)
        elif step.action_type == "collect_info":
            return await self._execute_collection(step, user_input, context)
        elif step.action_type == "execute":
            return await self._execute_booking(step, context)
        else:
            return {
                "success": False,
                "message": f"Unknown action type: {step.action_type}",
                "requires_user_input": False
            }
    
    async def _execute_search(
        self,
        step: ActionStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute restaurant search."""
        try:
            restaurant_name = step.metadata.get("restaurant_name")
            
            if restaurant_name:
                # Search for specific restaurant
                restaurant = await restaurant_service.find_restaurant_by_name(restaurant_name)
                
                if restaurant:
                    # Store in context
                    context["collected_data"]["restaurant_id"] = restaurant.id
                    context["collected_data"]["restaurant_name"] = restaurant.name
                    context["selected_restaurant"] = restaurant
                    
                    # Update booking state
                    await state_manager.update_state(
                        context["booking_state"].session_id,
                        restaurant_id=restaurant.id,
                        restaurant_name=restaurant.name,
                        step="restaurant_confirmation"
                    )
                    
                    return {
                        "success": True,
                        "restaurant": restaurant,
                        "message": f"Found {restaurant.name}",
                        "requires_user_input": False
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Could not find restaurant '{restaurant_name}'",
                        "requires_user_input": True,
                        "awaiting_input": "restaurant_name"
                    }
            else:
                # General search - list all restaurants
                restaurants = await restaurant_service.get_all_restaurants()
                context["available_restaurants"] = restaurants
                
                return {
                    "success": True,
                    "restaurants": restaurants,
                    "message": "Here are available restaurants",
                    "requires_user_input": True,
                    "awaiting_input": "restaurant_selection"
                }
                
        except Exception as e:
            logger.error(f"Error in search execution: {e}")
            return {
                "success": False,
                "message": "Error searching for restaurants",
                "requires_user_input": False
            }
    
    async def _execute_validation(
        self,
        step: ActionStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute availability validation."""
        try:
            collected = context.get("collected_data", {})
            
            # Check if we have all required data
            is_valid, missing = self._validate_required_data(step, collected)
            
            if not is_valid:
                return {
                    "success": False,
                    "message": f"Missing required information: {', '.join(missing)}",
                    "requires_user_input": True,
                    "awaiting_input": missing[0]
                }
            
            # Check availability
            restaurant_id = collected.get("restaurant_id")
            date = collected.get("date")
            time = collected.get("time")
            party_size = collected.get("party_size")
            
            is_available = await api_client.check_availability(
                restaurant_id=restaurant_id,
                date=date,
                time=time,
                party_size=party_size
            )
            
            if is_available:
                return {
                    "success": True,
                    "available": True,
                    "message": "Table is available!",
                    "requires_user_input": False
                }
            else:
                return {
                    "success": False,
                    "available": False,
                    "message": "Sorry, no tables available for that time. Please choose a different time.",
                    "requires_user_input": True,
                    "awaiting_input": "datetime"
                }
                
        except Exception as e:
            logger.error(f"Error in validation execution: {e}")
            return {
                "success": False,
                "message": "Error checking availability",
                "requires_user_input": False
            }
    
    async def _execute_collection(
        self,
        step: ActionStep,
        user_input: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute information collection."""
        # This step always requires user input
        required_fields = step.required_data
        
        if not required_fields:
            return {
                "success": True,
                "message": "No information needed",
                "requires_user_input": False
            }
        
        # Determine what to ask for
        collected = context.get("collected_data", {})
        missing_fields = [f for f in required_fields if f not in collected]
        
        if missing_fields:
            field = missing_fields[0]
            return {
                "success": False,
                "message": self._get_collection_prompt(field),
                "requires_user_input": True,
                "awaiting_input": field
            }
        else:
            return {
                "success": True,
                "message": "All information collected",
                "requires_user_input": False
            }
    
    async def _execute_booking(
        self,
        step: ActionStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the actual booking creation."""
        try:
            collected = context.get("collected_data", {})
            
            # Validate all required data is present
            is_valid, missing = self._validate_required_data(step, collected)
            
            if not is_valid:
                return {
                    "success": False,
                    "message": f"Cannot create booking: missing {', '.join(missing)}",
                    "requires_user_input": True
                }
            
            # Create booking request
            booking_request = BookingRequest(
                restaurant_id=collected["restaurant_id"],
                restaurant_name=collected["restaurant_name"],
                date=collected["date"],
                time=collected["time"],
                guest_count=int(collected["party_size"]),
                user_name=collected["name"],
                email=collected["email"],
                phone=collected["phone"]
            )
            
            # Submit booking
            confirmation = await api_client.create_booking(booking_request)
            
            if confirmation and confirmation.status == "confirmed":
                # Update state
                await state_manager.update_state(
                    context["booking_state"].session_id,
                    confirmation_number=confirmation.confirmation_number,
                    step="completed"
                )
                
                context["confirmation"] = confirmation
                
                return {
                    "success": True,
                    "confirmation": confirmation,
                    "message": "Booking created successfully!",
                    "requires_user_input": False
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to create booking. Please try again.",
                    "requires_user_input": False
                }
                
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return {
                "success": False,
                "message": "Error creating booking",
                "requires_user_input": False
            }
    
    async def _process_user_input(
        self,
        step: ActionStep,
        user_input: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process user input for a collection step."""
        collected = context.get("collected_data", {})
        
        # Determine what we're collecting based on step metadata or description
        if "date" in step.required_data or "time" in step.required_data:
            # Extract date/time from input
            datetime_info = await self._extract_datetime(user_input)
            if datetime_info.get("date"):
                collected["date"] = datetime_info["date"]
            if datetime_info.get("time"):
                collected["time"] = datetime_info["time"]
        
        if "party_size" in step.required_data or "guest_count" in step.required_data:
            # Extract number
            party_size = self._extract_number(user_input)
            if party_size:
                collected["party_size"] = party_size
                collected["guest_count"] = party_size
        
        if "name" in step.required_data:
            collected["name"] = user_input.strip()
        
        if "email" in step.required_data:
            email = self._extract_email(user_input)
            if email:
                collected["email"] = email
        
        if "phone" in step.required_data:
            phone = self._extract_phone(user_input)
            if phone:
                collected["phone"] = phone
        
        if "selected_restaurant" in step.required_data:
            # Handle restaurant selection from list
            selection = self._extract_number(user_input)
            if selection and "available_restaurants" in context:
                restaurants = context["available_restaurants"]
                if 0 < selection <= len(restaurants):
                    restaurant = restaurants[selection - 1]
                    collected["restaurant_id"] = restaurant.id
                    collected["restaurant_name"] = restaurant.name
                    context["selected_restaurant"] = restaurant
        
        context["collected_data"] = collected
        
        return {"success": True, "collected_data": collected}
    
    async def _extract_datetime(self, text: str) -> Dict[str, str]:
        """Extract date and time from text using LLM."""
        prompt = f"""Extract the date and time from this text: "{text}"

Return in JSON format:
{{
    "date": "YYYY-MM-DD",
    "time": "HH:MM"
}}

If date or time is not found, use null for that field.
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.generate_response(messages=messages)
            
            import json
            result = json.loads(response)
            return result
        except Exception as e:
            logger.error(f"Error extracting datetime: {e}")
            return {}
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract a number from text."""
        import re
        match = re.search(r'\d+', text)
        return int(match.group()) if match else None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email from text."""
        import re
        match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        return match.group() if match else None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number from text."""
        import re
        # Remove common separators and extract digits
        digits = re.sub(r'[^\d]', '', text)
        if len(digits) >= 10:
            return digits[-10:]  # Last 10 digits
        return None
    
    def _get_collection_prompt(self, field: str) -> str:
        """Get prompt for collecting a specific field."""
        prompts = {
            "date": "What date would you like to make the reservation?",
            "time": "What time would you prefer?",
            "party_size": "How many guests will be dining?",
            "guest_count": "How many people will be joining you?",
            "name": "May I have your name for the reservation?",
            "email": "What email address should we use for the confirmation?",
            "phone": "What phone number should we use to contact you?",
            "selected_restaurant": "Which restaurant would you like to book? Please enter the number.",
            "restaurant_selection": "Please select a restaurant from the list above."
        }
        return prompts.get(field, f"Please provide {field}")
    
    async def _generate_response(
        self,
        step: ActionStep,
        execution_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Generate user-facing response."""
        if not execution_result.get("success"):
            return execution_result.get("message", "An error occurred")
        
        if step.action_type == "search":
            if "restaurant" in execution_result:
                restaurant = execution_result["restaurant"]
                return f"""Great! I found **{restaurant.name}**.

📍 Location: {restaurant.location}
🍽️ Cuisine: {restaurant.cuisine}
⭐ Rating: {restaurant.rating}/5
💰 Price: {restaurant.price_range}

{restaurant.description or ''}

Let's proceed with your reservation!"""
            elif "restaurants" in execution_result:
                restaurants = execution_result["restaurants"]
                response = "Here are the available restaurants:\n\n"
                for i, r in enumerate(restaurants[:5], 1):
                    response += f"{i}. **{r.name}** - {r.cuisine} ({r.location}) - {r.price_range}\n"
                response += "\nWhich restaurant would you like to book? (Enter the number)"
                return response
        
        elif step.action_type == "validate":
            if execution_result.get("available"):
                return "✅ Great news! A table is available for your requested time."
            else:
                return execution_result.get("message", "Checking availability...")
        
        elif step.action_type == "collect_info":
            return execution_result.get("message", "Please provide the requested information")
        
        elif step.action_type == "execute":
            if "confirmation" in execution_result:
                conf = execution_result["confirmation"]
                return f"""🎉 **Booking Confirmed!**

Confirmation Number: **{conf.confirmation_number}**
Restaurant: {conf.restaurant_name}
Date: {conf.date}
Time: {conf.time}
Guests: {conf.guest_count}
Name: {conf.user_name}

A confirmation email has been sent. See you there!"""
        
        return execution_result.get("message", "Step completed")
    
    async def _create_completion_response(
        self,
        plan: ActionPlan,
        context: Dict[str, Any]
    ) -> ExecutorResponse:
        """Create response when plan is completed."""
        confirmation = context.get("confirmation")
        
        if confirmation:
            content = f"""🎉 **Booking Completed!**

Your reservation at {confirmation.restaurant_name} is confirmed.
Confirmation #: {confirmation.confirmation_number}

Is there anything else I can help you with?"""
        else:
            content = "The booking process is complete. Is there anything else I can help you with?"
        
        return ExecutorResponse(
            content=content,
            completed_steps=context["completed_steps"],
            current_step_id=None,
            next_step_id=None,
            plan_completed=True,
            requires_user_input=False,
            metadata={"confirmation": confirmation.model_dump() if confirmation else None}
        )


# Global booking executor instance
booking_executor = BookingExecutor()
