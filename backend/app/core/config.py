from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # OpenRouter configurations
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="anthropic/claude-3-haiku", alias="OPENROUTER_MODEL")
    
    # Kubernetes configuration
    kubeconfig_path: str = Field(default="~/.kube/config", alias="KUBECONFIG_PATH")
    
    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000"]
    
    # Fast API environment
    environment: str = Field(default="development", alias="ENV")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
