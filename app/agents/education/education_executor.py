"""Education executor agent for school search execution."""
from app.agents.base_executor import BaseExecutor
from app.models.plan_schemas import (
    ExecutorRequest, ExecutorResponse, ActionPlan, ActionStep
)
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class EducationExecutor(BaseExecutor):
    """Executor agent for education domain."""
    
    def __init__(self):
        """Initialize the education executor."""
        super().__init__(
            domain="education",
            description="Executes school search and educational resource workflows"
        )
    
    def get_execution_capabilities(self) -> str:
        """Get education executor capabilities."""
        return """I can execute:
- School searches by location and criteria
- School detail retrieval
- School comparisons
- Educational resource discovery
- Child profile management
"""
    
    async def execute(self, request: ExecutorRequest) -> ExecutorResponse:
        """
        Execute an education action plan.
        
        Args:
            request: Executor request with plan and optional user input
            
        Returns:
            Executor response with results
        """
        try:
            # For now, create a simple mock implementation
            # In production, this would integrate with school APIs
            
            plan = request.plan
            
            # Execute search
            schools = await self._search_schools(plan.steps[0].metadata.get("search_criteria", {}))
            
            # Format response
            response_content = self._format_school_results(schools)
            
            return ExecutorResponse(
                content=response_content,
                completed_steps=[s.step_id for s in plan.steps],
                current_step_id=None,
                next_step_id=None,
                plan_completed=True,
                requires_user_input=False,
                metadata={"school_count": len(schools)}
            )
            
        except Exception as e:
            logger.error(f"Error in education executor: {e}")
            return ExecutorResponse(
                content="I encountered an error searching for schools. Please try again.",
                completed_steps=[],
                current_step_id=None,
                next_step_id=None,
                plan_completed=False,
                requires_user_input=False,
                metadata={"error": str(e)}
            )
    
    async def _search_schools(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for schools (mock implementation)."""
        # Mock school data
        mock_schools = [
            {
                "id": "school_1",
                "name": "Lincoln Elementary School",
                "type": "Public Elementary",
                "address": "123 School St, San Francisco, CA 94105",
                "rating": 4.5,
                "grades": "K-5",
                "students": 450,
                "programs": ["STEM", "Arts", "After School Care"]
            },
            {
                "id": "school_2",
                "name": "Washington Middle School",
                "type": "Public Middle School",
                "address": "456 Education Ave, San Francisco, CA 94105",
                "rating": 4.2,
                "grades": "6-8",
                "students": 600,
                "programs": ["Sports", "Music", "Advanced Math"]
            },
            {
                "id": "school_3",
                "name": "Roosevelt High School",
                "type": "Public High School",
                "address": "789 Learning Blvd, San Francisco, CA 94105",
                "rating": 4.7,
                "grades": "9-12",
                "students": 1200,
                "programs": ["AP Courses", "Athletics", "Robotics", "Drama"]
            }
        ]
        
        return mock_schools[:3]  # Return top 3
    
    def _format_school_results(self, schools: List[Dict[str, Any]]) -> str:
        """Format school search results for display."""
        if not schools:
            return "I couldn't find any schools matching your criteria. Would you like to adjust your search?"
        
        response = f"I found {len(schools)} schools for you:\n\n"
        
        for i, school in enumerate(schools, 1):
            response += f"""**{i}. {school['name']}**
🏫 Type: {school['type']}
📍 Address: {school['address']}
⭐ Rating: {school['rating']}/5
📚 Grades: {school['grades']}
👥 Students: {school['students']}
✨ Programs: {', '.join(school['programs'])}

"""
        
        response += "Would you like more details on any of these schools?"
        return response


# Global education executor instance
education_executor = EducationExecutor()
