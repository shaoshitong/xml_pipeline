"""Allow only OpenAI generation requests through a private host Unix socket."""

import argparse
import base64
from hashlib import sha256
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import time
from urllib.parse import urlsplit


ALLOWED = {("POST", "/v1/chat/completions"), ("GET", "/v1/models")}
MAX_BODY = 128 * 1024 * 1024
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate",
               "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"}
SECRET_HEADERS = {"authorization", "set-cookie", "www-authenticate",
                  "authentication-info", "x-api-key"}
IMAGE_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,",
                  "data:image/webp;base64,", "data:image/gif;base64,")


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=900):
        super().__init__("localhost", timeout=timeout)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def request_body(handler):
    lengths = handler.headers.get_all("Content-Length", [])
    encoding = handler.headers.get("Transfer-Encoding", "").lower()
    if encoding and (encoding != "chunked" or lengths):
        raise ValueError("Ambiguous request framing")
    if encoding:
        chunks, total = [], 0
        while True:
            line = handler.rfile.readline(65537)
            size = int(line.split(b";", 1)[0], 16)
            if size < 0 or len(line) > 65536:
                raise ValueError("Invalid chunk")
            if not size:
                trailers = 0
                while True:
                    line = handler.rfile.readline(65537)
                    trailers += len(line)
                    if line in (b"\r\n", b"\n"):
                        break
                    if not line or trailers > 65536:
                        raise ValueError("Incomplete trailers")
                return b"".join(chunks)
            total += size
            if total > MAX_BODY:
                raise ValueError("Request too large")
            chunk = handler.rfile.read(size)
            if len(chunk) != size or handler.rfile.read(2) != b"\r\n":
                raise ValueError("Incomplete chunk")
            chunks.append(chunk)
    if len(lengths) > 1:
        raise ValueError("Duplicate content length")
    size = int(lengths[0]) if lengths else 0
    if size < 0 or size > MAX_BODY:
        raise ValueError("Invalid content length")
    body = handler.rfile.read(size)
    if len(body) != size:
        raise ValueError("Incomplete request")
    return body


def validate_images(body):
    """Drawio requests use inline raster images, never upstream URL/file fetches."""
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    if any(key in data for key in ("image_data", "video_data", "audio_data", "files")):
        raise ValueError("Unsupported media")
    for message in data.get("messages", []):
        if not isinstance(message, dict):
            raise ValueError("Invalid message")
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                raise ValueError("Invalid content")
            kind = part.get("type")
            if kind in ("text", "input_text"):
                continue
            image = part.get("image_url")
            url = image.get("url") if isinstance(image, dict) else image
            if kind != "image_url" or not isinstance(url, str) or not url.startswith(IMAGE_PREFIXES):
                raise ValueError("Only inline raster images are allowed")
    return data


