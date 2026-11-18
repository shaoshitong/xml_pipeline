"""One direct image-to-XML OpenAI/SGLang request, without an agent harness."""

import argparse
import base64
from contextlib import ExitStack
from datetime import datetime, timezone
from hashlib import sha256
import html
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from xml.etree import ElementTree


SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20,
            "presence_penalty": 1.5, "repetition_penalty": 1.0,
            "min_p": 0.0, "max_tokens": 32768}
PROMPT = (
    "Reconstruct this image as a complete, uncompressed, native editable Draw.io XML document. "
    "Match its visible text, shapes, layout, colors, and connectors. Use the standard "
    "mxfile > diagram > mxGraphModel > root structure with valid cell IDs, parents, and geometry. "
    "Do not embed the input image, screenshots, flattened SVGs, or external image assets. "
    "Return the complete XML directly; a single XML markdown fence is also acceptable. "
    "Do not call tools or explain your answer."
)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def receive_event(data, state, files, started):
    elapsed = time.monotonic() - started
    if data == b"[DONE]":
        state["stream_done"] = True
        state["response_complete"] = True
        return
    try:
        event = json.loads(data)
    except json.JSONDecodeError as error:
        state["parse_errors"].append({"seconds": elapsed, "error": str(error)})
        return
    files["events"].write(json.dumps({"seconds": elapsed, "event": event}, ensure_ascii=False) + "\n")
    files["events"].flush()
    if event.get("error") is not None:
        state["error"] = {"type": "upstream_response_error", "value": event["error"]}
    if event.get("usage") is not None:
        state["usage"] = event["usage"]
    for choice in event.get("choices", []):
        index = choice.get("index", 0)
        delta = choice.get("delta") or choice.get("message") or {}
        if choice.get("finish_reason") is not None:
            state["finish_reasons"][str(index)] = choice["finish_reason"]
        content = delta.get("content")
        if index == 0 and isinstance(content, str):
            files["content"].write(content)
            files["content"].flush()
            state["content_characters"] += len(content)
            if content and state["first_content_seconds"] is None:
                state["first_content_seconds"] = elapsed
        for key in ("reasoning_content", "reasoning"):
            value = delta.get(key)
            if index == 0 and isinstance(value, str):
                files[key].write(value)
                files[key].flush()
                state["reasoning_characters"][key] += len(value)
        for field, output in (("tool_calls", "tools"), ("logprobs", "logprobs")):
            value = delta.get(field) if field == "tool_calls" else choice.get(field)
            if value is not None:
                files[output].write(json.dumps({"seconds": elapsed, "choice": index,
                                               "value": value}, ensure_ascii=False) + "\n")
                files[output].flush()
                state[output + "_chunks"] += 1


