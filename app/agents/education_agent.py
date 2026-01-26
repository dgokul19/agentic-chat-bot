"""Education Agent for school search and children profiles."""
from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentRequest, AgentResponse
import logging

logger = logging.getLogger(__name__)


class EducationAgent(BaseAgent):
    """Agent specialized in education, schools, and children profiles."""
    
    def __init__(self):
        super().__init__(
            name="Education Agent",
            description="Specialized in school search, educational resources, and children profile management"
        )
    
    def get_capabilities(self) -> str:
        """Get agent capabilities description."""
        return """I can help you with:
- Finding schools (elementary, middle, high school)
- School ratings, reviews, and comparisons
- Educational programs and curricula
- Managing children profiles and educational needs
- School district information
- Extracurricular activities and resources
"""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process education-related requests.
        
        Args:
            request: Agent request with query and context
            
        Returns:
            Agent response with education information
        """
        try:
            logger.info(f"Education Agent processing: {request.query}")
            
            # Extract context
            context = request.context or {}
            
            # Generate response using LLM
            response_content = await self._generate_response(
                query=request.query,
                context=context
            )
            
            # TODO: Add actual education search logic
            # Potential features:
            # - Parse school search criteria (location, type, ratings)
            # - Query school database/API
            # - Manage children profiles (age, grade, interests)
            # - Match schools to children's needs
            # - Provide educational recommendations
            
            return AgentResponse(
                agent_name=self.name,
                content=response_content,
                metadata={
                    "intent": "education",
                    "status": "processed"
                },
                requires_followup=self._check_requires_followup(response_content)
            )
            
        except Exception as e:
            logger.error(f"Error in Education Agent: {e}")
            return AgentResponse(
                agent_name=self.name,
                content=f"I apologize, but I encountered an error processing your education request. Please try again.",
                metadata={"error": str(e)},
                requires_followup=False
            )
    
    def _check_requires_followup(self, response: str) -> bool:
        """Check if response requires follow-up."""
        followup_indicators = ["?", "please tell me", "need to know", "which grade", "age", "location"]
        return any(indicator in response.lower() for indicator in followup_indicators)


# Global education agent instance
education_agent = EducationAgent()
