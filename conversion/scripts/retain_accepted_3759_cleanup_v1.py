"""Freeze accepted pairs; prune only an explicit plan outside protected data/code.

The complete arXiv working tree and its running procedure are excluded from
cleanup. Never follows symlinks during deletion. Original accepted assets and
declared evidence remain at their existing paths; a compact pair view hardlinks
the exact same bytes without duplicating data storage.
"""
import argparse
import concurrent.futures as cf
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

R = Path('/backup/shaoshitong/img2code_20261029')
D = R / 'reports/retention_3759_v1'
A = R / 'clean/accepted_3759_v1'
SNAPSHOT = 'clean/research_pairs_catalog/snapshot_20261103T050123984464Z_v5_ce4384b8de20'
INDEX_SHA = 'ff8be5a09c73f63b35c5e10fdf45c99101fb0b10ce128caf78fe1b2304e3bf43'
VALIDATION_SHA = '8dc0f04f07e2633c81d660e2616ee1ad9962d588a92dc137fa1d735fc2294e31'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(2 ** 20), b''):
            h.update(block)
    return h.hexdigest()


def put(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + '.tmp')
    temp.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, p)


def original_rows():
    p = R / SNAPSHOT / 'pairs.jsonl'
    assert digest(p) == INDEX_SHA
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert len(rows) == len({x['id'] for x in rows}) == 3759
    return rows


def check_assets(rows, prefix=''):
    jobs = {}
    for row in rows:
        for field, key in [('code_file', 'code_sha256'), ('image_file', 'image_sha256')]:
            p = R / row[field]
            assert p.resolve(strict=True).is_relative_to(R)
            assert p not in jobs or jobs[p] == row[key]
            jobs[p] = row[key]
    def check(item):
        p, expected = item
        assert digest(p) == expected, str(p)
        return p.stat().st_size
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        total = sum(pool.map(check, jobs.items()))
    out = dict(at_utc=now(), pairs=len(rows), files=len(jobs), bytes=total, all_sha256_match=True)
    print(json.dumps(dict(check=prefix, **out)), flush=True)
    return out


