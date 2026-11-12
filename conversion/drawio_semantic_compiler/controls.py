"""Control variants with a known verdict, to prove the variant checker.

    controls.py make SAMPLE --out DIR      writes variants and DIR/controls.jsonl
    controls.py check DIR/controls.jsonl RUN

SAMPLE maps case IDs to canonical files, one {"id", "xml"} object per line.
Every case gets three deterministic rewrites of its canonical XML:

  safe      renames every cell ID the editor does not observe, reverses XML
            attribute order and plain style keys, and deflates each page; the
            checker must accept it
  seed      renames one observed cell ID (where the case has any); the
            checker must reject it for the observed ID
  moved     shifts one vertex by 7 units; the checker must reject it

``batch.py DIR/controls.jsonl --bases SAMPLE --out RUN`` produces the verdicts
that ``check`` compares with the expectations.
"""

import argparse
import base64
import json
from pathlib import Path
import sys
import urllib.parse
from xml.etree import ElementTree
import zlib

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from compiler import compile_bytes  # noqa: E402

REFERENCES = ("parent", "source", "target")


def deflate(text):
    """A page body as the editor stores it compressed."""
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    quoted = urllib.parse.quote(text, safe="~()*!'").encode("ascii")
    return base64.b64encode(packer.compress(quoted) + packer.flush()).decode("ascii")


def pages(tree):
    if tree.tag != "mxfile":
        raise ValueError("canonical XML is an mxfile")
    for diagram in tree.findall("diagram"):
        yield diagram, diagram.find("mxGraphModel").find("root")


def inner(record):
    return record if record.tag == "mxCell" else record.find("mxCell")


def rename(root, names):
    for record in root:
        if record.get("id") in names:
            record.set("id", names[record.get("id")])
        cell = inner(record)
        for key in REFERENCES:
            if cell.get(key) in names:
                cell.set(key, names[cell.get(key)])


def observed(page):
    return {cell["id"] for cell in page["cells"] if cell.get("id_roles")}


def write(tree):
    return ElementTree.tostring(tree, encoding="utf-8")


def safe(base, compiled):
    tree = ElementTree.fromstring(base)
    renamed = 0
    for (diagram, root), page, mapped in zip(pages(tree), compiled.document.pages, compiled.source_map["pages"],
                                             strict=True):
        taken = {record.get("id") for record in root}
        names = {}
        for record in root:
            old = record.get("id")
            if page.pinned or old in observed(mapped):
                continue
            new = "v" + old
            while new in taken:
                new += "_"
            taken.add(new)
            names[old] = new
        rename(root, names)
        renamed += len(names)
        for element in diagram.iter():
            style = element.get("style") if element.tag == "mxCell" else None
            if style:
                tokens = [token for token in style.split(";") if token]
                keys = [token.partition("=")[0] for token in tokens]
                if all("=" in token for token in tokens) and len(set(keys)) == len(keys):
                    element.set("style", ";".join(reversed(tokens)))
            items = list(element.attrib.items())
            element.attrib.clear()
            element.attrib.update(reversed(items))
        model = diagram.find("mxGraphModel")
        diagram.remove(model)
        diagram.text = deflate(ElementTree.tostring(model, encoding="unicode"))
    return write(tree), {"renamed_ids": renamed}


def seed(base, compiled):
    tree = ElementTree.fromstring(base)
    for (diagram, root), mapped in zip(pages(tree), compiled.source_map["pages"], strict=True):
        names = observed(mapped)
        if names:
            taken = {record.get("id") for record in root}
            old = next(record.get("id") for record in root if record.get("id") in names)
            new = old + "x"
            while new in taken:
                new += "x"
            rename(root, {old: new})
            return write(tree), {"renamed_observed_id": [old, new]}
    return None, None


def moved(base, compiled):
    tree = ElementTree.fromstring(base)
    for diagram, root in pages(tree):
        for record in root:
            cell = inner(record)
            geometry = cell.find("mxGeometry")
            if cell.get("vertex") == "1" and geometry is not None and geometry.get("relative") != "1" \
                    and geometry.get("width") and geometry.get("height"):
                geometry.set("x", repr(float(geometry.get("x", "0")) + 7))
                return write(tree), {"moved_cell": record.get("id")}
    return None, None


CONTROLS = {
    "safe": (safe, "accepted", []),
    "seed": (seed, "rejected", ["converges_to_base_bytes", "keeps_observed_ids", "native_model_equal"]),
    "moved": (moved, "rejected", ["converges_to_base_bytes", "converges_to_base_ir"]),
}


def make(args):
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in args.sample.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        base = Path(case["xml"]).read_bytes()
        compiled = compile_bytes(base)
        if compiled.xml != base:
            raise ValueError(f"{case['xml']} is not canonical")
        for name, (function, verdict, failed) in CONTROLS.items():
            data, change = function(base, compiled)
            if data is None:
                continue
            path = args.out / f"{case['id']}.{name}.drawio"
            path.write_bytes(data)
            rows.append({"id": f"{case['id']}.{name}", "case": case["id"], "xml": str(path.resolve()),
                         "control": name, "expect": verdict, "expect_failed": failed, "change": change})
    with open(args.out / "controls.jsonl", "w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    counts = {name: sum(row["control"] == name for row in rows) for name in CONTROLS}
    print(json.dumps({"controls": len(rows), "by_kind": counts, "manifest": str(args.out / "controls.jsonl")}))
    return 0


def check(args):
    wrong, counts, native = [], {}, {}
    for line in args.manifest.read_text().splitlines():
        row = json.loads(line)
        status = json.loads((args.run / "cases" / row["id"] / "status.json").read_text())
        failed = sorted(key for key, value in status["checks"].items() if not value)
        tally = counts.setdefault(row["control"], {"cases": 0, "as_expected": 0})
        tally["cases"] += 1
        if status["state"] == row["expect"] and set(row["expect_failed"]) <= set(failed):
            tally["as_expected"] += 1
        else:
            wrong.append({"id": row["id"], "state": status["state"], "failed_checks": failed,
                          "error": status.get("error")})
        for key in failed:
            if key.startswith("native_"):
                native.setdefault(row["control"], {}).setdefault(key, 0)
                native[row["control"]][key] += 1
    result = {"schema": "drawio-semantic-control-verdicts/1", "controls": counts, "native_rejections": native,
              "not_as_expected": wrong, "all_as_expected": not wrong}
    (args.run / "control_verdicts.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({key: result[key] for key in ("controls", "native_rejections", "all_as_expected")}))
    for item in wrong[:20]:
        print(json.dumps(item), file=sys.stderr)
    return 0 if not wrong else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    maker = commands.add_parser("make")
    maker.add_argument("sample", type=Path)
    maker.add_argument("--out", type=Path, required=True)
    maker.set_defaults(run_command=make)
    checker = commands.add_parser("check")
    checker.add_argument("manifest", type=Path)
    checker.add_argument("run", type=Path)
    checker.set_defaults(run_command=check)
    args = parser.parse_args(argv)
    return args.run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
