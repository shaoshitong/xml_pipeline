"""Run a real DSH generator and a separate frozen visual reviewer."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import time

from dsh_profiles import profile_yaml
from prompts import generation_prompt, review_prompt


HERE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run_turn(args, role, number, session):
    root = args.out / role
    logs = root / f"round{number}"
    logs.mkdir(parents=True)
    home = root / "home"
    home.mkdir(exist_ok=True)
    model = args.generator_model if role == "generator" else args.reviewer_model
    endpoint = args.generator_url if role == "generator" else args.reviewer_url
    patch = root / "profile.yml"
    patch.write_text(profile_yaml(base_url=endpoint, model=model, role=role,
                                  context_window=args.context_window,
                                  max_tokens=args.max_tokens))
    prompt = generation_prompt(number, args.rounds) if role == "generator" else review_prompt(number)
    if role == "generator":
        renderer = [str(args.renderer_python), "/integration/render.py", f"round{number}.drawio",
                    f"round{number}.png", "--runtime", str(args.render_runtime)]
        prompt += "\nOfficial renderer command: " + shlex.join(renderer) + "\n"
    runtime = args.runtime.resolve()
    case = (args.out / "case").resolve()
    mounts = ["--bind" if role == "generator" else "--ro-bind", str(case), "/case"]
    command = ["bwrap", "--unshare-all", "--share-net", "--new-session", "--die-with-parent",
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
                    "--ro-bind", "/share/anaconda3/envs/vllm017", "/share/anaconda3/envs/vllm017"))
    for name in ("venv", "source", "chrome-linux64", "draw.war", "lib", "fonts", "fonts.conf"):
        path = args.render_runtime / name
        command.extend(("--ro-bind", str(path), str(path)))
    for name in ("resolv.conf", "hosts", "nsswitch.conf", "ssl/certs", "fonts", "ld.so.cache"):
        path = f"/etc/{name}"
        command.extend(("--ro-bind", path, path))
    command.extend(("--", str(runtime / "node/bin/node"),
                    str(runtime / "dsh/node_modules/@deepseek-ai/dsh/lib/bin.js"),
                    "--profile", "headless", "--patch", "/profile.yml", "--json"))
    if session:
        command.extend(("--session-id", session))
    command.append(prompt)
    started = time.monotonic()
    with (logs / "events.jsonl").open("wb") as out, (logs / "stderr.log").open("wb") as err:
        result = subprocess.run(command, stdout=out, stderr=err, timeout=args.turn_timeout,
                                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    events = [json.loads(line) for line in (logs / "events.jsonl").read_text().splitlines()
              if line.startswith("{")]
    final = next((e for e in reversed(events) if e.get("type") == "final"), None)
    sid = next((e["sessionId"] for e in events if e.get("type") == "session"), session)
    status = {"role": role, "round": number, "exit": result.returncode,
              "completed": result.returncode == 0 and final is not None, "session_id": sid,
              "seconds": round(time.monotonic() - started, 2),
              "tool_calls": sum(e.get("type") == "tool_call" for e in events)}
    save(logs / "status.json", status)
    print(json.dumps(status), flush=True)
    if result.returncode or final is None:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runtime", "reference", "out", "renderer_python", "render_runtime"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--generator-url", default="http://127.0.0.1:30101/v1")
    parser.add_argument("--reviewer-url", default="http://127.0.0.1:30102/v1")
    parser.add_argument("--generator-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--reviewer-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--rounds", default=4, type=int)
    parser.add_argument("--context-window", default=32768, type=int)
    parser.add_argument("--max-tokens", default=8192, type=int)
    parser.add_argument("--turn-timeout", default=900, type=int)
    args = parser.parse_args()
    args.out = args.out.resolve()
    case = args.out / "case"
    case.mkdir(parents=True)
    shutil.copyfile(args.reference, case / "reference.png")
    skill = case / ".agents/skills/drawio-reconstruction"
    skill.mkdir(parents=True)
    shutil.copyfile(HERE / "reconstruction_skill.txt", skill / "SKILL.md")
    save(args.out / "protocol.json", {"generator": args.generator_model,
         "reviewer": args.reviewer_model, "reviewer_frozen": True,
         "separate_model_instances": True, "gold_feedback": False, "rounds": args.rounds,
         "reference_sha256": sha256(args.reference.read_bytes()).hexdigest()})
    generator = reviewer = None
    for n in range(1, args.rounds + 1):
        generator, _ = run_turn(args, "generator", n, generator)
        xml = case / f"round{n}.drawio"
        subprocess.run([str(args.renderer_python), str(HERE / "render.py"), str(xml),
                        str(case / f"round{n}.png"), "--runtime", str(args.render_runtime)], check=True)
        save(args.out / "progress.json", {"completed_generation": n,
             "xml_bytes": xml.stat().st_size, "xml_sha256": sha256(xml.read_bytes()).hexdigest(),
             "timestamp": time.time()})
        if n < args.rounds:
            digest = sha256(xml.read_bytes()).hexdigest()
            reviewer, event = run_turn(args, "reviewer", n, reviewer)
            text = final_text(event).strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            save(case / f"review{n}.json", json.loads(text))
            if sha256(xml.read_bytes()).hexdigest() != digest:
                raise RuntimeError("Reviewer modified the frozen candidate")
    save(args.out / "completed.json", {"candidate": str(case / f"round{args.rounds}.drawio"),
         "generator_session": generator, "reviewer_session": reviewer, "timestamp": time.time()})


if __name__ == "__main__":
    main()
