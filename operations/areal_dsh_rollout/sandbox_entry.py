"""Run inside bwrap --unshare-all: expose a loopback bridge, then exec real DSH."""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from sandbox_gateway import Relay, ThreadedHTTPServer, UnixHTTPConnection, configure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True, help="Socket in the sole read-only gateway mount")
    parser.add_argument("--port", type=int, default=30101)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="Real DSH command after --; profile uses this loopback port")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a child command is required")
    marker = Path(args.socket + ".netns")
    if int(marker.read_text()) == os.stat("/proc/self/ns/net").st_ino:
        parser.error("entry must run in a different network namespace from the host gateway")
    server = configure(ThreadedHTTPServer(("127.0.0.1", args.port), Relay),
                       lambda: UnixHTTPConnection(args.socket, args.timeout),
                       validate=False, timeout=args.timeout)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    child = None
    def stop(signum, _):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        child = subprocess.Popen(command, start_new_session=True)
        result = child.wait()
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        server.shutdown()
        server.server_close()
        worker.join()
    return result if result >= 0 else 128 - result


if __name__ == "__main__":
    sys.exit(main())

