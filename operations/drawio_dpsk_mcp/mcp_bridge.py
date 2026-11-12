"""MCP stdio adapter. The only backend is this case's mounted Unix socket."""

import json
import socket
import sys

TOOL = {
    "name": "check",
    "description": "Compile and check an editable draw.io checkpoint. Returns a candidate render, "
                   "and, when available, structural and field-level reports with candidate cell IDs "
                   "and target-image regions. Read the case-local reports using their line ranges.",
    "inputSchema": {"type": "object", "properties": {"candidate": {"type": "string",
                    "description": "A case-local .drawio filename"}}, "required": ["candidate"],
                    "additionalProperties": False},
}


def check(arguments):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(140)
        connection.connect("/verifier/check.sock")
        connection.sendall(json.dumps(arguments).encode() + b"\n")
        with connection.makefile("rb") as stream:
            return json.loads(stream.readline(128 * 1024))


def dispatch(method, params, invoke, instructions):
    if method == "initialize":
        result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "drawio-check", "version": "1.0"}}
        if instructions:
            result["instructions"] = instructions
        return result
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [TOOL]}
    if method == "tools/call" and params.get("name") == "check":
        try:
            value = invoke(params.get("arguments", {}))
        except (OSError, ValueError):
            value = {"ok": False, "error": "Verifier connection failed"}
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                "isError": not value["ok"]}
    raise KeyError(method)


def serve(invoke, instructions=None):
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        response = {"jsonrpc": "2.0", "id": request["id"]}
        try:
            response["result"] = dispatch(request["method"], request.get("params", {}), invoke, instructions)
        except KeyError:
            response["error"] = {"code": -32601, "message": "Method not found"}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve(check)
