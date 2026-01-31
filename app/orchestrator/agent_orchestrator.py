"""Enhanced agent orchestrator using routing agent and planner/executor pattern."""
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END
from app.agents.routing_agent import routing_agent
from app.agents.booking.booking_planner import booking_planner
from app.agents.booking.booking_executor import booking_executor
from app.agents.properties.properties_planner import properties_planner
from app.agents.properties.properties_executor import properties_executor
from app.agents.education.education_planner import education_planner
from app.agents.education.education_executor import education_executor
from app.models.plan_schemas import (
    PlannerRequest, ExecutorRequest, ActionPlan, RoutingDecision
)
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the enhanced agent orchestrator graph."""
    query: str
    session_id: str
    context: dict
    routing_decision: Optional[RoutingDecision]
    domain: str
    action_plan: Optional[ActionPlan]
    current_step_id: Optional[str]
    user_input: Optional[str]
    agent_response: str
    requires_followup: bool
    metadata: dict


class EnhancedAgentOrchestrator:
    """Orchestrates agents using routing agent and planner/executor pattern."""
    
    def __init__(self):
        """Initialize the enhanced orchestrator."""
        self.routing_agent = routing_agent
        
        # Planner agents
        self.planners = {
            "booking": booking_planner,
            "properties": properties_planner,
            "education": education_planner,
        }
        
        # Executor agents
        self.executors = {
            "booking": booking_executor,
            "properties": properties_executor,
            "education": education_executor,
        }
        
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the enhanced LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("route_query", self._route_query)
        workflow.add_node("create_plan", self._create_plan)
        workflow.add_node("execute_plan", self._execute_plan)
        workflow.add_node("handle_unclear", self._handle_unclear_intent)
        
        # Add edges
        workflow.set_entry_point("route_query")
        workflow.add_conditional_edges(
            "route_query",
            self._should_create_plan,
            {
                "plan": "create_plan",
                "unclear": "handle_unclear"
            }
        )
        workflow.add_edge("create_plan", "execute_plan")
        workflow.add_edge("execute_plan", END)
        workflow.add_edge("handle_unclear", END)
        
        return workflow.compile()
    
    async def _route_query(self, state: AgentState) -> AgentState:
        """
        Route query using the routing agent.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with routing decision
        """
        try:
            routing_decision = await self.routing_agent.route(
                query=state["query"],
                session_id=state["session_id"],
                context=state["context"]
            )
            
            state["routing_decision"] = routing_decision
            state["domain"] = routing_decision.domain
            
            logger.info(
                f"Routing decision: domain={routing_decision.domain}, "
                f"confidence={routing_decision.confidence}"
            )
            
        except Exception as e:
            logger.error(f"Error in routing: {e}")
            state["domain"] = "unclear"
        
        return state
    
    def _should_create_plan(self, state: AgentState) -> Literal["plan", "unclear"]:
        """
        Determine if we should create a plan or handle as unclear.
        
        Args:
            state: Current agent state
            
        Returns:
            Routing decision
        """
        domain = state.get("domain", "unclear")
        if domain in ["booking", "properties", "education"]:
            return "plan"
        return "unclear"
    
    async def _create_plan(self, state: AgentState) -> AgentState:
        """
        Create an action plan using the appropriate planner.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with action plan
        """
        domain = state["domain"]
        planner = self.planners.get(domain)
        
        if not planner:
            logger.error(f"No planner found for domain: {domain}")
            state["domain"] = "unclear"
            return state
        
        try:
            # Create planner request
            planner_request = PlannerRequest(
                query=state["query"],
                session_id=state["session_id"],
                context=state["context"],
                domain=domain
            )
            
            # Get plan from planner
            planner_response = await planner.plan(planner_request)
            
            state["action_plan"] = planner_response.plan
            state["metadata"] = {
                "planner_confidence": planner_response.confidence,
                "planner_reasoning": planner_response.reasoning,
                "requires_clarification": planner_response.requires_clarification
            }
            
            logger.info(
                f"Created plan for {domain}: {len(planner_response.plan.steps)} steps, "
                f"confidence={planner_response.confidence}"
            )
            
        except Exception as e:
            logger.error(f"Error creating plan: {e}")
            state["domain"] = "unclear"
        
        return state
    
    async def _execute_plan(self, state: AgentState) -> AgentState:
        """
        Execute the action plan using the appropriate executor.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with execution results
        """
        domain = state["domain"]
        executor = self.executors.get(domain)
        
        if not executor or not state.get("action_plan"):
            logger.error(f"No executor or plan for domain: {domain}")
            state["agent_response"] = "I apologize, but I couldn't process your request."
            state["requires_followup"] = False
            return state
        
        try:
            # Create executor request
            executor_request = ExecutorRequest(
                plan=state["action_plan"],
                current_step_id=state.get("current_step_id"),
                user_input=state.get("user_input"),
                session_id=state["session_id"],
                context=state["context"]
            )
            
            # Execute plan
            executor_response = await executor.execute(executor_request)
            
            state["agent_response"] = executor_response.content
            state["requires_followup"] = executor_response.requires_user_input
            state["metadata"].update({
                "executor_metadata": executor_response.metadata,
                "plan_completed": executor_response.plan_completed,
                "completed_steps": executor_response.completed_steps,
                "current_step_id": executor_response.current_step_id,
                "next_step_id": executor_response.next_step_id
            })
            
            logger.info(
                f"Executed plan for {domain}: "
                f"completed={executor_response.plan_completed}, "
                f"requires_input={executor_response.requires_user_input}"
            )
            
        except Exception as e:
            logger.error(f"Error executing plan: {e}")
            state["agent_response"] = "I encountered an error processing your request. Please try again."
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
        routing_decision = state.get("routing_decision")
        
        if routing_decision:
            clarification = await self.routing_agent.get_clarification_message(
                state["query"],
                routing_decision
            )
        else:
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
        context: dict = None,
        current_step_id: str = None,
        user_input: str = None
    ) -> dict:
        """
        Process a user query through the enhanced orchestrator.
        
        Args:
            query: User query
            session_id: Session identifier
            context: Optional conversation context
            current_step_id: Current step ID for multi-turn conversations
            user_input: User input for current step
            
        Returns:
            Dictionary with response and metadata
        """
        # Initialize state
        initial_state: AgentState = {
            "query": query,
            "session_id": session_id,
            "context": context or {},
            "routing_decision": None,
            "domain": "",
            "action_plan": None,
            "current_step_id": current_step_id,
            "user_input": user_input,
            "agent_response": "",
            "requires_followup": False,
            "metadata": {}
        }
        
        # Run through graph
        final_state = await self.graph.ainvoke(initial_state)
        
        return {
            "response": final_state["agent_response"],
            "intent": final_state["domain"],
            "requires_followup": final_state["requires_followup"],
            "metadata": final_state["metadata"]
        }


# Global enhanced orchestrator instance
orchestrator = EnhancedAgentOrchestrator()
