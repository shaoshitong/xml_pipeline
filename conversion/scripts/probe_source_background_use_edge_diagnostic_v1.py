"""Finite development from consumed failures and saved source observations."""
from pathlib import Path
import copy
import hashlib
import json
import sqlite3
import sys
import time
import uuid

R = Path('/backup/shaoshitong/img2code_20261029')
S = R / 'conversion/scripts'
sys.path.insert(0, str(S))
sys.path.append(str(R / 'conversion/prototype'))


def main():
    from svg_source_stroke_support_v1 import may_overlap
    def line(key, points):
        return dict(id=key, type='shape', tag='path', matrix=[1,0,0,1,0,0],
                    bbox=dict(x=min(x for x,y in points),y=min(y for x,y in points),
                              w=max(x for x,y in points)-min(x for x,y in points),
                              h=max(y for x,y in points)-min(y for x,y in points)),
                    style=dict(fill='none',stroke='black',strokeWidth=1,linejoin='round'),
                    sceneGeometry=dict(topology=dict(subpaths=[dict(operations=[
                        dict(operation='moveTo',points=[points[0]]),
                        *[dict(operation='lineTo',points=[p])for p in points[1:]],
                        dict(operation='endPath',points=[])])])))
    diagonal = line('a',[(0,0),(100,100)])
    disjoint = line('b',[(0,50),(40,90)])
    crossing = line('c',[(0,100),(100,0)])
    controls = dict(disjoint_broad_boxes=not may_overlap(diagonal,disjoint,{}),
                    true_crossing_retained=may_overlap(diagonal,crossing,{}))
    assert all(controls.values()), controls
    audit=R/'conversion/source_semantic_admission_audit_v1/e430695f8e8042d3bf1b4426ca99b423/status.sqlite'
    run=R/'release/compiler_iterations/runs/svg_complex_semantic_admission_unseen_20261102_v8_C/status.sqlite'
    with sqlite3.connect(run.as_uri()+'?mode=ro',uri=True)as db:
        failed=[json.loads(r[0])for r in db.execute("select result from samples where status='abandoned'")]
    targets=[r for r in failed if r.get('reason')=='source_layer_interleaving_needs_compound_paint_representation'][:1]
    assert targets
    output=R/'conversion/source_background_use_edge_diagnostic_v1'/uuid.uuid4().hex
    output.mkdir(parents=True)
    backend=S/'compiler_svg_scene_backend_v11.py'
    original=backend.read_bytes()
    module=dict(__name__='source_stroke_support_development_backend_v1',__file__=str(backend))
    source=original.decode().replace('from svg_source_edge_layers_v2 import repair',
                                   'from svg_source_edge_layers_v5 import repair')
    assert source!=original.decode()
    exec(compile(source,str(backend),'exec'),module)
    results=[]
    for prior in targets:
        started=time.monotonic()
        with sqlite3.connect(audit.as_uri()+'?mode=ro',uri=True)as db:
            row=json.loads(db.execute('select result from sources where id=?',(prior['id'],)).fetchone()[0])
        work=Path(row['source_observation_work'])
        dom=json.loads((work/'dom.json').read_bytes())
        proof=json.loads((work/'sourceproof.json').read_bytes())
        from PIL import Image
        size=Image.open(work/'browser_source.png').size
        result=dict(id=prior['id'],prior_failure=prior['reason'],source_observation_work=str(work))
        try:
            xml,stats=module['build'](copy.deepcopy(dom),size)
            path=output/(prior['id']+'.xml');path.write_text(xml)
            result.update(structural_order_passed=True,xml_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          source_edge_layers=stats['source_edge_layers'])
        except Exception as error:
            result.update(structural_order_passed=False,reason=str(error))
            tb=error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_name=='repair':
                    loc=tb.tb_frame.f_locals
                    result['group_count']=len(loc.get('groups',{}))
                    result['edge_parent_changes']=loc.get('changes',[])
                    result['groups']={k:(v[0],list(map(str,v[1])))for k,v in loc.get('groups',{}).items()}
                    pairs=list(loc.get('constraints',{}).get(loc.get('parent'),[]))
                    result['direct_cycle_pairs']=[(a,b)for a,b in pairs if(b,a)in pairs][:8]
                    result['cycle_parent']=loc.get('parent')
                tb=tb.tb_next
        result['elapsed_seconds']=time.monotonic()-started
        results.append(result)
    assert backend.read_bytes()==original
    summary=dict(root=str(output),controls=controls,results=results,normal_conversion_calls=0,
                 browser_recaptures=0,QA_calls=0,model_calls=0,qualification_claimed=False,
                 running_validation_unchanged=True)
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
