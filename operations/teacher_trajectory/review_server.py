"""Serve selected, completed teacher traces privately over an SSH forward."""

import argparse
import base64
from functools import lru_cache
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from interruption import annotation
from verify import open_archive


def read_events(path, folder):
    records = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        record = {"source": str(path.relative_to(folder)), "line": number}
        try:
            record["event"] = json.loads(line)
        except json.JSONDecodeError:
            record.update(event={}, raw_line=line, parse_error="Incomplete JSON event retained verbatim")
        records.append(record)
    return records


@lru_cache(maxsize=16)
def tool_events(folder):
    records = {}
    for role in ("generator", "reviewer"):
        for path in sorted(folder.glob(role + "/round*/events.jsonl")):
            for record in read_events(path, folder):
                event = record["event"]
                if event.get("type") in ("tool_call", "tool_result"):
                    records.setdefault(event["callId"], []).append(record)
    return records


def display(value, images):
    if isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
        prefix, payload = value.split(",", 1)
        raw = base64.b64decode(payload)
        digest = sha256(raw).hexdigest()
        images.add(digest)
        return {"image": "/image/" + digest, "sha256": digest, "mime": prefix[5:].split(";")[0]}
    if isinstance(value, list):
        return [display(item, images) for item in value]
    if isinstance(value, dict):
        return {key: display(item, images) for key, item in value.items()}
    return value


class Handler(BaseHTTPRequestHandler):
    def send(self, value, kind="application/json; charset=utf-8"):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        store = open_archive(self.server.root)
        try:
            self.route(urlsplit(self.path).path.strip("/").split("/"), store)
        except (KeyError, FileNotFoundError):
            self.send_error(404)
        finally:
            store.db.close()

    def route(self, parts, store):
        cases = self.server.cases
        if parts == [""]:
            return self.send(Path(__file__).with_name("trace_view.html").read_bytes(), "text/html; charset=utf-8")
        if parts == ["manifest"]:
            return self.send(self.server.manifest)
        if len(parts) == 3 and parts[0] == "case" and parts[1] in cases:
            allowed = {"reference.png", "round1.png", "round2.png", "round1.drawio", "round2.drawio", "review1.json"}
            if parts[2] not in allowed:
                raise KeyError(parts[2])
            path = self.server.root / "episodes" / parts[1] / "case" / parts[2]
            digest = sha256(path.read_bytes()).hexdigest()
            if digest != cases[parts[1]]["files"][parts[2]]["sha256"]:
                raise ValueError("Selected artifact changed since sampling")
            kind = "image/png" if path.suffix == ".png" else "text/plain; charset=utf-8"
            return self.send(path.read_bytes(), kind)
        if len(parts) == 2 and parts[0] == "calls" and parts[1] in cases:
            rows = store.db.execute("""select id,role,stage,started,ended,status,error,usage,cost_upper
                from calls where episode=? order by id""", (parts[1],)).fetchall()
            names = ("id", "role", "stage", "started", "ended", "status", "error", "usage", "cost_cny")
            return self.send([dict(zip(names, row)) for row in rows])
        if len(parts) == 2 and parts[0] == "image" and parts[1] in self.server.images:
            raw = store.raw(parts[1])
            kind = "image/jpeg" if raw.startswith(b"\xff\xd8") else "image/png"
            return self.send(raw, kind)
        if len(parts) == 3 and parts[0] == "events" and parts[1] in cases and parts[2] in ("generator", "reviewer"):
            folder = self.server.root / "episodes" / parts[1]
            rows = [record for path in sorted(folder.glob(parts[2] + "/round*/events.jsonl"))
                    for record in read_events(path, folder)]
            return self.send(rows)
        if len(parts) != 2 or parts[0] not in ("call", "request", "raw-request", "wire") or not parts[1].isdigit():
            raise KeyError(parts)
        row = store.db.execute("""select episode,role,stage,request,response,wire,status,error,completed
            from calls where id=?""", (int(parts[1]),)).fetchone()
        if row is None or row[0] not in cases:
            raise KeyError(parts[1])
        episode, role, stage, request, response, wire, status, error, completed = row
        if parts[0] == "wire":
            return self.send(store.raw(wire), "text/plain; charset=utf-8")
        if parts[0] in ("request", "raw-request"):
            payload = store.get(request)
            return self.send(payload if parts[0] == "raw-request" else display(payload, self.server.images))
        payload = store.get(response) if response else {}
        choices = payload.get("choices", [])
        message = choices[0]["message"] if choices else {}
        events = tool_events(self.server.root / "episodes" / episode)
        tools = [{"model_call": call, "executed_events": events.get(call["id"], [])}
                 for call in message.get("tool_calls", [])]
        eligibility = annotation(store, {"call_id": int(parts[1]), "request_ref": request, "response_ref": response})
        return self.send(display({"id": int(parts[1]), "episode": episode, "role": role, "stage": stage,
            "status": status, "error": error, "completed": bool(completed), "request_ref": request,
            "response_ref": response, "response": payload, "tool_execution": tools, **eligibility}, self.server.images))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18769)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.root = args.root
    server.manifest = json.loads(args.manifest.read_text())
    server.cases = {row["id"]: row for row in server.manifest["cases"]}
    server.images = set()
    server.serve_forever()


if __name__ == "__main__":
    main()
