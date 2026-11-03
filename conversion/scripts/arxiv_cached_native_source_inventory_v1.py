"""Read extraction inventories; find unprocessed author-native editable files.

No conversion, external request, qualification change, or source modification.
"""
from pathlib import Path
import concurrent.futures as cf
import collections
import datetime
import hashlib
import json
import re
import sqlite3

R = Path('/backup/shaoshitong/img2code_20261029')
P = R / 'clean/arxiv_research_figures_v1'
D = P / 'cached_author_native_inventory_v1'


def paper_inventory(paper):
    f = paper / 'extraction.json'
    try:
        values = json.loads(f.read_text()).get('extracted', [])
        if not isinstance(values, list):
            return [], collections.Counter(), None
        rows, counts = [], collections.Counter()
        for name in values:
            suffix = Path(name).suffix.lower()
            counts[suffix] += 1
            if suffix not in {'.drawio', '.xml', '.svg'}:
                continue
            p = paper / 'source' / name
            if not p.resolve().is_relative_to(paper / 'source'):
                continue
            with p.open('rb') as stream:
                start = stream.read(262144)
            direct = suffix in {'.drawio', '.xml'} and re.search(br'<(?:mxfile|mxGraphModel)(?:\s|>)', start)
            embedded = suffix == '.svg' and (b'mxfile' in start or b'mxGraphModel' in start)
            if direct or embedded:
                b = p.read_bytes()
                rows.append(dict(paper=paper.name, source_file=str(p.relative_to(R)), source_bytes=len(b), source_sha256=hashlib.sha256(b).hexdigest(), kind='author_XML' if direct else 'SVG_with_author_graph_metadata', acquisition=str(paper.parent.parent.relative_to(R))))
        return rows, counts, None
    except Exception as e:
        return [], collections.Counter(), dict(paper=paper.name, error=type(e).__name__)


def main():
    D.mkdir(exist_ok=True)
    papers = [p for name in ['new_bulk_200_v1', 'recent_ai_source_expansion_v2'] for p in (P / name / 'papers').iterdir() if p.is_dir()]
    candidates, counts, errors = [], collections.Counter(), []
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for i, (rows, stats, error) in enumerate(pool.map(paper_inventory, papers), 1):
            candidates.extend(rows)
            counts.update(stats)
            if error:
                errors.append(error)
            if i % 2000 == 0:
                print(json.dumps(dict(papers_checked=i, total=len(papers), candidate_files=len(candidates))), flush=True)
    (D / 'candidates.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in candidates))
    (D / 'errors.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in errors))
    result = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), papers=len(papers), candidate_files=len(candidates), unique_candidate_source_hashes=len({r['source_sha256'] for r in candidates}), candidate_kinds=dict(collections.Counter(r['kind'] for r in candidates)), file_suffixes=dict(counts), read_errors=len(errors), conversions=0, network_requests=0, qualified_pairs_added=0)
    (D / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
