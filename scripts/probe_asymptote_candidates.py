"""Read only CoSyn code/metadata columns; parser-only bounded candidate audit."""
import argparse
import collections
import hashlib
import heapq
import importlib.util
import json
from pathlib import Path
import time


def main(args):
    import pyarrow.parquet as pq
    root = args.root.resolve()
    path = args.support or root / 'scripts/asymptote_support.py'
    spec = importlib.util.spec_from_file_location('probe_asy_support', path)
    support = importlib.util.module_from_spec(spec); spec.loader.exec_module(support)
    started = time.monotonic(); deadline = started + args.seconds
    counts = collections.Counter(); by_figure = collections.Counter(); files = []; warnings = []
    sample_heap = []; first_by_figure = {}; ordinal = 0
    sources = sorted((root / 'raw/allenai--CoSyn-400K/graphic').glob('*.parquet'))
    for source in sources:
        pf = pq.ParquetFile(source)
        columns = [name for name in ('code', 'metadata') if name in pf.schema_arrow.names]
        file_stats = {'file': str(source.relative_to(root)), 'footer_rows': pf.metadata.num_rows,
                      'read_columns': columns, 'image_column_read': False, 'rows_inspected': 0}
        files.append(file_stats)
        row_index = 0
        for batch in pf.iter_batches(columns=columns, batch_size=128):
            for row in batch.to_pylist():
                if time.monotonic() > deadline:
                    warnings.append('scan_time_budget_exhausted'); break
                ordinal += 1; counts['rows_inspected'] += 1; file_stats['rows_inspected'] += 1
                code = row.get('code')
                if not isinstance(code, str): counts['nonstring_code'] += 1; row_index += 1; continue
                # Real inspected rows are plain strings. Keep this probe's scope
                # explicit rather than silently adapting arbitrary wrappers.
                if not support.is_asymptote(code): counts['not_asymptote_signature'] += 1; row_index += 1; continue
                counts['asymptote_signature_candidates'] += 1
                facts = support.visual_facts(code)
                if not facts.get('chart'):
                    counts['no_positive_chart_evidence'] += 1; row_index += 1; continue
                counts['positive_chart_candidates'] += 1
                meta = row.get('metadata')
                figure = str(meta.get('figure_type', ''))[:100] if isinstance(meta, dict) else '[metadata_unavailable]'
                by_figure[figure] += 1
                digest = hashlib.sha256(code.encode('utf-8')).hexdigest()
                ref = {'file': str(source.relative_to(root)), 'row': row_index, 'figure_type': figure,
                       'code_chars': len(code), 'code_sha256': digest, 'visual_facts': facts}
                candidate = (ref, code)
                if figure not in first_by_figure: first_by_figure[figure] = candidate
                item = (-int(digest, 16), ordinal, ref, code)
                if args.samples > 0:
                    if len(sample_heap) < args.samples: heapq.heappush(sample_heap, item)
                    elif item > sample_heap[0]: heapq.heapreplace(sample_heap, item)
                row_index += 1
            if warnings: break
        if warnings: break
    selected = {(r['file'], r['row']): (r, code) for r, code in first_by_figure.values()}
    selected.update({(item[2]['file'], item[2]['row']): (item[2], item[3]) for item in sample_heap})
    outcomes = []; issues = collections.Counter()
    for ref, code in selected.values():
        if time.monotonic() > deadline:
            warnings.append('native_sample_time_budget_exhausted'); break
        raw_root = root / 'raw/allenai--CoSyn-400K'
        dependency = support.dependency_issue(code, raw_root)
        syntax = support.syntax_facts(code, task_root=root)
        reason = dependency or syntax.get('issue')
        counts['native_samples_checked'] += 1
        counts['native_samples_structurally_valid'] += reason is None
        if reason: issues[reason] += 1
        outcomes.append({**ref, 'syntax': syntax, 'dependency_issue': dependency,
                         'structurally_valid_without_code_execution': reason is None})
    print(json.dumps({'read_only': True, 'observed_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      'support_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'counts': dict(counts), 'positive_candidates_by_figure_type': dict(by_figure),
                      'files': files, 'native_sample_issue_counts': dict(issues), 'samples': outcomes,
                      'warnings': warnings, 'seconds': round(time.monotonic() - started, 2),
                      'scope': 'Code and metadata only; no image column, source execution, rendering, model, download, curator or canonical manifest writes. Candidate counts are not accepted pair totals. Native syntax check is upstream parseonly with stdout discarded. Hash-ranked sample plus first positive per figure type.'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--support', type=Path); parser.add_argument('--samples', type=int, default=48)
    parser.add_argument('--seconds', type=int, default=45); main(parser.parse_args())
