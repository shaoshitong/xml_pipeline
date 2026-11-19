"""Real AReaL v2 online external-API evaluation, with no trainer or token fabrication.

The episode command is a JSON argv list for the real DSH rollout driver. Use
@AREAL_BASE_URL@ and @AREAL_AUTH_FILE@ in its host gateway arguments, and
@EPISODE_OUT@ / @REFERENCE@ for its ordinary paths. The credential upstream
must be a local gateway: only its task token enters AReaL, never the provider key.
"""

import argparse
from hashlib import sha256
import hmac
import http.client
import json
import os
from pathlib import Path
import secrets
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


AREAL_COMMIT = "64a7fcca3936ddf2ab16bb1dd3e776d66ced31ff"
HERE = Path(__file__).resolve().parent
RECOVERY_POLICY = ("Previous host time limit interrupted this stage. Reuse your saved work. "
                   "Complete at most one render-and-inspect cycle in each remaining generation stage, "
                   "then return artifact paths and remaining limitations so scheduled independent review can proceed.")


def serve_credential_gateway(args):
    from sandbox_gateway import Relay, ThreadedHTTPServer, configure

    task_token = os.environ[args.provider_token_env]
    if args.key_file.stat().st_mode & 0o077:
        raise ValueError("Provider key file must be private")
    provider_key = args.key_file.read_text().strip()
    proxy = urlsplit(os.environ.get("ROLLOUT_HTTPS_CONNECT_PROXY", ""))

    class AuthenticatedRelay(Relay):
        def relay(self):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + task_token):
                self.send_error(403)
                return
            super().relay()

    def connection():
        if proxy.hostname:
            client = http.client.HTTPSConnection(proxy.hostname, proxy.port, timeout=900)
            client.set_tunnel("api.deepseek.com", 443)
            return client
        return http.client.HTTPSConnection("api.deepseek.com", 443, timeout=900)

    server = configure(ThreadedHTTPServer(("127.0.0.1", args.port), AuthenticatedRelay),
                       connection, {"Authorization": "Bearer " + provider_key})
    print(json.dumps({"credential_gateway_ready": True, "port": server.server_port}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def native_post(base_url, path, key, body):
    # Control-plane traffic must stay local even when provider egress uses a proxy.
    request = Request(base_url.rstrip("/") + path, data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with build_opener(ProxyHandler({})).open(request, timeout=30) as response:
        return json.load(response)


def episode_command(template, replacements):
    if not isinstance(template, list) or not template or not all(isinstance(x, str) for x in template):
        raise ValueError("episode-command must contain a JSON argv list")
    for required in ("@AREAL_BASE_URL@", "@AREAL_AUTH_FILE@"):
        if not any(required in item for item in template):
            raise ValueError("The real DSH driver must route through both native AReaL placeholders")
    command = []
    for item in template:
        for marker, value in replacements.items():
            item = item.replace(marker, value)
        command.append(item)
    return command


def default_episode(args):
    return [sys.executable, str(HERE / "rollout.py"), "--runtime", str(args.runtime.resolve()),
            "--reference", "@REFERENCE@", "--out", "@EPISODE_OUT@",
            "--renderer-python", str(args.root / "renderer/venv/bin/python"),
            "--render-runtime", str(args.root / "renderer"), "--generator-model", args.model,
            "--generator-url", "@AREAL_BASE_URL@", "--generator-auth-file", "@AREAL_AUTH_FILE@",
            "--reviewer-model", "Qwen/Qwen3.5-4B", "--reviewer-url", args.reviewer_url,
            "--rounds", str(args.rounds), "--skill-mode", args.skill_mode,
            "--sampling-preset", "model", "--reviewer-sampling-preset", "instruct",
            "--context-window", str(args.context_window), "--max-tokens", str(args.max_tokens),
            "--reasoning-effort", args.reasoning_effort, "--turn-timeout", str(args.turn_timeout)]


def run_dsh(command, output, timeout, token_env):
    environment = dict(os.environ)
    environment.pop(token_env, None)
    with (output / "dsh.stdout").open("wb") as out, (output / "dsh.stderr").open("wb") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err,
                                   env=environment, start_new_session=True)
        try:
            return {"exit": process.wait(timeout=timeout), "timed_out": False}
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return {"exit": process.returncode, "timed_out": True}


def image_count(value):
    if isinstance(value, dict):
        own = int(value.get("type") == "image_url")
        return own + sum(image_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(image_count(item) for item in value)
    return 0


def add_evaluation_arguments(evaluation):
    for name in ("root", "runtime", "reference", "out"):
        evaluation.add_argument("--" + name, type=Path, required=True)
    evaluation.add_argument("--episode-command", type=Path)
    evaluation.add_argument("--resume-from", type=Path, help="Previous evaluation root containing this DSH episode")
    evaluation.add_argument("--restart-reviewer", action="store_true", help="Resume Generator with a fresh Reviewer session")
    evaluation.add_argument("--api-url", default="http://127.0.0.1:30555/v1")
    evaluation.add_argument("--model", default="deepseek-flash")
    evaluation.add_argument("--reviewer-url", default="http://127.0.0.1:30001/v1")
    evaluation.add_argument("--provider-token-env", default="AREAL_EXTERNAL_TASK_TOKEN")
    evaluation.add_argument("--host-evaluation", type=Path)
    evaluation.add_argument("--rounds", type=int, default=4)
    evaluation.add_argument("--skill-mode", choices=("full", "no-skill", "minimal"), default="full")
    evaluation.add_argument("--context-window", type=int, default=1048576)
    evaluation.add_argument("--max-tokens", type=int, default=131072)
    evaluation.add_argument("--reasoning-effort", choices=("low", "high", "max"), default="max")
    evaluation.add_argument("--turn-timeout", type=int, default=900)
    evaluation.add_argument("--timeout", type=float, default=7200)


def run_managed(args):
    args.out = args.out.resolve()
    args.out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = args.out.parent / (args.out.name + ".credential-gateway.log")
    token = secrets.token_urlsafe(32)
    environment = dict(os.environ, **{args.provider_token_env: token})
    if args.proxy:
        environment["ROLLOUT_HTTPS_CONNECT_PROXY"] = args.proxy
    command = [sys.executable, str(Path(__file__).resolve()), "credential-gateway",
               "--key-file", str(args.key_file), "--port", str(args.credential_port),
               "--provider-token-env", args.provider_token_env]
    previous = os.environ.get(args.provider_token_env)
    with log_path.open("wb") as log:
        gateway = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log,
                                   env=environment, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(gateway.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=30):
                    raise TimeoutError(f"Credential gateway not ready; inspect {log_path}")
                line = gateway.stdout.readline()
            if not line:
                raise RuntimeError(f"Credential gateway exited before ready; inspect {log_path}")
            ready = json.loads(line)
            if not ready.get("credential_gateway_ready") or not ready.get("port"):
                raise RuntimeError("Credential gateway returned an invalid readiness record")
            args.api_url = f"http://127.0.0.1:{ready['port']}/v1"
            os.environ[args.provider_token_env] = token
            print(json.dumps({"phase": "credential_gateway_ready", "port": ready["port"]}), flush=True)
            return evaluate(args)
        finally:
            if previous is None:
                os.environ.pop(args.provider_token_env, None)
            else:
                os.environ[args.provider_token_env] = previous
            if gateway.poll() is None:
                gateway.terminate()
                try:
                    gateway.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    gateway.kill()
                    gateway.wait()
            if args.out.is_dir():
                log.flush()
                log_path.replace(args.out / "credential-gateway.log")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    gateway_parser = subparsers.add_parser("credential-gateway")
    gateway_parser.add_argument("--key-file", type=Path, required=True)
    gateway_parser.add_argument("--port", type=int, default=30555)
    gateway_parser.add_argument("--provider-token-env", default="AREAL_EXTERNAL_TASK_TOKEN")
    add_evaluation_arguments(subparsers.add_parser("eval"))
    managed = subparsers.add_parser("run")
    add_evaluation_arguments(managed)
    managed.add_argument("--key-file", type=Path, required=True)
    managed.add_argument("--proxy", help="Restricted HTTPS CONNECT relay for the owned credential gateway")
    managed.add_argument("--credential-port", type=int, default=0)
    args = parser.parse_args()
    if args.mode == "credential-gateway":
        serve_credential_gateway(args)
        return 0
    if args.mode == "run":
        return run_managed(args)
    return evaluate(args)


def evaluate(args):
    if args.restart_reviewer and not args.resume_from:
        raise ValueError("restart-reviewer requires resume-from")
    target = urlsplit(args.api_url)
    if target.scheme != "http" or target.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("api-url must point to the local credential gateway, not directly to the provider")
    if target.username or target.password or target.query or target.fragment or target.path != "/v1":
        raise ValueError("api-url must be a credential-free local API origin ending in /v1")

    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ["PYTHONPATH"] = str(HERE)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    from areal.api.cli_args import AgentConfig, InferenceEngineConfig
    from areal.infra.scheduler.local import LocalScheduler
    from areal.utils.network import gethostip
    from areal.v2.inference_service.controller.controller import RolloutControllerV2

    source = Path(sys.modules["areal"].__file__).resolve().parents[1]
    assert source == args.root.resolve() / "controller/source" / ("AReaL-" + AREAL_COMMIT)
    local_hosts = ("127.0.0.1", "localhost", "::1", gethostip())
    os.environ["NO_PROXY"] = ",".join(filter(None, (os.environ.get("NO_PROXY", ""), *local_hosts)))
    task_token = os.environ.pop(args.provider_token_env)
    args.out = args.out.resolve()
    args.out.mkdir(mode=0o700, parents=True)
    reference_sha256 = sha256(args.reference.read_bytes()).hexdigest()
    resumed_from = args.resume_from.resolve() if args.resume_from else None
    if resumed_from:
        previous_episode = resumed_from / "episode"
        previous_protocol = json.loads((previous_episode / "protocol.json").read_text())
        if previous_protocol["reference_sha256"] != reference_sha256:
            raise ValueError("Resume reference SHA256 does not match the previous DSH episode")
        shutil.copytree(previous_episode, args.out / "episode", symlinks=True)
        reviewer = args.out / "episode/reviewer"
        if args.restart_reviewer and reviewer.exists():
            reviewer.rename(reviewer.with_name("reviewer-before-restart-" + secrets.token_hex(4)))
    template = json.loads(args.episode_command.read_text()) if args.episode_command else default_episode(args)
    if resumed_from:
        template += ["--resume", "--resume-note", RECOVERY_POLICY]
    episode_command(template, {})
    admin_key = "admin-" + secrets.token_urlsafe(32)
    trial = "external-eval-" + secrets.token_hex(6)
    config = InferenceEngineConfig(
        _version="v2", api_url=args.api_url, model=args.model, provider_api_key=task_token,
        experiment_name="drawio-external-eval", trial_name=trial, fileroot=str(args.out),
        max_concurrent_rollouts=1, consumer_batch_size=1, request_retries=1,
        agent=AgentConfig(agent_cls_path="areal.experimental.openai.proxy.online_agent._OnlineAgent",
                          mode="online", admin_api_key=admin_key,
                          export_style="individual", turn_discount=1.0),
        admin_api_key=admin_key,
    )
    name_resolve_root = args.out / "name-resolve"
    name_resolve_root.mkdir()
    scheduler = LocalScheduler(log_dir=str(args.out / "native-logs"),
                               experiment_name=config.experiment_name, trial_name=trial,
                               fileroot=str(args.out), enable_tms_offload=False,
                               nfs_record_root=str(name_resolve_root))
    controller = RolloutControllerV2(config=config, scheduler=scheduler)
    audit = {"kind": "native_areal_external_api_eval", "areal_commit": AREAL_COMMIT,
             "model": args.model, "training_eligible": False, "optimizer_started": False,
             "native_mode": "online", "gpu_resources": 0, "model_services_started": False,
             "behavior_token_ids_available": False, "behavior_logprobs_available": False,
             "quality_reward": None, "host_evaluation": None,
             "native_lifecycle_placeholder": 0.0,
             "placeholder_meaning": "Only finalizes the native online session; never a quality score",
             "real_provider_key_read_by_this_process": False,
             "credential_boundary": "AReaL receives only the local gateway task token",
             "captured_role": "generator",
             "reviewer": {"model": "Qwen/Qwen3.5-4B", "url": args.reviewer_url,
                          "frozen": True, "native_capture": False},
             "reference_sha256": reference_sha256, "resumed_from": str(resumed_from) if resumed_from else None,
             "recovery_policy": RECOVERY_POLICY if resumed_from else None,
             "reviewer_restarted": args.restart_reviewer}
    save(args.out / "eval-contract.json", audit)
    try:
        controller.initialize(role="external-eval", wait=True)
        gateway = controller.proxy_gateway_addr.rstrip("/")
        task_id = controller.submit(data={}, workflow=None, is_eval=True, group_size=1,
                                    workflow_kwargs={"timeout": args.timeout, "export_style": "individual",
                                                     "discount": 1.0})
        session = native_post(gateway, "/rl/start_session", admin_key,
                              {"task_id": str(task_id), "group_size": 1})["sessions"][0]
        audit["native_task_id"] = task_id
        audit["native_session_id"] = session["session_id"]
        with tempfile.TemporaryDirectory(prefix="host-auth-", dir=args.out) as private:
            auth_file = Path(private) / "auth.json"
            descriptor = os.open(auth_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as auth:
                json.dump({"headers": {"Authorization": "Bearer " + session["session_api_key"]}}, auth)
            command = episode_command(template, {
                "@AREAL_BASE_URL@": gateway + "/v1", "@AREAL_AUTH_FILE@": str(auth_file),
                "@EPISODE_OUT@": str(args.out / "episode"), "@REFERENCE@": str(args.reference.resolve()),
            })
            save(args.out / "episode-command.json", command)
            audit["dsh_process"] = run_dsh(command, args.out, args.timeout, args.provider_token_env)
        # v2 online export requires a ready trajectory, which set_reward creates.
        # The explicit sentinel remains visibly unscored in both contract and result.
        native_post(gateway, "/rl/set_reward", session["session_api_key"],
                    {"interaction_id": None, "reward": 0.0, "model": args.model})
        trajectory = controller.wait_for_task(task_id, timeout=60)
        if not trajectory or not trajectory.get("interactions"):
            raise RuntimeError("Native external mode exported no real string interactions")
        if any(key in trajectory for key in ("input_ids", "logprobs", "loss_mask")):
            raise RuntimeError("External evaluation unexpectedly returned token-backed training fields")
        interactions = trajectory["interactions"]
        audit["native_interactions"] = len(interactions)
        audit["image_bearing_interactions"] = sum(image_count(item["request"]) > 0 for item in interactions)
        audit["episode_success"] = audit["dsh_process"]["exit"] == 0
        audit["valid_visual_benchmark"] = audit["episode_success"] and audit["image_bearing_interactions"] > 0
        if args.host_evaluation:
            audit["host_evaluation"] = json.loads(args.host_evaluation.read_text())
        save(args.out / "native-string-trajectory.json", trajectory)
        audit["status"] = "completed"
        save(args.out / "eval-result.json", audit)
        print(json.dumps({key: audit[key] for key in ("native_interactions", "episode_success",
                                                     "valid_visual_benchmark", "training_eligible")}), flush=True)
        return 0 if audit["valid_visual_benchmark"] else 1
    except Exception as error:
        audit.update(status="failed", error_type=type(error).__name__)
        save(args.out / "eval-result.json", audit)
        raise
    finally:
        controller.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
