"""Properties Agent for real estate search."""
from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentRequest, AgentResponse
import logging

logger = logging.getLogger(__name__)


class PropertiesAgent(BaseAgent):
    """Agent specialized in property search and real estate."""
    
    def __init__(self):
        super().__init__(
            name="Properties Agent",
            description="Specialized in property search, real estate listings, and housing recommendations"
        )
    
    def get_capabilities(self) -> str:
        """Get agent capabilities description."""
        return """I can help you with:
- Searching for properties (apartments, houses, condos)
- Filtering by location, price range, bedrooms, amenities
- Providing property details and comparisons
- Neighborhood information and recommendations
- Rental and purchase options
"""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process property search requests.
        
        Args:
            request: Agent request with query and context
            
        Returns:
            Agent response with property information
        """
        try:
            logger.info(f"Properties Agent processing: {request.query}")
            
            # Extract context
            context = request.context or {}
            
            # Generate response using LLM
            response_content = await self._generate_response(
                query=request.query,
                context=context
            )
            
            # TODO: Add actual property search logic
            # Potential features:
            # - Parse search criteria (location, price, bedrooms, etc.)
            # - Query property database/API
            # - Filter and rank results
            # - Format property listings
            # - Save user preferences
            
            return AgentResponse(
                agent_name=self.name,
                content=response_content,
                metadata={
                    "intent": "property_search",
                    "status": "processed"
                },
                requires_followup=self._check_requires_followup(response_content)
            )
            
        except Exception as e:
            logger.error(f"Error in Properties Agent: {e}")
            return AgentResponse(
                agent_name=self.name,
                content=f"I apologize, but I encountered an error searching for properties. Please try again.",
                metadata={"error": str(e)},
                requires_followup=False
            )
    
    def _check_requires_followup(self, response: str) -> bool:
        """Check if response requires follow-up."""
        followup_indicators = ["?", "please specify", "need more", "which", "what type", "budget"]
        return any(indicator in response.lower() for indicator in followup_indicators)


# Global properties agent instance
properties_agent = PropertiesAgent()
