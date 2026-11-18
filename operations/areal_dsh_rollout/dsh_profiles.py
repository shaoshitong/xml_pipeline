"""Emit a fresh headless DSH patch for one local Qwen vision endpoint."""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit


DSH_VERSION = "0.2.1-rc.2"
MODELS = ("Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-9B")
SGLANG_PARSERS = ("--reasoning-parser", "qwen3", "--tool-call-parser", "qwen3_coder")

# These IDs come from the installed dsh-base/headless 0.2.1-rc.2 bundles.
DISABLED = (
    "credentials", "authorization", "deepseek-account", "llm-deepseek",
    "llm-deepseek-account", "deepseek-llm-api-extensions", "settings", "hmr",
    "session-title-llm", "otel", "session-telemetry-otel", "remote-access",
    "tool-plugin-manager", "web-search-deepseek", "web-deepseek-api", "tool-web",
    "mcp-resources", "tool-subagent", "tool-subagent-fork",
    "tool-subagent-control", "tool-subagent-list-agents", "subagent-spawn-in-process",
    "subagent-fork-in-process", "workflow-ptc", "tool-workflow",
)


def build_patch(
    base_url: str,
    model: str,
    *,
    role: str = "generator",
    api_key_env: str = "ROLLOUT_API_KEY",
    context_window: int = 32768,
    max_tokens: int = 8192,
    reasoning_effort: str = "high",
) -> list[dict]:
    """Use with an empty DSH_HOME, never an account or gold-MCP profile.

    Generator and reviewer need separate server processes/checkpoints; naming
    routes does not freeze weights or provide filesystem/network isolation.
    """
    endpoint = base_url.rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not endpoint.endswith("/v1"):
        raise ValueError("base_url must be the SGLang API root ending in /v1")
    if model not in MODELS or role not in ("generator", "reviewer"):
        raise ValueError("Select Qwen3.5-4B/9B and generator/reviewer explicitly")
    if reasoning_effort not in ("off", "high") or not 0 < max_tokens < context_window:
        raise ValueError("Invalid reasoning effort or output/context token limits")

    provider = f"rollout-{role}"
    route = {
        "api": "openai-completions",
        "baseURL": endpoint,
        "apiKeyEnv": api_key_env,
        "compat": {
            "thinkingFormat": "qwen-chat-template",
            "maxTokensField": "max_tokens",
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": False,
            "requiresReasoningContentOnAssistantMessages": True,
        },
        "models": [{
            "id": model,
            "input": ["text", "image"],
            "contextWindow": context_window,
            "maxTokens": max_tokens,
            "reasoningEfforts": {"off": None, "high": "high"},
        }],
    }
    patch = [{"id": name, "disabled": True} for name in DISABLED]
    patch.extend([
        {"id": "llm-pi-ai", "disabled": False,
         "config": {"providers": {provider: route}}},
        {"id": "agent-default-model", "config": {
            "provider": provider, "model": model, "reasoningEffort": reasoning_effort}},
        {"id": "attachment-local", "disabled": False},
        {"id": "tool-fs", "disabled": False,
         "config": {"read": True, "readImage": True, "write": True, "edit": True}},
        {"id": "tool-fs-search", "disabled": False},
        {"id": "tool-bash", "disabled": False},
        {"id": "bash-sandbox", "config": {"timeoutMs": 60000}},
        {"id": "approval", "config": {"policy": "never"}},
    ])
    return patch


def profile_yaml(**kwargs) -> str:
    """JSON is a YAML subset, accepted by DSH without a Python YAML dependency."""
    return json.dumps(build_patch(**kwargs), ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--role", choices=("generator", "reviewer"), default="generator")
    parser.add_argument("--api-key-env", default="ROLLOUT_API_KEY")
    parser.add_argument("--context-window", type=int, default=32768)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--reasoning-effort", choices=("off", "high"), default="high")
    print(profile_yaml(**vars(parser.parse_args())), end="")


if __name__ == "__main__":
    main()
