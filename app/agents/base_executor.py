"""Base executor agent interface for all domain-specific executors."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.models.plan_schemas import ExecutorRequest, ExecutorResponse, ActionPlan, ActionStep
from app.utils.llm_client import llm_client
import logging

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """Abstract base class for all executor agents."""
    
    def __init__(self, domain: str, description: str):
        """
        Initialize the base executor.
        
        Args:
            domain: Domain this executor handles (booking, properties, education)
            description: Description of executor capabilities
        """
        self.domain = domain
        self.description = description
        self.llm = llm_client
    
    @abstractmethod
    async def execute(self, request: ExecutorRequest) -> ExecutorResponse:
        """
        Execute an action plan or continue execution with user input.
        
        Args:
            request: Executor request with plan and optional user input
            
        Returns:
            Executor response with results and next steps
        """
        pass
    
    @abstractmethod
    def get_execution_capabilities(self) -> str:
        """
        Get a description of this executor's capabilities.
        
        Returns:
            String describing what this executor can execute
        """
        pass
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this executor.
        
        Returns:
            System prompt string
        """
        return f"""You are an execution agent for the {self.domain} domain.

Your role: {self.description}

Capabilities: {self.get_execution_capabilities()}

Your task is to execute action plans step-by-step:
1. Execute the current step in the plan
2. Collect required information from users
3. Interact with services and APIs
4. Handle errors gracefully
5. Track progress through the plan
6. Provide clear feedback to users

Guidelines:
- Execute steps in order, respecting dependencies
- Validate data before proceeding
- Provide clear, helpful responses
- Handle errors with recovery options
- Track state between conversation turns
- Complete plans efficiently
"""
    
    def _get_next_step(
        self,
        plan: ActionPlan,
        completed_steps: list,
        current_step_id: Optional[str] = None
    ) -> Optional[ActionStep]:
        """
        Get the next step to execute based on plan and completed steps.
        
        Args:
            plan: Action plan being executed
            completed_steps: List of completed step IDs
            current_step_id: Current step ID (if any)
            
        Returns:
            Next step to execute, or None if plan is complete
        """
        completed_set = set(completed_steps)
        
        for step in plan.steps:
            # Skip completed steps
            if step.step_id in completed_set:
                continue
            
            # Check if dependencies are met
            dependencies_met = all(dep in completed_set for dep in step.dependencies)
            
            if dependencies_met:
                return step
        
        return None
    
    def _is_plan_complete(
        self,
        plan: ActionPlan,
        completed_steps: list
    ) -> bool:
        """
        Check if all steps in the plan are completed.
        
        Args:
            plan: Action plan being executed
            completed_steps: List of completed step IDs
            
        Returns:
            True if plan is complete
        """
        return len(completed_steps) == len(plan.steps)
    
    async def _execute_step(
        self,
        step: ActionStep,
        user_input: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single step in the plan.
        
        Args:
            step: Step to execute
            user_input: Optional user input for this step
            context: Execution context
            
        Returns:
            Dictionary with execution results
        """
        # This is a base implementation that subclasses should override
        # for domain-specific execution logic
        logger.info(f"Executing step: {step.step_id} - {step.description}")
        
        return {
            "success": True,
            "step_id": step.step_id,
            "result": None,
            "requires_user_input": False,
            "message": f"Executed: {step.description}"
        }
    
    async def _generate_response(
        self,
        step: ActionStep,
        execution_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Generate user-facing response for step execution.
        
        Args:
            step: Step that was executed
            execution_result: Result of step execution
            context: Execution context
            
        Returns:
            User-facing response message
        """
        if execution_result.get("requires_user_input"):
            return execution_result.get("message", "Please provide the required information.")
        
        return execution_result.get("message", "Step completed successfully.")
    
    def _validate_required_data(
        self,
        step: ActionStep,
        context: Dict[str, Any]
    ) -> tuple[bool, list]:
        """
        Validate that all required data for a step is available.
        
        Args:
            step: Step to validate
            context: Execution context
            
        Returns:
            Tuple of (is_valid, missing_data_list)
        """
        missing_data = []
        
        for required_field in step.required_data:
            if required_field not in context or context[required_field] is None:
                missing_data.append(required_field)
        
        return len(missing_data) == 0, missing_data
    
    async def _handle_error(
        self,
        error: Exception,
        step: ActionStep,
        context: Dict[str, Any]
    ) -> ExecutorResponse:
        """
        Handle execution errors gracefully.
        
        Args:
            error: Exception that occurred
            step: Step that failed
            context: Execution context
            
        Returns:
            Error response
        """
        logger.error(f"Error executing step {step.step_id}: {error}")
        
        error_message = f"I encountered an error while {step.description.lower()}. "
        error_message += "Could you please try again or rephrase your request?"
        
        return ExecutorResponse(
            content=error_message,
            completed_steps=context.get("completed_steps", []),
            current_step_id=step.step_id,
            next_step_id=None,
            plan_completed=False,
            requires_user_input=True,
            metadata={"error": str(error), "step_failed": step.step_id}
        )
