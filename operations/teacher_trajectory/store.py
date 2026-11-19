"""Lossless JSON DAG and image/blob storage for independent teacher decisions."""

import base64
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import threading
import time


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / "ledger.sqlite", check_same_thread=False)
        self.db.execute("pragma journal_mode=wal")
        self.db.executescript("""
            create table if not exists objects(id text primary key, bytes integer, stored_bytes integer);
            create table if not exists calls(
                id integer primary key, episode text, role text, stage integer,
                started real, ended real, request text, response text, wire text,
                artifacts text, status integer, error text, usage text, reserved real,
                cost_upper real, completed integer default 0);
            create table if not exists metadata(key text primary key, value text);
        """)
        self.db.commit()

    def blob(self, raw):
        digest = sha256(raw).hexdigest()
        path = self.objects / digest[:2] / (digest[2:] + ".gz")
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            packed = gzip.compress(raw, compresslevel=3, mtime=0)
            try:
                with path.open("xb") as stream:
                    stream.write(packed)
            except FileExistsError:
                pass
            with self.lock:
                self.db.execute("insert or ignore into objects values(?,?,?)",
                                (digest, len(raw), len(packed)))
        return digest

    def raw(self, digest):
        path = self.objects / digest[:2] / (digest[2:] + ".gz")
        raw = gzip.decompress(path.read_bytes())
        if sha256(raw).hexdigest() != digest:
            raise ValueError("Corrupt content-addressed object: " + digest)
        return raw

    def put(self, value):
        if isinstance(value, dict):
            node = ["dict", [[key, self.put(item)] for key, item in value.items()]]
        elif isinstance(value, list):
            node = ["list", [self.put(item) for item in value]]
        elif isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
            prefix, payload = value.split(",", 1)
            raw = base64.b64decode(payload, validate=True)
            if base64.b64encode(raw).decode() == payload:
                node = ["image", prefix, self.blob(raw)]
            else:
                node = ["value", value]
        else:
            node = ["value", value]
        return self.blob(canonical(node))

    def get(self, reference):
        node = json.loads(self.raw(reference))
        if node[0] == "dict":
            return {key: self.get(value) for key, value in node[1]}
        if node[0] == "list":
            return [self.get(value) for value in node[1]]
        if node[0] == "image":
            return node[1] + "," + base64.b64encode(self.raw(node[2])).decode()
        return node[1]

    def metadata(self, key, value):
        with self.lock:
            self.db.execute("insert or replace into metadata values(?,?)", (key, json.dumps(value)))
            self.db.commit()

    def reserve(self, episode, role, stage, request, artifacts, amount, total_cap, episode_cap):
        with self.lock:
            total = self.db.execute("select coalesce(sum(cost_upper),0),coalesce(sum(reserved),0) from calls").fetchone()
            local = self.db.execute("select coalesce(sum(cost_upper),0)+coalesce(sum(reserved),0) from calls where episode=?",
                                    (episode,)).fetchone()[0]
            if sum(total) + amount > total_cap or local + amount > episode_cap:
                raise BudgetExhausted("Reservation would exceed the authorized cost ceiling")
            cursor = self.db.execute("""insert into calls(episode,role,stage,started,request,artifacts,reserved,cost_upper)
                values(?,?,?,?,?,?,?,0)""", (episode, role, stage, time.time(), request, artifacts, amount))
            self.db.commit()
            return cursor.lastrowid

    def finish(self, number, response, wire, status, usage, cost, error=None):
        with self.lock:
            self.db.execute("""update calls set ended=?,response=?,wire=?,status=?,usage=?,
                cost_upper=?,reserved=0,error=?,completed=1 where id=?""",
                (time.time(), response, wire, status, json.dumps(usage), cost, error, number))
            self.db.commit()

    def summary(self):
        with self.lock:
            rows = self.db.execute("select completed,usage,cost_upper,reserved from calls").fetchall()
            sizes = self.db.execute("select count(*),sum(bytes),sum(stored_bytes) from objects").fetchone()
        usage = [json.loads(row[1]) for row in rows if row[1]]
        hit = sum(x.get("prompt_cache_hit_tokens", 0) for x in usage)
        miss = sum(x.get("prompt_cache_miss_tokens", 0) for x in usage)
        return {"calls": len(rows), "completed_calls": sum(row[0] for row in rows),
                "cost_upper_cny": sum(row[2] or 0 for row in rows),
                "reserved_cny": sum(row[3] or 0 for row in rows),
                "cache_hit_tokens": hit, "cache_miss_tokens": miss,
                "cache_hit_ratio": hit / (hit + miss) if hit + miss else None,
                "completion_tokens": sum(x.get("completion_tokens", 0) for x in usage),
                "object_count": sizes[0], "object_raw_bytes": sizes[1], "object_disk_bytes": sizes[2]}


class BudgetExhausted(RuntimeError):
    pass


def snapshot(store, directory):
    files = {}
    for path in sorted(Path(directory).rglob("*")):
        if path.is_file() and not path.is_symlink():
            files[str(path.relative_to(directory))] = store.blob(path.read_bytes())
    return store.put(files)
