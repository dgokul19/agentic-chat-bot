"""FastAPI application with WebSocket streaming."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.orchestrator.agent_orchestrator import orchestrator
from app.memory.memory_manager import memory_manager
from app.config import settings
import logging
import json
from typing import Dict

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
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}


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
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "llm_provider": settings.llm_provider
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming chat.
    
    Args:
        websocket: WebSocket connection
        session_id: Unique session identifier
    """
    await websocket.accept()
    active_connections[session_id] = websocket
    logger.info(f"WebSocket connection established for session: {session_id}")
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "content": "Connected to Multi-Agent Chatbot. How can I help you today?",
            "session_id": session_id
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            logger.info(f"Received message from {session_id}: {message_data}")
            
            # Extract user query
            user_query = message_data.get("content", "")
            
            if not user_query:
                await websocket.send_json({
                    "type": "error",
                    "content": "Empty message received",
                    "session_id": session_id
                })
                continue
            
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
                context=context
            )
            
            # Send response to client
            response_message = {
                "type": "agent_response",
                "content": result["response"],
                "session_id": session_id,
                "metadata": {
                    "intent": result["intent"],
                    "requires_followup": result["requires_followup"],
                    **result["metadata"]
                }
            }
            
            await websocket.send_json(response_message)
            
            # Save assistant response to memory
            await memory_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=result["response"],
                agent=result["metadata"].get("agent"),
                metadata=result["metadata"]
            )
            
            logger.info(f"Sent response to {session_id}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
        if session_id in active_connections:
            del active_connections[session_id]
    
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": "An error occurred processing your request",
                "session_id": session_id
            })
        except:
            pass
        
        if session_id in active_connections:
            del active_connections[session_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.ws_host,
        port=settings.ws_port,
        reload=True
    )
