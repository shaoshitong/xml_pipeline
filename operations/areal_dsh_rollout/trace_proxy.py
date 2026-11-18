"""Transparent local inference audit proxy; no reward or gold endpoint exists."""

import argparse
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
            yield {"bytes": len(url), "sha256": sha256(url.encode()).hexdigest()}
        for item in value.values():
            yield from images(item)
    elif isinstance(value, list):
        for item in value:
            yield from images(item)


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
        while chunk := response.read1(65536):
            self.wfile.write(chunk)
            self.wfile.flush()
        upstream.close()
        self.close_connection = True


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
