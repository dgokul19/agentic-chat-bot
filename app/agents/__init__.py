"""Agents package initialization."""
from app.agents.booking.booking_agent import booking_agent
from app.agents.properties_agent import properties_agent
from app.agents.education_agent import education_agent

__all__ = ['booking_agent', 'properties_agent', 'education_agent']
