"""Host-side stdio MCP for staging selected compiler source on the lab node.

Install a reviewed copy outside the sandbox mount. This service reads only
regular source files from that mount and invokes one fixed SSH operation.
"""

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import sys
import tarfile


MAX_SIZE = 8 * 1024 * 1024
MAX_FILES = 160
SOURCE_ROOTS = ("conversion/", "operations/drawio-semantic-compiler/", "tests/")
SUFFIXES = {".py", ".js", ".mjs", ".ts", ".sh", ".md", ".toml", ".json", ".yaml", ".yml"}
REMOTE_STAGE = """
import hashlib, io, json, os, pathlib, sys, tarfile, tempfile
os.umask(0o077)
parent = pathlib.Path(sys.argv[1]) / 'source_deployments'
expected = sys.argv[2]
raw = sys.stdin.buffer.read(9 * 1024 * 1024)
if hashlib.sha256(raw).hexdigest() != expected:
    raise ValueError('source archive checksum mismatch')
parent.mkdir(exist_ok=True)
target = parent / expected
with tempfile.TemporaryDirectory(dir=parent) as temporary:
    stage = pathlib.Path(temporary) / 'source'
    stage.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        archive.extractall(stage, filter='data')
    try:
        stage.rename(target)
    except OSError:
        if not target.is_dir() or any(
            not (target / file.relative_to(stage)).is_file() or
            (target / file.relative_to(stage)).read_bytes() != file.read_bytes()
            for file in stage.rglob('*') if file.is_file()
        ):
            raise
print(json.dumps({'source': str(target), 'archive_sha256': expected}))
"""
TOOL = {
    "name": "drawio_deploy_source",
    "description": "Stage compiler code from the shared project on lab_4090_3. "
                   "Pass project-relative file paths, including every new source dependency. "
                   "Returns the verified, content-addressed deployment directory. "
                   "Use lab_host_control to execute code there; reuse baseline_source for existing tooling.",
    "inputSchema": {
        "type": "object",
        "properties": {"files": {"type": "array", "items": {"type": "string"},
                                 "minItems": 1, "maxItems": MAX_FILES, "uniqueItems": True}},
        "required": ["files"],
        "additionalProperties": False,
    },
}


def open_source(project, value):
    path = PurePosixPath(value)
    if (str(path) != value or not re.fullmatch(r"[A-Za-z0-9_/.-]+", value)
            or any(part.startswith('.') for part in path.parts)
            or (not value.startswith(SOURCE_ROOTS) and value != "pyproject.toml")
            or path.suffix not in SUFFIXES):
        raise ValueError(f"Not an allowed source path: {value}")
    directory = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        return os.fdopen(os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                dir_fd=directory), "rb")
    finally:
        os.close(directory)


def deploy(project, ssh_alias, remote_directory, files):
    if (not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES
            or any(not isinstance(file, str) for file in files) or len(set(files)) != len(files)):
        raise ValueError("Expected a list of distinct source files")
    data = io.BytesIO()
    remaining = MAX_SIZE
    with tarfile.open(fileobj=data, mode="w") as archive:
        for name in sorted(files):
            with open_source(project, name) as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError(f"Expected a regular source file: {name}")
                payload = stream.read(remaining + 1)
            remaining -= len(payload)
            if remaining < 0:
                raise ValueError("Source deployment exceeds 8 MiB")
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))
    digest = hashlib.sha256(data.getbuffer()).hexdigest()
    command = shlex.join(["/home/shaoshitong/anaconda3/bin/python", "-c", REMOTE_STAGE,
                          remote_directory, digest])
    result = subprocess.run(["/usr/bin/ssh", "-oBatchMode=yes", "-oConnectTimeout=8", ssh_alias, command],
                            input=data.getvalue(), capture_output=True, timeout=45, check=False)
    if result.returncode:
        raise RuntimeError(f"Lab deployment failed (SSH exit {result.returncode})")
    receipt = json.loads(result.stdout)
    if receipt["archive_sha256"] != digest:
        raise RuntimeError("Invalid lab deployment receipt")
    return {**receipt, "files": len(files)}


def serve(project, ssh_alias, remote_directory):
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        params = request.get("params", {})
        reply = {"jsonrpc": "2.0", "id": request["id"]}
        if method == "initialize":
            reply["result"] = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                               "serverInfo": {"name": "lab-drawio-source", "version": "1.0"}}
        elif method == "ping":
            reply["result"] = {}
        elif method == "tools/list":
            reply["result"] = {"tools": [TOOL]}
        elif method == "tools/call" and params.get("name") == TOOL["name"]:
            error = False
            try:
                value = json.dumps(deploy(project, ssh_alias, remote_directory, params["arguments"]["files"]))
            except (KeyError, TypeError, ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                value, error = str(exc), True
            reply["result"] = {"content": [{"type": "text", "text": value}], "isError": error}
        else:
            reply["error"] = {"code": -32601, "message": "Unsupported method"}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    serve(Path(sys.argv[1]).resolve(strict=True), sys.argv[2], sys.argv[3])
