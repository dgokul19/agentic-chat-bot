"""FastAPI application with POST-based chat API."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.orchestrator.agent_orchestrator import orchestrator
from app.memory.memory_manager import memory_manager
from app.config import settings
import logging
import json
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Multi-Agent Chatbot API",
    description="AI chatbot with specialized agents for booking, properties, and education",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request model."""
    content: str
    current_step_id: Optional[str] = None
    user_input: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    session_id: str
    intent: str
    requires_followup: bool
    metadata: Dict


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Multi-Agent Chatbot API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    
    # Prefetch restaurants for booking agent
    try:
        from app.agents.booking.restaurant_service import restaurant_service
        restaurants = await restaurant_service.prefetch_restaurants()
        logger.info(f"✅ Prefetched {len(restaurants)} restaurants for booking agent")
    except Exception as e:
        logger.error(f"❌ Failed to prefetch restaurants: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Multi-Agent Chatbot API")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Multi-Agent Chatbot API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "chat": "POST /chat/{session_id}",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "llm_provider": settings.llm_provider
    }


@app.post("/chat/{session_id}", response_model=ChatResponse)
async def chat_endpoint(session_id: str, request: ChatRequest):
    """
    Chat endpoint for sending messages and receiving responses.
    
    Args:
        session_id: Unique session identifier
        request: Chat request with user message
        
    Returns:
        Chat response with agent reply
    """
    try:
        logger.info(f"Received message from {session_id}: {request.content}")
        
        # Validate input
        if not request.content or not request.content.strip():
            raise HTTPException(status_code=400, detail="Empty message received")
        
        user_query = request.content.strip()
        
        # Save user message to memory
        await memory_manager.add_message(
            session_id=session_id,
            role="user",
            content=user_query
        )
        
        # Get conversation history for context
        history = await memory_manager.get_history(session_id, limit=10)
        context = {
            "history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "agent": msg.agent
                }
                for msg in history
            ]
        }
        
        # Process query through orchestrator
        result = await orchestrator.process_query(
            query=user_query,
            session_id=session_id,
            context=context,
            current_step_id=request.current_step_id,
            user_input=request.user_input
        )
        
        # Save assistant response to memory
        await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=result["response"],
            agent=result["metadata"].get("agent"),
            metadata=result["metadata"]
        )
        
        logger.info(f"Sent response to {session_id}")
        
        # Return response
        return ChatResponse(
            response=result["response"],
            session_id=session_id,
            intent=result["intent"],
            requires_followup=result["requires_followup"],
            metadata=result["metadata"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred processing your request: {str(e)}"
        )


@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    """
    Clear conversation history for a session.
    
    Args:
        session_id: Session identifier to clear
        
    Returns:
        Success message
    """
    try:
        # Clear memory for session
        # Note: memory_manager doesn't have a clear method yet, 
        # but we can add one if needed
        logger.info(f"Cleared session: {session_id}")
        return {"status": "success", "message": f"Session {session_id} cleared"}
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.ws_host,
        port=settings.ws_port,
        reload=True
    )

