"""Configuration management for the customer health agent."""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# CData Connect AI
CDATA_EMAIL = os.getenv("CDATA_EMAIL")
CDATA_PAT = os.getenv("CDATA_PAT")
MCP_ENDPOINT = "https://mcp.cloud.cdata.com/mcp"

# Optional: force a specific catalog for demos
CDATA_CATALOG = os.getenv("CDATA_CATALOG")

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# Schema cache TTL in seconds (default 24h)
SCHEMA_CACHE_TTL = int(os.getenv("SCHEMA_CACHE_TTL", "86400"))

# Log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Max ReAct iterations (recursion_limit = MAX_ITERATIONS * 2)
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "25"))

# Output directory
OUTPUT_DIR = "output"


def get_llm(temperature: float = 0, model_override: str = None):
    """Factory function to create an LLM instance based on LLM_PROVIDER.

    Supports openai, anthropic, google, and ollama providers.
    Install the corresponding langchain package for your chosen provider.
    """
    provider = LLM_PROVIDER.lower()
    model = model_override or LLM_MODEL

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Install langchain-openai: pip install langchain-openai")
        return ChatOpenAI(model=model, temperature=temperature)

    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("Install langchain-anthropic: pip install langchain-anthropic")
        return ChatAnthropic(model=model, temperature=temperature)

    elif provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "Install langchain-google-genai: pip install langchain-google-genai"
            )
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError("Install langchain-ollama: pip install langchain-ollama")
        return ChatOllama(model=model, temperature=temperature)

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: '{provider}'. "
            "Use openai, anthropic, google, or ollama."
        )
