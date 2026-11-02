"""Read-only terminal mass-run and publication audit; no conversion or QA reruns."""
from pathlib import Path
import collections, datetime, hashlib, json, sqlite3

R = Path('/backup/shaoshitong/img2code_20261029')
D = R / 'clean/complexity_curation_20261102T054553Z_v1'
RUN = 'svg_complex_background_rotation_cached_unseen_20261102_v9'

def checked(ref):
    data = (R / ref['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == ref['sha256'], ref
    return data

def main():
    run = R / 'release/compiler_iterations/runs' / (RUN + '_mass')
    with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        counts = dict(db.execute('select status,count(*) from samples group by status'))
        ids = {r[0] for r in db.execute("select id from samples where status='qualified'")}
    assert counts == {'abandoned': 651, 'qualified': 83}, counts
    with sqlite3.connect((D/'value_review_registry_v1/status.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        reviews = [r for r in db.execute('select id,status,review_root from reviews') if r[0] in ids]
    assert len(reviews) == len(ids) == 83
    assert all(status in ('held', 'published') for _, status, _ in reviews)
    pointer = json.loads((D/'current.json').read_bytes())
    ref = pointer['views']['paired_priority_complex']
    main_rows = [json.loads(s) for s in checked(ref).splitlines()]
    assert len(main_rows) == ref['rows'] == 962
    main_ids = {r['id'] for r in main_rows}
    assets = 0
    for identity, status, root in reviews:
        rows = [json.loads(s) for s in (Path(root)/'reviewed_pairs.jsonl').read_text().splitlines()]
        match = [r for r in rows if r['id'] == identity]
        assert len(match) == 1
        row = match[0]
        assert row['direct_native_PNG_visual_inspection'] is True
        pair = row['pair']
        for field, digest in [('code_file','code_sha256'), ('image_file','image_sha256'),
                              ('metadata_file','metadata_sha256'), ('original_source_code','source_code_sha256'),
                              ('original_reference','source_image_sha256')]:
            checked({'file': pair[field], 'sha256': pair[digest]}); assets += 1
        assert (identity in main_ids) == (status == 'published')
    catalog = json.loads((R/'clean/research_pairs_catalog/current.json').read_bytes())
    out = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), run=RUN,
               mass_counts=counts, content_decisions=dict(collections.Counter(r[1] for r in reviews)),
               pending_reviews=0, checked_assets=assets, strict_main=ref,
               catalogue={k:catalog.get(k) for k in ['at_utc','unique_code_PNG_pairs','unique_pairs_by_evidence_view']},
               new_normal_calls=0, new_QA_calls=0, model_calls=0, goal_complete=False)
    print(json.dumps(out))

if __name__ == '__main__':
    main()
