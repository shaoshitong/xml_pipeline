#!/usr/bin/env python3
"""Bounded arXiv source pilot. Run only on the destination server.
Downloads PDFs/source for <=10 papers, indexes editable figure source statically,
optionally rasterizes PDF assets, and never executes TeX or downloaded scripts.
Requires requests; PyMuPDF is optional.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import requests

DEFAULT_PAPERS = ['2405.15306', '2603.03072', '2504.09479', '2604.05514', '2605.15677', '1706.03762']


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


class ArxivClient:
    def __init__(self, interval, max_bytes, logger):
        self.interval = max(3.1, interval)
        self.last_start = 0
        self.max_bytes = max_bytes
        self.logger = logger
        self.session = requests.Session()  # honor destination HTTP(S)_PROXY
        self.session.headers['User-Agent'] = 'img2code-research-source-pilot/1.0 (bounded six-paper metadata/source collection)'

    def fetch(self, url, path):
        if path.exists():
            payload = path.read_bytes()
            self.logger({'event': 'reuse_download', 'url': url, 'path': str(path), 'bytes': len(payload)})
            return {'url': url, 'path': str(path), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(), 'reused': True}
        last = None
        for attempt in range(2):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_start)))
            self.last_start = time.monotonic()
            self.logger({'event': 'request_start', 'url': url, 'attempt': attempt + 1})
            part = Path(str(path) + '.part')
            try:
                with self.session.get(url, stream=True, timeout=(30, 180)) as response:
                    response.raise_for_status()
                    length = response.headers.get('Content-Length')
                    if length and int(length) > self.max_bytes:
                        raise ValueError('response exceeds bounded pilot byte limit')
                    digest = hashlib.sha256()
                    total = 0
                    with part.open('wb') as output:
                        for chunk in response.iter_content(1024 * 1024):
                            if not chunk:
                                continue
                            total += len(chunk)
                            if total > self.max_bytes:
                                raise ValueError('stream exceeds bounded pilot byte limit')
                            digest.update(chunk)
                            output.write(chunk)
                    os.replace(part, path)
                    record = {'url': url, 'path': str(path), 'bytes': total,
                              'sha256': digest.hexdigest(), 'content_type': response.headers.get('Content-Type'),
                              'retrieved_at': now()}
                    self.logger({'event': 'download_complete', **record})
                    return record
            except Exception as exc:
                last = type(exc).__name__
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    last += ':' + str(exc.response.status_code)
                    if exc.response.status_code in (400, 401, 403, 404, 429):
                        break
                elif isinstance(exc, ValueError):
                    last += ':' + str(exc)
                self.logger({'event': 'request_failed', 'url': url, 'error': last})
        raise RuntimeError('arXiv request failed: ' + str(last))


def metadata_from_abs(text, paper_id):
    base = re.sub(r'v\d+$', '', paper_id)
    explicit = re.search(r'v(\d+)$', paper_id)
    versions = [int(v) for v in re.findall(r'/(?:abs|pdf|html)/' + re.escape(base) + r'v(\d+)', text)]
    versions += [int(v) for v in re.findall(r'arXiv:' + re.escape(base) + r'v(\d+)', text)]
    version = int(explicit.group(1)) if explicit else max(versions, default=0)
    if not version:
        raise ValueError('cannot prove fixed arXiv version from abs page')
    def meta(name):
        # Meta attribute order varies; inspect each tag independently.
        for tag in re.findall(r'<meta\b[^>]*>', text, flags=re.I):
            if re.search(r'name=["\']' + re.escape(name) + r'["\']', tag, flags=re.I):
                match = re.search(r'content=["\'](.*?)["\']\s*/?>', tag, flags=re.I)
                if match:
                    return html.unescape(match.group(1))
        return None
    licenses = sorted(set(html.unescape(x) for x in re.findall(
        r'href=["\'](https?://(?:arxiv\.org/licenses/[^"\']+|creativecommons\.org/licenses/[^"\']+))["\']', text, re.I)))
    return {'arxiv_id': base, 'version': version, 'versioned_id': f'{base}v{version}',
            'title': meta('citation_title'), 'publication_date': meta('citation_date'),
            'license_urls': licenses, 'abs_url': f'https://arxiv.org/abs/{base}v{version}',
            'license_note': 'arXiv distribution license does not automatically grant training/redistribution rights; retain source license and author attribution.'}


def safe_extract(source, target, max_total=2 * 1024**3, max_files=100000):
    """No extraction API follows links. Only ordinary files/directories are created."""
    target.mkdir(parents=True, exist_ok=True)
    extracted, rejected = [], []
    total = 0
    try:
        archive = tarfile.open(source, 'r:*')
    except tarfile.ReadError:
        payload = source.read_bytes()
        if payload.startswith(b'%PDF'):
            return {'format': 'pdf_only', 'extracted': [], 'rejected': [], 'source_editable': False}
        if payload.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                payload = stream.read(max_total + 1)
        if len(payload) > max_total:
            raise ValueError('source decompression exceeds byte limit')
        if b'\\documentclass' in payload[:100000] or b'\\begin{document}' in payload:
            path = target / 'source.tex'
            path.write_bytes(payload)
            return {'format': 'single_tex', 'extracted': ['source.tex'], 'rejected': []}
        return {'format': 'unknown', 'extracted': [], 'rejected': [], 'source_editable': False}
    with archive:
        for count, member in enumerate(archive):
            if count >= max_files:
                raise ValueError('source member count exceeds limit')
            name = member.name
            parts = PurePosixPath(name).parts
            if PurePosixPath(name).is_absolute() or '..' in parts or '\\' in name or not parts:
                rejected.append({'member': name, 'reason': 'unsafe_path'})
                continue
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                rejected.append({'member': name, 'reason': 'link_or_special_file'})
                continue
            dest = target.joinpath(*parts)
            # Reject links already present from earlier runs or manual changes too.
            if any(parent.is_symlink() for parent in [dest, *dest.parents] if parent != target.parent):
                rejected.append({'member': name, 'reason': 'existing_symlink'})
                continue
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            total += member.size
            if member.size < 0 or total > max_total:
                raise ValueError('source extraction exceeds byte limit')
            dest.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                rejected.append({'member': name, 'reason': 'unreadable_member'})
                continue
            with stream, dest.open('wb') as output:
                remaining = member.size
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('truncated archive member')
                    output.write(block)
                    remaining -= len(block)
            os.chmod(dest, 0o600)
            extracted.append(str(dest.relative_to(target)))
    return {'format': 'tar', 'extracted': extracted, 'rejected': rejected, 'uncompressed_bytes': total}


def static_index(folder, render_pdf=True):
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            fitz = None
    output = folder.parent / 'derived_rasters'
    records, refs = [], []
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = str(path.relative_to(folder))
        suffix = path.suffix.lower()
        size = path.stat().st_size
        record = {'path': relative, 'bytes': size}
        text = ''
        if suffix in ('.tex', '.sty', '.cls', '.svg', '.xml', '.drawio', '.py', '.r', '.jl', '.js', '.mmd', '.puml') and size <= 5 * 1024**2:
            text = path.read_text(errors='replace')
        if suffix in ('.tex', '.sty', '.cls'):
            tikz = [m.start() for m in re.finditer(r'\\begin\s*\{tikzpicture\}', text)]
            plots = [m.start() for m in re.finditer(r'\\begin\s*\{(?:axis|semilogxaxis|semilogyaxis|loglogaxis|groupplot)\}', text)]
            if tikz or plots:
                record.update(kind='editable_latex_figure_source', tikz_environments=len(tikz), pgfplots_environments=len(plots),
                              pair_status='candidate_requires_render_and_asset_verification', editable=True)
            for match in re.finditer(r'\\(includegraphics|input|include|pgfplotstableread|addplot\s+table)\*?(?:\s*\[[^\]]*\])?\s*\{([^}]+)\}', text):
                target = match.group(2).strip()
                candidates = [path.parent / target]
                if not Path(target).suffix:
                    candidates += [path.parent / (target + ext) for ext in ('.pdf', '.png', '.jpg', '.eps', '.svg', '.tex', '.csv', '.dat')]
                existing = [str(x.relative_to(folder)) for x in candidates if x.exists() and x.is_relative_to(folder)]
                refs.append({'from': relative, 'command': match.group(1), 'target': target,
                             'resolved_paths': existing, 'status': 'present' if existing else 'unresolved_or_macro'})
        elif suffix == '.svg' and '<svg' in text[:2000]:
            record.update(kind='editable_svg_source', editable=True, pair_status='candidate_source_no_independent_raster_verified')
        elif suffix == '.drawio' or (suffix == '.xml' and ('<mxfile' in text or '<mxGraphModel' in text)):
            record.update(kind='editable_mxgraph_source', editable=True, pair_status='candidate_source_no_independent_raster_verified')
        elif suffix in ('.py', '.r', '.jl', '.js') and re.search(r'matplotlib|pyplot|plotly|ggplot|seaborn|bokeh|altair|vega|d3\.', text, re.I):
            record.update(kind='plotting_script_candidate', editable=True, pair_status='not_executed_dependencies_unverified')
        elif suffix in ('.mmd', '.puml'):
            record.update(kind='editable_diagram_language_source', editable=True, pair_status='not_rendered')
        elif suffix in ('.pdf', '.eps', '.ps'):
            record.update(kind='vector_asset_only', editable=False, pair_status='vector_only_not_editable_code_pair')
            if suffix == '.pdf' and render_pdf and fitz is not None and size < 100 * 1024**2:
                try:
                    document = fitz.open(path)
                    if document.page_count:
                        page = document[0]
                        scale = min(2, 2048 / max(page.rect.width, page.rect.height))
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                        output.mkdir(parents=True, exist_ok=True)
                        png = output / (hashlib.sha256(relative.encode()).hexdigest()[:14] + '.png')
                        pixmap.save(png)
                        record.update(derived_raster=str(png), raster_origin='rendered_from_pdf_vector_asset',
                                      render_page=1, pdf_pages=document.page_count,
                                      pdf_vector_drawing_count=len(page.get_drawings()))
                    document.close()
                except Exception as exc:
                    record['render_error'] = type(exc).__name__
        elif suffix in ('.png', '.jpg', '.jpeg', '.webp'):
            record.update(kind='raster_asset', editable=False, pair_status='no_corresponding_editable_source_established')
        if 'kind' in record:
            records.append(record)
    return {'files': records, 'figure_and_input_references': refs,
            'editable_source_candidates': sum(bool(x.get('editable')) for x in records),
            'vector_only_assets': sum(x.get('kind') == 'vector_asset_only' for x in records),
            'complete_pairs_claimed': 0,
            'note': 'Static pilot only. PDF/EPS assets and PDF-derived rasters are not editable code pairs. Source code and external dependencies must be rendered/verified before inclusion in clean training data.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--papers', nargs='+', default=DEFAULT_PAPERS)
    parser.add_argument('--interval', type=float, default=3.2)
    parser.add_argument('--max-download-mb', type=int, default=512)
    parser.add_argument('--no-render', action='store_true')
    args = parser.parse_args()
    if not 1 <= len(args.papers) <= 10:
        parser.error('bounded pilot requires 1-10 papers')
    if any(not re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?', x) for x in args.papers):
        parser.error('papers must be modern numeric arXiv IDs, optionally versioned')
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    log = (root / 'progress.jsonl').open('a', buffering=1)
    def emit(event):
        event = {'time': now(), **event}
        log.write(json.dumps(event, ensure_ascii=False) + '\n')
        print(json.dumps(event, ensure_ascii=False), flush=True)
    client = ArxivClient(args.interval, args.max_download_mb * 1024**2, emit)
    results = []
    for paper in args.papers:
        record = {'requested_id': paper, 'started_at': now(), 'downloads': {}}
        try:
            base = re.sub(r'v\d+$', '', paper)
            meta_folder = root / 'metadata'
            meta_folder.mkdir(exist_ok=True)
            abs_path = meta_folder / (paper + '.html')
            record['downloads']['abstract'] = client.fetch('https://arxiv.org/abs/' + paper, abs_path)
            meta = metadata_from_abs(abs_path.read_text(errors='replace'), paper)
            record.update(meta)
            target = root / meta['versioned_id']
            target.mkdir(exist_ok=True)
            write_json(target / 'provenance.json', meta)
            for kind, endpoint, filename in [('pdf', 'pdf', 'paper.pdf'), ('source', 'src', 'source.archive')]:
                try:
                    record['downloads'][kind] = client.fetch(f'https://arxiv.org/{endpoint}/{meta["versioned_id"]}', target / filename)
                except Exception as exc:
                    record['downloads'][kind] = {'status': 'failed', 'error': type(exc).__name__ + ':' + str(exc)[:160]}
            source = target / 'source.archive'
            if source.exists():
                record['extraction'] = safe_extract(source, target / 'source')
                index = static_index(target / 'source', render_pdf=not args.no_render)
                write_json(target / 'source_index.json', index)
                record['index_summary'] = {k: index[k] for k in ('editable_source_candidates', 'vector_only_assets', 'complete_pairs_claimed')}
                record['status'] = 'indexed' if record['extraction']['extracted'] else 'source_not_editable_or_unavailable'
            else:
                record['status'] = 'source_download_failed'
        except Exception as exc:
            record['status'] = 'failed'
            record['error'] = type(exc).__name__ + ':' + str(exc)[:180]
        record['finished_at'] = now()
        results.append(record)
        write_json(root / 'manifest.json', {'updated_at': now(), 'finished': False, 'papers': results})
        emit({'event': 'paper_finished', 'requested_id': paper, 'status': record['status'], 'index_summary': record.get('index_summary')})
    summary = {'updated_at': now(), 'finished': True, 'papers_requested': len(args.papers),
               'indexed_papers': sum(x['status'] == 'indexed' for x in results),
               'complete_pairs_claimed': 0, 'papers': results}
    write_json(root / 'manifest.json', summary)
    emit({'event': 'pilot_finished', 'papers_requested': len(args.papers), 'indexed_papers': summary['indexed_papers'], 'complete_pairs_claimed': 0})
    log.close()
    return 0 if all(x['status'] == 'indexed' for x in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
