"""Shared settings for the Campus Customs agent team.

Model rule for this homework: every agent uses gpt-6-luna through Portkey,
keyed by PORTKEY_API_KEY. The model name is a constant on purpose, not an
environment variable, so no other model can be swapped in.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_DIR / "backend"
PROMPTS_DIR = BACKEND_DIR / "prompts"
OUTPUT_DIR = PROJECT_DIR / "output"
AUDIT_PATH = OUTPUT_DIR / "audit_trail.json"
MCP_CONFIG_PATH = PROJECT_DIR / ".mcp.json"
MCP_SERVER_NAME = "campus-customs"
ORIGINAL_DB_PATH = PROJECT_DIR / "data" / "campus_customs.db"   # never modified; reset source
WORKING_DB_PATH = PROJECT_DIR / "data" / "campus_customs_new.db"  # what the MCP server reads/writes

# .env in this folder first; then the nearest parent .env (never overrides values already set).
load_dotenv(PROJECT_DIR / ".env")
for parent in PROJECT_DIR.parents:
    if (parent / ".env").is_file():
        load_dotenv(parent / ".env")
        break

# --------------------------------------------------------------------------- #
# Model: gpt-6-luna via Portkey, and nothing else.
# --------------------------------------------------------------------------- #
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = "gpt-6-luna"

MODEL_SETTINGS = OpenAIChatModelSettings(
    # gpt-6-luna on /v1/chat/completions only allows function tools with reasoning off.
    openai_reasoning_effort="none",
    max_tokens=1500,          # cap each model reply; agents return short structured reports
    parallel_tool_calls=True,  # e.g. check stock and pricing in one round trip
)


def portkey_model() -> OpenAIChatModel:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing: copy .env.example to .env and add your key.")
    client = AsyncOpenAI(
        api_key="not-used",
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key},
    )
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# --------------------------------------------------------------------------- #
# Token / loop limits (shared by the whole team for one run)
# --------------------------------------------------------------------------- #
MAX_DELEGATION_DEPTH = 3       # Boss -> A -> B -> C, no deeper
TEAM_USAGE_LIMITS = UsageLimits(
    request_limit=40,          # total model calls across all agents in one team run
    tool_calls_limit=80,       # total tool calls across all agents in one team run
    total_tokens_limit=200_000,
)
TEAM_RUN_TIMEOUT_SECONDS = 300
AGENT_RETRIES = 2              # retries for malformed tool args / output per agent
AUDIT_MAX_CHARS = 4000         # truncate very long tool results in the audit trail
