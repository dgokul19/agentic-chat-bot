"""Agent orchestrator using LangGraph for routing and state management."""
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from app.agents.booking.booking_agent import booking_agent
from app.agents.properties_agent import properties_agent
from app.agents.education_agent import education_agent
from app.models.schemas import AgentRequest, AgentResponse
from app.utils.llm_client import llm_client
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the agent orchestrator graph."""
    query: str
    session_id: str
    context: dict
    intent: str
    agent_response: str
    requires_followup: bool
    metadata: dict


class AgentOrchestrator:
    """Orchestrates multiple agents using LangGraph."""
    
    def __init__(self):
        """Initialize the orchestrator with all agents."""
        self.agents = {
            "booking": booking_agent,
            "properties": properties_agent,
            "education": education_agent,
        }
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("route_to_agent", self._route_to_agent)
        workflow.add_node("handle_unclear", self._handle_unclear_intent)
        
        # Add edges
        workflow.set_entry_point("classify_intent")
        workflow.add_conditional_edges(
            "classify_intent",
            self._should_route_to_agent,
            {
                "route": "route_to_agent",
                "unclear": "handle_unclear"
            }
        )
        workflow.add_edge("route_to_agent", END)
        workflow.add_edge("handle_unclear", END)
        
        return workflow.compile()
    
    async def _classify_intent(self, state: AgentState) -> AgentState:
        """
        Classify user intent to determine which agent should handle the request.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with intent classification
        """
        query = state["query"]
        
        classification_prompt = f"""Classify the following user query into one of these categories:
- booking: Restaurant reservations, dining recommendations, table bookings
- properties: Real estate search, property listings, housing, apartments, rentals
- education: Schools, educational resources, children profiles, school districts
- unclear: Cannot determine or doesn't fit any category

User query: "{query}"

Respond with ONLY the category name (booking, properties, education, or unclear).
"""
        
        try:
            messages = [{"role": "user", "content": classification_prompt}]
            intent = await llm_client.generate_response(messages)
            intent = intent.strip().lower()
            
            # Validate intent
            valid_intents = ["booking", "properties", "education", "unclear"]
            if intent not in valid_intents:
                intent = "unclear"
            
            logger.info(f"Classified intent: {intent} for query: {query}")
            state["intent"] = intent
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            state["intent"] = "unclear"
        
        return state
    
    def _should_route_to_agent(self, state: AgentState) -> Literal["route", "unclear"]:
        """
        Determine if query should be routed to an agent or handled as unclear.
        
        Args:
            state: Current agent state
            
        Returns:
            Routing decision
        """
        if state["intent"] in ["booking", "properties", "education"]:
            return "route"
        return "unclear"
    
    async def _route_to_agent(self, state: AgentState) -> AgentState:
        """
        Route the query to the appropriate agent.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with agent response
        """
        intent = state["intent"]
        agent = self.agents.get(intent)
        
        if not agent:
            logger.error(f"No agent found for intent: {intent}")
            state["agent_response"] = "I apologize, but I couldn't process your request."
            state["requires_followup"] = False
            return state
        
        try:
            # Create agent request
            request = AgentRequest(
                query=state["query"],
                session_id=state["session_id"],
                context=state["context"]
            )
            
            # Process with agent
            response: AgentResponse = await agent.process(request)
            
            # Update state
            state["agent_response"] = response.content
            state["requires_followup"] = response.requires_followup
            state["metadata"] = {
                "agent": response.agent_name,
                **response.metadata
            }
            
            logger.info(f"Agent {response.agent_name} processed request successfully")
            
        except Exception as e:
            logger.error(f"Error routing to agent: {e}")
            state["agent_response"] = "I apologize, but I encountered an error processing your request."
            state["requires_followup"] = False
        
        return state
    
    async def _handle_unclear_intent(self, state: AgentState) -> AgentState:
        """
        Handle queries with unclear intent.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with clarification request
        """
        clarification = """I'd be happy to help! I can assist you with:

🍽️ **Restaurant Bookings** - Find and reserve tables at restaurants
🏠 **Property Search** - Search for apartments, houses, and rentals  
🎓 **Education** - Find schools and manage children's educational needs

Could you please clarify what you're looking for?"""
        
        state["agent_response"] = clarification
        state["requires_followup"] = True
        state["metadata"] = {"intent": "clarification_needed"}
        
        return state
    
    async def process_query(
        self,
        query: str,
        session_id: str,
        context: dict = None
    ) -> dict:
        """
        Process a user query through the orchestrator.
        
        Args:
            query: User query
            session_id: Session identifier
            context: Optional conversation context
            
        Returns:
            Dictionary with response and metadata
        """
        # Initialize state
        initial_state: AgentState = {
            "query": query,
            "session_id": session_id,
            "context": context or {},
            "intent": "",
            "agent_response": "",
            "requires_followup": False,
            "metadata": {}
        }
        
        # Run through graph
        final_state = await self.graph.ainvoke(initial_state)
        
        return {
            "response": final_state["agent_response"],
            "intent": final_state["intent"],
            "requires_followup": final_state["requires_followup"],
            "metadata": final_state["metadata"]
        }


# Global orchestrator instance
orchestrator = AgentOrchestrator()
