"""Base planner agent interface for all domain-specific planners."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.models.plan_schemas import PlannerRequest, PlannerResponse, ActionPlan, ActionStep
from app.utils.llm_client import llm_client
import logging
import uuid

logger = logging.getLogger(__name__)


class BasePlanner(ABC):
    """Abstract base class for all planner agents."""
    
    def __init__(self, domain: str, description: str):
        """
        Initialize the base planner.
        
        Args:
            domain: Domain this planner handles (booking, properties, education)
            description: Description of planner capabilities
        """
        self.domain = domain
        self.description = description
        self.llm = llm_client
    
    @abstractmethod
    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        """
        Create an action plan for the given request.
        
        Args:
            request: Planner request with query and context
            
        Returns:
            Planner response with action plan
        """
        pass
    
    @abstractmethod
    def get_planning_capabilities(self) -> str:
        """
        Get a description of this planner's capabilities.
        
        Returns:
            String describing what this planner can plan for
        """
        pass
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this planner.
        
        Returns:
            System prompt string
        """
        return f"""You are a planning agent for the {self.domain} domain.

Your role: {self.description}

Capabilities: {self.get_planning_capabilities()}

Your task is to analyze user queries and create detailed action plans that include:
1. Breaking down the request into actionable steps
2. Identifying required information
3. Determining dependencies between steps
4. Estimating conversation complexity

Guidelines:
- Create clear, sequential steps
- Identify missing information early
- Plan for multi-turn conversations when needed
- Consider user context and history
- Be specific about data requirements
- Validate plan feasibility before returning
"""
    
    async def _analyze_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze user query to extract intent and requirements.
        
        Args:
            query: User query
            context: Optional conversation context
            
        Returns:
            Dictionary with analysis results
        """
        analysis_prompt = f"""Analyze the following user query for the {self.domain} domain:

Query: "{query}"

Extract:
1. Primary intent (what the user wants to accomplish)
2. Explicit requirements (information provided by user)
3. Missing requirements (information needed but not provided)
4. Complexity level (simple/moderate/complex)
5. Estimated conversation turns needed

Respond in JSON format:
{{
    "intent": "...",
    "explicit_requirements": {{}},
    "missing_requirements": [],
    "complexity": "simple|moderate|complex",
    "estimated_turns": 1
}}
"""
        
        try:
            messages = [{"role": "user", "content": analysis_prompt}]
            response = await self.llm.generate_response(
                messages=messages,
                system_prompt=self.get_system_prompt()
            )
            
            # Clean response - remove markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON response
            import json
            analysis = json.loads(cleaned_response)
            logger.info(f"Query analysis for {self.domain}: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            logger.debug(f"Response was: {response if 'response' in locals() else 'N/A'}")
            return {
                "intent": "unknown",
                "explicit_requirements": {},
                "missing_requirements": [],
                "complexity": "moderate",
                "estimated_turns": 2
            }
    
    def _create_plan_id(self) -> str:
        """Generate unique plan ID."""
        return f"{self.domain}_{uuid.uuid4().hex[:8]}"
    
    def _validate_plan(self, plan: ActionPlan) -> bool:
        """
        Validate that a plan is well-formed.
        
        Args:
            plan: Action plan to validate
            
        Returns:
            True if plan is valid
        """
        if not plan.steps:
            logger.warning("Plan has no steps")
            return False
        
        # Check for circular dependencies
        step_ids = {step.step_id for step in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    logger.warning(f"Step {step.step_id} has invalid dependency: {dep}")
                    return False
        
        return True
    
    async def _generate_clarification_questions(
        self,
        query: str,
        missing_requirements: list
    ) -> list:
        """
        Generate clarification questions for missing requirements.
        
        Args:
            query: Original user query
            missing_requirements: List of missing information
            
        Returns:
            List of clarification questions
        """
        if not missing_requirements:
            return []
        
        prompt = f"""Given this user query: "{query}"

The following information is missing: {', '.join(missing_requirements)}

Generate 1-3 friendly clarification questions to gather this information.
Return as a JSON array of strings.
"""
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.generate_response(messages=messages)
            
            # Clean response
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            import json
            questions = json.loads(cleaned_response)
            return questions if isinstance(questions, list) else [response]
            
        except Exception as e:
            logger.error(f"Error generating clarification questions: {e}")
            return [f"Could you provide more details about {', '.join(missing_requirements)}?"]
