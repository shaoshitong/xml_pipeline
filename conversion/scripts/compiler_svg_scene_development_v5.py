"""Run exactly the four preregistered seen cases in isolated bounded processes."""
from pathlib import Path
import copy
import hashlib
import html
import json
import os
import sqlite3
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
OWNER=W/'compiler_svg_scene_frontend_v5/development_run_v5'
COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at',
         'output_record','error','input_manifest','worker_pid')
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda d:(json.dumps(d,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()

def job(identifier):
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
        db.execute('pragma query_only=ON')
        return dict(zip(COLUMNS,db.execute('select '+','.join(COLUMNS)+' from jobs where id=?',(identifier,)).fetchone()))

def negative_records(record,casework):
    import compiler_svg_scene_frontend_v5 as compiler
    from auto_quality_source_vector_v2 import _plain,_world_box
    xml=compiler._read(record['code_file'],record['code_sha256']).decode();base=ET.fromstring(xml)
    cells={c.get('id'):c for c in base.iter('mxCell')};texts=[c for c in cells.values() if _plain(c.get('value','')).strip()]
    assert texts
    variants=[]
    tree=copy.deepcopy(base);target=next(c for c in tree.iter('mxCell') if c.get('id')==texts[0].get('id'))
    target.set('value',html.escape(_plain(target.get('value'))[:-1]));variants.append(('deleted_grapheme',tree))
    tree=copy.deepcopy(base);done=False
    for cell in tree.iter('mxCell'):
        if cell.get('edge')!='1':continue
        style=dict(p.split('=',1) for p in cell.get('style','').split(';') if '=' in p)
        for key in ('startArrow','endArrow'):
            if style.get(key,'none') not in ('none',''):
                style[key]='none';cell.set('style',';'.join(k+'='+v for k,v in style.items())+';');done=True;break
        if done:break
    if done:variants.append(('removed_arrow',tree))
    tree=copy.deepcopy(base);container=tree.find('.//mxGraphModel/root');x,y,width,height=_world_box(texts[0],cells)
    cell=ET.SubElement(container,'mxCell',{'id':'negative_opaque_text_cover','vertex':'1','parent':'1','style':'fillColor=#ffffff;strokeColor=none;opacity=100;'})
    ET.SubElement(cell,'mxGeometry',{'x':str(x),'y':str(y),'width':str(max(1,width)),'height':str(max(1,height)),'as':'geometry'})
    variants.append(('opaque_text_cover',tree))
    from compiler_svg_scene_quality_ro_v5 import verify
    reports=[]
    for name,tree in variants:
        mutated=ET.tostring(tree,encoding='unicode');size=compiler._inputs(record)[2]
        from PIL import Image
        import io
        dimensions=Image.open(io.BytesIO(size)).size;render=compiler._native(mutated,dimensions)
        dest=R/'clean/compiler_svg_scene_frontend_v5/controls'/record['id']/name/uuid.uuid4().hex;dest.mkdir(parents=True)
        cp=dest/'candidate.drawio';ip=dest/'image.png';cp.write_text(mutated);ip.write_bytes(render['png'])
        out={**record,'code_file':str(cp.relative_to(R)),'code_sha256':sha(mutated.encode()),'image_file':str(ip.relative_to(R)),'image_sha256':sha(render['png'])}
        rp=dest/'record.json';rp.write_bytes(raw(out))
        qa=verify(record['id'],rp,R,W/'scripts/compiler_svg_scene_frontend_v5.py',W/'prototype/candidate_quality_ro_v1'/('svg_scene_v5_negative_'+name+'_'+uuid.uuid4().hex))
        reports.append({'mutation':name,'rejected':not qa['ok'],'qa':qa})
    return reports

def one(case,index):
    import compiler_svg_scene_frontend_v5 as compiler
    from compiler_svg_scene_quality_ro_v5 import verify
    prior=job(case['id']);record=json.loads(prior['output_record']);casework=OWNER/('case_'+str(index));casework.mkdir()
    result={'id':case['id'],'role':case['role'],'static':compiler.static_support(prior),'B_source':None,'C':None,'negative_results':[]}
    def save(): (casework/'report.json').write_bytes(raw(result))
    save()
    if not result['static']['supported']:return result
    try:
        prepared=compiler.prepare_source(record,prior,casework/'B_source')
        result['B_source']={'ok':prepared['ok'],'sourceproof':prepared['sourceproof']}
    except Exception as error:result['B_source']={'ok':False,'reason':str(error).split(':',1)[0],'detail':str(error)[:3000]}
    save()
    converted=compiler.convert(record,prior,casework/'C');result['C']={k:v for k,v in converted.items() if k!='record'};save()
    if converted.get('source_reproduction') and result['B_source'].get('sourceproof'):
        result['B_C_sourceproof_equal']=result['B_source']['sourceproof']==converted['source_reproduction']
    if converted.get('ok'):
        rp=casework/'baseline_record.json';rp.write_bytes(raw(record))
        for phase,proposal in [('B',rp),('C',Path(converted['record_file']))]:
            result[phase+'_qa']=verify(case['id'],proposal,R,W/'scripts/compiler_svg_scene_frontend_v5.py',
                W/'prototype/candidate_quality_ro_v1'/('svg_scene_v5_dev_'+phase+'_'+str(index)+'_'+uuid.uuid4().hex));save()
        # Controls use every generated C case. There is no search for a passing
        # case or replacement of failures, even if source/target full QA fails.
        result['negative_results']=negative_records(converted['record'],casework);save()
    result['canonical_snapshot_unchanged']=job(case['id'])==prior;save();return result

def main():
    import compiler_svg_scene_frontend_v5 as compiler
    original=W/'compiler_svg_scene_frontend_v5/development_seen_plan_v5.json';plan=json.loads(original.read_text())
    if len(sys.argv)>1:
        index=int(sys.argv[1]);result=one(plan['cases'][index],index)
        print(json.dumps({'id':result['id'],'static_supported':result['static']['supported'],'B_source_ok':(result.get('B_source') or {}).get('ok'),
                          'C_ok':(result.get('C') or {}).get('ok'),'C_reason':(result.get('C') or {}).get('reason')}),flush=True);return
    OWNER.mkdir(parents=True,exist_ok=False)
    config=compiler.configuration();frozen={'version':'svg_general_scene_development_v1','original_fixed_four_plan':str(original),
        'original_fixed_four_plan_sha256':sha(original.read_bytes()),'cases':plan['cases'],'negative_mutations':plan['negative_mutations'],
        'case_timeout_seconds':360,'configuration':config,'driver_sha256':sha(Path(__file__).read_bytes()),
        'source_Cairo_to_reference_all_old_gates':True,'source_browser_to_native_all_old_gates':True,
        'native_to_reference_nonlocal_old_gates':True,'cross_renderer_local_diagnostic_only':True,
        'source_cairo_browser_actual_sfnt_equivalence_required':True,'unseen_consumed':0,'new_original_ids':0}
    (OWNER/'frozen_plan.json').write_bytes(raw(frozen));summary={'cases':[],'unseen_consumed':0,'model_calls':0,'canonical_writes':0}
    for index,case in enumerate(plan['cases']):
        try:
            child=subprocess.run([sys.executable,str(Path(__file__)),str(index)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=360,check=False,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
            (OWNER/('case_'+str(index)+'_stdout.log')).write_bytes(child.stdout);(OWNER/('case_'+str(index)+'_stderr.log')).write_bytes(child.stderr)
            path=OWNER/('case_'+str(index))/'report.json';result=json.loads(path.read_text()) if path.exists() else {}
            item={'id':case['id'],'returncode':child.returncode,'report':str(path),'static_supported':(result.get('static') or {}).get('supported'),
                  'B_source_ok':(result.get('B_source') or {}).get('ok'),'C_ok':(result.get('C') or {}).get('ok'),
                  'C_reason':(result.get('C') or {}).get('reason'),'B_C_sourceproof_equal':result.get('B_C_sourceproof_equal'),
                  'B_qa_ok':(result.get('B_qa') or {}).get('ok'),'C_qa_ok':(result.get('C_qa') or {}).get('ok'),
                  'negative_rejected':{r['mutation']:r['rejected'] for r in result.get('negative_results',[])},
                  'canonical_snapshot_unchanged':result.get('canonical_snapshot_unchanged')}
            if result.get('B_source',{}).get('sourceproof'):
                proof=result['B_source']['sourceproof'];item['source_reference_visual']={k:proof['source_reference'].get(k) for k in ('ok','ssim_1024','foreground_tile_p10_ssim','text_regions_checked','failures')};item['source_physical_font_equivalence']=proof['cairo_browser_physical_font_equivalence']
        except subprocess.TimeoutExpired:item={'id':case['id'],'reason':'finite_development_process_timeout'}
        summary['cases'].append(item);(OWNER/'summary.json').write_bytes(raw(summary));print(json.dumps(item),flush=True)
    summary['development_ready']=all(r.get('C_qa_ok') and len(r.get('negative_rejected',{}))==3 and all(r['negative_rejected'].values()) for r in summary['cases'])
    (OWNER/'summary.json').write_bytes(raw(summary));print(json.dumps({'summary':str(OWNER/'summary.json'),'sha256':sha((OWNER/'summary.json').read_bytes()),'development_ready':summary['development_ready']}),flush=True)

if __name__=='__main__':main()
