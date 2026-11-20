"""Upload an audited artifact to the logged-in owner's private dataset repo."""

import argparse
from functools import partial
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlsplit

from huggingface_hub import HfApi, configure_http_backend, get_token
import requests


def save(path, value):
    value = {**value, "at": time.time()}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


class UploadSession(requests.Session):
    def __init__(self, proxy, bulk_proxy, progress, lock, state):
        super().__init__()
        self.trust_env = False
        self.proxy, self.bulk_proxy = proxy, bulk_proxy
        self.progress, self.lock, self.state = progress, lock, state

    def send(self, request, **kwargs):
        url = urlsplit(request.url)
        host = url.hostname
        metadata = (host == "huggingface.co" and request.method in ("GET", "HEAD", "POST")
                    and (url.path.startswith("/api/") or url.path.endswith("/info/lfs/objects/batch")))
        proxy = self.proxy if metadata or self.bulk_proxy else None
        kwargs["proxies"] = {"https": proxy, "http": proxy}
        kwargs["timeout"] = kwargs.get("timeout") or (20, 180)
        response = super().send(request, **kwargs)
        if not metadata and request.method == "PUT" and response.ok:
            with self.lock:
                self.progress["accepted_storage_bytes"] += int(request.headers.get("Content-Length", 0))
                self.progress["accepted_storage_parts"] += 1
                self.progress["storage_host"] = host
                save(self.state, self.progress)
        return response


def publish(args):
    args.state.parent.mkdir(parents=True, exist_ok=True)
    progress = {"phase": "checking", "repo_id": args.repo_id, "file": args.file.name,
                "total_bytes": args.file.stat().st_size, "accepted_storage_bytes": 0,
                "accepted_storage_parts": 0, "bulk_proxy_allowed": args.allow_bulk_proxy}
    save(args.state, progress)
    configure_http_backend(partial(UploadSession, args.metadata_proxy, args.allow_bulk_proxy,
                                   progress, threading.Lock(), args.state))
    token = sys.stdin.readline().strip() if args.token_stdin else get_token()
    api = HfApi(token=token)
    account = api.whoami()["name"]
    if account.lower() != args.repo_id.split("/")[0].lower():
        raise RuntimeError("Logged-in HF account differs from the requested repository owner")
    api.create_repo(args.repo_id, repo_type="dataset", private=True, exist_ok=True, token=token)
    if not api.repo_info(args.repo_id, repo_type="dataset", token=token).private:
        raise RuntimeError("Refusing to upload to a public repository")
    progress.update(account=account, private=True, phase="checked" if args.check else "uploading")
    save(args.state, progress)
    if args.check:
        print(json.dumps(progress))
        return
    commit = api.upload_file(path_or_fileobj=args.file, path_in_repo=args.path_in_repo,
                             repo_id=args.repo_id, repo_type="dataset",
                             token=token,
                             commit_message="Publish verified artifact " + args.file.name)
    info = api.repo_info(args.repo_id, repo_type="dataset", revision=commit.oid, files_metadata=True, token=token)
    remote = next(file for file in info.siblings if file.rfilename == args.path_in_repo)
    if not info.private or remote.size != args.file.stat().st_size:
        raise RuntimeError("Uploaded artifact privacy or size differs")
    if remote.lfs:
        actual = remote.lfs.sha256
        if args.expected_sha256 and actual != args.expected_sha256:
            raise RuntimeError("Hub LFS SHA256 differs from the audited artifact")
    else:
        digest = hashlib.sha1(f"blob {args.file.stat().st_size}\0".encode())
        with args.file.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 ** 2), b""):
                digest.update(block)
        if digest.hexdigest() != remote.blob_id:
            raise RuntimeError("Hub Git blob differs from the local artifact")
        actual = remote.blob_id
    progress.update(phase="verified", revision=commit.oid, remote_digest=actual,
                    remote_bytes=remote.size, private=info.private,
                    url=f"https://huggingface.co/datasets/{args.repo_id}/tree/{commit.oid}")
    save(args.state, progress)
    print(json.dumps(progress))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--path-in-repo", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--metadata-proxy")
    parser.add_argument("--allow-bulk-proxy", action="store_true")
    parser.add_argument("--token-stdin", action="store_true", help="Use an ephemeral token from stdin without changing saved logins")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        publish(args)
    except Exception as error:
        response = getattr(error, "response", None)
        detail = ""
        host = None
        if response is not None:
            host = urlsplit(response.url).hostname
            try:
                body = response.json()
                detail = str(body.get("error") or body.get("message") or response.headers.get("X-Error-Message", ""))
            except (ValueError, AttributeError):
                detail = re.sub("<[^>]+>", " ", response.text)[:400]
        detail = re.sub(r"hf_[A-Za-z0-9]+|https?://\S+", "[REDACTED]", detail)
        failure = {"phase": "failed", "error_type": type(error).__name__,
                   "http_status": getattr(response, "status_code", None),
                   "error_code": response.headers.get("X-Error-Code") if response is not None else None,
                   "host": host, "detail": detail}
        previous = json.loads(args.state.read_text()) if args.state.exists() else {}
        args.state.parent.mkdir(parents=True, exist_ok=True)
        save(args.state, {**previous, **failure})
        print(json.dumps(failure))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
