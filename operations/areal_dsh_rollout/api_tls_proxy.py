"""Restricted CONNECT relay to DeepSeek through an existing SSH TLS forward."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import select
import socket
import time


class Relay(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_CONNECT(self):
        if self.path != "api.deepseek.com:443":
            self.send_error(403)
            return
        try:
            upstream = socket.create_connection(self.server.upstream, timeout=10)
        except OSError:
            self.send_error(502)
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.close_connection = True
        peers = (self.connection, upstream)
        last_data = time.monotonic()
        try:
            while time.monotonic() - last_data < 900:
                ready, _, _ = select.select(peers, [], [], 30)
                for source in ready:
                    data = source.recv(65536)
                    if not data:
                        return
                    target = upstream if source is self.connection else self.connection
                    target.sendall(data)
                    last_data = time.monotonic()
        except OSError:
            return
        finally:
            upstream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="HPC login private interface, never public 0.0.0.0")
    parser.add_argument("--port", type=int, default=30444)
    parser.add_argument("--forward-port", type=int, default=30443)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Relay)
    server.upstream = ("127.0.0.1", args.forward_port)
    # No API key is present here: the client verifies and terminates TLS at
    # api.deepseek.com; this relay can carry only encrypted bytes to that host.
    server.serve_forever()


if __name__ == "__main__":
    main()
