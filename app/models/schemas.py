"""Data models and schemas for the multi-agent chatbot system."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime


class Message(BaseModel):
    """WebSocket message model."""
    type: Literal["user_message", "agent_response", "error", "system"] = Field(
        description="Type of message"
    )
    content: str = Field(description="Message content")
    session_id: str = Field(description="Session identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class AgentRequest(BaseModel):
    """Request to an agent."""
    query: str = Field(description="User query")
    session_id: str = Field(description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Conversation context")


class AgentResponse(BaseModel):
    """Response from an agent."""
    agent_name: str = Field(description="Name of the agent that processed the request")
    content: str = Field(description="Response content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    requires_followup: bool = Field(default=False, description="Whether this requires follow-up")


class MemoryEntry(BaseModel):
    """Memory entry for conversation history."""
    session_id: str = Field(description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Entry timestamp")
    role: Literal["user", "assistant", "system"] = Field(description="Message role")
    content: str = Field(description="Message content")
    agent: Optional[str] = Field(default=None, description="Agent that handled the message")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class ConversationHistory(BaseModel):
    """Complete conversation history for a session."""
    session_id: str = Field(description="Session identifier")
    messages: list[MemoryEntry] = Field(default_factory=list, description="List of messages")
    created_at: datetime = Field(default_factory=datetime.now, description="Session creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
