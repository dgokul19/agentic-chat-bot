"""Booking planner agent for restaurant reservation planning."""
from app.agents.base_planner import BasePlanner
from app.models.plan_schemas import (
    PlannerRequest, PlannerResponse, ActionPlan, ActionStep
)
from app.agents.booking.restaurant_service import restaurant_service
import logging

logger = logging.getLogger(__name__)


class BookingPlanner(BasePlanner):
    """Planner agent for restaurant booking domain."""
    
    def __init__(self):
        """Initialize the booking planner."""
        super().__init__(
            domain="booking",
            description="Plans restaurant reservation workflows including search, selection, and booking"
        )
    
    def get_planning_capabilities(self) -> str:
        """Get booking planner capabilities."""
        return """I can plan workflows for:
- Restaurant search and discovery
- Specific restaurant bookings
- Table availability checking
- Multi-step reservation processes
- Information collection (date, time, party size, contact details)
"""
    
    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        """
        Create a booking action plan.
        
        Args:
            request: Planner request with query and context
            
        Returns:
            Planner response with action plan
        """
        try:
            # Analyze the query
            analysis = await self._analyze_query(request.query, request.context)
            
            # Determine booking scenario
            scenario = await self._determine_scenario(request.query, analysis)
            
            # Create plan based on scenario
            if scenario == "specific_restaurant_with_details":
                plan = self._create_specific_booking_plan(analysis)
            elif scenario == "specific_restaurant_no_details":
                plan = self._create_restaurant_info_collection_plan(analysis)
            elif scenario == "general_search":
                plan = self._create_search_and_book_plan(analysis)
            else:
                plan = self._create_clarification_plan(analysis)
            
            # Validate plan
            if not self._validate_plan(plan):
                return await self._create_fallback_response(request.query)
            
            # Determine if clarification is needed
            requires_clarification = len(analysis.get("missing_requirements", [])) > 3
            clarification_questions = []
            
            if requires_clarification:
                clarification_questions = await self._generate_clarification_questions(
                    request.query,
                    analysis.get("missing_requirements", [])
                )
            
            return PlannerResponse(
                plan=plan,
                confidence=0.9 if scenario != "unclear" else 0.3,
                reasoning=f"Created {scenario} plan with {len(plan.steps)} steps",
                requires_clarification=requires_clarification,
                clarification_questions=clarification_questions
            )
            
        except Exception as e:
            logger.error(f"Error in booking planner: {e}")
            return await self._create_fallback_response(request.query)
    
    async def _determine_scenario(self, query: str, analysis: dict) -> str:
        """Determine the booking scenario from query analysis."""
        explicit_reqs = analysis.get("explicit_requirements", {})
        query_lower = query.lower()
        
        # Check if restaurant name is mentioned
        has_restaurant = "restaurant_name" in explicit_reqs
        
        # Check if booking details are provided
        has_datetime = "date" in explicit_reqs or "time" in explicit_reqs
        has_party_size = "party_size" in explicit_reqs
        
        if has_restaurant and has_datetime and has_party_size:
            return "specific_restaurant_with_details"
        elif has_restaurant:
            return "specific_restaurant_no_details"
        elif any(word in query_lower for word in ["search", "find", "show", "list", "browse"]):
            return "general_search"
        elif any(word in query_lower for word in ["book", "reserve", "table", "reservation", "dining"]):
            # User wants to book but hasn't specified details - treat as general search
            return "general_search"
        else:
            return "unclear"
    
    def _create_specific_booking_plan(self, analysis: dict) -> ActionPlan:
        """Create plan for booking a specific restaurant with details."""
        plan_id = self._create_plan_id()
        explicit_reqs = analysis.get("explicit_requirements", {})
        
        steps = [
            ActionStep(
                step_id=f"{plan_id}_verify_restaurant",
                description="Verify restaurant exists and get details",
                action_type="search",
                required_data=["restaurant_name"],
                dependencies=[],
                metadata={"restaurant_name": explicit_reqs.get("restaurant_name")}
            ),
            ActionStep(
                step_id=f"{plan_id}_check_availability",
                description="Check table availability for requested date/time",
                action_type="validate",
                required_data=["restaurant_id", "date", "time", "party_size"],
                dependencies=[f"{plan_id}_verify_restaurant"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_collect_contact",
                description="Collect customer contact information",
                action_type="collect_info",
                required_data=["name", "email", "phone"],
                dependencies=[f"{plan_id}_check_availability"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_create_booking",
                description="Create the reservation",
                action_type="execute",
                required_data=["restaurant_id", "date", "time", "party_size", "name", "email", "phone"],
                dependencies=[f"{plan_id}_collect_contact"],
                metadata={}
            )
        ]
        
        return ActionPlan(
            plan_id=plan_id,
            domain="booking",
            goal="Book a table at a specific restaurant",
            steps=steps,
            estimated_turns=3,
            requires_user_input=True,
            metadata={"scenario": "specific_with_details"}
        )
    
    def _create_restaurant_info_collection_plan(self, analysis: dict) -> ActionPlan:
        """Create plan for booking a specific restaurant without full details."""
        plan_id = self._create_plan_id()
        explicit_reqs = analysis.get("explicit_requirements", {})
        missing_reqs = analysis.get("missing_requirements", [])
        
        steps = [
            ActionStep(
                step_id=f"{plan_id}_verify_restaurant",
                description="Verify restaurant and show details",
                action_type="search",
                required_data=["restaurant_name"],
                dependencies=[],
                metadata={"restaurant_name": explicit_reqs.get("restaurant_name")}
            )
        ]
        
        # Add steps for collecting missing information
        if "date" in missing_reqs or "time" in missing_reqs:
            steps.append(ActionStep(
                step_id=f"{plan_id}_collect_datetime",
                description="Collect date and time for reservation",
                action_type="collect_info",
                required_data=["date", "time"],
                dependencies=[f"{plan_id}_verify_restaurant"],
                metadata={}
            ))
        
        if "party_size" in missing_reqs:
            steps.append(ActionStep(
                step_id=f"{plan_id}_collect_party_size",
                description="Collect number of guests",
                action_type="collect_info",
                required_data=["party_size"],
                dependencies=[f"{plan_id}_verify_restaurant"],
                metadata={}
            ))
        
        # Add availability check
        steps.append(ActionStep(
            step_id=f"{plan_id}_check_availability",
            description="Check table availability",
            action_type="validate",
            required_data=["restaurant_id", "date", "time", "party_size"],
            dependencies=[s.step_id for s in steps if "collect" in s.step_id],
            metadata={}
        ))
        
        # Add contact collection and booking
        steps.extend([
            ActionStep(
                step_id=f"{plan_id}_collect_contact",
                description="Collect contact information",
                action_type="collect_info",
                required_data=["name", "email", "phone"],
                dependencies=[f"{plan_id}_check_availability"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_create_booking",
                description="Create the reservation",
                action_type="execute",
                required_data=["restaurant_id", "date", "time", "party_size", "name", "email", "phone"],
                dependencies=[f"{plan_id}_collect_contact"],
                metadata={}
            )
        ])
        
        return ActionPlan(
            plan_id=plan_id,
            domain="booking",
            goal="Book a table at specified restaurant",
            steps=steps,
            estimated_turns=len([s for s in steps if s.action_type == "collect_info"]) + 2,
            requires_user_input=True,
            metadata={"scenario": "specific_no_details"}
        )
    
    def _create_search_and_book_plan(self, analysis: dict) -> ActionPlan:
        """Create plan for searching restaurants and then booking."""
        plan_id = self._create_plan_id()
        
        steps = [
            ActionStep(
                step_id=f"{plan_id}_search_restaurants",
                description="Search for restaurants matching criteria",
                action_type="search",
                required_data=[],
                dependencies=[],
                metadata={"search_criteria": analysis.get("explicit_requirements", {})}
            ),
            ActionStep(
                step_id=f"{plan_id}_select_restaurant",
                description="User selects a restaurant from results",
                action_type="collect_info",
                required_data=["selected_restaurant"],
                dependencies=[f"{plan_id}_search_restaurants"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_collect_datetime",
                description="Collect reservation date and time",
                action_type="collect_info",
                required_data=["date", "time"],
                dependencies=[f"{plan_id}_select_restaurant"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_collect_party_size",
                description="Collect number of guests",
                action_type="collect_info",
                required_data=["party_size"],
                dependencies=[f"{plan_id}_select_restaurant"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_check_availability",
                description="Check table availability",
                action_type="validate",
                required_data=["restaurant_id", "date", "time", "party_size"],
                dependencies=[f"{plan_id}_collect_datetime", f"{plan_id}_collect_party_size"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_collect_contact",
                description="Collect contact information",
                action_type="collect_info",
                required_data=["name", "email", "phone"],
                dependencies=[f"{plan_id}_check_availability"],
                metadata={}
            ),
            ActionStep(
                step_id=f"{plan_id}_create_booking",
                description="Create the reservation",
                action_type="execute",
                required_data=["restaurant_id", "date", "time", "party_size", "name", "email", "phone"],
                dependencies=[f"{plan_id}_collect_contact"],
                metadata={}
            )
        ]
        
        return ActionPlan(
            plan_id=plan_id,
            domain="booking",
            goal="Search for restaurants and make a reservation",
            steps=steps,
            estimated_turns=6,
            requires_user_input=True,
            metadata={"scenario": "search_and_book"}
        )
    
    def _create_clarification_plan(self, analysis: dict) -> ActionPlan:
        """Create plan for unclear booking requests."""
        plan_id = self._create_plan_id()
        
        steps = [
            ActionStep(
                step_id=f"{plan_id}_clarify_intent",
                description="Ask user to clarify their booking intent",
                action_type="collect_info",
                required_data=["clarified_intent"],
                dependencies=[],
                metadata={"missing_info": analysis.get("missing_requirements", [])}
            )
        ]
        
        return ActionPlan(
            plan_id=plan_id,
            domain="booking",
            goal="Clarify booking intent",
            steps=steps,
            estimated_turns=1,
            requires_user_input=True,
            metadata={"scenario": "clarification"}
        )
    
    async def _create_fallback_response(self, query: str) -> PlannerResponse:
        """Create fallback response when planning fails."""
        plan_id = self._create_plan_id()
        
        fallback_plan = ActionPlan(
            plan_id=plan_id,
            domain="booking",
            goal="Handle booking request",
            steps=[
                ActionStep(
                    step_id=f"{plan_id}_fallback",
                    description="Provide general booking assistance",
                    action_type="collect_info",
                    required_data=[],
                    dependencies=[],
                    metadata={}
                )
            ],
            estimated_turns=1,
            requires_user_input=True,
            metadata={"scenario": "fallback"}
        )
        
        return PlannerResponse(
            plan=fallback_plan,
            confidence=0.3,
            reasoning="Created fallback plan due to planning error",
            requires_clarification=True,
            clarification_questions=["Could you provide more details about your restaurant booking?"]
        )


# Global booking planner instance
booking_planner = BookingPlanner()
