"""Print a base64 xz tarball of project files for argv-only transport to the lab host."""

import base64
import hashlib
import io
import sys
import tarfile


def main():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz", preset=9) as archive:
        for name in sorted(sys.argv[1:]):
            info = archive.gettarinfo(name)
            info.mtime = info.uid = info.gid = 0
            info.uname = info.gname = ""
            with open(name, "rb") as stream:
                archive.addfile(info, stream)
    blob = buffer.getvalue()
    sys.stderr.write("sha256 %s bytes %d\n" % (hashlib.sha256(blob).hexdigest(), len(blob)))
    print(base64.b64encode(blob).decode())


if __name__ == "__main__":
    main()
