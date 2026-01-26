"""Base agent interface for all specialized agents."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.models.schemas import AgentRequest, AgentResponse
from app.utils.llm_client import llm_client
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents."""
    
    def __init__(self, name: str, description: str):
        """
        Initialize the base agent.
        
        Args:
            name: Agent name
            description: Agent description/capabilities
        """
        self.name = name
        self.description = description
        self.llm = llm_client
    
    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process a user request.
        
        Args:
            request: Agent request containing query and context
            
        Returns:
            Agent response with content and metadata
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> str:
        """
        Get a description of the agent's capabilities.
        
        Returns:
            String describing what this agent can do
        """
        pass
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.
        
        Returns:
            System prompt string
        """
        return f"""You are {self.name}, a specialized AI assistant.
        
Your capabilities: {self.get_capabilities()}

Guidelines:
- Be helpful, accurate, and concise
- If you cannot handle a request, clearly state so
- Provide structured information when appropriate
- Ask clarifying questions if needed
"""
    
    async def _generate_response(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a response using the LLM.
        
        Args:
            query: User query
            context: Optional conversation context
            
        Returns:
            Generated response
        """
        messages = []
        
        # Add context if available
        if context and context.get("history"):
            for msg in context["history"][-5:]:  # Last 5 messages
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current query
        messages.append({
            "role": "user",
            "content": query
        })
        
        # Generate response
        response = await self.llm.generate_response(
            messages=messages,
            system_prompt=self.get_system_prompt()
        )
        
        return response
