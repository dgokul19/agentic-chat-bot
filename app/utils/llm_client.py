"""LLM client wrapper for OpenAI, Azure OpenAI, and Google Gemini."""
from typing import AsyncGenerator, Optional
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client supporting OpenAI, Azure OpenAI, and Google Gemini."""
    
    def __init__(self):
        """Initialize the LLM client based on configuration."""
        self.provider = settings.llm_provider
        self.llm = self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the appropriate LLM based on provider setting."""
        if self.provider == "azure":
            logger.info("Initializing Azure OpenAI client")
            return AzureChatOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                azure_deployment=settings.azure_openai_deployment_name,
                api_version=settings.azure_api_version,
                temperature=settings.model_temperature,
                max_tokens=settings.max_tokens,
                streaming=True,
            )
        elif self.provider == "gemini":
            logger.info("Initializing Google Gemini client")
            # Gemini model names should not include 'models/' prefix
            model_name = settings.model_name
            if model_name.startswith("models/"):
                model_name = model_name.replace("models/", "")
            
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.gemini_api_key,
                temperature=settings.model_temperature,
                max_output_tokens=settings.max_tokens,
            )
        else:
            logger.info("Initializing OpenAI client")
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.model_name,
                temperature=settings.model_temperature,
                max_tokens=settings.max_tokens,
                streaming=True,
            )
    
    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            
        Returns:
            Generated response text
        """
        try:
            # Convert messages to LangChain format
            lc_messages = []
            
            if system_prompt:
                lc_messages.append(SystemMessage(content=system_prompt))
            
            for msg in messages:
                if msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
            
            # Generate response
            response = await self.llm.ainvoke(lc_messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            raise
    
    async def stream_response(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from the LLM.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            
        Yields:
            Response chunks as they are generated
        """
        try:
            # Convert messages to LangChain format
            lc_messages = []
            
            if system_prompt:
                lc_messages.append(SystemMessage(content=system_prompt))
            
            for msg in messages:
                if msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
            
            # Stream response
            async for chunk in self.llm.astream(lc_messages):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            raise


# Global LLM client instance
llm_client = LLMClient()
