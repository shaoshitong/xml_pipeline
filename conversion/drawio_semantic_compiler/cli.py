"""drawio-compile: compile one draw.io file to canonical editable XML through a graph IR."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from compiler import COMPILER_VERSION, compile_bytes, dump
from source import CompileError

OUTPUT = "canonical.drawio"


def write_outputs(folder, result):
    (folder / OUTPUT).write_bytes(result.xml)
    (folder / "ir.json").write_bytes(dump(result.ir_json))
    (folder / "source_map.json").write_bytes(dump(result.source_map))
    (folder / "report.json").write_bytes(dump(result.report))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="drawio-compile", description=__doc__)
    parser.add_argument("source", type=Path, help="a .drawio file or bare mxGraphModel XML")
    parser.add_argument("--out", type=Path, required=True, help="new directory for the outputs")
    parser.add_argument("--verify-native", action="store_true",
                        help="also open source and output in the pinned draw.io editor and require equal "
                             "pixels and editing behaviour (needs the lab runtime)")
    parser.add_argument("--version", action="version", version=COMPILER_VERSION)
    args = parser.parse_args(argv)
    try:
        if args.out.exists():
            raise OSError(f"output directory already exists: {args.out}")
        data = args.source.read_bytes()
        result = compile_bytes(data)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".drawio-compile-", dir=args.out.parent) as staging:
            folder = Path(staging) / "result"
            folder.mkdir()
            write_outputs(folder, result)
            native = None
            if args.verify_native:
                from native_verify import verify_files
                native = verify_files(data, result, folder)
                (folder / "native.json").write_bytes(dump(native))
            folder.rename(args.out)
    except CompileError as error:
        for diagnostic in error.diagnostics:
            print(f"drawio-compile: {args.source}: {diagnostic}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"drawio-compile: {error}", file=sys.stderr)
        return 2
    summary = {"output": str(args.out / OUTPUT), "sha256": result.report["output"]["sha256"],
               "pages": result.report["pages"], "input_bytes": len(data), "output_bytes": len(result.xml),
               "warnings": sum(d["severity"] == "warning" for d in result.report["diagnostics"])}
    if native is not None:
        summary["native_equal"] = native["equal"]
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if native is None or native["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
