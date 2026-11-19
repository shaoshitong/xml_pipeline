"""Run a real DSH generator and a separate frozen visual reviewer."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time

from dsh_profiles import profile_yaml
from prompts import generation_prompt, review_prompt
from ablate_skill import prompt_for_mode
from setup_sampling import INSTRUCT_SAMPLING, SAMPLING


HERE = Path(__file__).resolve().parent


def isolated_turn(command, endpoint, auth_file, logs, timeout, sampling=None):
    """Keep host inference/control ports outside the model's network namespace."""
    headers = json.loads(auth_file.read_text())["headers"] if auth_file else {}
    with tempfile.TemporaryDirectory(prefix="dsh-gateway-") as directory:
        socket = Path(directory) / "generation.sock"
        gateway_env = dict(os.environ, SANDBOX_GATEWAY_HEADERS=json.dumps(headers))
        gateway_env["SANDBOX_GATEWAY_SAMPLING"] = json.dumps(sampling or {})
        with (logs / "gateway.log").open("wb") as gateway_log:
            gateway = subprocess.Popen([
                sys.executable,
                str(HERE / "sandbox_gateway.py"), "--socket", str(socket),
                "--upstream", endpoint], stdout=gateway_log, stderr=gateway_log,
                env=gateway_env)
            try:
                deadline = time.monotonic() + 10
                while not (socket.exists() and socket.with_name(socket.name + ".netns").exists()):
                    if gateway.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Generation gateway failed to start")
                    time.sleep(0.05)
                command[1:1] = ["--ro-bind", directory, "/gateway"]
                with (logs / "events.jsonl").open("wb") as out, (logs / "stderr.log").open("wb") as err:
                    return subprocess.run(command, stdout=out, stderr=err, timeout=timeout,
                                          env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
            finally:
                gateway.terminate()
                gateway.wait(timeout=10)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_events(path):
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.startswith("{") and line.endswith("}")]


def saved_final(state, events, role):
    final = next((event for event in reversed(events) if event.get("type") == "final"), None)
    if final is not None and role == "reviewer" and state.get("exit") == 0:
        try:
            review_payload(final)
        except ValueError:
            return None
        state.update(completed=True, validation_error=None, revalidated_saved_final=True)
    return final if state.get("completed") else None