class Relay(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_GET(self):
        self.relay()

    def do_POST(self):
        self.relay()

    def relay(self):
        self.close_connection = True
        if (self.command, self.path) not in ALLOWED:
            self.send_error(404)
            return
        upstream = None
        responding = False
        try:
            self.connection.settimeout(self.server.timeout_seconds)
            body = request_body(self)
            if self.server.validate_images and self.command == "POST":
                data = validate_images(body)
                if self.server.sampling:
                    data.update(self.server.sampling)
                    body = json.dumps(data, separators=(",", ":")).encode()
        except (OSError, ValueError, TypeError):
            self.send_error(400)
            return
        try:
            headers = {"Content-Type": "application/json",
                       "Accept": self.headers.get("Accept", "application/json")}
            headers.update(self.server.upstream_headers)
            upstream = self.server.connection_factory()
            request_time = time.time()
            if self.server.audit_path and self.command == "POST":
                data = json.loads(body)
                images = []
                for message in data.get("messages", []):
                    content = message.get("content")
                    for part in content if isinstance(content, list) else []:
                        if part.get("type") == "image_url":
                            url = part["image_url"]["url"]
                            pixels = base64.b64decode(url.split(",", 1)[1])
                            images.append({"bytes": len(pixels), "sha256": sha256(pixels).hexdigest()})
                record = {key: data[key] for key in ("model", "max_tokens", "thinking",
                          "reasoning_effort", "temperature", "presence_penalty") if key in data}
                record.update(phase="request", time=request_time, image_inputs=images,
                              tool_names=[tool.get("function", {}).get("name") for tool in data.get("tools", [])],
                              upstream=getattr(upstream, "_tunnel_host", None) or upstream.host)
                with self.server.audit_path.open("a") as log:
                    log.write(json.dumps(record) + "\n")
            upstream.request(self.command, self.path, body if body else None, headers)
            response = upstream.getresponse()
            if self.server.audit_path:
                with self.server.audit_path.open("a") as log:
                    log.write(json.dumps({"phase": "response_headers", "request_time": request_time,
                                          "status": response.status,
                                          "seconds": time.time() - request_time}) + "\n")
            self.send_response(response.status)
            responding = True
            blocked = HOP_HEADERS | SECRET_HEADERS
            blocked |= {token.strip().lower() for token in response.getheader("Connection", "").split(",")}
            for key, value in response.getheaders():
                if key.lower() not in blocked:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, ValueError, TypeError, http.client.HTTPException):
            if not responding:
                self.send_error(502)
        finally:
            if upstream is not None:
                upstream.close()


def configure(server, connection_factory, headers=None, validate=True, timeout=900, sampling=None):
    server.connection_factory = connection_factory
    server.upstream_headers = headers or {}
    server.validate_images = validate
    server.timeout_seconds = timeout
    server.sampling = sampling or {}
    audit = os.environ.get("ROLLOUT_API_WIRE_AUDIT")
    server.audit_path = Path(audit) if audit else None
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--upstream", required=True, help="HTTP(S) origin, optionally ending in /v1")
    parser.add_argument("--headers-env", default="SANDBOX_GATEWAY_HEADERS",
                        help="Host-only JSON object with upstream auth/session headers")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--sampling-env", default="SANDBOX_GATEWAY_SAMPLING")
    parser.add_argument("--connect-proxy-env", default="ROLLOUT_HTTPS_CONNECT_PROXY")
    args = parser.parse_args()
    target = urlsplit(args.upstream)
    if target.scheme not in ("http", "https") or not target.hostname or target.path not in ("", "/", "/v1"):
        parser.error("upstream must be an HTTP(S) API origin")
    if target.username or target.password or target.query or target.fragment:
        parser.error("upstream credentials, query and fragment are not allowed")
    headers = json.loads(os.environ.get(args.headers_env, "{}"))
    if not isinstance(headers, dict) or any(not isinstance(value, str) or key.lower() in HOP_HEADERS | {"host", "content-length"} for key, value in headers.items()):
        parser.error("invalid upstream headers")
    sampling = json.loads(os.environ.get(args.sampling_env, "{}"))
    if not isinstance(sampling, dict) or sampling.keys() - {
            "temperature", "top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty", "seed"}:
        parser.error("invalid explicit sampling fields")
    args.socket.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.socket.parent.stat().st_mode & 0o077:
        parser.error("socket directory must be private (mode 0700)")
    proxy = urlsplit(os.environ.get(args.connect_proxy_env, ""))
    def connection():
        if target.scheme == "https" and proxy.hostname:
            client = http.client.HTTPSConnection(proxy.hostname, proxy.port, timeout=args.timeout)
            client.set_tunnel(target.hostname, target.port or 443)
            return client
        cls = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        return cls(target.hostname, target.port, timeout=args.timeout)
    server = configure(UnixHTTPServer(str(args.socket), Relay),
                       connection,
                       headers, timeout=args.timeout, sampling=sampling)
    os.chmod(str(args.socket), 0o600)
    marker = args.socket.with_name(args.socket.name + ".netns")
    marker.write_text(str(os.stat("/proc/self/ns/net").st_ino))
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        args.socket.unlink()
        marker.unlink()


if __name__ == "__main__":
    main()

