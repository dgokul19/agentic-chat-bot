"""Properties executor agent for real estate search execution."""
from app.agents.base_executor import BaseExecutor
from app.models.plan_schemas import (
    ExecutorRequest, ExecutorResponse, ActionPlan, ActionStep
)
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class PropertiesExecutor(BaseExecutor):
    """Executor agent for properties domain."""
    
    def __init__(self):
        """Initialize the properties executor."""
        super().__init__(
            domain="properties",
            description="Executes property search and comparison workflows"
        )
    
    def get_execution_capabilities(self) -> str:
        """Get properties executor capabilities."""
        return """I can execute:
- Property searches with various criteria
- Property listing and filtering
- Property detail retrieval
- Search result presentation
- Property comparisons
"""
    
    async def execute(self, request: ExecutorRequest) -> ExecutorResponse:
        """
        Execute a properties action plan.
        
        Args:
            request: Executor request with plan and optional user input
            
        Returns:
            Executor response with results
        """
        try:
            # For now, create a simple mock implementation
            # In production, this would integrate with property APIs
            
            plan = request.plan
            
            # Execute search
            properties = await self._search_properties(plan.steps[0].metadata.get("search_criteria", {}))
            
            # Format response
            response_content = self._format_property_results(properties)
            
            return ExecutorResponse(
                content=response_content,
                completed_steps=[s.step_id for s in plan.steps],
                current_step_id=None,
                next_step_id=None,
                plan_completed=True,
                requires_user_input=False,
                metadata={"property_count": len(properties)}
            )
            
        except Exception as e:
            logger.error(f"Error in properties executor: {e}")
            return ExecutorResponse(
                content="I encountered an error searching for properties. Please try again.",
                completed_steps=[],
                current_step_id=None,
                next_step_id=None,
                plan_completed=False,
                requires_user_input=False,
                metadata={"error": str(e)}
            )
    
    async def _search_properties(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for properties (mock implementation)."""
        # Mock property data
        mock_properties = [
            {
                "id": "prop_1",
                "address": "123 Main St, San Francisco, CA",
                "price": "$2,500/month",
                "bedrooms": 2,
                "bathrooms": 2,
                "sqft": 1200,
                "type": "Apartment",
                "amenities": ["Parking", "Gym", "Pool"]
            },
            {
                "id": "prop_2",
                "address": "456 Oak Ave, San Francisco, CA",
                "price": "$1,800/month",
                "bedrooms": 1,
                "bathrooms": 1,
                "sqft": 800,
                "type": "Apartment",
                "amenities": ["Parking", "Laundry"]
            },
            {
                "id": "prop_3",
                "address": "789 Pine St, San Francisco, CA",
                "price": "$3,200/month",
                "bedrooms": 3,
                "bathrooms": 2.5,
                "sqft": 1600,
                "type": "Townhouse",
                "amenities": ["Parking", "Yard", "Garage"]
            }
        ]
        
        # Simple filtering based on criteria
        filtered = mock_properties
        
        if "bedrooms" in criteria:
            filtered = [p for p in filtered if p["bedrooms"] >= criteria["bedrooms"]]
        
        return filtered[:3]  # Return top 3
    
    def _format_property_results(self, properties: List[Dict[str, Any]]) -> str:
        """Format property search results for display."""
        if not properties:
            return "I couldn't find any properties matching your criteria. Would you like to adjust your search?"
        
        response = f"I found {len(properties)} properties for you:\n\n"
        
        for i, prop in enumerate(properties, 1):
            response += f"""**{i}. {prop['address']}**
💰 Price: {prop['price']}
🛏️ Bedrooms: {prop['bedrooms']} | 🚿 Bathrooms: {prop['bathrooms']}
📐 Size: {prop['sqft']} sqft
🏠 Type: {prop['type']}
✨ Amenities: {', '.join(prop['amenities'])}

"""
        
        response += "Would you like more details on any of these properties?"
        return response


# Global properties executor instance
properties_executor = PropertiesExecutor()
