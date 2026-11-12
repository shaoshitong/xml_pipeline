"""Read one bounded, case-local editable checkpoint."""

import os
import re
import stat

MAX_BYTES = 1024 * 1024
CHECKPOINT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\.drawio")


def read_candidate(case, name):
    if not isinstance(name, str) or not CHECKPOINT.fullmatch(name):
        raise ValueError("Use a case-local .drawio filename")
    root = os.open(case, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
    finally:
        os.close(root)
    with os.fdopen(fd, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Checkpoint must be a regular file")
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Checkpoint exceeds 1 MiB")
    return data
