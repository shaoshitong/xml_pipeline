"""Add rich flat research drawings omitted by group-dependent source rules.

Source selection only; neither successful conversion nor scientific merit is
asserted. Paths are not counted as logical nodes. Every prior target is kept.
"""
from pathlib import Path
import collections,concurrent.futures,datetime,hashlib,json,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
P=R/'release/compiler_iterations/source_pools/svg_complex_resolved_geometry_cached_unseen_20261102_v11'
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return[json.loads(l)for l in p.read_text().splitlines()if l.strip()]
def rule(f):
    return not f['stylesheet_visibility_requires_render'] and f['distinct_labels']>=18 and f['label_characters']>=300 and f['unique_word_tokens']>=15 and f['source_shape_units']>=25

def main():
    from priority_svg_dense_source_screen_v2 import features
    import sqlite3
    positive=('<svg>'+''.join('<rect/><text>Scientific attention module '+str(i)+' features channel embedding layer'+str(i)+'</text>'for i in range(30))+'</svg>').encode()
    assert rule(features(positive))
    for body in ['<svg>'+('<path d="M0 0L1 1"/>'*5000)+'</svg>','<svg>'+('<rect/><text>Repeated label</text>'*100)+'</svg>','<svg><defs>'+positive.decode()+'</defs></svg>','<svg><g display="none">'+positive.decode()+'</g></svg>']:
        assert not rule(features(body.encode()))
    full=rows(P/'all_supported_source_population.jsonl');prior=rows(P/'all_complex_raw_supported_population.jsonl');old={r['id']for r in prior};by={r['id']:r for r in full};tasks=[]
    index=R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources/index.jsonl'
    with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        for r in rows(index):
            if r['id']in old or r['id']not in by:continue
            f=r.get('features',{})
            if f.get('distinct_owner_labels',0)<18 or f.get('label_characters',0)<300 or f.get('collapsed_drawing_objects',0)<25:continue
            assert r.get('source_hash_matches_manifest')and r.get('read_status')=='read_code_only'
            hit=db.execute('select input_manifest from jobs where id=?',(r['id'],)).fetchone();assert hit
            tasks.append((by[r['id']],json.loads(hit[0])['source_code']))
    root=R/'clean/priority_svg_flat_source_screen_v1'/uuid.uuid4().hex;root.mkdir(parents=True);start=time.monotonic()
    policy=dict(source_only=True,all_prior_targets_retained=len(prior),prior_population_sha256=sha((P/'all_complex_raw_supported_population.jsonl').read_bytes()),global_supported_population_sha256=sha((P/'all_supported_source_population.jsonl').read_bytes()),index_sha256=sha(index.read_bytes()),producer_sha256=sha(Path(__file__).read_bytes()),feature_extractor_sha256=sha((S/'priority_svg_dense_source_screen_v2.py').read_bytes()),requirements=dict(distinct_labels=18,label_characters=300,unique_word_tokens=15,non_path_shape_units=25),group_count_not_required=True,paths_not_counted_as_nodes=True,scientific_value_review_still_required=True,thresholds_changed=False,normal_calls=0,QA_calls=0,model_calls=0)
    (root/'policy.json').write_text(json.dumps(policy,indent=2))
    def inspect(item):
        request,locator=item;p=(R/locator).resolve(strict=True);assert p.is_relative_to(R);b=p.read_bytes();assert sha(b)==request['source']['code_sha256'];f=features(b)
        return dict(id=request['id'],source_code_sha256=sha(b),source_image_sha256=request['source']['image_sha256'],source=request['source']['source'],source_code=locator,features=f,selected=bool(rule(f)),source_bytes=len(b))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:results=list(pool.map(inspect,tasks))
    selected=[r for r in results if r['selected']];selected_ids={r['id']for r in selected};requests=prior+[r for r in full if r['id']in selected_ids];assert len({r['id']for r in requests})==len(prior)+len(selected)
    for name,data in [('screened.jsonl',results),('selected.jsonl',selected),('additional_requests.jsonl',[r for r in full if r['id']in selected_ids]),('all_prior_and_additive_requests.jsonl',requests)]:
        (root/name).write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in data))
    out=dict(root=str(root),finished=True,metadata_prefiltered=len(tasks),additional_source_targets=len(selected),previous_targets=len(prior),total_targets=len(requests),source_bytes_read=sum(r['source_bytes']for r in results),elapsed_seconds=time.monotonic()-start,by_source=dict(collections.Counter(r['source']for r in selected)),source_admission_not_done=True,normal_calls=0,QA_calls=0,model_calls=0,goal_complete=False,files={p.name:dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)for p in root.iterdir()})
    (root/'summary.json').write_text(json.dumps(out,indent=2))
    for p in root.iterdir():p.chmod(0o444)
    print(json.dumps(out))

if __name__=='__main__':main()
