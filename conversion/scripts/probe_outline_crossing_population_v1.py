"""Bounded source-structure development census, never a qualification gate."""
from pathlib import Path
import argparse, concurrent.futures, copy, hashlib, json, multiprocessing, sqlite3, sys, time, uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
sys.path[:0]=[str(S),str(R/'conversion/prototype')]

def task(arguments):
    prior,entry,output=arguments;started=time.monotonic();ref=entry['cached_DOM'];p=R/ref['file']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256']
    from PIL import Image
    import compiler_svg_scene_backend_v15 as backend
    dom=json.loads(p.read_bytes());size=Image.open(Path(entry['source_observation_work'])/'browser_source.png').size
    row=dict(id=prior['id'],prior_reason=prior['reason'],source_DOM=ref,qualification_claimed=False)
    try:
        xml,stats=backend.build(copy.deepcopy(dom),size);path=Path(output)/(prior['id']+'.xml');path.write_text(xml)
        row.update(structural_passed=True,xml_file=str(path.relative_to(R)),xml_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),layer_proof=stats['source_edge_layers'])
    except Exception as exc:row.update(structural_passed=False,reason=str(exc)[:1000])
    row['elapsed_seconds']=time.monotonic()-started;return row

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=24);args=parser.parse_args();assert 1<=args.limit<=203
    run=R/'release/compiler_iterations/runs/svg_complex_background_rotation_cached_unseen_20261102_v9_mass'
    with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        failures=[json.loads(x[0])for x in db.execute("select result from samples where status='abandoned' order by seq")]
    targets=[r for r in failures if r.get('reason')=='source_layer_interleaving_needs_compound_paint_representation'][:args.limit]
    cached={r['id']:r for r in map(json.loads,(R/'conversion/source_cached_admission_v1/2d47ad593b4545038329916ff229a8ea/admitted.jsonl').read_text().splitlines())}
    root=R/'conversion/source_outline_crossing_population_development_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    started=time.monotonic();results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=6,mp_context=multiprocessing.get_context('fork'))as pool:
        tasks=[pool.submit(task,(r,cached[r['id']],str(root)))for r in targets]
        for future in concurrent.futures.as_completed(tasks):
            results.append(future.result());(root/'progress.json').write_text(json.dumps(dict(completed=len(results),total=len(targets),structural_passed=sum(r['structural_passed']for r in results))))
    summary=dict(root=str(root),results=results,completed=len(results),structural_passed=sum(r['structural_passed']for r in results),elapsed_seconds=time.monotonic()-started,normal_conversion_calls=0,QA_calls=0,model_calls=0,qualification_claimed=False,unseen_gate=False,all_cases_previously_consumed=True)
    (root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':main()
