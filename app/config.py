from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # Environment
    environment: Literal["development", "production"] = Field(
        default="development",
        description="Application environment"
    )
    
    # LLM Configuration
    llm_provider: Literal["openai", "azure", "gemini"] = Field(
        default="gemini",
        description="LLM provider to use"
    )
    openai_api_key: str = Field(default="", description="OpenAI API key")
    azure_openai_api_key: str = Field(default="", description="Azure OpenAI API key")
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint")
    azure_openai_deployment_name: str = Field(default="gpt-4", description="Azure deployment name")
    azure_api_version: str = Field(default="2024-02-15-preview", description="Azure API version")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    
    # Model Configuration
    model_name: str = Field(default="gpt-4-turbo-preview", description="Model name to use")
    model_temperature: float = Field(default=0.7, description="Model temperature")
    max_tokens: int = Field(default=2000, description="Maximum tokens for response")
    
    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: str = Field(default="", description="Redis password")
    
    # WebSocket Configuration
    ws_host: str = Field(default="0.0.0.0", description="WebSocket host")
    ws_port: int = Field(default=8000, description="WebSocket port")
    
    # Memory Configuration
    local_memory_path: str = Field(default="data/memory", description="Local memory storage path")
    
    restaurant_endpoint: str = Field(default="", description="Restaurant API endpoint")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


# Global settings instance
settings = Settings()