def prepare():
    D.mkdir(parents=True, exist_ok=True)
    rows = original_rows()
    pre = check_assets(rows, 'original_3759_before_cleanup')
    validation = R / SNAPSHOT / 'validation.json'
    assert digest(validation) == VALIDATION_SHA
    assets = json.loads(validation.read_text())['assets']
    keep = set()
    rehashed = 0
    for item in assets:
        p = R / item['file']
        resolved = p.resolve(strict=True)
        assert resolved.is_relative_to(R) and resolved.is_file()
        s = resolved.stat()
        if (s.st_ino, s.st_size, s.st_mtime_ns) != (item['inode'], item['bytes'], item['mtime_ns']):
            assert digest(resolved) == item['sha256'], str(p)
            rehashed += 1
        keep.update([str(p.relative_to(R)), str(resolved.relative_to(R))])
    A.mkdir(parents=True, exist_ok=True)
    frozen = []
    for number, row in enumerate(rows, 1):
        new = dict(row, accepted_baseline_number=number, original_code_file=row['code_file'], original_image_file=row['image_file'])
        folder = A / 'pairs' / f'{number:06d}'
        folder.mkdir(parents=True, exist_ok=True)
        for field, name in [('code_file', 'editable.drawio'), ('image_file', 'image.png')]:
            src, dest = R / row[field], folder / name
            if not dest.exists():
                os.link(src.resolve(strict=True), dest)
            assert os.path.samefile(src, dest)
            new[field] = str(dest.relative_to(R))
        frozen.append(new)
    manifest = A / 'pairs.jsonl'
    manifest.write_text(''.join(json.dumps(x, ensure_ascii=True, sort_keys=True) + '\n' for x in frozen))
    shutil.copy2(R / SNAPSHOT / 'summary.json', A / 'original_catalogue_summary.json')
    put(A / 'current.json', dict(pairs={'file': str(manifest.relative_to(R)), 'sha256': digest(manifest), 'rows': 3759}, accepted_baseline_frozen=True, source_snapshot=SNAPSHOT, source_index_sha256=INDEX_SHA, incremental_arxiv_catalogue='clean/research_pairs_catalog/current.json'))
    (A / 'README.md').write_text('# 用户确认保留的 3759 对成品\n\n固定基准：3759 对 = 框图/海报1151 + 科学图表2074 + arXiv534。\n\n`pairs.jsonl` 中路径相对 HKUST3 `/backup/shaoshitong/img2code_20261029`。每个 `pairs/编号/` 内是原字节 PNG 和可编辑 drawio。使用硬链接整理，不重复占用数据空间。来源和核验等级保留在记录中；不同等级不能混为原图保真。\n\narXiv 继续采集，新增合格结果由 `clean/research_pairs_catalog/current.json` 持续汇总；本目录基准固定不变。旧的其他数据集及未保留产物按用户授权清理。\n')
    protected = {'scripts', 'remote', 'conversion/scripts', 'conversion/prototype', 'conversion/private', 'conversion/private_arxiv_transport_v3', 'conversion/runtime', 'evaluation/assets', 'release/git', 'release/source_backups', 'release/source_publications', 'reports/retention_3759_v1', 'clean/arxiv_research_figures_v1', 'clean/accepted_3759_v1', 'clean/review_samples', SNAPSHOT, 'clean/curated_complex_research_delivery', 'clean/curated_complex_research_delivery_final_v2'}
    for p in (R / 'conversion').iterdir():
        if 'arxiv' in p.name or p.name == 'research_catalog_watch_supervisor_v1':
            protected.add(str(p.relative_to(R)))
    catalogue = R / 'clean/research_pairs_catalog'
    current = json.loads((catalogue / 'current.json').read_text())
    protected.add(current['snapshot'])
    for p in catalogue.iterdir():
        if p.is_file():
            keep.add(str(p.relative_to(R)))
    summary = json.loads((R / SNAPSHOT / 'summary.json').read_text())
    for item in summary['input_manifests']:
        keep.add(item['source'])
    curator = R / 'clean/complexity_curation_20261102T054553Z_v1/current.json'
    keep.add(str(curator.relative_to(R)))
    def references(x):
        if isinstance(x, dict):
            f = x.get('file')
            if isinstance(f, str) and (R / f).is_file() and (R / f).resolve().is_relative_to(R):
                keep.add(str((R / f).relative_to(R)))
            for value in x.values():
                references(value)
        elif isinstance(x, list):
            for value in x:
                references(value)
    references(json.loads(curator.read_text()))
    for row in json.loads((D / 'source_protection.json').read_text())['files']:
        if (R / row['file']).is_file():
            keep.add(row['file'])
    keep.update(['README.txt', 'RETAIN_3759_ONLY.json'])
    ancestors = set()
    for name in keep | protected:
        p = Path(name)
        assert not p.is_absolute() and '..' not in p.parts
        ancestors.update(str(q) for q in p.parents if str(q) != '.')
    removals = []
    def visit(folder):
        for p in folder.iterdir():
            rel = str(p.relative_to(R))
            if rel in protected or rel in keep:
                continue
            if rel in ancestors:
                assert not p.is_symlink() and p.is_dir(), str(p)
                visit(p)
            else:
                s = p.lstat()
                removals.append(dict(file=rel, inode=s.st_ino, device=s.st_dev, is_dir=stat.S_ISDIR(s.st_mode)))
    visit(R)
    names = [x['file'] for x in removals]
    for name in names:
        assert name not in keep and name not in protected and name not in ancestors
    plan = dict(schema='accepted3759_cleanup_plan_v1', at_utc=now(), root=str(R), baseline=3759, source_snapshot=SNAPSHOT, source_index_sha256=INDEX_SHA, original_assets_verified=pre, declared_evidence_files=len(assets), evidence_hashes_rechecked_on_stat_change=rehashed, kept_files=sorted(keep), protected_trees=sorted(protected), delete_roots=removals, arxiv_continues=True, disk_free_before=shutil.disk_usage(R).free)
    put(D / 'plan.json', plan)
    put(D / 'prepared.json', dict(at_utc=now(), plan_sha256=digest(D / 'plan.json'), delete_roots=len(removals), baseline=3759, preserved_evidence=len(assets), accepted_manifest_sha256=digest(manifest)))
    print((D / 'prepared.json').read_text(), flush=True)


