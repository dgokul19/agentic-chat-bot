"""Education planner agent for school search planning."""
from app.agents.base_planner import BasePlanner
from app.models.plan_schemas import (
    PlannerRequest, PlannerResponse, ActionPlan, ActionStep
)
import logging

logger = logging.getLogger(__name__)


class EducationPlanner(BasePlanner):
    """Planner agent for education domain."""
    
    def __init__(self):
        """Initialize the education planner."""
        super().__init__(
            domain="education",
            description="Plans school search and educational resource workflows"
        )
    
    def get_planning_capabilities(self) -> str:
        """Get education planner capabilities."""
        return """I can plan workflows for:
- School searches by location and criteria
- School comparisons and recommendations
- Child profile management
- Educational resource discovery
- School district information
"""
    
    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        """
        Create an education action plan.
        
        Args:
            request: Planner request with query and context
            
        Returns:
            Planner response with action plan
        """
        try:
            # Analyze the query
            analysis = await self._analyze_query(request.query, request.context)
            
            # Create search plan
            plan = self._create_search_plan(analysis)
            
            # Validate plan
            if not self._validate_plan(plan):
                return await self._create_fallback_response(request.query)
            
            # Check if clarification is needed
            missing_reqs = analysis.get("missing_requirements", [])
            requires_clarification = len(missing_reqs) > 2
            clarification_questions = []
            
            if requires_clarification:
                clarification_questions = await self._generate_clarification_questions(
                    request.query,
                    missing_reqs
                )
            
            return PlannerResponse(
                plan=plan,
                confidence=0.85,
                reasoning=f"Created education search plan with {len(plan.steps)} steps",
                requires_clarification=requires_clarification,
                clarification_questions=clarification_questions
            )
            
        except Exception as e:
            logger.error(f"Error in education planner: {e}")
            return await self._create_fallback_response(request.query)
    
    def _create_search_plan(self, analysis: dict) -> ActionPlan:
        """Create plan for school search."""
        plan_id = self._create_plan_id()
        explicit_reqs = analysis.get("explicit_requirements", {})
        
        steps = [
            ActionStep(
                step_id=f"{plan_id}_search_schools",
                description="Search for schools matching criteria",
                action_type="search",
                required_data=[],
                dependencies=[],
                metadata={"search_criteria": explicit_reqs}
            ),
            ActionStep(
                step_id=f"{plan_id}_present_results",
                description="Present school search results",
                action_type="execute",
                required_data=["search_results"],
                dependencies=[f"{plan_id}_search_schools"],
                metadata={}
            )
        ]
        
        return ActionPlan(
            plan_id=plan_id,
            domain="education",
            goal="Search and present schools",
            steps=steps,
            estimated_turns=1,
            requires_user_input=False,
            metadata={"scenario": "school_search"}
        )
    
    async def _create_fallback_response(self, query: str) -> PlannerResponse:
        """Create fallback response when planning fails."""
        plan_id = self._create_plan_id()
        
        fallback_plan = ActionPlan(
            plan_id=plan_id,
            domain="education",
            goal="Handle education request",
            steps=[
                ActionStep(
                    step_id=f"{plan_id}_fallback",
                    description="Provide general education assistance",
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
            clarification_questions=["Could you provide more details about the school or educational resource you're looking for?"]
        )


# Global education planner instance
education_planner = EducationPlanner()
