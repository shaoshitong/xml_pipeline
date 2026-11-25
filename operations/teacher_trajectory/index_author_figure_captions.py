"""Index original PNGs referenced by cached paper figures and their captions."""

import argparse
from collections import defaultdict
from itertools import groupby
from pathlib import Path, PurePosixPath
import re
import sqlite3

from export_original_pngs import DATABASE, PAPERS, paper_id, write_json


FIGURE = re.compile(r"\\begin\{(figure\*?|wrapfigure)\}(.*?)\\end\{\1\}", re.S)
GRAPHIC = re.compile(r"\\includegraphics\*?(?:\s*\[[^\]]*\])?\s*\{([^}]+)\}")
CAPTION = re.compile(r"\\caption\*?(?:\s*\[[^\]]*\])?\s*\{")
BRACE = re.compile(r"\\[{}]|[{}]")
COMMENT = re.compile(r"(?<!\\)%[^\n]*")
DIAGRAM = re.compile(
    r"architec(ture|tural)|framework|flow.?chart|block.?diagram|pipeline|workflow|"
    r"schematic|system design|network structure|overview of (our|the proposed)|"
    r"method overview|algorithm overview|data flow|control flow|configuration diagram",
    re.I,
)
PLOT = re.compile(
    r"ablation|histogram|scatter.?plot|box.?plot|bar.?chart|roc curve|precision.?recall|"
    r"loss curve|accuracy curve|training curve|confusion matrix|ablation study|"
    r"performance comparison|empirical results|heat.?map|\btable\b",
    re.I,
)


def figure_caption(body):
    start = CAPTION.search(body)
    if start is None:
        return ""
    depth = 1
    for brace in BRACE.finditer(body, start.end()):
        depth += {"{": 1, "}": -1}.get(brace[0], 0)
        if depth == 0:
            return " ".join(body[start.end():brace.start()].split())
    return ""


def figure_records(source, paths):
    suffixes = defaultdict(set)
    for path in paths:
        relative = path.relative_to(source)
        for i in range(len(relative.parts)):
            key = PurePosixPath(*relative.parts[i:])
            suffixes[str(key)].add(path)
            suffixes[str(key.with_suffix(""))].add(path)

    records = {}
    for tex in source.rglob("*.tex"):
        if tex.is_symlink() or not tex.resolve().is_relative_to(source.resolve()):
            continue
        try:
            with tex.open("rb") as stream:
                data = stream.read(4 * 1024 * 1024 + 1)
        except OSError:
            continue
        if len(data) > 4 * 1024 * 1024:
            continue
        for figure in FIGURE.finditer(COMMENT.sub("", data.decode("utf-8", errors="replace"))):
            body = figure[2]
            caption = figure_caption(body)
            if not caption:
                continue
            for graphic in GRAPHIC.finditer(body):
                key = PurePosixPath(graphic[1].strip())
                if key.is_absolute() or ".." in key.parts or "\\" in str(key):
                    continue
                matches = suffixes.get(str(key), ())
                exact = (tex.parent / key, source / key)
                path = next((item for item in exact if item in matches), None)
                if path is None and len(matches) == 1:
                    path = next(iter(matches))
                if path is None:
                    continue
                diagram = DIAGRAM.search(caption)
                plot = PLOT.search(caption+" "+path.stem)
                if plot and (not diagram or diagram.start() > plot.start()):
                    continue
                priority = int(not diagram)
                if path not in records or priority < records[path][0]:
                    records[path] = priority, caption[:1200], str(tex)
    return records


def index(out, excluded):
    db_path = out / "figures.sqlite"
    with sqlite3.connect(db_path) as db, sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True) as inventory:
        db.executescript(
            "CREATE TABLE IF NOT EXISTS figures (path TEXT PRIMARY KEY, paper TEXT, priority INTEGER, caption TEXT, tex TEXT);"
            "CREATE TABLE IF NOT EXISTS checkpoint (singleton INTEGER PRIMARY KEY, paper TEXT, scanned INTEGER);"
        )
        checkpoint = db.execute("SELECT paper, scanned FROM checkpoint WHERE singleton=1").fetchone()
        last, scanned = checkpoint or ("", 0)
        images = inventory.execute(
            "SELECT path FROM files WHERE status='checked' AND lower(substr(path,-4))='.png' ORDER BY path"
        )
        prefix = str(PAPERS) + "/"
        eligible = (path for path, in images if path.startswith(prefix) and path not in excluded)
        groups = groupby(eligible, key=lambda path: path[len(prefix):].split("/", 1)[0])
        for name, paths in groups:
            if name <= last:
                continue
            source = PAPERS / name / "source"
            valid = [Path(p) for p in paths if Path(p).is_relative_to(source)]
            records = figure_records(source, valid) if valid else {}
            db.executemany(
                "INSERT OR REPLACE INTO figures VALUES (?,?,?,?,?)",
                ((str(p), paper_id(name), *record) for p, record in records.items()),
            )
            scanned += 1
            db.execute("INSERT OR REPLACE INTO checkpoint VALUES (1,?,?)", (name, scanned))
            if scanned % 128 == 0:
                db.commit()
                report(out, db, scanned, "indexing")
        db.commit()
        report(out, db, scanned, "complete")


def report(out, db, scanned, phase):
    counts = dict(db.execute("SELECT priority,count(*) FROM figures GROUP BY priority"))
    write_json(out / "progress.json", {
        "phase": phase, "papers_scanned": scanned, "diagram_caption_candidates": counts.get(0, 0),
        "other_figure_caption_candidates": counts.get(1, 0), "source": str(DATABASE),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exclude-shortlist", type=Path, action="append", default=[])
    args = parser.parse_args()
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    excluded = {line for index_file in args.exclude_shortlist for line in index_file.read_text().splitlines()}
    index(args.out, excluded)


if __name__ == "__main__":
    main()
