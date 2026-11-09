#!/usr/bin/env python3
"""Inventory local editable draw.io files for HKUST-only deterministic QA.

The inventory is read-only: it excludes generated pipeline outputs, removes exact
byte duplicates, and records enough structure to rank candidates before the
expensive remote renderer is run on HKUST3.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
import xml.etree.ElementTree as ET

BAD_NAME = re.compile(r"(^|/)(smoke|tmp|draft|test|adapter|copy|backup|old)($|[._/-])", re.I)

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def one(path: Path, root: Path, seen: set[str]):
    raw = path.read_bytes()
    code_sha = sha(raw)
    if code_sha in seen:
        return None
    seen.add(code_sha)
    try:
        tree = ET.fromstring(raw.decode('utf-8-sig'))
        cells = list(tree.iter('mxCell'))
        diagrams = len(tree.findall('.//diagram'))
        vertices = sum(c.get('vertex') == '1' for c in cells)
        edges = sum(c.get('edge') == '1' for c in cells)
        texts = sum(bool((c.get('value') or '').strip()) for c in cells)
        images = sum('shape=image' in (c.get('style') or '') for c in cells)
        # This is a deterministic prefilter only; remote render/proof is the gate.
        bad_name = bool(BAD_NAME.search(str(path).lower()))
        score = (5 if diagrams == 1 else -20)
        score += min(20, vertices / 10) + min(20, edges / 10) + min(20, texts / 10)
        score += 5 if vertices >= 10 else -10
        score += 5 if texts >= 5 else -5
        score -= 10 if bad_name else 0
        return {
            'path': str(path),
            'relative_to_documents': str(path.relative_to(root)),
            'code_sha256': code_sha,
            'bytes': len(raw),
            'diagrams': diagrams,
            'vertices': vertices,
            'edges': edges,
            'text_cells': texts,
            'image_cells': images,
            'prefilter_score': round(score, 3),
            'prefilter_name_warning': bad_name,
        }
    except Exception as exc:
        return {'path': str(path), 'relative_to_documents': str(path.relative_to(root)),
                'code_sha256': code_sha, 'bytes': len(raw), 'prefilter_error': type(exc).__name__}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--documents-root', type=Path, default=Path('/Users/shaoshitong/Documents'))
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    root = args.documents_root.resolve()
    rows, seen = [], set()
    for path in sorted(root.rglob('*.drawio')):
        if not path.is_file() or '/outputs/' in str(path):
            continue
        row = one(path, root, seen)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: (-r.get('prefilter_score', -999), r['relative_to_documents']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))
    print(json.dumps({'rows': len(rows), 'unique_sha256': len(seen),
                      'bytes': sum(r.get('bytes', 0) for r in rows),
                      'output': str(args.output)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
