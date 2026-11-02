"""Finite actual rehashed control cases and immutable release evidence."""
import argparse,concurrent.futures,copy,json,re,sqlite3,sys,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_plantuml_engine_candidate_v1 as c
import compiler_plantuml_engine_iteration_case_v1 as case
from compiler_types_program_v1 import asset,checked,immutable,raw,sha
DIRECTORY=R/'release/compiler_iterations/controls/plantuml_official_engine_semantic_controls_20261101_v1'
NEGATIVES=('deleted_source_label','changed_bound_terminal','opaque_text_cover','oversized_native_marker','missing_source_arrow','wrong_uniform_spacing','wrong_whole_run_origin','changed_engine_parent','changed_engine_link_port','deleted_source_primitive','synthetic_double_bold','changed_invisible_layout_relation')
def negative(task):
 from svg_convert_v3 import unpack,pack
 from plantuml_engine_scene_quality_v1 import _world_box
 from clip_canvas_render_v4b import render
 from strict_canvas_gate import require_declared_page
 from deterministic_candidate_quality_ro_v1 import verify
 positive,name=task;record=json.loads(Path(positive['record']).read_bytes());tree=E.fromstring((R/record['code_file']).read_bytes());root=tree.find('.//mxGraphModel/root');cells={n.get('id'):n for n in root.iter('mxCell')};edges=[n for n in cells.values() if n.get('edge')=='1'];marked=[e for e in edges if any(unpack(e.get('style','')).get(s+'Arrow','none')!='none' for s in ('start','end'))];edge=marked[0] if marked else edges[0];label=next(n for n in cells.values() if n.get('value','').strip());extra={}
 if name=='deleted_source_label':label.set('value','')
 elif name=='changed_bound_terminal':edge.set('target',edge.get('source'))
 elif name=='changed_engine_link_port':
  style=unpack(edge.get('style',''));style['compilerEnginePort1']='undeclared_actual_port';edge.set('style',pack(style))
 elif name=='changed_invisible_layout_relation':
  hidden=next(n for n in edges if unpack(n.get('style','')).get('opacity')=='0');hidden.set('target',hidden.get('source'))
 elif name=='deleted_source_primitive':
  shape=next(n for n in cells.values() if n.get('vertex')=='1' and unpack(n.get('style','')).get('group')!='1' and unpack(n.get('style','')).get('shape')!='text');root.remove(shape)
 elif name=='synthetic_double_bold':
  style=unpack(label.get('style',''));style['fontStyle']=str(int(style.get('fontStyle','0'))^1);label.set('style',pack(style))
 elif name=='changed_engine_parent':
  groups=[n for n in cells.values() if 'compilerEngineUid' in unpack(n.get('style',''))];first,second=groups[:2];original=_world_box(first,cells);new_parent=_world_box(second,cells);first.set('parent',second.get('id'));g=first.find('mxGeometry');g.set('x',str(original[0]-new_parent[0]));g.set('y',str(original[1]-new_parent[1]));extra['visible_entity_frame_preserved_world_coordinates']=True
 elif name in ('wrong_uniform_spacing','wrong_whole_run_origin'):
  value=label.get('value')
  if name=='wrong_uniform_spacing':value=value.replace('letter-spacing:','letter-spacing:1.5px;unused-source-spacing:',1)
  else:value=re.sub(r'left:([+\-\d.eE]+)px',lambda m:'left:'+str(float(m[1])+1.)+'px',value,count=1)
  label.set('value',value)
 elif name=='opaque_text_cover':
  x,y,w,h=_world_box(label,cells);cell=E.SubElement(root,'mxCell',{'id':'actual_negative_opaque_cover','parent':'1','vertex':'1','style':'fillColor=#ffffff;strokeColor=none;opacity=100;'});E.SubElement(cell,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})
 else:
  style=unpack(edge.get('style',''));side=next(s for s in ('start','end') if style.get(s+'Arrow','none')!='none')
  if name=='oversized_native_marker':style[side+'Size']=str(float(style.get(side+'Size',6))+4)
  elif name=='missing_source_arrow':style[side+'Arrow']='none'
  else:raise ValueError('undeclared_negative')
  edge.set('style',pack(style))
 xml=E.tostring(tree,encoding='unicode');model=tree.find('.//mxGraphModel');width,height=[int(float(model.get(k))) for k in ('pageWidth','pageHeight')];actual=render(xml,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
 if not actual.get('ok'):raise ValueError('actual_negative_render_failed:'+str(actual.get('error')))
 require_declared_page(actual['native_render'],width,height);destination=R/'clean/compiler_plantuml_engine_actual_negative_controls_v1'/record['id']/name/uuid.uuid4().hex;destination.mkdir(parents=True);(destination/'candidate.drawio').write_text(xml);(destination/'candidate.png').write_bytes(actual['png']);record.update(code_file=str((destination/'candidate.drawio').relative_to(R)),image_file=str((destination/'candidate.png').relative_to(R)),code_sha256=c.sha(xml.encode()),image_sha256=c.sha(actual['png']),accepted=False,quality_state='actual_negative_control');rp=destination/'record.json';rp.write_bytes(c.raw(record));q=verify(record['id'],rp,R,Path(c.__file__),W/'prototype/candidate_quality_ro_v1'/('plantuml_engine_negative_'+name+'_'+uuid.uuid4().hex),database=Path(positive['database']));profile=q.get('checks',{}).get('source',{});marker=profile.get('evidence',{}).get('source_native_markers',{}).get('actual_full_closed_marker_paint_and_editing',{});bounds=[x['continuous_full_paint_certificate'] for x in marker.get('markers',[])];return {'name':name,'id':record['id'],'rejected':q['ok'] is False,'fresh_source_rejected':profile.get('ok') is False and bool(profile.get('failures')),'full_closed_paint_lower_bound_exceeds_one_pixel':any(x.get('lower_bound_px',0)>1 for x in bounds),'candidate':asset(rp),'qa':asset(q['evidence_file']),'quality_failures':q['failures'],'rehashed_XML_and_actual_native_PNG':True,**extra}
def main(reverify):
 from PIL import Image
 from plantuml_marker_calibration_proof_v1 import PLAN,REPORT,verified
 from plantuml_marker_grid_rule_v1 import POLICY
 from plantuml_engine_source_model_index_v1 import family
 report=json.loads(Path(reverify).read_bytes());config=c.configuration()
 if report.get('configuration_unchanged') is not True or report['configuration']!=config:raise ValueError('positive_frozen_frontend_changed')
 good=[r for r in report['results'] if r['QA']['ok']]
 if not good or not any(r['case']['name']=='styled_nested_description' for r in good):raise ValueError('full_hierarchy_style_and_hidden_relation_positive_missing')
 owner=W/c.VERSION/'actual_release_controls'/uuid.uuid4().hex;owner.mkdir(parents=True);(owner/'protocol.json').write_bytes(c.raw({'positive_reverify':asset(reverify),'configuration':config,'negatives':NEGATIVES,'negative_workers':2,'actual_native_rehashed_mutations':True,'unseen':0,'model_calls':0}));print(json.dumps({'owner':str(owner),'positives':len(good),'negatives':len(NEGATIVES)}),flush=True)
 positive=[{'name':r['case']['name'],'id':r['case']['id'],'record':r['case']['record'],'database':r['case']['database'],'synthetic':r['case']['synthetic'],'qa':r['QA']['evidence_file']} for r in good];real=next(p for p in positive if p['name']=='regression05d');hidden=next(p for p in positive if p['name']=='styled_nested_description');negatives=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
  for row in pool.map(negative,[(hidden if n=='changed_invisible_layout_relation' else real,n) for n in NEGATIVES]):negatives.append(row);(owner/'negative_progress.json').write_bytes(c.raw(negatives));print(json.dumps({'negative':row['name'],'rejected':row['rejected'],'fresh_source_rejected':row['fresh_source_rejected'],'full_closed_paint_lower_bound_exceeds_one_pixel':row['full_closed_paint_lower_bound_exceeds_one_pixel'],'qa':row['qa']}),flush=True)
 passed=len(negatives)==len(NEGATIVES) and all(x['rejected'] and x['fresh_source_rejected'] for x in negatives) and next(x['full_closed_paint_lower_bound_exceeds_one_pixel'] for x in negatives if x['name']=='oversized_native_marker') and config==c.configuration();development={'configuration':config,'configuration_unchanged':config==c.configuration(),'positives':positive,'negatives':negatives,'passed':passed,'new_unseen':0,'model_calls':0};(owner/'report.json').write_bytes(c.raw(development))
 if not passed:print(json.dumps({'report':str(owner/'report.json'),'passed':False}),flush=True);return
 calibration=verified();proof={'schema':'compiler_plantuml_engine_iteration_controls_v1','producer':asset(__file__),'development':asset(owner/'report.json'),'frozen_frontend':config,'positives':[],'positive_cases':[],'negatives':[],'negative_cases':[],'marker_raster_policy':POLICY,'calibration_summary':{k:v for k,v in calibration.items() if k!='pins'},'calibration':{'preregistered_plan.json':asset(PLAN),'report.json':asset(REPORT)},'model_calls':0,'unseen_consumed':0,'canonical_mutations':0};manifests=[]
 # Every reference is checked before publishing a new immutable control bundle.
 for p in positive:
  record=json.loads(Path(p['record']).read_bytes());qa=json.loads(Path(p['qa']).read_bytes());case.full_quality(qa,record)
  if qa['input_record_sha256']!=asset(p['record'])['sha256'] or qa['profile_policy']!=config['policy']:raise ValueError('positive_metadata_policy_binding_changed')
  source_code=(R/record['original_source_code']).read_bytes();source_family,_=family(source_code);entry={'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':asset(p['record']),'qa':asset(p['qa']),'source_family':source_family,'synthetic_control_only':p['synthetic'],'database':asset(p['database']) if p['synthetic'] else None};proof['positives'].append(entry['qa']);proof['positive_cases'].append(entry)
  if not p['synthetic']:
   with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:source=json.loads(db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0])
   manifests.append(case.publish(record,source,qa,Path(p['qa']).parent))
 for row in negatives:
  record=json.loads(checked(row['candidate'])[1]);qa=json.loads(checked(row['qa'])[1]);profile=qa.get('checks',{}).get('source',{})
  if qa.get('ok') is not False or not qa.get('failures') or profile.get('ok') is not False or not profile.get('failures') or qa['input_record_sha256']!=row['candidate']['sha256'] or qa['profile_policy']!=config['policy']:raise ValueError('negative_full_source_binding_changed')
  stored=Image.open(R/record['image_file']).convert('RGBA');fresh=Image.open(Path(row['qa']['file']).parent/'fresh_native.png').convert('RGBA')
  if stored.size!=fresh.size or stored.tobytes()!=fresh.tobytes():raise ValueError('negative_not_actual_fresh_native_PNG')
  proof['negatives'].append(row['qa']);proof['negative_cases'].append({**{k:row[k] for k in ('name','id','candidate','qa','full_closed_paint_lower_bound_exceeds_one_pixel')},'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'rehashed_XML_and_actual_native_PNG':True,'actual_source_rejection':True})
 DIRECTORY.mkdir(parents=True,exist_ok=False);immutable(DIRECTORY/'qualified.jsonl',b''.join(raw(m) for m in manifests));proof['qualified_manifest']=asset(DIRECTORY/'qualified.jsonl');immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':str(DIRECTORY/'proof.json'),'positives':len(positive),'negatives':len(negatives),'dataset_qualified_pairs':len(manifests),'synthetic_qualified_in_dataset':0,'reserved':False,'launched':False}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reverify',type=Path,required=True);a=p.parse_args();main(a.reverify)
