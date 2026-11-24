"""Engine configuration: environment variables, model IDs, latency budget."""
import os

# Database (separate from the legacy app's database).
DATABASE_URL = os.environ.get("ENGINE_DATABASE_URL", "sqlite:///engine.db")

# Identity for stdio mode: the MCP client config sets CAMPFIRE_USER.
CAMPFIRE_USER = os.environ.get("CAMPFIRE_USER", "local")

# External services.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Models.
LLM_MODEL = os.environ.get("ENGINE_LLM_MODEL", "claude-haiku-5-5")
EMBEDDING_MODEL = os.environ.get("ENGINE_EMBEDDING_MODEL", "text-embedding-3-small")

# Product requirement (not a ranking parameter): discover() should answer in
# about this many seconds. Tag extraction that doesn't fit goes to the queue.
LATENCY_BUDGET_S = float(os.environ.get("ENGINE_LATENCY_BUDGET_S", "8"))
