"""Inspect source-owned ordering cycles on consumed development cases only."""
from pathlib import Path
import copy, hashlib, json, sqlite3, sys, time, uuid

R = Path('/backup/shaoshitong/img2code_20261029')
S = R/'conversion/scripts'
sys.path[:0] = [str(S), str(R/'conversion/prototype')]

def main():
    backend = S/'compiler_svg_scene_backend_v13.py'
    source = backend.read_text().replace('from svg_source_edge_layers_v9 import repair',
                                         'from svg_source_edge_layers_v14 import repair')
    module = dict(__name__='consumed_source_cycle_diagnosis', __file__=str(backend))
    exec(compile(source, str(backend), 'exec'), module)
    run = R/'release/compiler_iterations/runs/svg_complex_background_rotation_cached_unseen_20261102_v9_mass'
    with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        targets = [json.loads(x[0]) for x in db.execute("select result from samples where status='abandoned' order by seq")]
    targets = [r for r in targets if r.get('reason') == 'source_layer_interleaving_needs_compound_paint_representation'][:3]
    cached = {r['id']:r for r in map(json.loads,(R/'conversion/source_cached_admission_v1/2d47ad593b4545038329916ff229a8ea/admitted.jsonl').read_text().splitlines())}
    results = []
    for prior in targets:
        entry = cached[prior['id']]; ref = entry['cached_DOM']; path = R/ref['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256']
        dom = json.loads(path.read_bytes()); evidence = []
        from PIL import Image
        size = Image.open(Path(entry['source_observation_work'])/'browser_source.png').size

        def trace(frame, event, arg):
            if event == 'exception' and frame.f_code.co_name == 'repair' and str(arg[1]) == 'source_layer_interleaving_needs_compound_paint_representation':
                f = frame.f_locals; parent = f['parent']; pairs = f['constraints'][parent]; objects = f['source_objects']; cells = f['cells']
                def describe(key):
                    paint = [o for o,owner in f['painted'] if key in f['_ancestors'](owner,cells)] if '_ancestors' in f else []
                    # The painter helper is global, not a frame-local value.
                    paint = [o for o,owner in f['painted'] if key in frame.f_globals['_ancestors'](owner,cells)]
                    return dict(cell=key,parent=cells[key].get('parent'),style=cells[key].get('style'),
                                paint=[dict(id=o['id'],kind=o['type'],tag=o.get('tag'),text=o.get('text','')[:120],node=o.get('node'),bbox=o.get('bbox'),style=o.get('style'),order=f['source_order'][o['id']]) for o in paint])
                # Return concrete bidirectional witnesses, plus graph edges for longer cycles.
                mutual=[(a,b) for a,b in sorted(pairs) if (b,a) in pairs]
                selected=set(k for pair in mutual[:4] for k in pair)
                if not selected:selected=set(k for pair in sorted(pairs)[:8] for k in pair)
                witnesses=[]
                for i,(a,ka) in enumerate(f['painted']):
                    for b,kb in f['painted'][i+1:]:
                        if ka==kb:continue
                        aa=list(reversed(frame.f_globals['_ancestors'](ka,cells)));bb=list(reversed(frame.f_globals['_ancestors'](kb,cells)));j=0
                        while j<min(len(aa),len(bb)) and aa[j]==bb[j]:j+=1
                        if j==0 or j==min(len(aa),len(bb)) or aa[j-1]!=parent:continue
                        if aa[j] not in selected or bb[j] not in selected:continue
                        if not frame.f_globals['_overlap'](frame.f_globals['_paint_box'](a),frame.f_globals['_paint_box'](b)):continue
                        if not f['may_overlap'](a,b,f['support_cache']):continue
                        witnesses.append(dict(before=a['id'],after=b['id'],before_owner=aa[j],after_owner=bb[j]))
                evidence.append(dict(parent=parent,mutual=mutual[:8],constraints=sorted(pairs),groups=[describe(k)for k in sorted(selected)],witnesses=witnesses))
            return trace

        started = time.monotonic();sys.settrace(trace)
        try: module['build'](copy.deepcopy(dom),size);error=None
        except Exception as exc:error=str(exc)
        finally:sys.settrace(None)
        results.append(dict(id=prior['id'],source_DOM=ref,error=error,cycle_evidence=evidence[-1:],elapsed_seconds=time.monotonic()-started))
    root = R/'conversion/source_compound_cycle_diagnosis_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    out=dict(root=str(root),results=results,normal_conversion_calls=0,QA_calls=0,model_calls=0,qualification_claimed=False)
    (root/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))

if __name__=='__main__':main()
