"""Routing agent for intelligent domain selection."""
from typing import Dict, Any, Optional
from app.models.plan_schemas import RoutingDecision
from app.utils.llm_client import llm_client
import logging
import json

logger = logging.getLogger(__name__)


class RoutingAgent:
    """Intelligent routing agent that determines which domain should handle a query."""
    
    def __init__(self):
        """Initialize the routing agent."""
        self.llm = llm_client
        self.domains = {
            "booking": "Restaurant reservations, dining recommendations, table bookings, food-related queries",
            "properties": "Real estate search, property listings, housing, apartments, rentals, buying/selling homes",
            "education": "Schools, educational resources, children profiles, school districts, educational planning"
        }
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for routing decisions."""
        domain_descriptions = "\n".join([
            f"- {domain}: {desc}"
            for domain, desc in self.domains.items()
        ])
        
        return f"""You are an intelligent routing agent that analyzes user queries and determines which domain should handle them.

Available domains:
{domain_descriptions}

Your task:
1. Analyze the user query carefully
2. Consider conversation context and history
3. Determine the most appropriate domain
4. Assess confidence in your decision
5. Identify if the query spans multiple domains
6. Determine if clarification is needed

Guidelines:
- Use context from previous messages to improve routing
- Be confident when the domain is clear
- Request clarification when the query is ambiguous
- Identify multi-domain queries (e.g., "book a restaurant near this property")
- Default to "unclear" if you cannot confidently route
"""
    
    async def route(
        self,
        query: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Route a query to the appropriate domain.
        
        Args:
            query: User query to route
            session_id: Session identifier
            context: Optional conversation context
            
        Returns:
            Routing decision with domain and confidence
        """
        try:
            # Build routing prompt
            routing_prompt = self._build_routing_prompt(query, context)
            
            # Get routing decision from LLM
            messages = [{"role": "user", "content": routing_prompt}]
            response = await self.llm.generate_response(
                messages=messages,
                system_prompt=self.get_system_prompt()
            )
            
            # Parse response
            decision = self._parse_routing_response(response)
            
            logger.info(
                f"Routing decision for session {session_id}: "
                f"domain={decision.domain}, confidence={decision.confidence}"
            )
            
            return decision
            
        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return RoutingDecision(
                domain="unclear",
                confidence=0.0,
                reasoning=f"Error during routing: {str(e)}",
                requires_clarification=True
            )
    
    def _build_routing_prompt(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the routing prompt with query and context."""
        prompt = f"""Analyze this user query and determine the appropriate domain:

User Query: "{query}"
"""
        
        # Add conversation history if available
        if context and context.get("history"):
            history_text = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in context["history"][-3:]  # Last 3 messages
            ])
            prompt += f"\nRecent Conversation:\n{history_text}\n"
        
        prompt += """
Respond in JSON format:
{
    "domain": "booking|properties|education|unclear",
    "confidence": 0.0-1.0,
    "reasoning": "explanation of your decision",
    "is_multi_domain": false,
    "domains": [],
    "requires_clarification": false
}

Notes:
- Set confidence to 0.9-1.0 for very clear queries
- Set confidence to 0.6-0.8 for moderately clear queries
- Set confidence to 0.0-0.5 for unclear queries
- Set is_multi_domain to true if query involves multiple domains
- List all relevant domains in "domains" array if multi-domain
- Set requires_clarification to true if the query is too ambiguous
"""
        
        return prompt
    
    def _parse_routing_response(self, response: str) -> RoutingDecision:
        """Parse LLM response into RoutingDecision."""
        try:
            # Clean the response - remove markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]  # Remove ```
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]  # Remove trailing ```
            cleaned_response = cleaned_response.strip()
            
            # Try to parse as JSON
            data = json.loads(cleaned_response)
            
            # Validate domain
            domain = data.get("domain", "unclear").lower()
            valid_domains = list(self.domains.keys()) + ["unclear"]
            if domain not in valid_domains:
                domain = "unclear"
            
            # Ensure confidence is in valid range
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            
            # Build routing decision
            return RoutingDecision(
                domain=domain,
                confidence=confidence,
                reasoning=data.get("reasoning", "No reasoning provided"),
                is_multi_domain=data.get("is_multi_domain", False),
                domains=data.get("domains", [domain] if domain != "unclear" else []),
                requires_clarification=data.get("requires_clarification", False)
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse routing response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            
            # Fallback: try to extract domain from text
            response_lower = response.lower()
            
            # Check for explicit domain mentions
            for domain in self.domains.keys():
                if domain in response_lower:
                    logger.info(f"Extracted domain '{domain}' from text response")
                    return RoutingDecision(
                        domain=domain,
                        confidence=0.7,
                        reasoning=f"Extracted domain from text response",
                        is_multi_domain=False,
                        domains=[domain],
                        requires_clarification=False
                    )
            
            # Check for keywords
            if any(word in response_lower for word in ["restaurant", "book", "table", "dining", "food", "eat"]):
                logger.info("Detected booking intent from keywords")
                return RoutingDecision(
                    domain="booking",
                    confidence=0.8,
                    reasoning="Detected booking keywords in response",
                    is_multi_domain=False,
                    domains=["booking"],
                    requires_clarification=False
                )
            
            if any(word in response_lower for word in ["property", "apartment", "house", "rent", "real estate"]):
                logger.info("Detected properties intent from keywords")
                return RoutingDecision(
                    domain="properties",
                    confidence=0.8,
                    reasoning="Detected properties keywords in response",
                    is_multi_domain=False,
                    domains=["properties"],
                    requires_clarification=False
                )
            
            if any(word in response_lower for word in ["school", "education", "child", "student", "learning"]):
                logger.info("Detected education intent from keywords")
                return RoutingDecision(
                    domain="education",
                    confidence=0.8,
                    reasoning="Detected education keywords in response",
                    is_multi_domain=False,
                    domains=["education"],
                    requires_clarification=False
                )
            
            # Ultimate fallback
            logger.warning("Could not parse routing response, defaulting to unclear")
            return RoutingDecision(
                domain="unclear",
                confidence=0.0,
                reasoning="Could not parse routing response",
                requires_clarification=True
            )
    
    async def get_clarification_message(
        self,
        query: str,
        decision: RoutingDecision
    ) -> str:
        """
        Generate a clarification message when routing is unclear.
        
        Args:
            query: Original user query
            decision: Routing decision
            
        Returns:
            Clarification message
        """
        if decision.is_multi_domain:
            return f"""I noticed your query might involve multiple areas: {', '.join(decision.domains)}.

Could you clarify which aspect you'd like help with first?

🍽️ **Restaurant Bookings** - Find and reserve tables
🏠 **Property Search** - Search for homes and apartments
🎓 **Education** - Find schools and educational resources
"""
        
        return """I'd be happy to help! I can assist you with:

🍽️ **Restaurant Bookings** - Find and reserve tables at restaurants
🏠 **Property Search** - Search for apartments, houses, and rentals
🎓 **Education** - Find schools and manage children's educational needs

Could you please clarify what you're looking for?"""


# Global routing agent instance
routing_agent = RoutingAgent()
