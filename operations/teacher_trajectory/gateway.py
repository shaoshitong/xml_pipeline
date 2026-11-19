"""Record real teacher requests/replies without duplicated prefixes or credentials."""

from datetime import datetime
from hashlib import sha256
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from store import BudgetExhausted, canonical, snapshot


PRICING = {"source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
           "model": "deepseek-flash", "currency": "CNY", "per_million": {
               "off_peak": {"hit": .02, "miss": 1., "output": 4.},
               "peak": {"hit": .04, "miss": 2., "output": 8.}},
           "public_holiday_policy": "Conservatively charge weekday peak hours at peak rates"}


def peak(timestamp):
    dt = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Shanghai"))
    return dt.weekday() < 5 and (9 <= dt.hour < 12 or 14 <= dt.hour < 18)


def charge(usage, started, ended):
    rate = PRICING["per_million"]["peak" if peak(started) or peak(ended) else "off_peak"]
    hit = usage.get("prompt_cache_hit_tokens", usage.get("prompt_tokens_details", {}).get("cached_tokens", 0))
    miss = usage.get("prompt_cache_miss_tokens", max(0, usage.get("prompt_tokens", 0) - hit))
    return (hit * rate["hit"] + miss * rate["miss"] + usage.get("completion_tokens", 0) * rate["output"]) / 1e6


def parse_reply(raw):
    frames, choices, usage, metadata = [], {}, {}, {}
    lines = raw.splitlines() if raw.lstrip().startswith((b"data:", b":")) else []
    if not lines:
        value = json.loads(raw)
        return value, value.get("usage", {})
    for line in lines:
        if not line.startswith(b"data:") or line[5:].strip() == b"[DONE]":
            continue
        event = json.loads(line[5:].strip())
        frames.append(event)
        for key in ("id", "model", "created", "system_fingerprint"):
            if key in event:
                metadata[key] = event[key]
        if event.get("usage"):
            usage = event["usage"]
        for item in event.get("choices", []):
            output = choices.setdefault(item["index"], {"role": "assistant", "content": "",
                                                       "reasoning_content": "", "tools": {}})
            delta = item.get("delta", {})
            for key in ("content", "reasoning_content"):
                output[key] += delta.get(key) or ""
            for fragment in delta.get("tool_calls", []):
                tool = output["tools"].setdefault(fragment["index"], {
                    "id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if fragment.get("id"):
                    tool["id"] = fragment["id"]
                for key in ("name", "arguments"):
                    tool["function"][key] += fragment.get("function", {}).get(key) or ""
            if item.get("finish_reason"):
                output["finish_reason"] = item["finish_reason"]
    result = {**metadata, "choices": [], "usage": usage}
    for index, value in sorted(choices.items()):
        tools = value.pop("tools")
        finish = value.pop("finish_reason", None)
        if tools:
            value["tool_calls"] = [tool for _, tool in sorted(tools.items())]
        result["choices"].append({"index": index, "message": value, "finish_reason": finish})
    return result, usage


class Provider:
    def __init__(self, key, proxy=None):
        self.key = key
        self.proxy = urlsplit(proxy or "")

    def connection(self, timeout=900):
        if self.proxy.hostname:
            connection = http.client.HTTPSConnection(self.proxy.hostname, self.proxy.port, timeout=timeout)
            connection.set_tunnel("api.deepseek.com", 443)
            return connection
        return http.client.HTTPSConnection("api.deepseek.com", 443, timeout=timeout)

    def balance(self):
        connection = self.connection(timeout=15)
        try:
            connection.request("GET", "/user/balance", headers={"Authorization": "Bearer " + self.key})
            response = connection.getresponse()
            value = json.loads(response.read())
            if response.status != 200:
                raise RuntimeError("Balance endpoint HTTP " + str(response.status))
            return value
        finally:
            connection.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_GET(self):
        self.send_error(404)

    def do_POST(self):
        self.close_connection = True
        server = self.server
        if self.path != "/v1/chat/completions" or not hmac.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + server.task_token):
            self.send_error(403)
            return
        from sandbox_gateway import request_body, validate_images
        body = request_body(self)
        request = validate_images(body)
        if request.get("model") != "deepseek-flash":
            self.send_error(400, "Only the authorized teacher model is available")
            return
        if request.get("stream"):
            request.setdefault("stream_options", {})["include_usage"] = True
        body = canonical(request)
        request_ref = server.store.put(request)
        if canonical(server.store.get(request_ref)) != canonical(request):
            raise ValueError("Request round-trip verification failed")
        artifacts = snapshot(server.store, server.case)
        maximum = int(request.get("max_tokens", 0))
        if not 0 < maximum <= 131072:
            self.send_error(400, "Invalid output budget")
            return
        # Use the full context and peak output price when reserving a call.
        # Real costs later replace this reservation using returned API usage.
        reservation = (1048576 * 2 + maximum * 8) / 1e6
        try:
            number = server.store.reserve(server.episode, server.role, server.stage,
                                          request_ref, artifacts, reservation,
                                          server.total_cap, server.episode_cap)
        except BudgetExhausted:
            self.send_error(402, "Authorized experiment budget reached")
            return
        started, raw, status, error = time.time(), bytearray(), 0, None
        connection = server.provider.connection()
        try:
            connection.request("POST", "/chat/completions", body, {
                "Authorization": "Bearer " + server.provider.key,
                "Content-Type": "application/json", "Accept": "text/event-stream"})
            upstream = connection.getresponse()
            status = upstream.status
            self.send_response(status)
            self.send_header("Content-Type", upstream.getheader("Content-Type", "application/json"))
            self.send_header("Connection", "close")
            self.end_headers()
            connected = True
            while chunk := upstream.read1(65536):
                raw.extend(chunk)
                if connected:
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except OSError:
                        connected = False
        except Exception as failure:
            error = type(failure).__name__
        finally:
            connection.close()
            wire = server.store.blob(bytes(raw))
            try:
                reply, usage = parse_reply(bytes(raw))
                cost = charge(usage, started, time.time()) if usage else reservation
            except (ValueError, KeyError, TypeError):
                reply, usage, cost = {"parse_error": True}, {}, reservation
                error = error or "IncompleteProviderReply"
            response_ref = server.store.put(reply)
            server.store.finish(number, response_ref, wire, status, usage, cost, error)
            progress = server.store.root / f"progress.{number}.tmp"
            progress.write_text(json.dumps({"at": time.time(), **server.store.summary()}, indent=2))
            os.replace(progress, server.store.root / "progress.json")


def gateway(store, provider, episode, role, case, token, total_cap, episode_cap):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.store, server.provider, server.episode = store, provider, episode
    server.role, server.stage, server.case = role, 1, Path(case)
    server.task_token, server.total_cap, server.episode_cap = token, total_cap, episode_cap
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
