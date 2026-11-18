"""A native AReaL agent entry for an explicitly unscored real DSH episode."""

import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import tempfile


HERE = Path(__file__).resolve().parent
SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20,
            "max_completion_tokens": 32768, "max_total_tokens": 65536,
            "frequency_penalty": 0.0}


class DSHAgent:
    def __init__(self, root, runtime, out, generator_model="Qwen/Qwen3.5-4B",
                 reviewer_url="http://127.0.0.1:30102/v1", rounds=4,
                 reasoning_effort="off", sampling=None, episode_timeout=7200):
        self.root = Path(root)
        self.runtime = Path(runtime)
        self.out = Path(out)
        self.generator_model = generator_model
        self.reviewer_url = reviewer_url
        self.rounds = rounds
        self.reasoning_effort = reasoning_effort
        self.sampling = dict(SAMPLING if sampling is None else sampling)
        self.episode_timeout = episode_timeout
        self.metadata = {"policy_role": "generator", "reviewer_frozen": True,
                         "gold_feedback": False, "reward_status": "unscored",
                         "training_eligible": False, "optimizer_started": False}

    def get_session_metadata(self, data):
        return {**self.metadata, "generation_args": self.sampling,
                "chat_template_kwargs": {"enable_thinking": self.reasoning_effort == "high",
                                         "preserve_thinking": False}}

    def get_episode_metadata(self):
        return dict(self.metadata)

    async def run(self, data, *, base_url, api_key, proxy_gateway_api_key,
                  session_id, proxy_session_token, **kwargs):
        """Use only generation-scoped credentials; never pass the RL session key.

        An empty reward mapping invokes no set_reward call. AReaL's native
        individual exporter later fills missing returns with zero; those are
        unscored placeholders, not quality scores or eligible training data.
        """
        del api_key
        self.out.mkdir(mode=0o700, parents=True, exist_ok=True)
        episode = self.out / ("session-" + session_id.replace("/", "_"))
        episode.mkdir(mode=0o700)
        generator_url = base_url.rstrip("/") + "/v1"
        if generator_url.rstrip("/") == self.reviewer_url.rstrip("/"):
            raise ValueError("The frozen reviewer must bypass the Generator policy proxy")
        routing = {"generator_url": generator_url, "reviewer_url": self.reviewer_url,
                   "reviewer_policy_auth": False, "policy_session": session_id,
                   "reward_status": "unscored", "training_eligible": False}
        (episode / "routing.json").write_text(json.dumps(routing, indent=2) + "\n")
        with tempfile.TemporaryDirectory(prefix="policy-auth-", dir=self.out) as private:
            auth_file = Path(private) / "auth.json"
            headers = {"Authorization": "Bearer " + proxy_gateway_api_key,
                       "x-session-id": session_id, "x-session-token": proxy_session_token}
            descriptor = os.open(auth_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as auth:
                json.dump({"headers": headers}, auth)
            command = [sys.executable, str(HERE / "rollout.py"),
                       "--runtime", str(self.runtime), "--reference", str(data["reference"]),
                       "--out", str(episode / "episode"),
                       "--renderer-python", str(self.root / "renderer/venv/bin/python"),
                       "--render-runtime", str(self.root / "renderer"),
                       "--generator-model", self.generator_model,
                       "--generator-url", generator_url, "--generator-auth-file", str(auth_file),
                       "--reviewer-url", self.reviewer_url, "--rounds", str(self.rounds),
                       "--context-window", str(self.sampling["max_total_tokens"]),
                       "--max-tokens", str(self.sampling["max_completion_tokens"]),
                       "--reasoning-effort", self.reasoning_effort]
            with (episode / "rollout.stdout").open("wb") as out, (episode / "rollout.stderr").open("wb") as err:
                process = await asyncio.create_subprocess_exec(
                    *command, stdout=out, stderr=err, start_new_session=True)
                try:
                    code = await asyncio.wait_for(process.wait(), self.episode_timeout)
                except (TimeoutError, asyncio.CancelledError):
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        await asyncio.wait_for(process.wait(), 10)
                    except TimeoutError:
                        os.killpg(process.pid, signal.SIGKILL)
                        await process.wait()
                    raise
            if code:
                raise RuntimeError(f"Real DSH episode failed with exit {code}; inspect {episode}")
        self.metadata["episode_directory"] = str(episode)
        return {}