def stream_request(endpoint, body, out, api_key, timeout, nonstream=False):
    headers = {"Content-Type": "application/json",
               "Accept": "application/json" if nonstream else "text/event-stream"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    state = {"http_status": None, "stream_done": False, "response_complete": False,
             "mode": "nonstream" if nonstream else "stream", "finish_reasons": {},
             "usage": None, "content_characters": 0, "first_byte_seconds": None,
             "first_content_seconds": None, "reasoning_characters": {
                 "reasoning_content": 0, "reasoning": 0},
             "tools_chunks": 0, "logprobs_chunks": 0, "parse_errors": [], "error": None}
    names = {"events": "native-events.jsonl", "content": "content.txt",
             "reasoning_content": "reasoning_content.txt", "reasoning": "reasoning.txt",
             "tools": "native-tool-deltas.jsonl", "logprobs": "native-logprob-deltas.jsonl"}
    started = time.monotonic()
    state["started_utc"] = datetime.now(timezone.utc).isoformat()
    with ExitStack() as stack:
        files = {key: stack.enter_context((out / name).open("w")) for key, name in names.items()}
        raw = stack.enter_context((out / ("response.json" if nonstream else "response.sse")).open("wb"))
        data = []
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(Request(endpoint, data=body, headers=headers), timeout=timeout) as response:
                state["http_status"] = response.status
                write_json(out / "response-headers.json", {
                    key: value for key, value in response.headers.items()
                    if key.lower() not in {"set-cookie", "authorization", "proxy-authorization"}})
                for line in response:
                    raw.write(line)
                    raw.flush()
                    if state["first_byte_seconds"] is None:
                        state["first_byte_seconds"] = time.monotonic() - started
                    if nonstream:
                        data.append(line)
                    elif not line.strip() and data:
                        receive_event(b"\n".join(data), state, files, started)
                        data = []
                    elif line.startswith(b"data:"):
                        data.append(line[5:].lstrip(b" ").rstrip(b"\r\n"))
                if data:
                    receive_event((b"" if nonstream else b"\n").join(data), state, files, started)
                if nonstream:
                    state["response_complete"] = not state["parse_errors"]
        except HTTPError as error:
            state["http_status"] = error.code
            (out / "http-error-body.bin").write_bytes(error.read())
            state["error"] = {"type": type(error).__name__, "message": str(error)}
        except Exception as error:
            state["error"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            state["wall_seconds"] = time.monotonic() - started
            state["ended_utc"] = datetime.now(timezone.utc).isoformat()
            write_json(out / "stream-summary.json", state)
    return state


def validate_and_render(root, out):
    content = (out / "content.txt").read_text()
    first_root = re.search(r"<(mxfile|mxGraphModel)\b", content)
    matches = list(re.finditer(r"<(mxfile|mxGraphModel)\b[\s\S]*?</\1\s*>", content))
    result = {"xml_parsed": False, "rendered": False, "host_repairs": False}
    if len(matches) != 1 or matches[0].start() != first_root.start():
        result["error"] = "Expected one complete Draw.io XML document in native content"
        result["complete_xml_documents"] = len(matches)
        return result
    match = matches[0]
    xml = match.group()
    candidate = out / "candidate.drawio"
    candidate.write_text(xml)
    result.update(content_span=[match.start(), match.end()],
                  candidate_sha256=sha256(candidate.read_bytes()).hexdigest())
    try:
        document = ElementTree.fromstring(xml)
        result.update(xml_parsed=True, xml_root=document.tag,
                      embedded_image_markers=len(re.findall(
                          r"data\s*:\s*image/|(?:[;\"\s]image\s*=)|<(?:img|svg)\b",
                          html.unescape(xml), re.I)))
        command = [str(root / "renderer/venv/bin/python"),
                   str(root / "source/operations/areal_dsh_rollout/render.py"),
                   str(candidate), str(out / "candidate.png"), "--runtime", str(root / "renderer")]
        started = time.monotonic()
        with (out / "render.json").open("w") as stdout, (out / "render.stderr").open("w") as stderr:
            process = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=180)
        result.update(render_exit=process.returncode, render_wall_seconds=time.monotonic() - started)
        if process.returncode == 0:
            result["native_render"] = json.loads((out / "render.json").read_text())
            result["rendered"] = (out / "candidate.png").is_file()
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--generator-model", required=True,
                        choices=("Qwen/Qwen3.5-4B", "Qwen/Qwen3.5-9B"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tokens", type=int, default=32768,
                        help="Keep 32768 for matched quality tests; smaller values label protocol fixtures")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--api-key-env", default="ROLLOUT_API_KEY")
    parser.add_argument("--logprobs", "--return-logprob", action="store_true")
    parser.add_argument("--nonstream", action="store_true",
                        help="Independent JSON/logprob protocol control; default preserves native SSE")
    args = parser.parse_args()
    os.umask(0o077)
    root, out = args.root.resolve(), args.out.resolve()
    out.mkdir(mode=0o700, parents=True)
    image = args.reference.read_bytes()
    (out / "reference.png").write_bytes(image)
    endpoint = args.base_url.rstrip("/")
    endpoint += "/chat/completions" if endpoint.endswith("/v1") else "/v1/chat/completions"
    sampling = dict(SAMPLING, max_tokens=args.max_tokens)
    payload = {"model": args.generator_model, **sampling, "seed": args.seed,
               "stream": not args.nonstream, "n": 1,
               "tools": [], "tool_choice": "none",
               "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False},
               "messages": [{"role": "user", "content": [
                   {"type": "text", "text": PROMPT},
                   {"type": "image_url", "image_url": {
                       "url": "data:image/png;base64," + base64.b64encode(image).decode()}}]}]}
    if not args.nonstream:
        payload["stream_options"] = {"include_usage": True}
    if args.logprobs:
        payload.update(logprobs=True, top_logprobs=0)
    body = json.dumps(payload, ensure_ascii=False).encode()
    (out / "request-body.json").write_bytes(body)
    protocol = {"mode": "direct_openai_image_chat", "endpoint": endpoint,
                "generator_model": args.generator_model, "sampling": sampling,
                "seed": args.seed, "expected_server_context_tokens": 65536,
                "context_enforced_by": "existing SGLang server, not this client",
                "host": socket.gethostname(), "reference_sha256": sha256(image).hexdigest(),
                "request_body_sha256": sha256(body).hexdigest(),
                "probe_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "harness_loaded": False, "skill_loaded": False, "gold_loaded": False,
                "response_mode": "nonstream" if args.nonstream else "stream",
                "tool_definitions": 0, "logprobs_requested": args.logprobs,
                "scope": "Single-case baseline; no generalization conclusion."}
    write_json(out / "protocol.json", protocol)
    stream = stream_request(endpoint, body, out, os.environ.get(args.api_key_env), args.timeout,
                            args.nonstream)
    validation = validate_and_render(root, out)
    summary = {"protocol": protocol, "stream": stream, "validation": validation}
    write_json(out / "summary.json", summary)
    print(json.dumps({"out": str(out), "http_status": stream["http_status"],
                      "finish_reasons": stream["finish_reasons"], "usage": stream["usage"],
                      "content_characters": stream["content_characters"],
                      "reasoning_characters": stream["reasoning_characters"],
                      "wall_seconds": stream["wall_seconds"],
                      "xml_parsed": validation["xml_parsed"], "rendered": validation["rendered"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
