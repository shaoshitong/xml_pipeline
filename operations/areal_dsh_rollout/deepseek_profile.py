"""DeepSeek Flash vision profile using DSH's native pi-ai DeepSeek wire format.

The profile points only at the sandbox gateway. The real API key belongs to the
host gateway auth file; DSH receives a non-secret placeholder via api_key_env.
Context/output limits are explicit inputs from the host's verified model metadata.
"""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit

from dsh_profiles import MODELS, build_patch as common_patch


MODEL = "deepseek-flash"
PROVIDER = "deepseek"
EFFORTS = ("off", "low", "high", "max")


def build_patch(
    base_url: str,
    model: str = MODEL,
    *,
    context_window: int,
    max_tokens: int,
    role: str = "generator",
    api_key_env: str = "ROLLOUT_API_KEY",
    reasoning_effort: str = "max",
) -> list[dict]:
    """Reuse common tools/isolation, replacing the entire Qwen provider route."""
    if model != MODEL or reasoning_effort not in EFFORTS:
        raise ValueError("Use the vision-capable deepseek-flash and a supported effort")
    if urlsplit(base_url).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("DSH must use its loopback host-auth gateway")
    patch = common_patch(
        base_url, MODELS[0], role=role, api_key_env=api_key_env,
        context_window=context_window, max_tokens=max_tokens,
        reasoning_effort="off" if reasoning_effort == "off" else "high",
    )
    route = {
        "api": "openai-completions",
        "baseURL": base_url.rstrip("/"),
        "apiKeyEnv": api_key_env,
        "retryPolicy": {"mode": "normal", "maxRetries": 0},
        "compat": {
            "thinkingFormat": "deepseek",
            "maxTokensField": "max_tokens",
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": True,
            "requiresReasoningContentOnAssistantMessages": True,
            "supportsStore": False,
        },
        "models": [{
            "id": MODEL, "input": ["text", "image"],
            "contextWindow": context_window, "maxTokens": max_tokens,
            "reasoningEfforts": {"off": None, "low": "low", "high": "high", "max": "max"},
        }],
    }
    for item in patch:
        if item["id"] == "llm-pi-ai":
            item["config"] = {"providers": {PROVIDER: route}}
        elif item["id"] == "agent-default-model":
            item["config"] = {"provider": PROVIDER, "model": MODEL,
                              "reasoningEffort": reasoning_effort}
    return patch


def profile_yaml(**kwargs) -> str:
    return json.dumps(build_patch(**kwargs), ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", choices=(MODEL,), default=MODEL)
    parser.add_argument("--role", choices=("generator", "reviewer"), default="generator")
    parser.add_argument("--api-key-env", default="ROLLOUT_API_KEY")
    parser.add_argument("--context-window", required=True, type=int)
    parser.add_argument("--max-tokens", required=True, type=int)
    parser.add_argument("--reasoning-effort", choices=EFFORTS, default="max")
    print(profile_yaml(**vars(parser.parse_args())), end="")


if __name__ == "__main__":
    main()

