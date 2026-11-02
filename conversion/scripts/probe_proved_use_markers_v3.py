"""Actual source reconstruction plus negative ownership evidence controls."""
from pathlib import Path
import copy,json,sqlite3,sys,uuid
import compiler_svg_scene_frontend_v11 as f
import compiler_svg_scene_backend_v9 as backend
from svg_source_use_instance_proof_v2 import require_owner

def main():
    identifier='0dc3f8bb2a134a79aba055dc8cc6686f7d097b187bd08267a5bdc4f8d8bd633e'
    with sqlite3.connect((f.W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        db.row_factory=sqlite3.Row;job=dict(db.execute('select*from jobs where id=?',(identifier,)).fetchone())
    source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest'])
    record=dict(id=identifier,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=manifest['source_code'],original_reference=manifest['reference_image'])
    root=f.W/f.VERSION/'source_use_marker_proof_probe_v3'/uuid.uuid4().hex;root.mkdir(parents=True)
    prepared=f.prepare_source(record,job,root/'source');assert prepared['ok'];dom=prepared['capture']['dom']
    semantic,proof=backend.derive(dom,prepared['size']);assert len(proof['markers'])==8
    owners=[next(o for o in dom['objects']if o['id']==m['owner'])for m in proof['markers']]
    controls=[]
    for mutation in ['missing_replacement_proof','changed_shadow_paint','changed_clone_bbox','changed_paint_css']:
        broken=copy.deepcopy(dom);owner=next(o for o in broken['objects']if o['id']==owners[0]['id']);ctx=broken['sceneMetadata']['useContexts'][owner['sceneUseContexts'][0]]
        if mutation=='missing_replacement_proof':ctx.pop('actual_source_use_replacement_proof')
        elif mutation=='changed_shadow_paint':ctx['actual_source_use_replacement_proof']['clone_paint_sha256']='0'*64
        elif mutation=='changed_clone_bbox':ctx['syntheticCloneBBox']['x']+=4
        else:ctx['paintRelevantUnforwardedCss']=[dict(property='stroke',call='red',clone='blue')]
        try:require_owner(broken,owner)
        except ValueError as error:controls.append(dict(mutation=mutation,rejected=True,reason=str(error)))
        else:raise AssertionError('negative_source_use_evidence_accepted:'+mutation)
    (root/'source_marker_proof.json').write_text(json.dumps(proof,indent=2))
    out=dict(id=identifier,root=str(root),markers=len(proof['markers']),verified_source_instances=len({m['source_instance_proof']['use_context']for m in proof['markers']}),original_reference_reproduced=prepared['sourceproof']['source_reference']['ok'],controls=controls,new_normal_conversions=0,full_QA_claimed=False)
    (root/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)

if __name__=='__main__':main()
