"""Transparent local inference audit proxy; no reward or gold endpoint exists."""

import argparse
import base64
from hashlib import sha256
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import urlsplit


def images(value):
    if isinstance(value, dict):
        if value.get("type") == "image_url":
            url = value["image_url"]["url"]
            if url.startswith("data:"):
                payload = base64.b64decode(url.split(",", 1)[1])
                yield {"bytes": len(payload), "sha256": sha256(payload).hexdigest(), "inline": True}
            else:
                yield {"url_sha256": sha256(url.encode()).hexdigest(), "inline": False}
        for item in value.values():
            yield from images(item)
    elif isinstance(value, list):
        for item in value:
            yield from images(item)


def response_summary(chunks):
    summary = {"content_characters": 0, "reasoning_characters": 0, "tool_calls": {}}
    for line in b"".join(chunks).splitlines():
        if not line.startswith(b"data: ") or line == b"data: [DONE]":
            continue
        event = json.loads(line[6:])
        if event.get("usage"):
            summary["usage"] = event["usage"]
        for choice in event.get("choices", []):
            if choice.get("finish_reason"):
                summary["finish_reason"] = choice["finish_reason"]
            delta = choice.get("delta", {})
            summary["content_characters"] += len(delta.get("content") or "")
            summary["reasoning_characters"] += len(delta.get("reasoning_content") or "")
            for call in delta.get("tool_calls", []):
                tool = summary["tool_calls"].setdefault(str(call.get("index", 0)),
                                                       {"name": "", "argument_characters": 0})
                function = call.get("function", {})
                tool["name"] += function.get("name") or ""
                tool["argument_characters"] += len(function.get("arguments") or "")
    return summary


class Proxy(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        data = json.loads(body)
        record = {"timestamp": time.time(), "path": self.path, "model": data.get("model"),
                  "image_inputs": list(images(data)), "messages": len(data.get("messages", [])),
                  "tool_observations": sum(m.get("role") == "tool" for m in data.get("messages", [])),
                  "tool_definitions": len(data.get("tools", []))}
        record["sampling"] = {key: data[key] for key in (
            "temperature", "top_p", "top_k", "presence_penalty", "max_tokens",
            "chat_template_kwargs") if key in data}
        with self.server.audit.open("a") as log:
            log.write(json.dumps(record) + "\n")
        upstream = HTTPConnection(self.server.upstream.hostname, self.server.upstream.port, timeout=900)
        upstream.request("POST", self.path, body, {"Content-Type": "application/json"})
        response = upstream.getresponse()
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in ("connection", "transfer-encoding", "keep-alive"):
                self.send_header(key, value)
        self.send_header("Connection", "close")
        self.end_headers()
        chunks = []
        while chunk := response.read1(65536):
            chunks.append(chunk)
            self.wfile.write(chunk)
            self.wfile.flush()
        upstream.close()
        self.close_connection = True
        with self.server.audit.open("a") as log:
            log.write(json.dumps({"response_to": record["timestamp"], "status": response.status,
                                  "seconds": round(time.time() - record["timestamp"], 3),
                                  **response_summary(chunks)}) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Proxy)
    server.upstream = urlsplit(args.upstream)
    server.audit = args.audit
    server.serve_forever()


if __name__ == "__main__":
    main()