def run_turn(args, role, number, session):
    root = args.out / role
    checkpoint = root / f"round{number}"
    logs = checkpoint
    continuing = args.resume and checkpoint.exists()
    if continuing:
        state_file = checkpoint / "status.json"
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        previous = root / state.get("log_dir", checkpoint.name) / "events.jsonl"
        events = read_events(previous) if previous.exists() else []
        session = state.get("session_id") or next(
            (e["sessionId"] for e in events if e.get("type") == "session"), session)
        final = saved_final(state, events, role)
        if final is not None:
            save(state_file, state)
            return session, final
        sequence = len(list(root.glob(f"round{number}-continuation-*"))) + 1
        logs = root / f"round{number}-continuation-{sequence}"
    logs.mkdir(parents=True)
    home = root / "home"
    home.mkdir(exist_ok=True)
    model = args.generator_model if role == "generator" else args.reviewer_model
    endpoint = args.generator_url if role == "generator" else args.reviewer_url
    patch = root / "profile.yml"
    builder = profile_yaml
    effort = args.reasoning_effort
    context_window = args.context_window
    max_tokens = args.max_tokens
    if model == "deepseek-flash":
        from deepseek_profile import profile_yaml as builder
    if role == "reviewer":
        effort = "off"
        context_window = min(context_window, getattr(args, "reviewer_context_window", 65536))
        max_tokens = min(max_tokens, 32768)
    patch.write_text(builder(base_url="http://127.0.0.1:30101/v1", model=model, role=role,
                             context_window=context_window, max_tokens=max_tokens,
                             reasoning_effort=effort))
    prompt = generation_prompt(number, args.rounds) if role == "generator" else review_prompt(number)
    prompt = prompt_for_mode(args.skill_mode, role, number, args.rounds, prompt)
    if role == "generator" and number == 1 and args.seeded:
        prompt += ("\nround1.drawio is your own previous candidate, not a reference answer. "
                   "Inspect it and reference.png afresh, repair its technical validity as needed, "
                   "then render, inspect, and finish this round.\n")
    if role == "generator" and number == 1 and session:
        prompt += ("\nContinue the interrupted first generation in this session. Reuse the image inspection "
                   "and inventory already completed. Write the native XML with tools now instead of "
                   "repeating the inventory. Preserve any work already saved.\n")
    elif continuing:
        prompt += "\nContinue this interrupted stage using this session's own saved work.\n"
    if args.resume_note:
        prompt += "\nHost runtime recovery note: " + args.resume_note + "\n"
    if role == "generator" and args.single_self_review:
        prompt += "\nPerform at most one render-and-inspect cycle in this generation stage. Return artifact paths and remaining limitations afterward; the independent Reviewer performs the next review.\n"
    prompt += (f"\nWorkspace paths: /case/reference.png; /case/round{number}.drawio; "
               f"/case/round{number}.png. Use these absolute paths for file tools.\n")
    if role == "generator":
        renderer = [str(args.renderer_python), "/integration/render.py", f"/case/round{number}.drawio",
                    f"/case/round{number}.png", "--runtime", str(args.render_runtime)]
        prompt += "\nOfficial renderer command: " + shlex.join(renderer) + "\n"
    runtime = args.runtime.resolve()
    case = (args.out / "case").resolve()
    mounts = ["--bind" if role == "generator" else "--ro-bind", str(case), "/case"]
    command = ["bwrap", "--unshare-all", "--new-session", "--die-with-parent",
               "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
               "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
               "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
               "--ro-bind", str(runtime), str(runtime),
               "--bind", str(home.resolve()), "/session",
               "--ro-bind", str(patch.resolve()), "/profile.yml", *mounts,
               "--ro-bind", str(case / "reference.png"), "/case/reference.png",
               "--setenv", "HOME", "/session", "--setenv", "DSH_HOME", "/session/.dsh",
               "--setenv", "PATH", str(runtime / "node/bin") + ":" + str(args.renderer_python.parent) + ":/usr/bin:/bin",
               "--setenv", "LANG", "C.UTF-8", "--setenv", "ROLLOUT_API_KEY", "EMPTY",
               "--setenv", "DSH_TELEMETRY_DISABLED", "1", "--chdir", "/case"]
    command.extend(("--ro-bind", str(HERE / "render.py"), "/integration/render.py",
                    "--ro-bind", str(HERE / "sandbox_entry.py"), "/integration/sandbox_entry.py",
                    "--ro-bind", str(HERE / "sandbox_gateway.py"), "/integration/sandbox_gateway.py",
                    "--ro-bind", str(args.python_runtime_root), str(args.python_runtime_root)))
    for path in getattr(args, "extra_runtime_mounts", ()):
        command.extend(("--ro-bind", str(path), str(path)))
    for name in ("venv", "source", "chrome-linux64", "draw.war", "lib", "fonts", "fonts.conf"):
        path = args.render_runtime / name
        command.extend(("--ro-bind", str(path), str(path)))
    for name in ("resolv.conf", "hosts", "nsswitch.conf", "ssl/certs", "fonts", "ld.so.cache"):
        path = f"/etc/{name}"
        command.extend(("--ro-bind", path, path))
    command.extend(("--", str(args.renderer_python), "/integration/sandbox_entry.py",
                    "--socket", "/gateway/generation.sock", "--",
                    str(runtime / "node/bin/node"),
                    str(runtime / "dsh/node_modules/@deepseek-ai/dsh/lib/bin.js"),
                    "--profile", "headless", "--patch", "/profile.yml", "--json"))
    if session:
        command.extend(("--session-id", session))
    command.append(prompt)
    started = time.monotonic()
    auth_file = args.generator_auth_file if role == "generator" else getattr(args, "reviewer_auth_file", None)
    preset = getattr(args, "reviewer_sampling_preset", None) if role == "reviewer" else None
    preset = preset or args.sampling_preset
    sampling = dict({"model": {}, "instruct": INSTRUCT_SAMPLING,
                     "precise-coding": SAMPLING}[preset])
    if args.seed is not None:
        sampling["seed"] = args.seed
    try:
        result = isolated_turn(command, endpoint, auth_file, logs, args.turn_timeout, sampling)
        exit_code, timed_out = result.returncode, False
    except subprocess.TimeoutExpired:
        exit_code, timed_out = 124, True
    events = read_events(logs / "events.jsonl")
    final = next((e for e in reversed(events) if e.get("type") == "final"), None)
    validation_error = None
    if role == "reviewer" and exit_code == 0 and final is not None:
        try:
            review_payload(final)
        except ValueError:
            validation_error = "invalid_reviewer_json"
    sid = next((e["sessionId"] for e in events if e.get("type") == "session"), session)
    status = {"role": role, "round": number, "exit": exit_code, "timed_out": timed_out,
              "completed": exit_code == 0 and final is not None and validation_error is None,
              "validation_error": validation_error, "session_id": sid,
              "log_dir": logs.name,
              "seconds": round(time.monotonic() - started, 2),
              "tool_calls": sum(e.get("type") == "tool_call" for e in events)}
    save(logs / "status.json", status)
    if logs != checkpoint:
        save(checkpoint / "status.json", status)
    print(json.dumps(status), flush=True)
    if exit_code or final is None or validation_error:
        raise RuntimeError(f"DSH {role} round {number} failed; inspect {logs}")
    return sid, final


def final_text(event):
    for key in ("text", "content", "message"):
        value = event.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return final_text(value)
    raise ValueError("DSH final event has no textual payload")


