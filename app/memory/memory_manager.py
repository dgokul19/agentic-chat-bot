"""Memory manager with Redis and JSON file fallback."""
import json
import os
import aiofiles
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.config import settings
from app.models.schemas import MemoryEntry, ConversationHistory
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation memory with Redis/JSON fallback."""
    
    def __init__(self):
        """Initialize memory manager."""
        self.use_redis = False
        self.redis_client = None
        self.local_path = settings.local_memory_path
        
        # Ensure local memory directory exists
        os.makedirs(self.local_path, exist_ok=True)
        
        # Try to connect to Redis
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Attempt to initialize Redis connection."""
        if settings.environment == "production":
            try:
                import redis.asyncio as aioredis
                self.redis_client = aioredis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password if settings.redis_password else None,
                    decode_responses=True
                )
                self.use_redis = True
                logger.info("Redis connection initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis, using JSON fallback: {e}")
                self.use_redis = False
        else:
            logger.info("Development mode: Using JSON file storage")
            self.use_redis = False
    
    def _get_session_file_path(self, session_id: str) -> str:
        """Get the file path for a session's JSON storage."""
        return os.path.join(self.local_path, f"{session_id}.json")
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a message to conversation history.
        
        Args:
            session_id: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            agent: Agent that handled the message
            metadata: Additional metadata
        """
        entry = MemoryEntry(
            session_id=session_id,
            role=role,
            content=content,
            agent=agent,
            metadata=metadata or {}
        )
        
        if self.use_redis:
            await self._add_message_redis(entry)
        else:
            await self._add_message_json(entry)
    
    async def _add_message_redis(self, entry: MemoryEntry):
        """Add message to Redis."""
        try:
            key = f"session:{entry.session_id}"
            message_data = entry.model_dump_json()
            await self.redis_client.rpush(key, message_data)
            # Set expiration to 24 hours
            await self.redis_client.expire(key, 86400)
        except Exception as e:
            logger.error(f"Error adding message to Redis: {e}")
            raise
    
    async def _add_message_json(self, entry: MemoryEntry):
        """Add message to JSON file."""
        try:
            file_path = self._get_session_file_path(entry.session_id)
            
            # Load existing history or create new
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    history_data = json.loads(content)
                    history = ConversationHistory(**history_data)
            else:
                history = ConversationHistory(session_id=entry.session_id)
            
            # Add new message
            history.messages.append(entry)
            history.updated_at = datetime.now()
            
            # Save back to file with UTF-8 encoding
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(history.model_dump_json(indent=2))
                
        except Exception as e:
            logger.error(f"Error adding message to JSON: {e}")
            raise
    
    async def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[MemoryEntry]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return (most recent)
            
        Returns:
            List of memory entries
        """
        if self.use_redis:
            return await self._get_history_redis(session_id, limit)
        else:
            return await self._get_history_json(session_id, limit)
    
    async def _get_history_redis(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[MemoryEntry]:
        """Get history from Redis."""
        try:
            key = f"session:{session_id}"
            
            if limit:
                messages = await self.redis_client.lrange(key, -limit, -1)
            else:
                messages = await self.redis_client.lrange(key, 0, -1)
            
            return [MemoryEntry(**json.loads(msg)) for msg in messages]
            
        except Exception as e:
            logger.error(f"Error getting history from Redis: {e}")
            return []
    
    async def _get_history_json(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[MemoryEntry]:
        """Get history from JSON file."""
        try:
            file_path = self._get_session_file_path(session_id)
            
            if not os.path.exists(file_path):
                return []
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                history = ConversationHistory(**json.loads(content))
            
            messages = history.messages
            if limit:
                messages = messages[-limit:]
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting history from JSON: {e}")
            return []
    
    async def clear_session(self, session_id: str):
        """Clear all messages for a session."""
        if self.use_redis:
            await self._clear_session_redis(session_id)
        else:
            await self._clear_session_json(session_id)
    
    async def _clear_session_redis(self, session_id: str):
        """Clear session from Redis."""
        try:
            key = f"session:{session_id}"
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error clearing session from Redis: {e}")
    
    async def _clear_session_json(self, session_id: str):
        """Clear session from JSON file."""
        try:
            file_path = self._get_session_file_path(session_id)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error clearing session from JSON: {e}")


# Global memory manager instance
memory_manager = MemoryManager()
