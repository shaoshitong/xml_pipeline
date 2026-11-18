"""Capture real DSH request settings against a deliberate HTTP 503 stub."""

import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace

from rollout import run_turn
from setup_sampling import INSTRUCT_SAMPLING, SAMPLING


class Capture(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append({
            "path": self.path, "model": body.get("model"),
            "max_tokens": body.get("max_tokens"),
            "chat_template_kwargs": body.get("chat_template_kwargs"),
            "tools": [tool["function"]["name"] for tool in body.get("tools", [])],
            "sampling": {key: body.get(key) for key in INSTRUCT_SAMPLING},
        })
        response = json.dumps({"error": {"message": "Deliberate protocol preflight 503",
                                        "type": "preflight"}}).encode()
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=39303)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Capture)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        for effort in ("high", "off"):
            output = args.output.with_suffix("") / effort
            case = output / "case"
            case.mkdir(parents=True)
            # A protocol fixture only; no model generates or evaluates this image.
            (case / "reference.png").write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="))
            endpoint = f"http://127.0.0.1:{args.port}/v1"
            options = SimpleNamespace(
                out=output, runtime=args.runtime, resume=False, resume_note="", rounds=4,
                seeded=False, skill_mode="full", seed=None,
                sampling_preset="precise-coding" if effort == "high" else "instruct",
                generator_model="Qwen/Qwen3.5-4B", reviewer_model="Qwen/Qwen3.5-4B",
                generator_url=endpoint, reviewer_url=endpoint,
                generator_auth_file=None,
                context_window=65536, max_tokens=32768, reasoning_effort=effort,
                renderer_python=args.root / "renderer/venv/bin/python",
                render_runtime=args.root / "renderer", turn_timeout=30,
            )
            before = len(server.requests)
            error = None
            try:
                run_turn(options, "generator", 1, None)
            except RuntimeError as exc:
                error = str(exc)
            requests = server.requests[before:]
            profile = json.loads((output / "generator/profile.yml").read_text())
            route = next(item for item in profile if item["id"] == "llm-pi-ai")["config"]["providers"]["rollout-generator"]
            passed = bool(requests) and all(
                request["path"] == "/v1/chat/completions"
                and request["model"] == "Qwen/Qwen3.5-4B"
                and request["max_tokens"] == 32768
                and request["chat_template_kwargs"] == {
                    "enable_thinking": effort == "high", "preserve_thinking": False}
                and "read_image" in request["tools"]
                and request["sampling"] == (SAMPLING if effort == "high" else INSTRUCT_SAMPLING)
                for request in requests)
            status = json.loads((output / "generator/round1/status.json").read_text())
            results.append({"reasoning_effort": effort, "passed": passed,
                            "model_input": route["models"][0]["input"],
                            "requests": requests, "dsh_exit": status["exit"],
                            "completed": status["completed"], "expected_error": error})
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    report = {"kind": "protocol_preflight_only", "model_called": False,
              "stub_port": args.port, "results": results,
              "passed": all(result["passed"] and not result["completed"]
                            and result["model_input"] == ["text", "image"]
                            for result in results)}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