def apply(expected, commit):
    planfile = D / 'plan.json'
    assert digest(planfile) == expected
    plan = json.loads(planfile.read_text())
    publication = json.loads((D / 'cleanup_source_publication.json').read_text())
    assert publication['source_commit'] == publication['remote_sha'] == commit
    assert publication['cleanup_script_sha256'] == digest(Path(__file__))
    assert plan['baseline'] == 3759 and plan['arxiv_continues'] is True
    frozen = [json.loads(x) for x in (A / 'pairs.jsonl').read_text().splitlines()]
    assert len(frozen) == 3759
    # Hardlinks must still refer to the protected originals immediately before deletion.
    for row in frozen:
        for field, original in [('code_file', 'original_code_file'), ('image_file', 'original_image_file')]:
            assert os.path.samefile(R / row[field], R / row[original])
    protected = set(plan['protected_trees']) | set(plan['kept_files'])
    protected_ancestors = {str(q) for name in protected for q in Path(name).parents if str(q) != '.'}
    def remove(item):
        rel = item['file']
        assert rel not in protected and rel not in protected_ancestors
        target = R / rel
        assert target.parent.resolve().is_relative_to(R) and target != R
        try:
            s = target.lstat()
        except FileNotFoundError:
            return rel
        assert (s.st_ino, s.st_dev) == (item['inode'], item['device']), rel
        if stat.S_ISDIR(s.st_mode):
            shutil.rmtree(target)
        else:
            target.unlink()
        return rel
    put(D / 'deletion_started.json', dict(at_utc=now(), plan_sha256=expected, source_commit=commit, roots=len(plan['delete_roots'])))
    completed = 0
    with (D / 'deleted_roots.jsonl').open('a', buffering=1) as log:
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            for name in pool.map(remove, plan['delete_roots']):
                log.write(json.dumps({'deleted': name, 'at_utc': now()}) + '\n')
                completed += 1
                if completed % 100 == 0:
                    put(D / 'progress.json', dict(at_utc=now(), completed_roots=completed, total_roots=len(plan['delete_roots']), disk_free=shutil.disk_usage(R).free))
                    print(json.dumps({'deleted_roots': completed, 'total': len(plan['delete_roots'])}), flush=True)
    assert not any((R / x['file']).exists() or (R / x['file']).is_symlink() for x in plan['delete_roots'])
    verify = check_assets(frozen, 'accepted3759_after_cleanup')
    for name in plan['kept_files']:
        assert (R / name).exists(), name
    result = dict(at_utc=now(), completed=True, baseline=3759, deleted_roots=completed, plan_sha256=expected, source_commit=commit, arxiv_working_tree_preserved=(R / 'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/once.sqlite').is_file(), post_deletion_verification=verify, disk_free_before=plan['disk_free_before'], disk_free_after=shutil.disk_usage(R).free)
    result['net_disk_free_increase_bytes'] = result['disk_free_after'] - result['disk_free_before']
    put(D / 'complete.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=['prepare', 'apply'])
    p.add_argument('--expected-plan-sha')
    p.add_argument('--source-commit')
    args = p.parse_args()
    if args.phase == 'prepare':
        prepare()
    else:
        assert args.expected_plan_sha and args.source_commit
        apply(args.expected_plan_sha, args.source_commit)
