"""Pydantic schemas for planning and execution."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ActionStep(BaseModel):
    """Individual step in an action plan."""
    step_id: str = Field(..., description="Unique identifier for this step")
    description: str = Field(..., description="Description of what this step does")
    action_type: str = Field(..., description="Type of action (search, collect_info, validate, execute, etc.)")
    required_data: List[str] = Field(default_factory=list, description="Data required to execute this step")
    dependencies: List[str] = Field(default_factory=list, description="Step IDs that must complete before this step")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional step-specific metadata")


class ActionPlan(BaseModel):
    """Complete action plan with steps and metadata."""
    plan_id: str = Field(..., description="Unique identifier for this plan")
    domain: str = Field(..., description="Domain this plan belongs to (booking, properties, education)")
    goal: str = Field(..., description="High-level goal of this plan")
    steps: List[ActionStep] = Field(..., description="Ordered list of steps to execute")
    estimated_turns: int = Field(default=1, description="Estimated number of conversation turns needed")
    requires_user_input: bool = Field(default=False, description="Whether this plan requires user input")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional plan-specific metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this plan was created")


class PlannerRequest(BaseModel):
    """Request to a planner agent."""
    query: str = Field(..., description="User query to plan for")
    session_id: str = Field(..., description="Session identifier")
    context: Dict[str, Any] = Field(default_factory=dict, description="Conversation context")
    domain: str = Field(..., description="Domain for this planning request")


class PlannerResponse(BaseModel):
    """Response from a planner agent."""
    plan: ActionPlan = Field(..., description="The created action plan")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this plan (0-1)")
    reasoning: str = Field(..., description="Explanation of the planning decision")
    requires_clarification: bool = Field(default=False, description="Whether clarification is needed")
    clarification_questions: List[str] = Field(default_factory=list, description="Questions to ask user if clarification needed")


class ExecutorRequest(BaseModel):
    """Request to an executor agent."""
    plan: ActionPlan = Field(..., description="Plan to execute")
    current_step_id: Optional[str] = Field(None, description="Current step being executed (None for first step)")
    user_input: Optional[str] = Field(None, description="User input for current step")
    session_id: str = Field(..., description="Session identifier")
    context: Dict[str, Any] = Field(default_factory=dict, description="Conversation context")


class ExecutorResponse(BaseModel):
    """Response from an executor agent."""
    content: str = Field(..., description="Response content to show user")
    completed_steps: List[str] = Field(default_factory=list, description="Step IDs that have been completed")
    current_step_id: Optional[str] = Field(None, description="Current step being executed")
    next_step_id: Optional[str] = Field(None, description="Next step to execute")
    plan_completed: bool = Field(default=False, description="Whether the entire plan is completed")
    requires_user_input: bool = Field(default=False, description="Whether user input is needed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution metadata")


class RoutingDecision(BaseModel):
    """Routing decision from routing agent."""
    domain: str = Field(..., description="Selected domain (booking, properties, education, unclear)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in routing decision (0-1)")
    reasoning: str = Field(..., description="Explanation of routing decision")
    is_multi_domain: bool = Field(default=False, description="Whether query spans multiple domains")
    domains: List[str] = Field(default_factory=list, description="All relevant domains if multi-domain")
    requires_clarification: bool = Field(default=False, description="Whether clarification is needed")
