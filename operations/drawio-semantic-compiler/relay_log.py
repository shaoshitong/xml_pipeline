"""Relay a local controller's stream to a lab log across short SSH outages."""

import argparse
import os
from pathlib import PurePosixPath
from queue import Empty, Queue
import shlex
import subprocess
import sys
from threading import Thread
import time


APPEND = """
import fcntl, os, pathlib, sys
os.umask(0o077)
p, offset = pathlib.Path(sys.argv[1]), int(sys.argv[2])
data = sys.stdin.buffer.read(1048577)
if not data or len(data) > 1048576:
    raise ValueError('invalid log chunk')
p.parent.mkdir(exist_ok=True, parents=True)
with p.open('a+b') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0, 2)
    size = stream.tell()
    if size < offset:
        raise ValueError('log has a gap')
    stream.seek(offset)
    present = stream.read(min(len(data), size - offset))
    if not data.startswith(present):
        raise ValueError('conflicting log data')
    stream.write(data[len(present):])
    stream.flush()
    os.fsync(stream.fileno())
print(offset + len(data))
"""


def read_chunks(output):
    while chunk := os.read(sys.stdin.fileno(), 65536):
        output.put(chunk)
    output.put(None)


def forward(ssh_alias, destination):
    pending = Queue(maxsize=192)
    Thread(target=read_chunks, args=(pending,), daemon=True).start()
    position = 0
    done = False
    while not done:
        first = pending.get()
        if first is None:
            break
        batch = bytearray(first)
        end = time.monotonic() + 2.0
        while len(batch) < 786432:
            try:
                next_chunk = pending.get(timeout=max(0, end - time.monotonic()))
            except Empty:
                break
            if next_chunk is None:
                done = True
                break
            batch.extend(next_chunk)
        command = shlex.join(["/home/shaoshitong/anaconda3/bin/python", "-c", APPEND,
                              destination, str(position)])
        expected = position + len(batch)
        retry = 0
        while True:
            try:
                result = subprocess.run(["/usr/bin/ssh", "-oBatchMode=yes", "-oConnectTimeout=7",
                                         ssh_alias, command], input=batch, capture_output=True, timeout=16)
                if result.returncode == 0 and result.stdout.strip() == str(expected).encode():
                    if retry:
                        print("Lab log transfer recovered.", file=sys.stderr, flush=True)
                    break
                if result.returncode and result.returncode != 255:
                    raise RuntimeError(f"Lab log receiver exited {result.returncode}")
            except subprocess.TimeoutExpired:
                pass
            retry += 1
            if retry == 1 or retry % 10 == 0:
                print("Lab log transfer waiting for SSH; producer stays connected.", file=sys.stderr, flush=True)
            time.sleep(min(2 + retry, 12))
        position = expected
    print(f"Lab log persisted {position} bytes.", file=sys.stderr, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ssh_alias")
    parser.add_argument("destination", type=PurePosixPath)
    options = parser.parse_args()
    forward(options.ssh_alias, str(options.destination))
