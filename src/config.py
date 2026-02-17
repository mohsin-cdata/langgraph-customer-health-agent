"""Configuration management for the customer health agent."""
import os
from dotenv import load_dotenv

# Load environment variables (.env takes precedence over system env)
load_dotenv(override=True)

class Config:
    """Central configuration class."""

    # CData Connect Cloud MCP
    CDATA_EMAIL = os.getenv("CDATA_EMAIL")
    CDATA_PAT = os.getenv("CDATA_PAT")
    MCP_ENDPOINT = "https://mcp.cloud.cdata.com/mcp"

    # Data Source Connection (Salesforce or Google Sheets)
    SALESFORCE_CONNECTION = os.getenv("SALESFORCE_CONNECTION", "LangGraph_Customer_Health_Agent")
    GOOGLE_SHEETS_CONNECTION = os.getenv("GOOGLE_SHEETS_CONNECTION", "LangGraph_Customer_Health_Agent_Google_Sheet")
    DATA_SOURCE = os.getenv("DATA_SOURCE", "google_sheets")  # "salesforce" or "google_sheets"

    # LLM API (OpenAI or any OpenAI-compatible API)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Output directory
    OUTPUT_DIR = "output"

    @classmethod
    def validate(cls):
        """Validate that all required environment variables are set."""
        missing = []

        if not cls.CDATA_EMAIL:
            missing.append("CDATA_EMAIL")
        if not cls.CDATA_PAT:
            missing.append("CDATA_PAT")
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Please create a .env file based on .env.example"
            )

        return True

# Validate on import
Config.validate()