def review_payload(event):
    text = final_text(event).strip()
    if not text.startswith("{"):
        blocks = re.findall(r"```(?:json)?[ \t]*\n(.*?)\n```", text, re.DOTALL)
        if len(blocks) == 1:
            text = blocks[0]
    repair = None
    try:
        review = json.loads(text)
    except json.JSONDecodeError as error:
        if error.msg != "Expecting ',' delimiter" or text[error.pos:error.pos + 1] != "]":
            raise
        normalized = text[:error.pos] + text[error.pos + 1:]
        review = json.loads(normalized)
        repair = {
            "operation": "remove_one_unexpected_array_closer", "offset": error.pos,
            "removed_character": "]", "original_sha256": sha256(text.encode()).hexdigest(),
            "normalized_sha256": sha256(normalized.encode()).hexdigest()}
    if (not isinstance(review, dict) or review.get("status") not in ("PASS", "FIX", "UNCERTAIN")
            or not isinstance(review.get("issues"), list)):
        raise ValueError("Reviewer must return a JSON object with status and issues")
    if repair:
        review["_host_json_repair"] = repair
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runtime", "reference", "out", "renderer_python", "render_runtime"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--python-runtime-root", type=Path,
                        default=Path("/share/anaconda3/envs/vllm017"))
    parser.add_argument("--generator-url", default="http://127.0.0.1:30101/v1")
    parser.add_argument("--generator-auth-file", type=Path,
                        help="Host-private generation credentials; never mounted into DSH")
    parser.add_argument("--reviewer-auth-file", type=Path,
                        help="Separate host-private credentials for an external frozen reviewer")
    parser.add_argument("--reviewer-context-window", type=int, default=65536)
    parser.add_argument("--reviewer-url", default="http://127.0.0.1:30102/v1")
    parser.add_argument("--generator-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--reviewer-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--rounds", default=4, type=int)
    parser.add_argument("--generator-session-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seeded", action="store_true")
    parser.add_argument("--skill-mode", choices=("full", "no-skill", "minimal"), default="full")
    parser.add_argument("--sampling-preset", choices=("model", "instruct", "precise-coding"),
                        default="model", help="Explicit wire parameters; model preserves legacy behavior")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--reviewer-sampling-preset", choices=("model", "instruct", "precise-coding"))
    parser.add_argument("--resume-note", default="")
    parser.add_argument("--single-self-review", action="store_true")
    parser.add_argument("--context-window", default=65536, type=int)
    parser.add_argument("--max-tokens", default=32768, type=int)
    parser.add_argument("--reasoning-effort", choices=("off", "low", "high", "max"), default="high")
    parser.add_argument("--turn-timeout", default=900, type=int)
    args = parser.parse_args()
    args.out = args.out.resolve()
    case = args.out / "case"
    case.mkdir(parents=True, exist_ok=args.resume or args.seeded or args.generator_session_id is not None)
    shutil.copyfile(args.reference, case / "reference.png")
    skill = case / ".agents/skills/drawio-reconstruction"
    if args.skill_mode == "full":
        skill.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / "reconstruction_skill.txt", skill / "SKILL.md")
    elif skill.exists():
        shutil.rmtree(skill)
    save(args.out / "protocol.json", {"generator": args.generator_model,
         "reviewer": args.reviewer_model, "reviewer_frozen": True,
         "separate_model_instances": args.generator_model.startswith("Qwen/"),
         "external_api_generator": args.generator_model == "deepseek-flash",
         "training": False, "gold_feedback": False, "rounds": args.rounds,
         "context_window": args.context_window, "max_tokens": args.max_tokens,
         "reasoning_effort": args.reasoning_effort,
         "single_self_review": args.single_self_review,
         "continued_generator_session": args.generator_session_id,
         "runtime_recovery_note": args.resume_note,
         "fresh_context_from_own_candidate": args.seeded,
         "skill_mode": args.skill_mode,
         "sampling_preset": args.sampling_preset,
         "reviewer_sampling_preset": args.reviewer_sampling_preset,
         "seed": args.seed,
         "reference_sha256": sha256(args.reference.read_bytes()).hexdigest()})
    generator, reviewer = args.generator_session_id, None
    for n in range(1, args.rounds + 1):
        generator, _ = run_turn(args, "generator", n, generator)
        xml = case / f"round{n}.drawio"
        preview = case / f"round{n}.png"
        subprocess.run([str(args.renderer_python), str(HERE / "render.py"), str(xml),
                        str(preview), "--runtime", str(args.render_runtime)], check=True)
        save(args.out / "progress.json", {"completed_generation": n,
             "xml_bytes": xml.stat().st_size, "xml_sha256": sha256(xml.read_bytes()).hexdigest(),
             "timestamp": time.time()})
        if n < args.rounds:
            digest = sha256(xml.read_bytes()).hexdigest()
            reviewer, event = run_turn(args, "reviewer", n, reviewer)
            save(case / f"review{n}.json", review_payload(event))
            if sha256(xml.read_bytes()).hexdigest() != digest:
                raise RuntimeError("Reviewer modified the frozen candidate")
    save(args.out / "completed.json", {"candidate": str(case / f"round{args.rounds}.drawio"),
         "generator_session": generator, "reviewer_session": reviewer, "timestamp": time.time()})


if __name__ == "__main__":
    main()
